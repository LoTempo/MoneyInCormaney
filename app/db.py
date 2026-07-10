from pathlib import Path

import click
import psycopg
from flask import current_app, g
from psycopg.rows import dict_row


def get_db():
    """Return one PostgreSQL connection for the current HTTP request."""

    if "db" not in g:
        common_options = {
            "row_factory": dict_row,
            "connect_timeout": current_app.config["DATABASE_CONNECT_TIMEOUT"],
        }
        database_url = current_app.config.get("DATABASE_URL")

        if database_url:
            g.db = psycopg.connect(database_url, **common_options)
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
    """Close the request connection, rolling back unfinished changes."""

    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db():
    """Create database tables from sql/schema.sql."""

    schema_path = Path(current_app.root_path).parent / "sql" / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")

    connection = get_db()
    connection.execute(schema)
    connection.commit()


@click.command("init-db")
def init_db_command():
    """Create all application tables."""

    init_db()
    click.echo("Database tables have been created.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
