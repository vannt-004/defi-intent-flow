import time

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
        if not symbol:
            return default

        self._maybe_refresh()
        token = self._token_map.get(self.normalize_symbol(symbol))
        if not token:
            return default

        coingecko_id = token.get("coingeckoId")
        if not coingecko_id:
            return default

        snapshot = self.snapshot_repository.get_price_nearest(coingecko_id, timestamp)
        if not snapshot:
            snapshot = self.snapshot_repository.get_price_nearest_any(coingecko_id, timestamp)
        if not snapshot:
            current_price = token.get("price")
            return float(current_price or default)

        return float(snapshot.get("price") or default)

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

            for token in tokens:
                symbol = token.get("symbol")
                if not symbol:
                    continue

                raw_symbol = symbol.upper()
                token_map[raw_symbol] = token
                supported_symbols.append(raw_symbol)

            for raw_symbol, token in list(token_map.items()):
                normalized_symbol = self.normalize_symbol(raw_symbol)
                token_map.setdefault(normalized_symbol, token)

            self._token_map = token_map
            self._supported_symbols = supported_symbols
            self._last_loaded = time.time()
            self.logger.info(f"PricingService loaded {len(self._supported_symbols)} tokens from DB")
        except Exception as exc:
            self.logger.error(f"Failed to load token map: {exc}")
