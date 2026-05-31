from shared.databases.base_repository import BaseRepository


class ConfigRepository(BaseRepository):

    def __init__(self, db):
        super().__init__(db, "configs")

    def get_cursor(self, worker_name: str):
        config = self.collection.find_one({"_id": worker_name})

        return config.get("last_id", "") if config else ""

    def save_cursor(self, worker_name: str, last_id: str):
        self.collection.update_one({"_id": worker_name}, {"$set": {"last_id": last_id}}, upsert=True)
