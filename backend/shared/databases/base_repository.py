class BaseRepository:

    def __init__(self, db, collection_name: str):
        self.collection = db[collection_name]

    def find_all(self, query=None, projection=None):
        return list(self.collection.find(query or {}, projection))

    def find_one(self, query, projection=None):
        return self.collection.find_one(query, projection)

    def insert_one(self, data):
        return self.collection.insert_one(data)

    def update_one(self, query, update):
        return self.collection.update_one(query, update)

    def delete_one(self, query):
        return self.collection.delete_one(query)