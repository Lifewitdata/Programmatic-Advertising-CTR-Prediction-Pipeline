"""Package current aggregate CSVs and a Tableau workbook.

XML structure follows Tableau's document-api-python worksheet examples.
This is structural packaging, not a substitute for Tableau Desktop visual QA.
"""
from pathlib import Path
import copy
import xml.etree.ElementTree as E
import zipfile
import pandas as pd


def build(output='dashboards/Advertising_Current_Demo.twbx'):
    root = E.Element('workbook', {'version': '18.1', 'source-platform': 'win'})
    sources = E.SubElement(root, 'datasources')
    ds = E.SubElement(sources, 'datasource', {'name': 'campaigns', 'caption': 'Synthetic advertising observations', 'inline': 'true', 'version': '18.1'})
    connection = E.SubElement(ds, 'connection', {'class': 'textscan', 'directory': 'Data',
        'filename': 'campaign_daily.csv', 'header': 'yes', 'separator': ',', 'format': 'utf-8'})
    E.SubElement(connection, 'relation', {'name': 'campaign_daily.csv', 'table': '[campaign_daily.csv]', 'type': 'table'})
    columns = [('event_date', 'date', 'dimension', 'ordinal'),
        ('advertiser_id', 'integer', 'dimension', 'nominal'), ('campaign_id', 'integer', 'dimension', 'nominal'),
        ('device', 'string', 'dimension', 'nominal'), ('country', 'string', 'dimension', 'nominal'),
        ('impressions', 'integer', 'measure', 'quantitative'), ('clicks', 'integer', 'measure', 'quantitative')]
    for name, datatype, role, kind in columns:
        E.SubElement(ds, 'column', {'name': f'[{name}]', 'datatype': datatype, 'role': role, 'type': kind})
    ctr = E.SubElement(ds, 'column', {'name': '[CTR]', 'caption': 'CTR', 'datatype': 'real', 'role': 'measure', 'type': 'quantitative'})
    E.SubElement(ctr, 'calculation', {'class': 'tableau', 'formula': 'IF SUM([impressions]) > 0 THEN SUM([clicks]) / SUM([impressions]) END'})
    E.SubElement(ctr, 'default-format', {'format': 'p2%'})
    worksheets = E.SubElement(root, 'worksheets')
    definitions = [
        ('CTR by device - synthetic', 'device', 'CTR', 'User'),
        ('Impressions by advertiser - synthetic', 'advertiser_id', 'impressions', 'Sum'),
        ('Clicks by campaign - synthetic', 'campaign_id', 'clicks', 'Sum'),
    ]
    colmap = {c.get('name'): c for c in ds.findall('column')}
    for title, dimension, measure, derivation in definitions:
        worksheet = E.SubElement(worksheets, 'worksheet', {'name': title})
        table = E.SubElement(worksheet, 'table')
        view = E.SubElement(table, 'view')
        view_sources = E.SubElement(view, 'datasources')
        E.SubElement(view_sources, 'datasource', {'caption': ds.get('caption'), 'name': 'campaigns'})
        deps = E.SubElement(view, 'datasource-dependencies', {'datasource': 'campaigns'})
        for field in [dimension, measure]:
            deps.append(copy.deepcopy(colmap[f'[{field}]']))
        di, mi = f'[none:{dimension}:nk]', f'[{derivation.lower()}:{measure}:qk]'
        E.SubElement(deps, 'column-instance', {'column': f'[{dimension}]', 'derivation': 'None', 'name': di, 'pivot': 'key', 'type': 'nominal'})
        E.SubElement(deps, 'column-instance', {'column': f'[{measure}]', 'derivation': derivation, 'name': mi, 'pivot': 'key', 'type': 'quantitative'})
        E.SubElement(view, 'aggregation', {'value': 'true'})
        E.SubElement(table, 'style')
        pane = E.SubElement(E.SubElement(table, 'panes'), 'pane')
        E.SubElement(E.SubElement(pane, 'view'), 'breakdown', {'value': 'auto'})
        E.SubElement(pane, 'mark', {'class': 'Bar'})
        E.SubElement(table, 'rows').text = '[campaigns].' + di
        E.SubElement(table, 'cols').text = '[campaigns].' + mi
    dashboard = E.SubElement(E.SubElement(root, 'dashboards'), 'dashboard', {'name': 'Advertising performance - synthetic demo'})
    E.SubElement(dashboard, 'style')
    E.SubElement(dashboard, 'size', {'maxheight': '850', 'maxwidth': '1200', 'minheight': '850', 'minwidth': '1200'})
    zones = E.SubElement(dashboard, 'zones')
    for i, (title, _, _, _) in enumerate(definitions):
        E.SubElement(zones, 'zone', {'id': str(i+1), 'name': title, 'x': '1000',
            'y': str(1000 + i*33000), 'w': '98000', 'h': '32000'})
    windows = E.SubElement(root, 'windows')
    E.SubElement(windows, 'window', {'class': 'dashboard', 'name': dashboard.get('name')})
    payload = E.tostring(root, encoding='utf-8', xml_declaration=True)
    E.fromstring(payload)
    output = Path(output)
    output.parent.mkdir(exist_ok=True)
    data = pd.read_csv('reports/current/campaign_daily.csv').drop(columns=['ctr', 'scope']).to_csv(index=False)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('Advertising_Current_Demo.twb', payload)
        z.writestr('Data/campaign_daily.csv', data)
    with zipfile.ZipFile(output) as z:
        xml = E.fromstring(z.read('Advertising_Current_Demo.twb'))
        assert len(xml.findall('./worksheets/worksheet')) == 3
        assert len(xml.findall('./dashboards/dashboard/zones/zone')) == 3
        actual = pd.read_csv(z.open('Data/campaign_daily.csv'))
        assert actual.impressions.sum() == pd.read_csv('reports/current/reconciliation.csv').iloc[0].source_total
    return output


if __name__ == '__main__':
    print(build())
