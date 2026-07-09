from collections import defaultdict

from pymongo import ASCENDING, DESCENDING

from shared.databases.base_repository import BaseRepository


class PriceSnapshotRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "token_price_snapshots")
        self.collection.create_index([("coingeckoId", 1), ("timestamp", 1)])
        self.collection.create_index([("coingeckoId", 1), ("timestamp", -1)])

    def get_price_histories(self, tokens: list[str], from_ts: int):
        cursor = (
            self.collection.find({"coingeckoId": {"$in": tokens}, "timestamp": {"$gte": from_ts}}, {"_id": 0}).sort(
                [("coingeckoId", 1), ("timestamp", 1)]))

        result = defaultdict(list)

        for item in cursor:
            result[item["coingeckoId"]].append({"timestamp": item["timestamp"], "price": item["price"]})

        return dict(result)

    def get_latest_prices_before(self, tokens: list[str], timestamp: int) -> dict[str, dict]:
        result = {}

        for token in tokens:
            row = self.get_price_at_or_before(token, timestamp)
            if row:
                result[token] = row

        return result

    def get_price_at_or_before(self, coingecko_id: str, timestamp: int) -> dict | None:
        return self.collection.find_one(
            {"coingeckoId": coingecko_id, "timestamp": {"$lte": timestamp}},
            {"_id": 0},
            sort=[("timestamp", DESCENDING)],
        )

    def get_price_at_timestamp(self, coingecko_id: str, timestamp: int) -> dict | None:
        return self.collection.find_one(
            {"coingeckoId": coingecko_id, "timestamp": timestamp},
            {"_id": 0},
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

    def get_price_nearest_any(self, coingecko_id: str, timestamp: int) -> dict | None:
        before = self.collection.find_one(
            {"coingeckoId": coingecko_id, "timestamp": {"$lte": timestamp}},
            {"_id": 0},
            sort=[("timestamp", DESCENDING)],
        )
        if before:
            return before

        return self.collection.find_one(
            {"coingeckoId": coingecko_id, "timestamp": {"$gte": timestamp}},
            {"_id": 0},
            sort=[("timestamp", ASCENDING)],
        )

    def get_average_price_nearby(self, coingecko_id: str, timestamp: int, limit: int = 5) -> dict | None:
        if limit <= 0:
            return None

        before = list(
            self.collection.find(
                {"coingeckoId": coingecko_id, "timestamp": {"$lte": timestamp}, "price": {"$gt": 0}},
                {"_id": 0, "coingeckoId": 1, "timestamp": 1, "price": 1},
            )
            .sort("timestamp", DESCENDING)
            .limit(limit)
        )
        after = list(
            self.collection.find(
                {"coingeckoId": coingecko_id, "timestamp": {"$gte": timestamp}, "price": {"$gt": 0}},
                {"_id": 0, "coingeckoId": 1, "timestamp": 1, "price": 1},
            )
            .sort("timestamp", ASCENDING)
            .limit(limit)
        )

        rows_by_timestamp: dict[int, dict] = {}
        for row in before + after:
            rows_by_timestamp[int(row["timestamp"])] = row

        rows = sorted(
            rows_by_timestamp.values(),
            key=lambda row: (abs(int(row["timestamp"]) - timestamp), int(row["timestamp"])),
        )[:limit]
        prices = [float(row.get("price") or 0) for row in rows if float(row.get("price") or 0) > 0]
        if not prices:
            return None

        return {
            "coingeckoId": coingecko_id,
            "timestamp": timestamp,
            "price": sum(prices) / len(prices),
            "source": "nearby_average",
            "sampleSize": len(prices),
            "sampleTimestamps": [int(row["timestamp"]) for row in rows],
        }

    async def insert_snapshots(self, snapshots: list[dict]):

        if not snapshots:
            return

        return self.collection.insert_many(snapshots, ordered=False)
