import json
from pathlib import Path

import pytest

from src.etl.extract import extract


def test_postgres_failure_does_not_silently_switch_to_stale_csv(monkeypatch):
    def fail():
        raise RuntimeError('schema changed')
    monkeypatch.setattr('src.etl.extract.extract_from_postgres', fail)
    with pytest.raises(RuntimeError, match='schema changed'):
        extract({'source': 'postgres', 'csv_dir': 'does-not-exist'})


def test_unknown_source_fails_explicitly():
    with pytest.raises(ValueError, match='Unknown'):
        extract({'source': 'unknown'})


def test_postgres_copy_uses_named_csv_columns_in_schema_order(tmp_path):
    from src.database.load_to_postgres import load_csv
    source = tmp_path / 'input.csv'
    source.write_text('second,first\n20,10\n')
    captured = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def copy_expert(self, sql, buffer):
            captured.append(buffer.read())

        def execute(self, sql):
            pass

        def fetchone(self):
            return (1,)

    class Connection:
        def cursor(self):
            return Cursor()

    assert load_csv(Connection(), source, 'fixture', 'first,second') == 1
    assert captured == ['first,second\n10,20\n']


def test_verified_postgres_permissions_and_reconciliation():
    path = Path('reports/current/postgres_verification.json')
    if not path.exists():
        pytest.skip('Run PostgreSQL verification first')
    report = json.loads(path.read_text())
    assert report['analytical_queries_executed'] == 10
    assert report['raw_identity_access'] == report['reporting_writes'] == 'DENIED'
    assert report['postgres_source_report_reconciliation'] == 'MATCH'


def test_query_benchmark_checks_equal_results():
    path = Path('reports/current/query_benchmark.json')
    if not path.exists():
        pytest.skip('Run PostgreSQL benchmark first')
    report = json.loads(path.read_text())
    assert report['results_equal']
    assert len(report['before_plans']) == len(report['after_plans']) == 7


def test_overlapping_pipeline_run_rejected(tmp_path, monkeypatch):
    import fcntl
    from src.run_pipeline import run
    monkeypatch.chdir(tmp_path)
    Path('reports').mkdir()
    Path('config').mkdir()
    Path('config/etl_config.yaml').write_text('{}')
    with Path('reports/.pipeline.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(RuntimeError, match='Another pipeline'):
            run()


def test_failed_run_preserves_last_good_report(tmp_path, monkeypatch):
    from src.run_pipeline import run
    monkeypatch.chdir(tmp_path)
    Path('reports/run-good').mkdir(parents=True)
    Path('reports/run-good/sentinel').write_text('last good')
    Path('reports/current').symlink_to('run-good', target_is_directory=True)
    Path('config').mkdir()
    Path('config/etl_config.yaml').write_text('{}')
    def fail(**kwargs):
        raise ValueError('input unavailable')
    monkeypatch.setattr('src.run_pipeline.generate', fail)
    with pytest.raises(ValueError, match='input unavailable'):
        run()
    assert Path('reports/current/sentinel').read_text() == 'last good'
    assert not list(Path('reports').glob('.run-*'))
