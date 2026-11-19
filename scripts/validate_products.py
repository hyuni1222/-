"""Fail publication if a product claim loses its source or example conditions."""
from datetime import date
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]

def validate_catalog(data):
    def require(condition,message):
        if not condition:
            raise ValueError(message)
    require(data.get('schema_version')==1,'Unsupported product schema')
    asof=date.fromisoformat(data['research_date'])
    require(len(data['insurers'])==len(set(data['insurers'])),'Duplicate insurer')
    sources={s['id']:s for s in data['sources']}
    require(len(sources)==len(data['sources']),'Duplicate source ID')
    for source in sources.values():
        if source['url'] is None:
            require(bool(source.get('link_note')),'Missing nonpublic source note')
            continue
        url=urlsplit(source['url'])
        require(url.scheme in ('https','http') and bool(url.netloc) and not url.username and not url.password,'Unsafe source URL')
    ids=set()
    example_ids=set()
    for product in data['products']:
        require(product['id'] not in ids,'Duplicate product ID')
        ids.add(product['id'])
        require(product['insurer'] in data['insurers'],'Unknown insurer')
        require(product['category'] in ('종신','연금','정기'),'Unknown category')
        require(product['channel_status']=='ga_material_found','Unconfirmed GA product in main catalog')
        require(bool(product['version']) and bool(product['pay_basis']) and bool(product['pays']),'Missing version or payment scope')
        require(product['currency'] in ('KRW','USD'),'Missing currency')
        require(bool(product['source_ids']) and set(product['source_ids'])<=sources.keys(),'Missing product source')
        for example in product['examples']:
            require(example['id'] not in example_ids,'Duplicate example ID')
            example_ids.add(example['id'])
            source=sources.get(example['source_id'])
            require(source is not None and source['kind']=='공식 상품요약서','Refund percentage requires official summary')
            require(example['source_id'] in product['source_ids'],'Example source must belong to product')
            require(example['currency']==product['currency'],'Example currency mismatch')
            for field in ('age','amount','form','interest','note','type'):
                require(bool(example[field]),'Missing refund example condition: '+field)
            require(example['version_status'] in ('current_document','version_unconfirmed'),'Unknown example status')
            require(date.fromisoformat(example['document_date'])<=asof,'Future document date')
            require(date.fromisoformat(example['source_checked_on'])<=asof,'Future source check')
            require(example['rate10'] is not None or example['rate15'] is not None,'Empty refund example')
            for field in ('rate10','rate15'):
                value=example[field]
                require(value is None or (type(value) in (int,float) and 0<=value<=10),'Invalid refund percentage')
            if example['version_status']=='current_document':
                checked=example.get('version_checked_on')
                current_source=sources.get(example.get('version_source_id'))
                require(bool(checked) and date.fromisoformat(checked)<=asof,'Missing version-check date')
                require(current_source is not None and current_source['kind'].startswith('공식'),'Missing current-version evidence')
    for pending in data['pending']:
        require(pending['id'] not in ids,'Pending product leaked into catalog')
        require(pending['insurer'] in data['insurers'] and bool(pending['reason']),'Missing pending reason')
    return {'products':len(ids),'examples':len(example_ids),'pending':len(data['pending'])}

if __name__=='__main__':
    data=json.loads((ROOT/'data/products.json').read_text())
    print(json.dumps(validate_catalog(data)))
