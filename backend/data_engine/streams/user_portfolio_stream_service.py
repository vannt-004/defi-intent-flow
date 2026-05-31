from config import RedisConfig
from data_engine.services.user.portfolio_sync_service import PortfolioSyncService
from data_engine.streams.base_stream_service import BaseStreamService
from shared.utils.logger_utils import get_logger

logger = get_logger("UserPortfolioStreamService")


class UserPortfolioStreamService(BaseStreamService):

    def __init__(self,
        redis_url: str = RedisConfig.CONNECTION_URL,
        group_name: str = RedisConfig.PORTFOLIO_GROUP,
        consumer_name: str = RedisConfig.PORTFOLIO_CONSUMER,
        stream_name: str = RedisConfig.PORTFOLIO_STREAM, ):
        super().__init__(
            redis_url=redis_url,
            group_name=group_name,
            consumer_name=consumer_name,
            stream_name=stream_name
        )
        self.portfolio_sync = PortfolioSyncService()

    async def process_event(self, event_dict: dict):
        wallet = event_dict.get("wallet")
        mode = event_dict.get("mode") or event_dict.get("action")

        if not wallet:
            raise ValueError(f"Missing wallet in event: {event_dict}")

        wallet = wallet.lower().strip()
        logger.info(f"[Queue] Processing sync event for wallet: {wallet}")

        await self.portfolio_sync.sync_user(wallet=wallet, mode=mode)