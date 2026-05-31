from collections import defaultdict

from pymongo import ASCENDING, DESCENDING

from shared.databases.base_repository import BaseRepository


class PriceSnapshotRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "token_price_snapshots")
        self.collection.create_index([("coingeckoId", 1), ("timestamp", 1)])

    def get_price_histories(self, tokens: list[str], from_ts: int):
        cursor = (
            self.collection.find({"coingeckoId": {"$in": tokens}, "timestamp": {"$gte": from_ts}}, {"_id": 0}).sort(
                [("coingeckoId", 1), ("timestamp", 1)]))

        result = defaultdict(list)

        for item in cursor:
            result[item["coingeckoId"]].append({"timestamp": item["timestamp"], "price": item["price"]})

        return dict(result)

    def get_price_at_or_before(self, coingecko_id: str, timestamp: int) -> dict | None:
        return self.collection.find_one(
            {"coingeckoId": coingecko_id, "timestamp": {"$lte": timestamp}},
            {"_id": 0},
            sort=[("timestamp", DESCENDING)],
        )

    def get_price_nearest(self, coingecko_id: str, timestamp: int, max_window_seconds: int = 86400) -> dict | None:
        before = self.collection.find_one(
            {
                "coingeckoId": coingecko_id,
                "timestamp": {"$lte": timestamp, "$gte": timestamp - max_window_seconds},
            },
            {"_id": 0},
            sort=[("timestamp", DESCENDING)],
        )
        if before:
            return before

        return self.collection.find_one(
            {
                "coingeckoId": coingecko_id,
                "timestamp": {"$gte": timestamp, "$lte": timestamp + max_window_seconds},
            },
            {"_id": 0},
            sort=[("timestamp", ASCENDING)],
        )

    async def insert_snapshots(self, snapshots: list[dict]):

        if not snapshots:
            return

        return self.collection.insert_many(snapshots, ordered=False)
