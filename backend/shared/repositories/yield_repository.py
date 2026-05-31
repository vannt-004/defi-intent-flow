from pymongo import UpdateOne

from shared.databases.base_repository import BaseRepository
from shared.utils.case_utils import keys_to_camel, keys_to_snake


class YieldRepository(BaseRepository):

    def __init__(self, db):

        super().__init__(db=db, collection_name="yields")

    def bulk_upsert(self, markets: list[dict]):
        operations = []

        for market in markets:
            normalized = keys_to_camel(market)
            operations.append(UpdateOne({"_id": normalized["_id"]}, {"$set": normalized}, upsert=True))

        if not operations:
            return None

        return self.collection.bulk_write(operations, ordered=False)

    def get_markets(self, limit: int = 100) -> list[dict]:
        query = {}

        cursor = (self.collection.find(query, {"_id": 0}).sort("tvl", -1).limit(limit))

        return [keys_to_snake(row) for row in cursor]

    def get_market_by_id(self, market_id: str) -> dict | None:
        row = self.collection.find_one(
            {"$or": [{"_id": market_id}, {"marketId": market_id}, {"address": market_id}, {"poolId": market_id}]},
            {"_id": 0},
        )
        return keys_to_snake(row) if row else None
