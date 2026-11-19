"""Generate separate article summaries and operational insights for every edition."""
import json
from pathlib import Path
from update_news import ROOT,atomic_json
from editorial import VERSION,daily_analysis


def build(root=ROOT):
    editions={}
    for path in sorted((root/'data/editions').glob('????-??-??.json')):
        edition=json.loads(path.read_text())
        if edition.get('demo'):continue
        editions[edition['date']]={article['id']:daily_analysis(article) for article in edition['articles']}
    latest=json.loads((root/'data/latest.json').read_text())
    editions[latest['date']]={article['id']:daily_analysis(article) for article in latest['articles']}
    result={'version':VERSION,'editions':editions}
    atomic_json(root/'data/daily-analysis.json',result)
    print('Daily analysis:',len(editions),'editions,',sum(len(v) for v in editions.values()),'article insights')
    return result


if __name__=='__main__':build()
