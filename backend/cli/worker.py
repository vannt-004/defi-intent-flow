import asyncio
import click
from core.worker import workers


async def run_workers_loop():
    click.echo("Starting all background workers...")

    tasks = [asyncio.create_task(worker.start()) for worker in workers]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        click.echo("Cancellation requested, stopping workers...")
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        click.echo("All workers stopped clean.")


@click.command()
def start_workers():
    try:
        asyncio.run(run_workers_loop())
    except KeyboardInterrupt:
        click.echo("\nWorker CLI interrupted by user. Exiting...")