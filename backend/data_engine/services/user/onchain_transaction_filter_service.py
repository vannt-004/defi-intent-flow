from collections import defaultdict

from data_engine.services.prices.pricing_service import PricingService, TokenNotFoundException
from shared.repositories.token_repository import TokenRepository


class OnchainTransactionFilterService:

    def __init__(self, db):
        self.pricing = PricingService(db)
        self.token_repository = TokenRepository(db)
        self.supported_symbols, self.supported_addresses = self._load_supported_tokens()

    def filter_and_label(self, rows: list[dict]) -> list[dict]:
        self._classify_swaps(rows)

        result = []
        for row in rows:
            if not self.is_supported(row):
                continue

            row["action_label"] = self._action_label(row["action"])
            row["transaction_category"] = self._category(row["action"])
            result.append(row)

        return result

    def is_supported(self, row: dict) -> bool:
        symbol = self.pricing.normalize_symbol(row.get("symbol") or "")
        address = (row.get("contract_address") or "").lower()

        return symbol in self.supported_symbols or bool(address and address in self.supported_addresses)

    def _load_supported_tokens(self) -> tuple[set[str], set[str]]:
        symbols = set()
        addresses = set()

        for token in self.token_repository.get_all_tokens():
            symbol = token.get("symbol")
            address = token.get("address")

            if symbol:
                raw_symbol = symbol.upper()
                symbols.add(raw_symbol)
                symbols.add(self.pricing.normalize_symbol(raw_symbol))

            if address:
                addresses.add(address.lower())

        try:
            self.pricing.get_token_info("ETH")
            symbols.add("ETH")
        except TokenNotFoundException:
            pass

        return symbols, addresses

    def _classify_swaps(self, rows: list[dict]):
        by_hash = defaultdict(list)
        for row in rows:
            by_hash[row["tx_hash"]].append(row)

        for tx_rows in by_hash.values():
            incoming = [row for row in tx_rows if row["direction"] == "in"]
            outgoing = [row for row in tx_rows if row["direction"] == "out"]

            if incoming and outgoing:
                for row in incoming:
                    row["action"] = "buy"
                for row in outgoing:
                    row["action"] = "sell"

    def _action_label(self, action: str) -> str:
        return {
            "buy": "Buy",
            "sell": "Sell",
            "transfer_in": "Receive",
            "transfer_out": "Send",
        }.get(action, action)

    def _category(self, action: str) -> str:
        if action in ("buy", "sell"):
            return "swap"
        if action in ("transfer_in", "transfer_out"):
            return "transfer"

        return "unknown"
