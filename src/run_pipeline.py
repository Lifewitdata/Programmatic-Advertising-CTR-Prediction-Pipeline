"""One reproducible command. Results are promoted only after checks succeed."""
import argparse
import hashlib
import fcntl
import json
import os
from pathlib import Path
import shutil
import tempfile

import yaml

from src.generate_data import main as generate
from src.etl.validate import validate
from src.features import labels, build_features
from src.modeling import train
from src.reporting import export_reports


def run(n_impressions=25000, config_path='config/etl_config.yaml'):
    config = yaml.safe_load(Path(config_path).read_text())
    Path('reports').mkdir(exist_ok=True)
    # Exclusive lock protects shared generated inputs and processed artifacts too.
    lock = Path('reports/.pipeline.lock')
    lock_handle = lock.open('a+')
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_handle.close()
        raise RuntimeError('Another pipeline run is active') from None
    staging = Path(tempfile.mkdtemp(prefix='.run-', dir='reports'))
    try:
        tables, manifest = generate(n_impressions=n_impressions)
        validation = validate(tables, config)
        frame = labels(tables['impressions'], tables['clicks'], manifest['observed_through'])
        frame = build_features(frame)
        Path('data/processed').mkdir(parents=True, exist_ok=True)
        frame.to_parquet('data/processed/features.parquet', index=False)
        summary = train(frame, config, str(staging))
        export_reports(frame, tables, summary, manifest, str(staging))
        (staging / 'validation_report.json').write_text(json.dumps(validation, indent=2) + '\n')
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path('data/raw').glob('*.csv'))}
        (staging / 'source_sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
        # The current symlink swap is atomic. Failed runs leave last-good reports intact.
        final = Path('reports') / staging.name.replace('.run-', 'run-')
        staging.rename(final)
        temp_link = Path('reports/.current-next')
        temp_link.unlink(missing_ok=True)
        temp_link.symlink_to(final.name, target_is_directory=True)
        os.replace(temp_link, 'reports/current')
        print(json.dumps(summary, indent=2))
        return summary
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        fcntl.flock(lock_handle, fcntl.LOCK_UN)
        lock_handle.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--n-impressions', type=int, default=25000)
    parser.add_argument('--config', default='config/etl_config.yaml')
    args = parser.parse_args()
    run(args.n_impressions, args.config)
