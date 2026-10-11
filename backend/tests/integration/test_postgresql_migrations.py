import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app.config import Settings


BACKEND_DIR = Path(__file__).resolve().parents[2]
EXPECTED_HEAD = "0003_email_unique_constraint"


def test_empty_postgresql_schema_migrates_to_head_with_expected_constraints() -> None:
    database_url = os.getenv("TEST_POSTGRESQL_URL")
    if not database_url:
        pytest.skip("Set TEST_POSTGRESQL_URL to a dedicated PostgreSQL test database to run this test")

    database_url = Settings(_env_file=None, database_url=database_url).database_url
    url = make_url(database_url)
    if "test" not in (url.database or "").casefold():
        pytest.fail("TEST_POSTGRESQL_URL must target a dedicated database whose name includes 'test'")

    engine = create_engine(database_url)
    schema_name = f"migration_test_{uuid4().hex}"
    try:
        with engine.connect() as connection:
            with connection.begin():
                connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
                connection.execute(
                    text("SELECT set_config('search_path', :schema_name, true)"),
                    {"schema_name": schema_name},
                )

                config = Config(str(BACKEND_DIR / "alembic.ini"))
                config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
                config.attributes["connection"] = connection
                command.upgrade(config, "head")

                inspector = inspect(connection)
                assert set(inspector.get_table_names()) >= {
                    "alembic_version",
                    "datasets",
                    "users",
                }
                assert MigrationContext.configure(connection).get_current_revision() == EXPECTED_HEAD

                user_constraints = inspector.get_unique_constraints("users")
                assert any(
                    constraint["name"] == "uq_users_email"
                    and constraint["column_names"] == ["email"]
                    for constraint in user_constraints
                )
                dataset_constraints = inspector.get_unique_constraints("datasets")
                assert any(
                    constraint["column_names"] == ["stored_filename"]
                    for constraint in dataset_constraints
                )

                dataset_foreign_keys = inspector.get_foreign_keys("datasets")
                user_id_foreign_key = next(
                    foreign_key
                    for foreign_key in dataset_foreign_keys
                    if foreign_key["constrained_columns"] == ["user_id"]
                )
                assert user_id_foreign_key["referred_table"] == "users"
                assert user_id_foreign_key["referred_columns"] == ["id"]
                assert user_id_foreign_key["options"]["ondelete"] == "CASCADE"

                user_id = connection.execute(
                    text(
                        "INSERT INTO users (name, email, password_hash) "
                        "VALUES ('Migration Test', 'migration@example.com', 'hashed') "
                        "RETURNING id"
                    )
                ).scalar_one()
                connection.execute(
                    text(
                        "INSERT INTO datasets "
                        "(user_id, original_filename, stored_filename, file_path, file_type, file_size) "
                        "VALUES (:user_id, 'source.csv', 'stored.csv', '/tmp/stored.csv', '.csv', 10)"
                    ),
                    {"user_id": user_id},
                )
                connection.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})
                assert connection.execute(
                    text("SELECT count(*) FROM datasets WHERE user_id = :user_id"),
                    {"user_id": user_id},
                ).scalar_one() == 0
    finally:
        engine.dispose()
