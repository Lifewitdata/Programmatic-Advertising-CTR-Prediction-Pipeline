"""Create local JSON inputs for PostgreSQL WASM verification; never publish identities."""
import json
from pathlib import Path
import pandas as pd

tables = {name: pd.read_csv(f'data/raw/{name}.csv').to_dict('records')
          for name in ['users', 'advertisers', 'campaigns', 'creatives', 'impressions', 'clicks']}
tables['campaign_daily'] = pd.read_csv('reports/current/campaign_daily.csv').drop(columns=['ctr', 'scope']).to_dict('records')
Path('data/processed/postgres_input.json').write_text(json.dumps(tables))
