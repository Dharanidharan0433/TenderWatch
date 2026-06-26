"""
database/db.py
----------------
Connection management layer for the TenderWatch SQLite database.

Responsibilities:
    - Provide a single, consistent way to open SQLite connections.
    - Enforce foreign key constraints (off by default in SQLite).
    - Return rows as dict-like objects (sqlite3.Row) so calling code
      can access columns by name instead of brittle positional indexes.
    - Own database initialization (building tables from schema.py).

This module deliberately contains NO business logic and NO knowledge
of tenders/bids/vendors as concepts -- it only knows how to talk to
SQLite safely. Detectors, services, and data generation all depend on
this module; this module depends on nothing else in the project.
"""

import sqlite3
import os
from contextlib import contextmanager

from database.schema import SCHEMA_STATEMENTS

# Default location of the SQLite database file.
# Kept as a module-level constant (rather than hardcoded inline) so
# other modules and tests can override it via DB_PATH if needed.
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tenderwatch.db")


def _row_factory(cursor, row):
    """
    Converts raw SQLite rows into a dict.

    Using a plain dict (instead of sqlite3.Row) keeps downstream code
    (pandas.DataFrame(rows), JSON serialization, etc.) simple, since
    sqlite3.Row objects are not natively JSON-serializable or directly
    usable as a list of plain dicts.
    """
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


@contextmanager
def get_connection(db_path: str = DB_PATH):
    """
    Context-managed SQLite connection.

    Usage:
        with get_connection() as conn:
            cursor = conn.execute("SELECT * FROM tenders")
            rows = cursor.fetchall()

    Guarantees:
        - Foreign key enforcement is turned on for this connection.
        - Connection is always closed, even if an exception occurs.
        - On successful exit, changes are committed; on exception,
          changes are rolled back, so callers don't need to manage
          transactions manually for typical single-block usage.
    """
    # Ensure the parent directory for the DB file exists before connecting.
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = _row_factory

    # SQLite does not enforce FK constraints unless explicitly told to.
    # Without this, orphaned bids/risk records could silently exist.
    conn.execute("PRAGMA foreign_keys = ON;")

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database(db_path: str = DB_PATH, drop_existing: bool = False) -> None:
    """
    Creates all tables and indexes defined in schema.py.

    Args:
        db_path: Path to the SQLite file to initialize.
        drop_existing: If True, drops all known tables first. Useful
            for a clean rebuild during development or before reseeding.
            Defaults to False so this is never destructive by accident.
    """
    with get_connection(db_path) as conn:
        if drop_existing:
            # Drop in reverse dependency order so foreign keys never
            # block a drop (children before parents).
            drop_order = [
                "risk_indicators",
                "risk_assessments",
                "bids",
                "tenders",
                "vendors",
            ]
            for table in drop_order:
                conn.execute(f"DROP TABLE IF EXISTS {table};")

        for statement in SCHEMA_STATEMENTS:
            conn.execute(statement)


def execute_query(query: str, params: tuple = (), db_path: str = DB_PATH) -> list:
    """
    Runs a SELECT query and returns all matching rows as a list of dicts.

    This is the primary read entrypoint used by database/queries.py,
    detectors, and services -- they should never open their own
    sqlite3 connections directly.
    """
    with get_connection(db_path) as conn:
        cursor = conn.execute(query, params)
        return cursor.fetchall()


def execute_write(query: str, params: tuple = (), db_path: str = DB_PATH) -> int:
    """
    Runs a single INSERT/UPDATE/DELETE statement.

    Returns:
        lastrowid -- useful for INSERTs where the caller needs the
        newly generated primary key (e.g. vendor_id after inserting
        a vendor).
    """
    with get_connection(db_path) as conn:
        cursor = conn.execute(query, params)
        return cursor.lastrowid


def execute_many(query: str, param_list: list, db_path: str = DB_PATH) -> None:
    """
    Bulk-executes the same INSERT/UPDATE statement against many rows.

    Used heavily by the synthetic data seeding process, where we need
    to insert hundreds or thousands of rows efficiently rather than
    one-by-one (executemany is significantly faster than a Python loop
    of individual execute() calls).
    """
    with get_connection(db_path) as conn:
        conn.executemany(query, param_list)
