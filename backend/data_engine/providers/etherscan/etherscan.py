import asyncio

import httpx

from config import EtherscanConfig
from shared.utils.logger_utils import get_logger


class EtherscanClient:
    MAX_RETRIES = 3

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

        for attempt in range(1, self.MAX_RETRIES + 1):
            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()
            payload = response.json()
            message = payload.get("message")
            result = payload.get("result")

            if payload.get("status") == "1" and isinstance(result, list):
                return result

            if message == "No transactions found":
                return []

            if isinstance(result, str) and "rate limit" in result.lower():
                await asyncio.sleep(attempt * 2)
                continue

            raise ValueError(f"Etherscan {action} failed: status={payload.get('status')} message={message} result={result}")

        return []
