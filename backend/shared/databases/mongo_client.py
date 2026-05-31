from pymongo import MongoClient
from config import MongoDBConfig
from shared.utils.logger_utils import get_logger

logger = get_logger("MongoDB")


class MongoConnection:
    _client = None
    _db = None

    @classmethod
    def connect(cls):
        if cls._db is None:
            try:
                cls._client = MongoClient(MongoDBConfig.CONNECTION_URL)
                cls._db = cls._client[MongoDBConfig.DATABASE]

                logger.info("Connected MongoDB")

            except Exception as ex:
                logger.exception("Failed to connect MongoDB")
                raise ex

        return cls._db

    @classmethod
    def get_database(cls):
        if cls._db is None:
            return cls.connect()

        return cls._db