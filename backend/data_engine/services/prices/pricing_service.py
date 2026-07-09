import time

from config import CoinGeckoConfig
from shared.repositories.price_snapshot_repository import PriceSnapshotRepository
from shared.repositories.token_repository import TokenRepository
from shared.utils.logger_utils import get_logger


class TokenNotFoundException(Exception):
    pass


class PricingService:
    CACHE_TTL = 60  # seconds

    SYMBOL_NORMALIZE_MAP = {
        "WETH": "ETH",
        "WBTC": "BTC",
        "WMATIC": "MATIC",
        "WAVAX": "AVAX",
        "WBNB": "BNB",
        "WFTM": "FTM",
        "AWETH": "ETH",
        "AWBTC": "BTC",
        "AUSDC": "USDC",
        "AUSDT": "USDT",
        "ADAI": "DAI",
        "ALINK": "LINK",
        "AAVE": "AAVE",
        "AETHWETH": "ETH",
        "AETHWBTC": "BTC",
        "AETHUSDC": "USDC",
        "AETHUSDT": "USDT",
        "AETHDAI": "DAI",
        "AETHLINK": "LINK",
        "AETHAAVE": "AAVE",
        "USDC.E": "USDC",
        "USDT.E": "USDT",
        "DAI.E": "DAI",
    }

    def __init__(self, db):
        self.logger = get_logger(self.__class__.__name__)
        self.db = db
        self.token_repository = TokenRepository(db)
        self.snapshot_repository = PriceSnapshotRepository(db)
        self._token_map: dict = {}
        self._supported_symbols: list[str] = []
        self._last_loaded: float = 0.0
        self._load_token_map()

    def get_price(self, symbol: str) -> float:
        self._maybe_refresh()
        lookup_symbol = self.normalize_symbol(symbol)
        token = self._token_map.get(lookup_symbol)

        if not token:
            raise TokenNotFoundException(f"Token not found: {lookup_symbol}")

        price = token.get("price")
        if not price or price <= 0:
            raise TokenNotFoundException(f"Invalid price for token: {lookup_symbol} (price={price})")

        return float(price)

    def get_token_info(self, symbol: str) -> dict:
        self._maybe_refresh()
        lookup_symbol = self.normalize_symbol(symbol)
        token = self._token_map.get(lookup_symbol)

        if not token:
            raise TokenNotFoundException(f"Token not found: {lookup_symbol}")

        return token

    def get_supported_tokens(self):
        self._maybe_refresh()
        return self._supported_symbols

    def get_histories(self, tokens: list[str], from_ts: int):
        return self.snapshot_repository.get_price_histories(tokens, from_ts)

    def get_historical_price(self, symbol: str, timestamp: int, default: float = 0.0) -> float:
        return float(self.get_historical_price_quote(symbol, timestamp, default).get("price") or default)

    def get_historical_price_quote(self, symbol: str, timestamp: int, default: float = 0.0) -> dict:
        requested_timestamp = int(timestamp or 0)
        max_delta_seconds = int(CoinGeckoConfig.PRICE_AT_TX_MAX_DELTA_SECONDS)
        base_quote = {
            "symbol": self.normalize_symbol(symbol) if symbol else symbol,
            "requestedTimestamp": requested_timestamp,
            "price": float(default or 0.0),
            "priceSource": "missing_symbol" if not symbol else "missing_snapshot",
            "priceTimestamp": None,
            "priceDeltaSeconds": None,
            "priceMaxDeltaSeconds": max_delta_seconds,
            "priceReliable": False,
            "priceNote": "Missing token symbol" if not symbol else "No historical price snapshot available",
            "sampleSize": 0,
            "sampleTimestamps": [],
        }
        if not symbol:
            return base_quote

        self._maybe_refresh()
        token = self._token_map.get(self.normalize_symbol(symbol))
        if not token:
            base_quote["priceSource"] = "unsupported_token"
            base_quote["priceNote"] = "Token is not configured for historical pricing"
            return base_quote

        coingecko_id = token.get("coingeckoId")
        if not coingecko_id:
            base_quote["priceSource"] = "missing_coingecko_id"
            base_quote["priceNote"] = "Token has no CoinGecko id configured"
            return base_quote

        snapshot = self.snapshot_repository.get_price_at_timestamp(coingecko_id, timestamp)
        price = self._snapshot_price(snapshot)
        if price > 0:
            return self._quote_from_snapshot(
                symbol=symbol,
                requested_timestamp=requested_timestamp,
                snapshot=snapshot,
                source="historical_snapshot",
                max_delta_seconds=max_delta_seconds,
                sample_size=1,
            )

        snapshot = self.snapshot_repository.get_average_price_nearby(coingecko_id, timestamp, limit=5)
        price = self._snapshot_price(snapshot)
        if price > 0:
            return self._quote_from_snapshot(
                symbol=symbol,
                requested_timestamp=requested_timestamp,
                snapshot=snapshot,
                source=snapshot.get("source") or "nearby_average",
                max_delta_seconds=max_delta_seconds,
                sample_size=int(snapshot.get("sampleSize") or 0),
                sample_timestamps=snapshot.get("sampleTimestamps") or [],
            )

        current_price = token.get("price")
        if current_price:
            base_quote.update({
                "price": float(current_price),
                "priceSource": "current_price_fallback",
                "priceNote": "Historical snapshot missing; current token price used as fallback",
            })
        return base_quote

    def _quote_from_snapshot(
        self,
        symbol: str,
        requested_timestamp: int,
        snapshot: dict,
        source: str,
        max_delta_seconds: int,
        sample_size: int = 1,
        sample_timestamps: list[int] | None = None,
    ) -> dict:
        sample_timestamps = [int(ts) for ts in (sample_timestamps or []) if ts is not None]
        snapshot_timestamp = int(snapshot.get("timestamp") or requested_timestamp)
        if sample_timestamps:
            delta_seconds = max(abs(ts - requested_timestamp) for ts in sample_timestamps)
        else:
            delta_seconds = abs(snapshot_timestamp - requested_timestamp)
        reliable = delta_seconds <= max_delta_seconds
        return {
            "symbol": self.normalize_symbol(symbol),
            "requestedTimestamp": requested_timestamp,
            "price": float(snapshot.get("price") or 0.0),
            "priceSource": source,
            "priceTimestamp": snapshot_timestamp,
            "priceDeltaSeconds": int(delta_seconds),
            "priceMaxDeltaSeconds": max_delta_seconds,
            "priceReliable": reliable,
            "priceNote": (
                "Historical price snapshot is within configured delta"
                if reliable
                else "Historical price snapshot is outside configured delta"
            ),
            "sampleSize": int(sample_size or 1),
            "sampleTimestamps": sample_timestamps or [snapshot_timestamp],
        }

    def _snapshot_price(self, snapshot: dict | None) -> float:
        if not snapshot:
            return 0.0
        return float(snapshot.get("price") or 0)

    def get_price_safe(self, symbol: str, default: float = 0.0) -> float:
        try:
            return self.get_price(symbol)
        except TokenNotFoundException:
            self.logger.warning(f"Price not found for {symbol}, using default={default}")
            return default

    def get_metadata(self, symbol: str) -> dict:
        self._maybe_refresh()
        symbol = self.normalize_symbol(symbol)
        token = self._token_map.get(symbol, {})

        return {
            "image": token.get("image"),
            "name": token.get("name"),
            "symbol": symbol,
        }

    def normalize_symbol(self, symbol: str) -> str:
        upper = symbol.upper().strip()
        return self.SYMBOL_NORMALIZE_MAP.get(upper, upper)

    def reload(self):
        self._load_token_map()

    def _maybe_refresh(self):
        if time.time() - self._last_loaded > self.CACHE_TTL:
            self._load_token_map()

    def _load_token_map(self):
        try:
            tokens = self.token_repository.get_all_tokens()
            token_map = {}
            supported_symbols = []
            seen_supported_symbols = set()

            for token in tokens:
                symbol = token.get("symbol")
                if not symbol:
                    continue

                raw_symbol = symbol.upper()
                token_map[raw_symbol] = token
                if raw_symbol not in seen_supported_symbols:
                    supported_symbols.append(raw_symbol)
                    seen_supported_symbols.add(raw_symbol)

            for raw_symbol, token in list(token_map.items()):
                normalized_symbol = self.normalize_symbol(raw_symbol)
                token_map.setdefault(normalized_symbol, token)

            self._token_map = token_map
            self._supported_symbols = supported_symbols
            self._last_loaded = time.time()
            self.logger.info(f"Loaded {len(self._supported_symbols)} tokens from DB")
        except Exception as exc:
            self.logger.error(f"Failed to load token map: {exc}")
