# -*- coding: utf-8 -*-
"""
Data Pipeline
=============
*Download US Treasury constant-maturity par yields from FRED, tidy them to
long format, initialise the SQLite schema, and persist the yield curve and
bond reference tables.*

"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd
import pandas_datareader.data as web

from src.config import (
    BOND_PORTFOLIO, DB_PATH, END_DATE, FRED_SERIES, SQL_SCHEMA_PATH, START_DATE,
)

__all__ = ["main"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)


def init_database(db_path: Path, schema_path: Path) -> None:
    """Run the SQL schema script to create tables in the database.

    Parameters
    ----------
    db_path : pathlib.Path
        Destination SQLite file (created if missing).
    schema_path : pathlib.Path
        File containing the ``CREATE TABLE`` statements.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with open(schema_path) as f:
        schema_sql = f.read()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_sql)
        conn.commit()
    logger.info(f"Initialized database at {db_path}")


def download_par_yields(series: dict, start_date: str, end_date: str) -> pd.DataFrame:
    """Download CMT par-yield series from FRED and reshape to long format.

    Parameters
    ----------
    series : dict
        Mapping from FRED series id to tenor in years.
    start_date : str
        Inclusive start date (YYYY-MM-DD).
    end_date : str
        Inclusive end date (YYYY-MM-DD).

    Returns
    -------
    out : pandas.DataFrame
        Long-format frame with columns ``date, tenor, par_yield`` where
        ``par_yield`` is a decimal (e.g. 0.0425 for 4.25%).
    """
    logger.info(f"Downloading {len(series)} FRED series from {start_date} to {end_date}")
    raw = web.DataReader(list(series), 'fred', start_date, end_date)
    raw = raw / 100.0  # FRED reports percentages

    pre_n = len(raw)
    raw = raw.dropna(how='all').ffill().dropna()
    logger.info(f"Kept {len(raw):,} of {pre_n:,} observation dates after cleaning")

    raw.columns = [series[c] for c in raw.columns]
    long_df = (
        raw.reset_index()
        .melt(id_vars='DATE', var_name='tenor', value_name='par_yield')
        .rename(columns={'DATE': 'date'})
    )
    long_df['date'] = pd.to_datetime(long_df['date']).dt.strftime('%Y-%m-%d')
    long_df = long_df.sort_values(['date', 'tenor']).reset_index(drop=True)
    logger.info(f"Reshaped to {len(long_df):,} rows across {long_df['date'].nunique():,} dates")
    return long_df


def write_to_sqlite(df: pd.DataFrame, table_name: str, db_path: Path,
                    if_exists: str = 'replace') -> None:
    """Write a DataFrame to a SQLite table and log the resulting row count.

    Parameters
    ----------
    df : pandas.DataFrame
        Data to persist.
    table_name : str
        Target table.
    db_path : pathlib.Path
        SQLite database file.
    if_exists : str, optional
        ``pandas.to_sql`` mode (default ``"replace"``).
    """
    with sqlite3.connect(db_path) as conn:
        df.to_sql(table_name, conn, if_exists=if_exists, index=False)
        n = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    logger.info(f"Wrote {len(df):,} rows to '{table_name}' (now has {n:,} rows)")


def load_bonds(db_path: Path) -> None:
    """Persist the static bond reference table from the configured portfolio.

    Parameters
    ----------
    db_path : pathlib.Path
        SQLite database file.
    """
    write_to_sqlite(pd.DataFrame(BOND_PORTFOLIO), 'bonds', db_path, if_exists='replace')


def validate_data(db_path: Path) -> None:
    """Assert that the yield_curves and bonds tables look correct.

    Parameters
    ----------
    db_path : pathlib.Path
        SQLite database file.
    """
    with sqlite3.connect(db_path) as conn:
        yc_count = conn.execute("SELECT COUNT(*) FROM yield_curves").fetchone()[0]
        n_dates = conn.execute("SELECT COUNT(DISTINCT date) FROM yield_curves").fetchone()[0]
        n_tenors = conn.execute("SELECT COUNT(DISTINCT tenor) FROM yield_curves").fetchone()[0]
        bonds_count = conn.execute("SELECT COUNT(*) FROM bonds").fetchone()[0]
        date_range = conn.execute("SELECT MIN(date), MAX(date) FROM yield_curves").fetchone()

    logger.info("--- Data Validation Summary ---")
    logger.info(f" yield_curves: {yc_count:>8,} rows")
    logger.info(f" dates:        {n_dates:>8,}")
    logger.info(f" tenors:       {n_tenors:>8,}")
    logger.info(f" bonds:        {bonds_count:>8,}")
    logger.info(f" date range:   {date_range[0]} to {date_range[1]}")

    assert n_tenors == len(FRED_SERIES), "tenor count mismatch"
    assert bonds_count == len(BOND_PORTFOLIO), "bond count mismatch"
    logger.info("Data validation passed.")


def main() -> None:
    """Download, transform, and persist the full yield curve dataset."""
    logger.info("Starting data pipeline")
    init_database(DB_PATH, SQL_SCHEMA_PATH)

    yields_df = download_par_yields(FRED_SERIES, START_DATE, END_DATE)
    write_to_sqlite(yields_df, 'yield_curves', DB_PATH, if_exists='replace')
    load_bonds(DB_PATH)
    validate_data(DB_PATH)

    logger.info("Data pipeline completed.")


if __name__ == '__main__':
    main()
