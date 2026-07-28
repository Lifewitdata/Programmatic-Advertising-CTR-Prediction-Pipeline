"""
Orchestrates the full Phase 5 ETL pipeline:

    extract -> validate -> clean -> transform (label + split) -> save

Usage:
    python -m src.etl.run_etl --config config/etl_config.yaml

Outputs, under data/processed/:
    ctr_dataset_full.parquet
    train.parquet, val.parquet, test.parquet
    validation_report.json
"""

import argparse
import json
import time
from pathlib import Path

from src.utils.config import load_config
from src.utils.logging_config import get_logger
from src.etl.extract import extract
from src.etl.validate import validate, ValidationError
from src.etl.clean import clean_impressions, clean_clicks
from src.etl.transform import attach_label, time_based_split

logger = get_logger(__name__)


def main(config_path: str) -> None:
    t0 = time.time()
    config = load_config(config_path)
    out_dir = Path(config["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- Extract ------------------------------------------------------
    logger.info("=== EXTRACT ===")
    data = extract(config)

    # ---- Validate -------------------------------------------------------
    logger.info("=== VALIDATE ===")
    try:
        report = validate(data, config)
    except ValidationError as exc:
        logger.error("Validation FAILED: %s", exc)
        raise

    # ---- Clean ------------------------------------------------------------
    logger.info("=== CLEAN ===")
    impressions_clean = clean_impressions(data["impressions"], config)
    clicks_clean = clean_clicks(data["clicks"])

    # ---- Transform (label + split) -----------------------------------------
    logger.info("=== TRANSFORM ===")
    labeled = attach_label(impressions_clean, clicks_clean)

    split_cfg = config["split"]
    train, val, test = time_based_split(
        labeled, split_cfg["train_end_date"], split_cfg["val_end_date"]
    )

    # ---- Save ---------------------------------------------------------------
    logger.info("=== SAVE ===")
    labeled.to_parquet(out_dir / "ctr_dataset_full.parquet", index=False)
    train.to_parquet(out_dir / "train.parquet", index=False)
    val.to_parquet(out_dir / "val.parquet", index=False)
    test.to_parquet(out_dir / "test.parquet", index=False)

    report["split_row_counts"] = {"train": len(train), "val": len(val), "test": len(test)}
    report["split_ctr"] = {
        "train": float(train["clicked"].mean()),
        "val": float(val["clicked"].mean()),
        "test": float(test["clicked"].mean()),
    }
    with open(out_dir / "validation_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)

    logger.info("Saved processed datasets and validation_report.json to %s", out_dir)
    logger.info("ETL pipeline complete in %.1fs", time.time() - t0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/etl_config.yaml")
    args = parser.parse_args()
    main(args.config)
