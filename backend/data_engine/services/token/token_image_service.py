import time

from shared.repositories.token_repository import TokenRepository
from shared.databases.mongo_client import MongoConnection


class TokenImageService:
    CACHE_TTL = 300

    def __init__(self):
        db = MongoConnection.get_database()
        self.repository = TokenRepository(db)
        self._symbol_map = {}
        self._last_loaded = 0
        self._load()

    def get_image(self, symbol: str) -> str | None:
        self._maybe_refresh()
        symbol = (symbol.upper().strip())

        token = self._symbol_map.get(symbol)

        if not token:
            return None

        return token

    def get_all_images(self):
        self._maybe_refresh()

        return self._symbol_map

    def _maybe_refresh(self):
        now = time.time()
        if now - self._last_loaded > self.CACHE_TTL:
            self._load()

    def _load(self):
        tokens = self.repository.get_all_tokens()

        self._symbol_map = {t["symbol"].upper(): t["image"] for t in tokens if t.get("image")}

        self._last_loaded = time.time()
