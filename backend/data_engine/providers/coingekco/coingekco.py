import asyncio

import httpx

from shared.utils.logger_utils import get_logger
from config import CoinGeckoConfig

logger = get_logger("CoinGecko")


class CoinGecko:
    _PRICE_BATCH_SIZE = 150
    _MAX_CONCURRENT = 3
    _RETRY_STATUSES = {429, 500, 502, 503, 504}

    def __init__(self, api_key: str = None):
        headers = {}
        if api_key:
            headers["x-cg-pro-routers-key"] = api_key

        self.client = httpx.AsyncClient(base_url=CoinGeckoConfig.BASE_URL, headers=headers,
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0), )
        self._semaphore = asyncio.Semaphore(self._MAX_CONCURRENT)

    async def get_prices(self, token_ids: set[str]) -> dict:
        ids = list(token_ids)
        batches = [ids[i: i + self._PRICE_BATCH_SIZE] for i in range(0, len(ids), self._PRICE_BATCH_SIZE)]

        results = await asyncio.gather(*[self._fetch_prices_batch(batch) for batch in batches])

        merged = {}
        for r in results:
            merged.update(r)
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

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def _fetch_prices_batch(self, ids: list[str]) -> dict:
        return await self._request("/simple/price", params={"ids": ",".join(ids), "vs_currencies": "usd", })

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
