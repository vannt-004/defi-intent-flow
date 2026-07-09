import click
from dotenv import load_dotenv

load_dotenv()

from cli.gas_fee import gas_fee_enqueue_missing, gas_fee_worker
from cli.onchain import onchain_crawl_active_wallets, onchain_crawl_wallet
from cli.worker import start_workers
from cli.portfolio import (
    portfolio_recover_stale_syncing,
    portfolio_rebuild_dashboard_view,
    portfolio_reset_wallet,
    portfolio_stream_worker,
    portfolio_sync_wallet,
)


@click.group()
@click.version_option(version="1.0.0")
@click.pass_context
def cli(ctx):
    pass


cli.add_command(start_workers, "run_workers")

cli.add_command(portfolio_stream_worker, "portfolio_stream_worker")
cli.add_command(portfolio_stream_worker, "portfolio_worker")
cli.add_command(portfolio_sync_wallet, "portfolio_sync_wallet")
cli.add_command(portfolio_reset_wallet, "portfolio_reset_wallet")
cli.add_command(portfolio_rebuild_dashboard_view, "portfolio_rebuild_dashboard_view")
cli.add_command(portfolio_recover_stale_syncing, "portfolio_recover_stale_syncing")
cli.add_command(onchain_crawl_wallet, "onchain_crawl_wallet")
cli.add_command(onchain_crawl_active_wallets, "onchain_crawl_active_wallets")
cli.add_command(gas_fee_worker, "gas_fee_worker")
cli.add_command(gas_fee_enqueue_missing, "gas_fee_enqueue_missing")


if __name__ == "__main__":
    cli()
