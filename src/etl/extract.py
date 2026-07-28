"""
Extraction layer: loads the six raw tables either from PostgreSQL (Phase 4)
or directly from data/raw/*.csv, depending on config["source"]. Returns a
plain dict of DataFrames so downstream stages (validate/clean/transform)
don't need to know or care where the data came from.
"""

from pathlib import Path
from typing import Dict

import pandas as pd
from sqlalchemy import create_engine

from src.database.db_config import DBConfig
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

TABLES = ["users", "advertisers", "campaigns", "creatives", "impressions", "clicks"]


def extract_from_postgres() -> Dict[str, pd.DataFrame]:
    db_config = DBConfig()
    engine = create_engine(db_config.sqlalchemy_url)
    data = {}
    for table in TABLES:
        logger.info("Extracting %s from PostgreSQL...", table)
        data[table] = pd.read_sql_table(table, engine)
        logger.info("  %s: %s rows", table, len(data[table]))
    engine.dispose()
    return data


def extract_from_csv(csv_dir: str) -> Dict[str, pd.DataFrame]:
    data_path = Path(csv_dir)
    data = {}
    for table in TABLES:
        file_path = data_path / f"{table}.csv"
        logger.info("Extracting %s from %s...", table, file_path)
        data[table] = pd.read_csv(file_path)
        logger.info("  %s: %s rows", table, len(data[table]))
    return data


def extract(config: dict) -> Dict[str, pd.DataFrame]:
    if config["source"] == "postgres":
        try:
            return extract_from_postgres()
        except Exception as exc:
            logger.warning("PostgreSQL extraction failed (%s) — falling back to CSV.", exc)
            return extract_from_csv(config["csv_dir"])
    return extract_from_csv(config["csv_dir"])
