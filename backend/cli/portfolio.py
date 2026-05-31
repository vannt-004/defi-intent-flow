import asyncio

import click

from config import RedisConfig
from data_engine.services.user.portfolio_sync_service import PortfolioSyncService
from data_engine.streams.user_portfolio_stream_service import UserPortfolioStreamService


@click.command()
@click.option("--redis-url", default=RedisConfig.CONNECTION_URL, show_default=True)
@click.option("--stream", default=RedisConfig.PORTFOLIO_STREAM, show_default=True)
@click.option("--group", default=RedisConfig.PORTFOLIO_GROUP, show_default=True)
@click.option("--consumer", default=RedisConfig.PORTFOLIO_CONSUMER, show_default=True)
def portfolio_stream_worker(redis_url: str, stream: str, group: str, consumer: str):
    """Consume wallet events from Redis Stream and write portfolio snapshots."""

    async def run():
        service = UserPortfolioStreamService(
            redis_url=redis_url,
            stream_name=stream,
            group_name=group,
            consumer_name=consumer,
        )
        await service.run()

    asyncio.run(run())


@click.command()
@click.argument("wallet")
@click.option("--mode", default="SYNC", show_default=True)
def portfolio_sync_wallet(wallet: str, mode: str):
    """Sync one wallet immediately without Redis."""

    async def run():
        service = PortfolioSyncService()
        snapshot = await service.sync_user(wallet=wallet, mode=mode)
        click.echo(
            "wallet={wallet} net_worth_usd={net_worth} total_pnl_usd={pnl}".format(
                wallet=snapshot["wallet"],
                net_worth=snapshot["net_worth_usd"],
                pnl=snapshot["total_pnl_usd"],
            )
        )

    asyncio.run(run())


@click.command()
@click.argument("wallet")
def portfolio_reset_wallet(wallet: str):
    """Delete derived portfolio data for one wallet, keeping token/price/yield data."""

    service = PortfolioSyncService()
    result = service.reset_wallet_data(wallet)
    click.echo(f"wallet={result['wallet']} deleted={result['deleted']}")
