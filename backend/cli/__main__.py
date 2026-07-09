import click
from dotenv import load_dotenv

load_dotenv()

from cli.onchain import onchain_crawl_active_wallets, onchain_crawl_wallet
from cli.portfolio import portfolio_reset_wallet, portfolio_stream_worker, portfolio_sync_wallet


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Command line interface."""
    pass


@click.command()
def start_workers():
    """Start configured background workers."""
    from cli.worker import start_workers as command

    command()


cli.add_command(start_workers, "start_workers")
cli.add_command(portfolio_stream_worker, "portfolio_stream_worker")
cli.add_command(portfolio_stream_worker, "portfolio_worker")
cli.add_command(portfolio_sync_wallet, "portfolio_sync_wallet")
cli.add_command(portfolio_reset_wallet, "portfolio_reset_wallet")
cli.add_command(onchain_crawl_wallet, "onchain_crawl_wallet")
cli.add_command(onchain_crawl_active_wallets, "onchain_crawl_active_wallets")


if __name__ == "__main__":
    cli()
