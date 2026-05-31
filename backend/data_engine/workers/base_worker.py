import asyncio
import time
from abc import ABC, abstractmethod

from shared.utils.logger_utils import get_logger
from shared.utils.scheduler_utils import parse_scheduler


class BaseWorker(ABC):
    def __init__(self, name: str, scheduler: str):
        self.name = name
        self.logger = get_logger(name)

        self.config = parse_scheduler(scheduler)

        self.run_now = self.config["run_now"]
        self.interval = self.config["interval"]
        self.delay = self.config["delay"]
        self.end_timestamp = self.config["end_timestamp"]
        self.retry_enabled = self.config["retry"]

        self._running = False

    async def start(self):
        self.logger.info(f"[{self.name}] Starting with config: {self.config}")
        self._running = True

        if self.delay > 0:
            self.logger.info(f"[{self.name}] Delay {self.delay}s...")
            await asyncio.sleep(self.delay)

        if not self.run_now:
            await asyncio.sleep(self.interval)

        await self._run_loop()

    async def stop(self):
        self.logger.info(f"[{self.name}] Stopping...")
        self._running = False

    async def _run_loop(self):
        while self._running:
            if self.end_timestamp and time.time() > self.end_timestamp:
                self.logger.info(f"[{self.name}] Reached end time. Stopping...")
                await self.stop()
                break

            if self.retry_enabled:
                await self._execute_with_retry()
            else:
                await self.process()

            if self.interval:
                await asyncio.sleep(self.interval)
            else:
                break

    async def _execute_with_retry(self):
        for attempt in range(1, 4):
            try:
                await self.process()
                return
            except Exception as e:
                self.logger.warning(f"[{self.name}] Attempt {attempt} failed: {e}")
                await asyncio.sleep(attempt * 2)

    @abstractmethod
    async def process(self):
        pass