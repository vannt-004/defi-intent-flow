import asyncio

from config import RedisConfig
from data_engine.streams.user_portfolio_stream_service import UserPortfolioStreamService


async def main():
    service = UserPortfolioStreamService(
        redis_url=RedisConfig.CONNECTION_URL,
        stream_name=RedisConfig.PORTFOLIO_STREAM,
        group_name=RedisConfig.PORTFOLIO_GROUP,
        consumer_name=RedisConfig.PORTFOLIO_CONSUMER,
    )
    await service.run()


if __name__ == "__main__":
    asyncio.run(main())
