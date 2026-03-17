"""CLI entry point for Life XP."""

from __future__ import annotations

import click
import uvicorn


@click.group()
def cli():
    """Life XP — Gamify your life."""
    pass


@cli.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=5175, type=int)
@click.option("--reload", is_flag=True, default=False)
def serve(host: str, port: int, reload: bool):
    """Start the Life XP API server."""
    uvicorn.run("life_xp.api:app", host=host, port=port, reload=reload)


@cli.command()
def init():
    """Initialize the database."""
    import asyncio
    from life_xp.database import get_db

    async def _init():
        db = await get_db()
        await db.close()
        click.echo("Database initialized.")

    asyncio.run(_init())


if __name__ == "__main__":
    cli()
