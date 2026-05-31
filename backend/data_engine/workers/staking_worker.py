import time
from pymongo import UpdateOne

from app.databases.mongo_client import MongoDB
from app.services.graphs.subgraphs.curve_service import CurveService
from core import BaseWorker

_MIN_TVL = 1_000
_MAX_APR = 500.0


class StakingWorker(BaseWorker):
    def __init__(self, scheduler: str = "^true@3600"):
        super().__init__(name="StakingWorker", scheduler=scheduler)
        self.db = MongoDB()
        self.service = CurveService()
        self.batch_size = 1000

    def _get_last_id(self) -> str:
        config = self.db.get_collection("configs").find_one({"_id": "staking_worker"})
        return config.get("last_id", "") if config else ""

    def _save_last_id(self, last_id: str):
        self.db.get_collection("configs").update_one(
            {"_id": "staking_worker"},
            {"$set": {"last_id": last_id}},
            upsert=True,
        )

    async def process(self):
        last_id = self._get_last_id()
        self.logger.info(f"[{self.name}] Crawling from last_id={last_id or '(start)'}")

        pools = await self.service.get_pools(
            last_id=last_id,
            batch_size=self.batch_size,
        )

        if not pools:
            self.logger.info(f"[{self.name}] Full scan complete → reset cursor")
            self._save_last_id("")
            return

        operations = []
        now = int(time.time())
        skipped = 0

        for pool in pools:
            operations.append(UpdateOne(
                {"_id": pool["_id"]},
                {"$set": {
                    **{k: v for k, v in pool.items() if k != "_id"},
                    "updatedAt": now
                }},
                upsert=True,
            ))

        if operations:
            result = self.db.get_collection("staking").bulk_write(operations, ordered=False)
            self.logger.info(
                f"[{self.name}] Bulk write: "
                f"matched={result.matched_count}, "
                f"modified={result.modified_count}, "
                f"upserted={len(result.upserted_ids)} | "
                f"skipped={skipped}"
            )

        new_last_id = pools[-1]["_id"]
        self._save_last_id(new_last_id)
        self.logger.info(f"[{self.name}] Batch done, last_id={new_last_id}")
