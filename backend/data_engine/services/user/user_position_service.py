from config import Web3Config
import time

from data_engine.providers.the_graph.sub.aave_service import AaveGraph
from data_engine.providers.the_graph.sub.curve_service import CurveService
from data_engine.providers.the_graph.sub.uniswap_service import UniswapGraph
from data_engine.services.prices.pricing_service import PricingService
from data_engine.services.user.wallet_service import WalletService
from shared.databases.mongo_client import MongoConnection


class UserPositionService:
    def __init__(self):
        self.db = MongoConnection.get_database()
        self.pricing = PricingService(self.db)

        self.uniswap = UniswapGraph(self.pricing)
        self.aave = AaveGraph(self.pricing)
        self.curve = CurveService(self.pricing)
        self.wallet = WalletService(w3=Web3Config.W3, multicall_address=Web3Config.MULTICALL_ADDRESS, mongodb=self.db, pricing=self.pricing)

    async def get_positions(self, wallet: str):
        uniswap_positions = await self.uniswap.get_positions(wallet)
        aave_positions = await self.aave.get_positions(wallet)
        curve_positions = await self.curve.get_positions(wallet)

        return {
            "wallet": wallet,
            "uniswap": uniswap_positions,
            "aave": aave_positions,
            "curve": curve_positions,
        }

    async def get_wallet(self, wallet: str):
        assets = self.wallet.get_wallet_portfolio(wallet)

        token_ids = list({asset.get("coingeckoId") for asset in assets if
                          asset.get("coingeckoId")})

        from_ts = int(time.time()) - (7 * 24 * 60 * 60)

        histories = self.pricing.get_histories(token_ids, from_ts)

        for asset in assets:
            token_id = asset.get("coingeckoId")

            asset["price_history"] = histories.get(token_id, [])

        return {"wallet": wallet, "assets": assets}

    async def close(self):
        await self.uniswap.close()
        await self.aave.close()
