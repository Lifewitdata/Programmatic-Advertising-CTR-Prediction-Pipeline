// Actual PostgreSQL execution via PGlite WASM. Not a server latency benchmark.
import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
import { PGlite } from '@electric-sql/pglite';

process.on('uncaughtException', error => { console.error(error.message); process.exit(1); });
const db = new PGlite();
const data = JSON.parse(await fs.readFile('data/processed/postgres_input.json', 'utf8'));
await db.exec(await fs.readFile('sql/schema.sql', 'utf8'));
for (const name of ['users', 'advertisers', 'campaigns', 'creatives', 'impressions', 'clicks']) {
  const rows = data[name];
  if (!rows.length) continue;
  const cols = Object.keys(rows[0]);
  for (let offset = 0; offset < rows.length; offset += 300) {
    const batch = rows.slice(offset, offset + 300);
    const params = batch.flatMap(r => cols.map(c => r[c]));
    const tuples = batch.map((_, i) => '(' + cols.map((_, j) => '$' + (i * cols.length + j + 1)).join(',') + ')');
    await db.query(`INSERT INTO ${name} (${cols.map(c => '"' + c + '"').join(',')}) VALUES ${tuples.join(',')}`, params);
  }
}
// Every committed analytical query must parse and execute against generated data.
const analyses = await db.exec(await fs.readFile('sql/ctr_analysis_queries.sql', 'utf8'));
assert.equal(analyses.length, 10);
// Display thresholds must not change the advertiser-wide blended denominator.
if (analyses[9].rows.length) {
  const row = analyses[9].rows[0];
  const direct = (await db.query(`SELECT 100.0 * count(cl.click_id) / count(i.impression_id) AS ctr
    FROM impressions i JOIN advertisers a ON a.advertiser_id=i.advertiser_id
    LEFT JOIN clicks cl ON cl.impression_id=i.impression_id
    WHERE a.advertiser_name=$1`, [row.advertiser_name])).rows[0].ctr;
  assert(Math.abs(Number(row.advertiser_blended_ctr_pct)-Number(direct)) < 0.000051);
}
const checks = { analytical_queries_executed: analyses.length };
await db.exec(await fs.readFile('sql/reporting_security.sql', 'utf8'));
for (const r of data.campaign_daily) {
  await db.query('INSERT INTO ctr_reporting.campaign_daily VALUES ($1,$2,$3,$4,$5,$6,$7)', Object.values(r));
}
for (const id of [1, 2]) {
  await db.exec(`SET ROLE advertiser_${id}`);
  const rows = (await db.query('SELECT DISTINCT advertiser_id FROM ctr_reporting.campaign_daily')).rows;
  assert.deepEqual(rows.map(r => Number(r.advertiser_id)), [id]);
  assert.equal((await db.query('SELECT count(*) AS n FROM ctr_reporting.campaign_daily WHERE advertiser_id <> $1', [id])).rows[0].n, 0);
  let denied = false;
  try { await db.query('SELECT * FROM public.users LIMIT 1'); } catch { denied = true; }
  assert(denied, 'Reporting role must not see user identities');
  denied = false;
  try { await db.query('DELETE FROM ctr_reporting.campaign_daily'); } catch { denied = true; }
  assert(denied, 'Reporting role must not write');
  await db.exec('RESET ROLE');
}
checks.advertiser_isolation = 'PASS for advertiser_1 and advertiser_2';
checks.raw_identity_access = 'DENIED';
checks.reporting_writes = 'DENIED';
const sqlTotal = (await db.query('SELECT sum(impressions) AS impressions, sum(clicks) AS clicks FROM ctr_reporting.campaign_daily')).rows[0];
assert.equal(Number(sqlTotal.impressions), data.impressions.length);
assert.equal(Number(sqlTotal.clicks), data.clicks.length);
checks.postgres_source_report_reconciliation = 'MATCH';

// Isolated fixture gives a reproducible before/after comparison without changing
// application indexes. The selective date/campaign filter is held constant.
await db.exec('CREATE TABLE benchmark_impressions AS SELECT * FROM impressions; ANALYZE benchmark_impressions;');
const query = `SELECT count(*) AS impressions FROM benchmark_impressions
               WHERE campaign_id = 1 AND "timestamp" >= TIMESTAMP '2025-11-01'
               AND "timestamp" < TIMESTAMP '2025-11-08'`;
const baselineRows = (await db.query(query)).rows;
async function plans() {
  await db.query(query); await db.query(query); // warm each condition equally
  const result = [];
  for (let i = 0; i < 7; i++) {
    const plan = (await db.query('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + query)).rows[0]['QUERY PLAN'][0];
    result.push(plan);
  }
  return result;
}
const before = await plans();
await db.exec('CREATE INDEX benchmark_campaign_time ON benchmark_impressions (campaign_id, "timestamp"); ANALYZE benchmark_impressions;');
const after = await plans();
assert.deepEqual((await db.query(query)).rows, baselineRows);
const median = xs => [...xs].sort((a,b) => a-b)[Math.floor(xs.length/2)];
const benchmark = {
  engine: (await db.query('SELECT version() AS version')).rows[0].version,
  environment: `PGlite single-process WASM in Node; synthetic ${data.impressions.length} rows, not production server latency`,
  warmups_per_condition: 2, repeats_per_condition: 7,
  row_count: data.impressions.length, query, results_equal: true,
  before_median_ms: median(before.map(p => p['Execution Time'])),
  after_median_ms: median(after.map(p => p['Execution Time'])), before_plans: before, after_plans: after,
};
await fs.writeFile('reports/current/postgres_verification.json', JSON.stringify(checks, null, 2) + '\n');
await fs.writeFile('reports/current/query_benchmark.json', JSON.stringify(benchmark, null, 2) + '\n');
console.log(JSON.stringify({ ...checks, before_ms: benchmark.before_median_ms, after_ms: benchmark.after_median_ms }, null, 2));
await db.close();
