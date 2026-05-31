from typing import List, Dict, Any

from eth_abi import decode
from web3 import Web3

from data_engine.services.prices.pricing_service import PricingService
from data_engine.services.web3_service import MulticallClient
from shared.databases.mongo_client import MongoConnection


class WalletService:

    def __init__(self, w3: Web3, multicall_address: str, pricing: PricingService):
        self.w3 = w3
        self.db = MongoConnection.get_database()
        self.pricing = pricing

        self.multicall = MulticallClient(w3, multicall_address)

    @staticmethod
    def _decode_uint256(data: bytes) -> int:
        try:
            return decode(["uint256"], data)[0]
        except:
            return 0

    def _build_balance_calls(self, wallet: str, tokens: List[Dict]):
        calls = []
        valid_tokens = []

        for token in tokens:

            try:
                token_address = Web3.to_checksum_address(token["address"])
                contract = self.w3.eth.contract(address=token_address, abi=self.multicall.ERC20_ABI)
                calldata = contract.functions.balanceOf(wallet)._encode_transaction_data()
                calls.append((token_address, calldata))
                valid_tokens.append(token)

            except:
                continue

        return valid_tokens, calls

    def _build_asset(self,
                     token: dict,
                     balance_raw: int,
                     balance: float,
                     symbol: str,
                     asset_type: str):

        price = self.pricing.get_price_safe(symbol)

        meta = self.pricing.get_metadata(symbol)

        value_usd = balance * price

        return {
            "type": asset_type,
            "symbol": symbol,
            "name": meta.get("name"),
            "address": token.get("address"),
            "balanceRaw": balance_raw,
            "decimals": token.get("decimals", 18),
            "balance": balance,
            "price": price,
            "valueUsd": value_usd,
        }

    def get_wallet_portfolio(self, wallet: str) -> List[Dict[str, Any]]:
        wallet = Web3.to_checksum_address(wallet)

        portfolio = []

        eth_balance_raw = self.w3.eth.get_balance(wallet)
        eth_balance = eth_balance_raw / 1e18
        if eth_balance > 0:
            eth_token = self.pricing.get_token_info("ETH")

            if eth_token:
                portfolio.append(
                    self._build_asset(
                        token=eth_token,
                        balance_raw=eth_balance_raw,
                        balance=eth_balance,
                        symbol="ETH",
                        asset_type="native"
                        )
                    )

        supported_tokens = [
            self.pricing.get_token_info(symbol)
            for symbol in self.pricing.get_supported_tokens()
        ]

        if not supported_tokens:
            return portfolio

        valid_tokens, calls = self._build_balance_calls(wallet, supported_tokens)

        if not calls:
            return portfolio

        return_data = self.multicall.execute(calls)

        for idx, token in enumerate(valid_tokens):
            try:
                balance_raw = self._decode_uint256(return_data[idx])
                if balance_raw <= 0:
                    continue

                decimals = token.get("decimals", 18)
                balance = (balance_raw / (10 ** decimals))
                symbol = token.get("symbol")
                portfolio.append(
                    self._build_asset(
                        token=token,
                        balance_raw=balance_raw,
                        balance=balance,
                        symbol=symbol,
                        asset_type="erc20"
                        )
                    )

            except:
                continue

        portfolio.sort(key=lambda x: x.get("valueUsd", 0), reverse=True)

        return portfolio
