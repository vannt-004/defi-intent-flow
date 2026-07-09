import asyncio
import json

import httpx
import redis.asyncio as redis
from redis.exceptions import RedisError

from shared.utils.logger_utils import get_logger
from config import CoinGeckoConfig, RedisConfig

logger = get_logger("CoinGecko")


class CoinGecko:
    _PRICE_BATCH_SIZE = 150
    _MAX_CONCURRENT = 3
    _RETRY_STATUSES = {429, 500, 502, 503, 504}

    def __init__(self, api_key: str = None, redis_url: str = RedisConfig.CONNECTION_URL):
        headers = {}
        if api_key:
            headers["x-cg-pro-routers-key"] = api_key

        self.client = httpx.AsyncClient(base_url=CoinGeckoConfig.BASE_URL, headers=headers,
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0), )
        self._semaphore = asyncio.Semaphore(self._MAX_CONCURRENT)
        self.price_cache_ttl = max(int(CoinGeckoConfig.PRICE_CACHE_TTL_SECONDS or 0), 0)
        self.redis = redis.from_url(redis_url, decode_responses=True) if self.price_cache_ttl > 0 else None

    async def get_prices(self, token_ids: set[str]) -> dict:
        ids = list(token_ids)
        if not ids:
            return {}

        cached = await self._get_cached_prices(ids)
        missing_ids = [token_id for token_id in ids if token_id not in cached]
        batches = [
            missing_ids[i: i + self._PRICE_BATCH_SIZE]
            for i in range(0, len(missing_ids), self._PRICE_BATCH_SIZE)
        ]

        results = await asyncio.gather(*[self._fetch_prices_batch(batch) for batch in batches]) if batches else []

        merged = dict(cached)
        for r in results:
            merged.update(r)
        fetched = {token_id: merged[token_id] for token_id in missing_ids if token_id in merged}
        await self._set_cached_prices(fetched)
        return merged

    async def get_markets(self, page: int = 1, per_page: int = 250) -> list[dict]:
        data = await self._request("/coins/markets",
                                   params={"vs_currency": "usd", "order": "market_cap_desc", "per_page": per_page,
                                       "page": page, "sparkline": False, "price_change_percentage": "24h", })
        return data if isinstance(data, list) else []

    async def get_token_metadata(self, token_id: str) -> dict:
        return await self._request(f"/coins/{token_id}",
                                   params={"localization": "false", "tickers": "false", "market_data": "false",
                                       "community_data": "false", "developer_data": "false", "sparkline": "false", })

    async def close(self):
        await self.client.aclose()
        if self.redis:
            await self.redis.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def _fetch_prices_batch(self, ids: list[str]) -> dict:
        return await self._request("/simple/price", params={"ids": ",".join(ids), "vs_currencies": "usd", })

    async def _get_cached_prices(self, ids: list[str]) -> dict:
        if not self.redis or not ids:
            return {}

        keys = [self._price_cache_key(token_id) for token_id in ids]
        try:
            values = await self.redis.mget(keys)
        except RedisError as exc:
            logger.warning(f"CoinGecko price cache read skipped: {exc}")
            return {}

        cached = {}
        for token_id, raw in zip(ids, values):
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if isinstance(payload, dict) and "usd" in payload:
                cached[token_id] = payload
        return cached

    async def _set_cached_prices(self, prices: dict):
        if not self.redis or not prices:
            return

        try:
            pipe = self.redis.pipeline(transaction=False)
            for token_id, payload in prices.items():
                if isinstance(payload, dict) and "usd" in payload:
                    pipe.setex(
                        self._price_cache_key(token_id),
                        self.price_cache_ttl,
                        json.dumps(payload),
                    )
            await pipe.execute()
        except RedisError as exc:
            logger.warning(f"CoinGecko price cache write skipped: {exc}")

    @staticmethod
    def _price_cache_key(token_id: str) -> str:
        return f"price:coingecko:{token_id}:usd"

    async def _request(self, path: str, params: dict = None, retries: int = 5) -> dict | list:
        async with self._semaphore:
            for attempt in range(retries):
                try:
                    response = await self.client.get(path, params=params)

                    if response.status_code in self._RETRY_STATUSES:
                        wait = self._backoff(attempt, response)
                        logger.warning(f"HTTP {response.status_code} on {path}, retry in {wait:.1f}s")
                        await asyncio.sleep(wait)
                        continue

                    response.raise_for_status()
                    return response.json()

                except httpx.TimeoutException:
                    logger.warning(f"Timeout on {path} (attempt {attempt + 1}/{retries})")
                except httpx.HTTPStatusError as exc:
                    logger.error(f"HTTP error {exc.response.status_code} on {path}: non-retryable")
                    return {}
                except Exception as exc:
                    logger.warning(f"Request failed on {path} (attempt {attempt + 1}): {exc}")

                await asyncio.sleep(self._backoff(attempt))

        logger.error(f"All {retries} attempts failed for {path}")
        return {}

    @staticmethod
    def _backoff(attempt: int, response: httpx.Response = None) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
        return min(2 ** attempt, 60)
