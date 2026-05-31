import click
from dotenv import load_dotenv

load_dotenv()

from cli.portfolio import portfolio_stream_worker, portfolio_sync_wallet
from cli.onchain import onchain_crawl_active_wallets, onchain_crawl_wallet
from cli.worker import start_workers  # 1. Import command mới tạo


@click.group()
@click.version_option(version="1.0.0")
@click.pass_context
def cli(ctx):
    pass


cli.add_command(start_workers, "run_workers")

cli.add_command(portfolio_stream_worker, "portfolio_stream_worker")
cli.add_command(portfolio_sync_wallet, "portfolio_sync_wallet")
cli.add_command(onchain_crawl_wallet, "onchain_crawl_wallet")
cli.add_command(onchain_crawl_active_wallets, "onchain_crawl_active_wallets")


if __name__ == "__main__":
    cli()