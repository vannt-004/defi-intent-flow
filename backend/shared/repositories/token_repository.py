from pymongo import UpdateOne

from shared.databases.base_repository import BaseRepository


class TokenRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "tokens")

    def get_all_tokens(self):
        return self.find_all()

    def get_coingecko_ids(self):
        tokens = self.find_all(projection={"_id": 0, "coingeckoId": 1})

        return [token["coingeckoId"] for token in tokens]

    def get_missing_metadata(self):
        return self.find_all(query={"$or": [{"address": {"$exists": False}}, {"decimals": {"$exists": False}},
            {"image": {"$exists": False}}, ]})

    def get_by_symbol(self, symbol: str):
        return self.find_one({"symbol": symbol.upper()},
            {"_id": 0, "symbol": 1, "name": 1, "image": 1, "price": 1, "coingeckoId": 1, "category": 1, "sector": 1,
                "is_stablecoin": 1, "risk_profile": 1, })

    async def get_tokens_missing_metadata(self):

        cursor = self.collection.find({"$or": [{"address": {"$exists": False}}, {"decimals": {"$exists": False}},
            {"image": {"$exists": False}}, ]})

        return list(cursor)

    async def bulk_update_prices(self, tokens: list[dict]):
        operations = []

        for token in tokens:
            operations.append(UpdateOne({"coingeckoId": token["coingeckoId"]}, {"$set": token}, upsert=True))

        if not operations:
            return

        return self.collection.bulk_write(operations, ordered=False)

    async def bulk_update_metadata(self, tokens: list[dict]):
        operations = []

        for token in tokens:
            operations.append(UpdateOne({"coingeckoId": token["coingeckoId"]}, {"$set": token}, upsert=True))

        if not operations:
            return

        return self.collection.bulk_write(operations, ordered=False)
