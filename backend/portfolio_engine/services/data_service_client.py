import httpx

from config import settings


class DataServiceClient:
    def __init__(self):
        self.base_url = settings.DATA_SERVICE_URL

    async def get_all_positions(self, wallet: str):
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(f"{self.base_url}/portfolio/positions/{wallet}")
            res.raise_for_status()
            return res.json()

    async def get_wallet(self, wallet: str):
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                f"{self.base_url}/portfolio/wallet/{wallet}",
            )
            res.raise_for_status()
            return res.json()