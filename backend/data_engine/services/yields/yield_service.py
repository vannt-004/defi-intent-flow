from typing import Any, Dict, List
from shared.databases.mongo_client import MongoConnection
from shared.repositories.yield_repository import YieldRepository
from shared.utils.logger_utils import get_logger

from decision_engine.defi_ahp_engine import DeFiAHPEngine

logger = get_logger("YieldService")


class YieldService:
    def __init__(self):
        db = MongoConnection.get_database()
        self.repository = YieldRepository(db)
        self.ahp_engine = DeFiAHPEngine()

    def _normalize_to_unified_model(self, raw_pool: Dict[str, Any]) -> Dict[str, Any]:

        is_amm = raw_pool.get("dex") == "uniswap" or raw_pool.get(
            "type"
        ) == "dex_liquidity"
        is_staking = raw_pool.get("type") == "staking"

        unified_market = {
            "market_id": raw_pool.get("market_id") or raw_pool.get(
                "address"
            ) or raw_pool.get("pool_id") or raw_pool.get("_id"),
            "protocol": raw_pool.get("protocol") or raw_pool.get("dex", "unknown"),
            "category": "dex_liquidity" if is_amm else (
                "staking" if is_staking else "yield"),
            "symbol": "",
            "tvl_usd": float(raw_pool.get("tvl") or raw_pool.get("tvl_usd") or 0.0),
            "apr": 0.0,
            "raw_data": raw_pool
        }

        if is_amm:
            unified_market["apr"] = float(
                raw_pool.get("total_apr") or raw_pool.get("pool_apr") or raw_pool.get("apr") or 0.0
            )
            unified_market["fee_apr_24h"] = float(raw_pool.get("fee_apr_24h") or unified_market["apr"])
            unified_market["fee_apr_7d"] = float(raw_pool.get("fee_apr_7d") or 0.0)
            unified_market["reward_apr"] = float(raw_pool.get("reward_apr") or 0.0)
            unified_market["apr_source"] = raw_pool.get("apr_source")
            if "token0" in raw_pool and "token1" in raw_pool:
                t0 = raw_pool["token0"].get("symbol", "")
                t1 = raw_pool["token1"].get("symbol", "")
                unified_market["symbol"] = f"{t0}-{t1}".upper()
            else:
                unified_market["symbol"] = str(
                    raw_pool.get("symbol", "LP-POOL")
                ).upper()

        else:
            unified_market["apr"] = float(
                raw_pool.get("supplyApr") or raw_pool.get("apr") or 0.0
            )
            unified_market["symbol"] = str(
                raw_pool.get("asset") or raw_pool.get("symbol", "UNKNOWN")
            ).upper()

        return unified_market

    def get_ranked_markets(self, profile_or_matrix: Any, limit: int = 100) -> List[
        Dict[str, Any]]:

        logger.info(
            f"Starting Yield Aggregation Pipeline for profile: {profile_or_matrix}"
        )

        raw_markets = self.repository.get_markets(limit=limit)
        if not raw_markets:
            logger.warning("No raw yield data found in database.")
            return []

        unified_markets = [self._normalize_to_unified_model(pool) for pool in
                           raw_markets]

        ranked_markets = self.ahp_engine.rank_markets(
            unified_markets, profile_or_matrix
        )

        return ranked_markets
