from pymongo import UpdateOne

from shared.databases.base_repository import BaseRepository


class YieldRepository(BaseRepository):

    def __init__(self, db):

        super().__init__(db=db, collection_name="yields")

    def bulk_upsert(self, markets: list[dict]):
        operations = []

        for market in markets:
            operations.append(UpdateOne({"_id": market["_id"]}, {"$set": market}, upsert=True))

        if not operations:
            return None

        return self.collection.bulk_write(operations, ordered=False)

    def get_markets(self, limit: int = 100) -> list[dict]:
        query = {}

        cursor = (self.collection.find(query, {"_id": 0}).sort("tvl", -1).limit(limit))

        return list(cursor)

    def get_market_by_id(self, market_id: str) -> dict | None:
        return self.collection.find_one({"_id": market_id}, {"_id": 0})
