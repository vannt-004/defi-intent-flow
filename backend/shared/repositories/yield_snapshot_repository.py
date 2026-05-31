from datetime import datetime, timezone

from pymongo import UpdateOne

from shared.databases.base_repository import BaseRepository
from shared.utils.case_utils import keys_to_camel, keys_to_snake


class YieldSnapshotRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db=db, collection_name="yield_snapshots")
        self.collection.create_index([("marketId", 1), ("timestamp", -1)])
        self.collection.create_index([("protocol", 1), ("timestamp", -1)])

    def bulk_upsert(self, markets: list[dict], timestamp: int | None = None):
        if not markets:
            return None

        timestamp = timestamp or int(datetime.now(timezone.utc).timestamp())
        operations = []
        for market in markets:
            item = keys_to_camel(self._snapshot_from_market(market, timestamp))
            operations.append(
                UpdateOne(
                    {"marketId": item["marketId"], "timestamp": item["timestamp"]},
                    {"$set": item},
                    upsert=True,
                )
            )

        return self.collection.bulk_write(operations, ordered=False)

    def get_latest_before(self, market_id: str, timestamp: int) -> dict | None:
        row = self.collection.find_one(
            {"marketId": market_id, "timestamp": {"$lte": timestamp}},
            {"_id": 0},
            sort=[("timestamp", -1)],
        )
        return keys_to_snake(row) if row else None

    def _snapshot_from_market(self, market: dict, timestamp: int) -> dict:
        raw = keys_to_snake(market)
        market_id = raw.get("market_id") or raw.get("pool_id") or raw.get("address") or raw.get("_id")
        protocol = raw.get("protocol") or raw.get("dex") or "unknown"
        symbol = raw.get("symbol") or raw.get("asset")
        if not symbol and raw.get("token0") and raw.get("token1"):
            symbol = f"{raw['token0'].get('symbol')}-{raw['token1'].get('symbol')}"

        return {
            "market_id": market_id,
            "timestamp": timestamp,
            "protocol": protocol,
            "category": raw.get("type") or ("dex_liquidity" if raw.get("dex") else "yield"),
            "symbol": str(symbol or "UNKNOWN").upper(),
            "asset": raw.get("asset"),
            "pool_id": raw.get("pool_id"),
            "tvl": raw.get("tvl") or raw.get("tvl_usd") or raw.get("total_deposit_usd") or 0,
            "supply_apr": raw.get("supply_apr") or raw.get("supplyApr") or raw.get("apr") or 0,
            "borrow_apr": raw.get("borrow_apr") or raw.get("borrowApr") or 0,
            "borrow_stable_apr": raw.get("borrow_stable_apr") or raw.get("borrowStableApr") or 0,
            "fee_apr_24h": raw.get("fee_apr_24h") or 0,
            "fee_apr_7d": raw.get("fee_apr_7d") or 0,
            "reward_apr": raw.get("reward_apr") or 0,
            "total_apr": raw.get("total_apr") or raw.get("pool_apr") or raw.get("apr") or raw.get("supply_apr") or 0,
            "max_ltv": raw.get("max_ltv") or raw.get("maxLtv") or 0,
            "liquidation_threshold": raw.get("liquidation_threshold") or raw.get("liquidationThreshold") or 0,
            "raw_data": raw,
            "created_at": datetime.now(timezone.utc),
        }
