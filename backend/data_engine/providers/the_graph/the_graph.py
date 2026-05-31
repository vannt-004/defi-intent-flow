import asyncio
import hashlib
import json

import httpx

from shared.utils.logger_utils import get_logger


class TheGraph:
    MAX_CONCURRENT = 5
    MAX_RETRIES = 5

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10), )
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)
        self._inflight: dict[str, asyncio.Future] = {}

    async def query(self, url: str, query: str, variables: dict = None) -> dict:
        cache_key = self._make_key(url, query, variables)

        if cache_key in self._inflight:
            self.logger.debug("Dedup request, waiting for inflight...")
            return await asyncio.shield(self._inflight[cache_key])

        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._inflight[cache_key] = future

        try:
            result = await self._execute(url, query, variables)
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            await self._inflight.pop(cache_key, None)

    async def close(self):
        await self.client.aclose()

    async def _execute(self, url: str, query: str, variables: dict = None) -> dict:
        payload = {"query": query, "variables": variables or {}}

        async with self._semaphore:
            for attempt in range(self.MAX_RETRIES):
                try:
                    response = await self.client.post(url, json=payload)

                    if response.status_code == 429:
                        wait = 2 ** (attempt + 1)
                        self.logger.warning(f"Rate limited, retry in {wait}s")
                        await asyncio.sleep(wait)
                        continue

                    if response.status_code != 200:
                        raise ValueError(f"HTTP {response.status_code}: {response.text[:200]}")

                    if not response.text:
                        raise ValueError("Empty response body")

                    data = response.json()

                    if "errors" in data:
                        err_msg = str(data["errors"])
                        if "timeout" in err_msg.lower() or "rate" in err_msg.lower():
                            raise ValueError(f"Retryable GraphQL error: {err_msg}")
                        self.logger.error(f"GraphQL error (non-retryable): {err_msg}")
                        return {}

                    return data.get("data", {})

                except (httpx.TimeoutException, httpx.ConnectError) as exc:
                    self.logger.warning(f"Network error attempt {attempt + 1}/{self.MAX_RETRIES}: {exc}")
                except ValueError as exc:
                    self.logger.warning(f"Query failed attempt {attempt + 1}/{self.MAX_RETRIES}: {exc}")
                except Exception as exc:
                    self.logger.error(f"Unexpected error: {exc}")
                    raise

                wait = (2 ** attempt) + (0.1 * attempt)
                await asyncio.sleep(min(wait, 30))

        self.logger.error(f"All {self.MAX_RETRIES} attempts failed for {url}")
        return {}

    @staticmethod
    def _make_key(url: str, query: str, variables: dict) -> str:
        raw = json.dumps({"url": url, "query": query, "variables": variables or {}}, sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()
