import asyncio

import httpx

from config import EtherscanConfig
from shared.utils.logger_utils import get_logger


class EtherscanClient:
    MAX_RETRIES = 4
    RETRY_STATUSES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        api_key: str = EtherscanConfig.API_KEY,
        base_url: str = EtherscanConfig.BASE_URL,
        chain_id: str = EtherscanConfig.CHAIN_ID,
    ):
        if not api_key:
            raise ValueError("Missing ETHERSCAN_API_KEY")

        self.api_key = api_key
        self.base_url = base_url
        self.chain_id = chain_id
        self.logger = get_logger(self.__class__.__name__)
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0))

    async def close(self):
        await self.client.aclose()

    async def get_normal_transactions(
        self,
        address: str,
        start_block: int = 0,
        end_block: int = 99999999,
        page: int = 1,
        offset: int = 1000,
        sort: str = "asc",
    ) -> list[dict]:
        return await self._account_request(
            action="txlist",
            address=address,
            start_block=start_block,
            end_block=end_block,
            page=page,
            offset=offset,
            sort=sort,
        )

    async def get_erc20_transfers(
        self,
        address: str,
        start_block: int = 0,
        end_block: int = 99999999,
        page: int = 1,
        offset: int = 1000,
        sort: str = "asc",
    ) -> list[dict]:
        return await self._account_request(
            action="tokentx",
            address=address,
            start_block=start_block,
            end_block=end_block,
            page=page,
            offset=offset,
            sort=sort,
        )

    async def get_block_number_by_timestamp(self, timestamp: int, closest: str = "before") -> int:
        params = {
            "chainid": self.chain_id,
            "module": "block",
            "action": "getblocknobytime",
            "timestamp": int(timestamp),
            "closest": closest,
            "apikey": self.api_key,
        }

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = await self.client.get(self.base_url, params=params)
                if response.status_code in self.RETRY_STATUSES:
                    wait = self._backoff(attempt, response)
                    last_error = ValueError(f"Etherscan getblocknobytime HTTP {response.status_code}")
                    self.logger.warning(
                        "Etherscan getblocknobytime HTTP %s timestamp=%s retry_in=%.1fs",
                        response.status_code,
                        timestamp,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                payload = response.json()
                result = payload.get("result")
                if payload.get("status") == "1" and result is not None:
                    return int(result)

                result_text = result.lower() if isinstance(result, str) else ""
                if "rate limit" in result_text or "max rate" in result_text:
                    wait = self._backoff(attempt, response)
                    last_error = ValueError("Etherscan getblocknobytime rate limited")
                    self.logger.warning(
                        "Etherscan getblocknobytime rate limited timestamp=%s retry_in=%.1fs",
                        timestamp,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                raise ValueError(
                    "Etherscan getblocknobytime failed: "
                    f"status={payload.get('status')} message={payload.get('message')} result={result}"
                )
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                wait = self._backoff(attempt)
                self.logger.warning(
                    "Etherscan getblocknobytime request failed timestamp=%s attempt=%s/%s retry_in=%.1fs error=%s",
                    timestamp,
                    attempt + 1,
                    self.MAX_RETRIES,
                    wait,
                    exc,
                )
                await asyncio.sleep(wait)

        if last_error:
            raise last_error
        raise ValueError("Etherscan getblocknobytime failed after retries")

    async def _account_request(
        self,
        action: str,
        address: str,
        start_block: int,
        end_block: int,
        page: int,
        offset: int,
        sort: str,
    ) -> list[dict]:
        params = {
            "chainid": self.chain_id,
            "module": "account",
            "action": action,
            "address": address,
            "startblock": start_block,
            "endblock": end_block,
            "page": page,
            "offset": offset,
            "sort": sort,
            "apikey": self.api_key,
        }

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = await self.client.get(self.base_url, params=params)
                if response.status_code in self.RETRY_STATUSES:
                    wait = self._backoff(attempt, response)
                    last_error = ValueError(f"Etherscan {action} HTTP {response.status_code}")
                    self.logger.warning(
                        "Etherscan %s HTTP %s wallet=%s retry_in=%.1fs",
                        action,
                        response.status_code,
                        address,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                payload = response.json()
                message = payload.get("message")
                result = payload.get("result")

                if payload.get("status") == "1" and isinstance(result, list):
                    return result

                if message == "No transactions found":
                    return []

                result_text = result.lower() if isinstance(result, str) else ""
                if "rate limit" in result_text or "max rate" in result_text:
                    wait = self._backoff(attempt, response)
                    last_error = ValueError(f"Etherscan {action} rate limited")
                    self.logger.warning(
                        "Etherscan %s rate limited wallet=%s retry_in=%.1fs",
                        action,
                        address,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                raise ValueError(f"Etherscan {action} failed: status={payload.get('status')} message={message} result={result}")
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                wait = self._backoff(attempt)
                self.logger.warning(
                    "Etherscan %s request failed wallet=%s attempt=%s/%s retry_in=%.1fs error=%s",
                    action,
                    address,
                    attempt + 1,
                    self.MAX_RETRIES,
                    wait,
                    exc,
                )
                await asyncio.sleep(wait)

        if last_error:
            raise last_error
        raise ValueError(f"Etherscan {action} failed after {self.MAX_RETRIES} attempts")

    @staticmethod
    def _backoff(attempt: int, response: httpx.Response = None) -> float:
        if response is not None:
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    return float(retry_after)
                except ValueError:
                    pass
        return min(2 ** attempt, 8)
