import asyncio

import click

from data_engine.services.user.onchain_transaction_crawler import OnchainTransactionCrawler


@click.command()
@click.argument("wallet")
@click.option("--start-block", type=int, default=None)
@click.option("--end-block", type=int, default=99999999, show_default=True)
@click.option("--offset", type=int, default=1000, show_default=True)
def onchain_crawl_wallet(wallet: str, start_block: int | None, end_block: int, offset: int):
    """Preview supported native and ERC20 wallet transactions from Etherscan."""

    async def run():
        crawler = OnchainTransactionCrawler()
        try:
            result = await crawler.crawl_wallet(
                wallet=wallet,
                start_block=start_block,
                end_block=end_block,
                offset=offset,
            )
            click.echo(result)
        finally:
            await crawler.close()

    asyncio.run(run())


@click.command()
@click.option("--limit", type=int, default=1000, show_default=True)
def onchain_crawl_active_wallets(limit: int):
    """Preview supported on-chain transactions for active wallets."""

    async def run():
        crawler = OnchainTransactionCrawler()
        try:
            results = await crawler.crawl_active_wallets(limit=limit)
            click.echo({"wallet_count": len(results), "results": results})
        finally:
            await crawler.close()

    asyncio.run(run())
