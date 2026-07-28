"""Small helper for loading the YAML config used across the pipeline."""

from pathlib import Path
import yaml


def load_config(config_path: str = "config/data_gen_config.yaml") -> dict:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found at: {path.resolve()}")
    with open(path, "r") as f:
        return yaml.safe_load(f)


def weighted_choice_arrays(items):
    """Split a list of {key: value, weight: w} dicts into parallel arrays
    of values and normalized weights, ready for np.random.choice(p=...).
    """
    import numpy as np

    keys = list(items[0].keys())
    value_key = [k for k in keys if k != "weight"][0]
    values = [item[value_key] for item in items]
    weights = np.array([item["weight"] for item in items], dtype=float)
    weights = weights / weights.sum()
    return values, weights
