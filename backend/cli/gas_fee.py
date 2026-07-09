import asyncio

import click

from config import RedisConfig, Web3Config
from data_engine.streams.gas_fee_stream_service import GasFeeStreamService


@click.command()
@click.option("--redis-url", default=RedisConfig.CONNECTION_URL, show_default=True)
@click.option("--stream", default=RedisConfig.GAS_FEE_STREAM, show_default=True)
@click.option("--group", default=RedisConfig.GAS_FEE_GROUP, show_default=True)
@click.option("--consumer", default=RedisConfig.GAS_FEE_CONSUMER, show_default=True)
@click.option("--rpc-url", default=Web3Config.RPC_URL, show_default=True)
@click.option("--batch-wait-seconds", default=30, show_default=True)
@click.option("--batch-size", default=100, show_default=True)
def gas_fee_worker(
    redis_url: str,
    stream: str,
    group: str,
    consumer: str,
    rpc_url: str,
    batch_wait_seconds: int,
    batch_size: int,
):
    """Consume tx hashes and backfill gas fee into cashflow."""

    async def run():
        service = GasFeeStreamService(
            redis_url=redis_url,
            stream_name=stream,
            group_name=group,
            consumer_name=consumer,
            rpc_url=rpc_url,
            batch_wait_seconds=batch_wait_seconds,
            batch_size=batch_size,
        )
        await service.run()

    asyncio.run(run())


@click.command()
@click.option("--limit", default=500, show_default=True)
def gas_fee_enqueue_missing(limit: int):
    """Queue existing cashflow tx hashes that have no gas fee yet."""

    async def run():
        service = GasFeeStreamService()
        count = await service.enqueue_missing_cashflows(limit=limit)
        click.echo(f"queued={count}")

    asyncio.run(run())
