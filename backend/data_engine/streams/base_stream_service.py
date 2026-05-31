import json
from abc import ABC, abstractmethod

import redis.asyncio as redis
from redis.exceptions import ResponseError

from shared.utils.logger_utils import get_logger


class BaseStreamService(ABC):

    def __init__(
        self,
        redis_url: str,
        group_name: str,
        consumer_name: str,
        stream_name: str,
        batch_size: int = 10,
        block_ms: int = 1000,
    ):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.group_name = group_name
        self.consumer_name = consumer_name
        self.stream_name = stream_name
        self.batch_size = batch_size
        self.block_ms = block_ms
        self.logger = get_logger(self.__class__.__name__)

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

    async def consume_event(self, last_id: str = ">"):
        messages = await self.redis.xreadgroup(
            groupname=self.group_name,
            consumername=self.consumer_name,
            streams={self.stream_name: last_id},
            count=self.batch_size,
            block=self.block_ms,
        )

        for _, entries in messages:
            for entry_id, message in entries:
                try:
                    event = self._decode_event(message)
                    await self.process_event(event)
                    await self.redis.xack(self.stream_name, self.group_name, entry_id)
                except Exception as exc:
                    self.logger.exception(
                        "[%s] failed entry_id=%s error=%s",
                        self.__class__.__name__,
                        entry_id,
                        exc,
                    )

    async def run(self):
        await self.ensure_group_exists()
        self.logger.info(
            "[%s] consuming stream=%s group=%s consumer=%s",
            self.__class__.__name__,
            self.stream_name,
            self.group_name,
            self.consumer_name,
        )

        while True:
            await self.consume_event()

    def _decode_event(self, message: dict) -> dict:
        raw = message.get("msg") or message.get("event") or message

        if isinstance(raw, str):
            return json.loads(raw)

        return raw

    @abstractmethod
    async def process_event(self, event_dict: dict):
        pass
