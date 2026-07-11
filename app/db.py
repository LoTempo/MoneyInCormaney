from pathlib import Path
import atexit

import click
import psycopg
from flask import current_app, g
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def get_db():
    """Return one PostgreSQL connection for the current HTTP request."""

    if "db" not in g:
        common_options = {
            "row_factory": dict_row,
            "connect_timeout": current_app.config["DATABASE_CONNECT_TIMEOUT"],
        }
        database_url = current_app.config.get("DATABASE_URL")

        pool = current_app.extensions.get("database_pool")
        if database_url and pool is not None:
            if pool.closed:
                pool.open()
            g.db = pool.getconn(timeout=current_app.config["DATABASE_CONNECT_TIMEOUT"])
            g.db_pool = pool
        else:
            g.db = psycopg.connect(
                host=current_app.config["DATABASE_HOST"],
                port=current_app.config["DATABASE_PORT"],
                dbname=current_app.config["DATABASE_NAME"],
                user=current_app.config["DATABASE_USER"],
                password=current_app.config["DATABASE_PASSWORD"],
                **common_options,
            )

    return g.db


def close_db(error=None):
    """Roll back unfinished work and return the connection to its pool."""

    connection = g.pop("db", None)
    pool = g.pop("db_pool", None)
    if connection is None:
        return

    if (
        not connection.closed
        and connection.info.transaction_status != TransactionStatus.IDLE
    ):
        connection.rollback()

    if pool is not None:
        pool.putconn(connection)
    else:
        connection.close()


def init_db():
    """Create database tables from sql/schema.sql."""

    schema_path = Path(current_app.root_path).parent / "sql" / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")

    admin_url = current_app.config.get("DATABASE_ADMIN_URL")
    if admin_url:
        with psycopg.connect(
            admin_url,
            connect_timeout=current_app.config["DATABASE_CONNECT_TIMEOUT"],
        ) as connection:
            connection.execute(schema)
        return

    connection = get_db()
    connection.execute(schema)
    connection.commit()


@click.command("init-db")
def init_db_command():
    """Create all application tables."""

    init_db()
    click.echo("Database tables have been created.")


def init_app(app):
    database_url = app.config.get("DATABASE_URL")
    if database_url:
        pool = ConnectionPool(
            conninfo=database_url,
            kwargs={
                "row_factory": dict_row,
                "connect_timeout": app.config["DATABASE_CONNECT_TIMEOUT"],
            },
            min_size=app.config["DATABASE_POOL_MIN_SIZE"],
            max_size=app.config["DATABASE_POOL_MAX_SIZE"],
            max_idle=app.config["DATABASE_POOL_MAX_IDLE"],
            timeout=app.config["DATABASE_CONNECT_TIMEOUT"],
            open=False,
            name="family-budget",
        )
        app.extensions["database_pool"] = pool
        atexit.register(pool.close)

    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
