import asyncio
import time

from data_engine.constants.token_contrants import STABLECOINS
from data_engine.providers.coingekco.coingekco import CoinGecko
from shared.repositories.price_snapshot_repository import PriceSnapshotRepository
from shared.repositories.token_repository import TokenRepository
from shared.utils.logger_utils import get_logger

logger = get_logger("PriceSyncService")


class PriceSyncService:

    def __init__(self, token_repository: TokenRepository, snapshot_repository: PriceSnapshotRepository,
                 coingecko_service: CoinGecko):
        self.token_repository = token_repository
        self.snapshot_repository = snapshot_repository
        self.coingecko_service = coingecko_service

        self.batch_size = 500
        self.meta_concurrency = 10000

    async def sync_prices(self):
        tokens = self.token_repository.get_all_tokens()

        if not tokens:
            logger.warning("No token found")
            return

        token_ids = set({token["coingeckoId"] for token in tokens if token.get("coingeckoId")})

        logger.info(f"Syncing prices for {len(token_ids)} token")

        prices = await self.coingecko_service.get_prices(token_ids)

        if not prices:
            logger.warning("No prices returned")
            return

        now = int(time.time())

        token_updates = []
        snapshot_docs = []

        for token in tokens:
            coingecko_id = token.get("coingeckoId")

            if not coingecko_id:
                continue

            price_data = prices.get(coingecko_id)

            if not price_data:
                continue

            price = price_data.get("usd")

            if price is None:
                continue

            token_updates.append({"coingeckoId": coingecko_id, "price": float(price), "updatedAt": now})

            symbol = (token.get("symbol") or "").upper()

            if symbol not in STABLECOINS:
                snapshot_docs.append({"coingeckoId": coingecko_id, "price": float(price), "timestamp": now})

            if len(token_updates) >= self.batch_size:
                await self.token_repository.bulk_update_prices(token_updates)
                token_updates.clear()

        if token_updates:
            await self.token_repository.bulk_update_prices(token_updates)

        if snapshot_docs:
            await self.snapshot_repository.insert_snapshots(snapshot_docs)

        logger.info(
            f"Price sync completed "
            f"(token={len(token_updates)}, "
            f"snapshots={len(snapshot_docs)})"
            )

    async def sync_metadata(self):
        tokens = await self.token_repository.get_tokens_missing_metadata()

        if not tokens:
            return

        logger.info(f"Syncing metadata for {len(tokens)} token")

        semaphore = asyncio.Semaphore(self.meta_concurrency)

        async def fetch_metadata(token: dict):
            async with semaphore:
                coingecko_id = token.get("coingeckoId")

                if not coingecko_id:
                    return None

                try:
                    metadata = (await self.coingecko_service.get_token_metadata(coingecko_id))
                    return (token, metadata)

                except Exception as exc:
                    logger.error(
                        f"Metadata fetch failed "
                        f"{coingecko_id}: {exc}"
                        )

                    return None

        results = await asyncio.gather(*[fetch_metadata(token) for token in tokens])

        now = int(time.time())

        metadata_updates = []

        print("metadata_updates", results)
        for result in results:
            if not result:
                continue

            token, metadata = result

            if not metadata:
                continue

            try:
                coingecko_id = token.get("coingeckoId")
                detail_platforms = metadata.get("detail_platforms", {})
                ethereum_platform = (detail_platforms.get("ethereum", {}))
                address = ethereum_platform.get("contract_address")

                decimals = ethereum_platform.get("decimal_place")

                if not address:
                    continue

                metadata_updates.append(
                    {"coingeckoId": coingecko_id, "name": metadata.get("name"),
                     "symbol": (metadata.get("symbol") or "").upper(),
                     "image": (metadata.get("image", {}).get("large")), "address": address, "decimals": decimals,
                     "metadataUpdatedAt": now}
                    )

                if len(metadata_updates) >= self.batch_size:
                    await (self.token_repository.bulk_update_metadata(metadata_updates))

                    metadata_updates.clear()

            except Exception as exc:

                logger.error(f"Metadata parse failed: {exc}")

        if metadata_updates:
            await (self.token_repository.bulk_update_metadata(metadata_updates))

        logger.info("Metadata sync completed")
