import asyncio
import json
import time

import httpx
import redis.asyncio as redis
from redis.exceptions import ResponseError

from config import RedisConfig, Web3Config
from data_engine.services.prices.pricing_service import PricingService
from shared.databases.mongo_client import MongoConnection
from shared.repositories.cashflow_repository import CashflowRepository
from shared.utils.logger_utils import get_logger


class GasFeeStreamService:

    def __init__(
        self,
        redis_url: str = RedisConfig.CONNECTION_URL,
        group_name: str = RedisConfig.GAS_FEE_GROUP,
        consumer_name: str = RedisConfig.GAS_FEE_CONSUMER,
        stream_name: str = RedisConfig.GAS_FEE_STREAM,
        rpc_url: str = Web3Config.RPC_URL,
        batch_wait_seconds: int = 30,
        batch_size: int = 100,
        block_ms: int = 1000,
    ):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.group_name = group_name
        self.consumer_name = consumer_name
        self.stream_name = stream_name
        self.rpc_url = rpc_url
        self.batch_wait_seconds = batch_wait_seconds
        self.batch_size = batch_size
        self.block_ms = block_ms
        self.logger = get_logger(self.__class__.__name__)

        db = MongoConnection.get_database()
        self.cashflow_repository = CashflowRepository(db)
        self.pricing = PricingService(db)

    async def ensure_group_exists(self):
        try:
            await self.redis.xgroup_create(
                name=self.stream_name,
                groupname=self.group_name,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def run(self):
        await self.ensure_group_exists()
        self.logger.info(
            "consuming stream=%s group=%s consumer=%s batch_wait=%ss",
            self.stream_name,
            self.group_name,
            self.consumer_name,
            self.batch_wait_seconds,
        )

        while True:
            entries = await self._collect_batch()
            if not entries:
                continue
            await self._process_entries(entries)

    async def enqueue_missing_cashflows(self, limit: int = 500) -> int:
        rows = self.cashflow_repository.get_missing_gas_tx_hashes(limit=limit)
        for row in rows:
            await self.redis.xadd(
                self.stream_name,
                {"msg": json.dumps({"wallet": row.get("wallet"), "txHash": row.get("txHash")})},
                id="*",
            )
        return len(rows)

    async def _collect_batch(self) -> list[tuple[str, dict]]:
        started_at = time.monotonic()
        entries: list[tuple[str, dict]] = []

        while len(entries) < self.batch_size and time.monotonic() - started_at < self.batch_wait_seconds:
            messages = await self.redis.xreadgroup(
                groupname=self.group_name,
                consumername=self.consumer_name,
                streams={self.stream_name: ">"},
                count=max(self.batch_size - len(entries), 1),
                block=self.block_ms,
            )
            for _, stream_entries in messages:
                for entry_id, message in stream_entries:
                    entries.append((entry_id, self._decode_event(message)))

            if entries and time.monotonic() - started_at >= self.batch_wait_seconds:
                break

        return entries

    async def _process_entries(self, entries: list[tuple[str, dict]]):
        tx_hashes = sorted({
            str(event.get("txHash") or event.get("tx_hash") or "").lower()
            for _, event in entries
            if event.get("txHash") or event.get("tx_hash")
        })
        tx_hashes = [tx_hash for tx_hash in tx_hashes if tx_hash.startswith("0x") and len(tx_hash) == 66]

        if tx_hashes:
            await self._sync_gas_for_hashes(tx_hashes)

        for entry_id, _ in entries:
            await self.redis.xack(self.stream_name, self.group_name, entry_id)

    async def _sync_gas_for_hashes(self, tx_hashes: list[str]):
        receipt_by_hash = await self._fetch_receipts_batch(tx_hashes)
        cashflows = self.cashflow_repository.get_cashflows_by_tx_hashes(tx_hashes)
        timestamp_by_hash = {}
        for row in cashflows:
            tx_hash = (row.get("tx_hash") or self._extract_hash(row.get("tx_id")) or "").lower()
            if tx_hash and tx_hash not in timestamp_by_hash:
                timestamp_by_hash[tx_hash] = int(row.get("timestamp") or 0)

        updated = 0
        for tx_hash, receipt in receipt_by_hash.items():
            if not receipt:
                continue
            gas_used = int(receipt.get("gasUsed") or "0", 16)
            gas_price = int(receipt.get("effectiveGasPrice") or receipt.get("gasPrice") or "0", 16)
            gas_cost_eth = gas_used * gas_price / 1e18
            timestamp = timestamp_by_hash.get(tx_hash) or 0
            eth_price = self.pricing.get_historical_price("ETH", timestamp) if timestamp else self.pricing.get_price_safe("ETH", 0.0)
            gas_cost_usd = gas_cost_eth * eth_price if eth_price else 0.0
            result = self.cashflow_repository.update_gas_by_tx_hash(
                tx_hash=tx_hash,
                gas_cost_eth=gas_cost_eth,
                gas_cost_usd=gas_cost_usd,
            )
            updated += int(getattr(result, "modified_count", 0) or 0)

        self.logger.info("receipts=%s cashflows_updated=%s", len(receipt_by_hash), updated)

    async def _fetch_receipts_batch(self, tx_hashes: list[str]) -> dict[str, dict | None]:
        payload = [
            {
                "jsonrpc": "2.0",
                "id": index + 1,
                "method": "eth_getTransactionReceipt",
                "params": [tx_hash],
            }
            for index, tx_hash in enumerate(tx_hashes)
        ]
        id_to_hash = {index + 1: tx_hash for index, tx_hash in enumerate(tx_hashes)}

        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)) as client:
            response = await client.post(self.rpc_url, json=payload)
            response.raise_for_status()
            data = response.json()

        rows = data if isinstance(data, list) else [data]
        return {
            id_to_hash.get(row.get("id")): row.get("result")
            for row in rows
            if id_to_hash.get(row.get("id"))
        }

    def _decode_event(self, message: dict) -> dict:
        raw = message.get("msg") or message.get("event") or message
        return json.loads(raw) if isinstance(raw, str) else raw

    def _extract_hash(self, value: str | None) -> str | None:
        if not value:
            return None
        marker = "0x"
        text = str(value).lower()
        index = text.find(marker)
        if index < 0:
            return None
        candidate = text[index:index + 66]
        return candidate if len(candidate) == 66 else None
