import asyncio

import click

from config import RedisConfig
from data_engine.services.user.portfolio_sync_service import PortfolioSyncService
from data_engine.streams.user_portfolio_stream_service import UserPortfolioStreamService
from portfolio_engine.services.portfolio_analytics_service import PortfolioAnalyticsService
from shared.databases.mongo_client import MongoConnection
from shared.repositories.wallet_repository import WalletRepository


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
@click.option(
    "--full-history",
    is_flag=True,
    help="Crawl protocol cashflow and supported on-chain transfers from genesis for this wallet.",
)
@click.option(
    "--reset-first",
    is_flag=True,
    help="Delete derived data for this wallet before syncing. Use carefully for reproducible backtests.",
)
@click.option("--full-history-start-block", type=int, default=None)
@click.option("--backfill-days", type=int, default=None)
@click.option("--provider-event-limit", type=int, default=None)
def portfolio_sync_wallet(
    wallet: str,
    mode: str,
    full_history: bool,
    reset_first: bool,
    full_history_start_block: int | None,
    backfill_days: int | None,
    provider_event_limit: int | None,
):
    """Sync one wallet immediately without Redis."""

    async def run():
        service = PortfolioSyncService()
        if full_history_start_block is not None:
            service.FULL_HISTORY_START_BLOCK = full_history_start_block
        if backfill_days is not None:
            service.FULL_HISTORY_SYNTHETIC_BACKFILL_DAYS = backfill_days
        if provider_event_limit is not None:
            service.CASHFLOW_PROVIDER_EVENT_LIMIT = provider_event_limit

        sync_mode = "CRAWL_FULL_HISTORY" if full_history else mode

        if reset_first:
            result = service.reset_wallet_data(wallet)
            click.echo(f"wallet={result['wallet']} reset_deleted={result['deleted']}")

        snapshot = await service.sync_user(wallet=wallet, mode=sync_mode)
        click.echo(
            "wallet={wallet} mode={mode} net_worth_usd={net_worth} total_pnl_usd={pnl} onchain_saved={onchain_saved}".format(
                wallet=snapshot["wallet"],
                mode=sync_mode,
                net_worth=snapshot["net_worth_usd"],
                pnl=snapshot["total_pnl_usd"],
                onchain_saved=snapshot.get("onchain_transaction_count", 0),
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


@click.command()
@click.argument("wallet")
def portfolio_rebuild_dashboard_view(wallet: str):
    """Rebuild materialized dashboard view for one wallet."""

    payload = PortfolioAnalyticsService().refresh_dashboard_view(wallet)
    click.echo(
        "wallet={wallet} net_worth_usd={net_worth} transactions={transactions}".format(
            wallet=wallet.lower().strip(),
            net_worth=payload.get("netWorth", {}).get("totalUsd", 0),
            transactions=len(payload.get("transactions") or []),
        )
    )


@click.command()
@click.option("--timeout-minutes", default=45, show_default=True)
def portfolio_recover_stale_syncing(timeout_minutes: int):
    """Mark wallets stuck in syncing beyond the lease as failed."""

    repository = WalletRepository(MongoConnection.get_database())
    count = repository.recover_stale_syncing(timeout_minutes=timeout_minutes)
    click.echo(f"recovered={count}")
