import json
import re

import redis

from config import RedisConfig


class GasFeeQueueService:

    def __init__(self, redis_url: str = RedisConfig.CONNECTION_URL, stream_name: str = RedisConfig.GAS_FEE_STREAM):
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.stream_name = stream_name

    def enqueue_hashes(self, wallet: str, tx_hashes: list[str]) -> int:
        wallet = wallet.lower().strip()
        count = 0
        for tx_hash in sorted({self.extract_tx_hash(tx_hash) for tx_hash in tx_hashes if tx_hash}):
            if not tx_hash:
                continue
            self.redis.xadd(
                self.stream_name,
                {"msg": json.dumps({"wallet": wallet, "txHash": tx_hash})},
                id="*",
            )
            count += 1
        return count

    @staticmethod
    def extract_tx_hash(value: str | None) -> str | None:
        if not value:
            return None
        match = re.search(r"0x[a-fA-F0-9]{64}", str(value))
        return match.group(0).lower() if match else None
