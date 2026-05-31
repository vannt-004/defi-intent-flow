from config import RedisConfig
from data_engine.services.user.portfolio_sync_service import PortfolioSyncService
from data_engine.streams.base_stream_service import BaseStreamService


class UserPortfolioStreamService(BaseStreamService):

    def __init__(
        self,
        redis_url: str = RedisConfig.CONNECTION_URL,
        group_name: str = RedisConfig.PORTFOLIO_GROUP,
        consumer_name: str = RedisConfig.PORTFOLIO_CONSUMER,
        stream_name: str = RedisConfig.PORTFOLIO_STREAM,
    ):
        super().__init__(
            redis_url=redis_url,
            group_name=group_name,
            consumer_name=consumer_name,
            stream_name=stream_name,
        )
        self.portfolio_sync = PortfolioSyncService()

    async def process_event(self, event_dict: dict):
        wallet = event_dict.get("wallet") or event_dict.get("address") or event_dict.get("user")
        if not wallet:
            raise ValueError(f"Missing wallet in event: {event_dict}")

        await self.portfolio_sync.sync_user(wallet=wallet)
