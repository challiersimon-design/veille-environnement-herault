#!/usr/bin/env python3
"""Veille environnementale Hérault. Python standard library only."""
import json, os, re, ssl, smtplib, urllib.parse, urllib.request
from email.message import EmailMessage
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree
from email.utils import format_datetime

BASE='https://www.projets-environnement.gouv.fr'
API=BASE+'/api/explore/v2.1/catalog/datasets/projets-environnement-diffusion/records'
ROOT=Path(__file__).parent
STATE=ROOT/'state.json'
FEED=ROOT/'docs'/'herault.xml'
LIMIT=100
MAX_PAGES=70

def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'JournalistEnvironmentWatch/1.0 (+public data)','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=45) as r: return json.load(r)

def records():
    # Full pagination: don't silently interpret partial scans as no news.
    offset=0
    while True:
        u=API+'?'+urllib.parse.urlencode({'limit':LIMIT,'offset':offset})
        j=get(u)
        batch=j.get('results')
        if not isinstance(batch,list): raise ValueError('Unexpected API format')
        yield from batch
        offset += len(batch)
        if not batch or offset >= j.get('total_count',offset): break
        if offset >= MAX_PAGES*LIMIT: raise RuntimeError('Pagination limit reached: incomplete scan')

def norm(s):
    return re.sub(r'\s+',' ',str(s or '')).strip()


def selected(row):
    f = row.get('fields', row)
    if not isinstance(f, dict):
        return False
    location = norm(f.get('dc_location')).lower()
    return bool(re.search(
        r'(?<!\d)34\s*[-–—]\s*h[ée]rault\b',
        location
    ))

def first(f,*names):
    for name in names:
        for k,v in f.items():
            if k.lower()==name.lower() and v: return norm(v)
    return ''

def convert(row):
    f=row.get('fields',row)
    rid=first(f,'recordsid','recordsid2') or norm(row.get('recordid'))
    title=first(f,'dc_title','titre','title','dc.title') or 'Projet environnemental'
    town=first(f,'location','location_ville','commune','ville','dc_coverage')
    date=first(f,'date_de_diffusion','dc_date_issued','date_avis_publication','dateavispublication')
    descr=first(f,'descriptif_du_projet','dc_description_abstract','description','descriptif')
    link=(BASE+'/page/fiche/?q='+urllib.parse.quote('recordsid:'+rid)) if rid else BASE+'/explore/dataset/projets-environnement-diffusion/'
    return {'id':rid or norm(row.get('recordid')) or title+'|'+town,'title':title,'town':town,'date':date,'description':descr[:1000], 'link':link}

def write_feed(entries):
    FEED.parent.mkdir(exist_ok=True)
    rss=Element('rss',version='2.0')
    ch=SubElement(rss,'channel')
    for k,v in [('title','Veille projets environnementaux — Hérault (34)'),('link',BASE),('description','Dossiers du département 34 repérés dans le jeu de données officiel projets-environnement-diffusion. Source distincte du portail des avis environnementaux.'),('language','fr-fr'),('lastBuildDate',format_datetime(datetime.now(timezone.utc)))]: SubElement(ch,k).text=v
    for e in entries[-300:][::-1]:
        item=SubElement(ch,'item')
        for k,v in [('title',e['title']+' — '+e['town'] if e['town'] else e['title']),('link',e['link']),('guid',e['id']),('description',e['description'] or e['date'] or 'Nouvelle fiche projet')]: SubElement(item,k).text=v
        SubElement(item,'pubDate').text=format_datetime(datetime.now(timezone.utc))
    ElementTree(rss).write(FEED,encoding='utf-8',xml_declaration=True)

def email_alert(items):
    required=['SMTP_HOST','SMTP_USER','SMTP_PASSWORD','ALERT_TO']
    if not all(os.getenv(k) for k in required):
        print('Email not configured; RSS updated.');return
    msg=EmailMessage()
    msg['Subject']=f'Veille environnementale 34 — {len(items)} nouveau(x) dossier(s)'
    msg['From']=os.environ['SMTP_USER'];msg['To']=os.environ['ALERT_TO']
    msg.set_content('\n\n'.join(f"{i['title']} | {i['town']} | {i['date']}\n{i['link']}\n{i['description']}" for i in items))
    with smtplib.SMTP_SSL(os.environ['SMTP_HOST'],int(os.getenv('SMTP_PORT','465')),timeout=30,context=ssl.create_default_context()) as s:
        s.login(os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD']);s.send_message(msg)

def main():
    # Fail BEFORE changing state if API down or malformed.
    
    rows = list(records())

    if not rows: raise RuntimeError('API returned no records; refusing to claim zero new files')
    matched=[convert(r) for r in rows if selected(r)]
    if not matched: raise RuntimeError('No 34 records found: check schema, cannot infer no updates')
    existing=json.loads(STATE.read_text()) if STATE.exists() else {'seen':[],'items':[]}
    known=set(existing['seen'])
    fresh=[r for r in matched if r['id'] not in known]
    # First run is a baseline; don't send hundreds of historical alerts.
    initial=not STATE.exists()
    entries={r['id']:r for r in existing['items']}
    for r in matched: entries[r['id']]=r
    values=list(entries.values())
    write_feed(values)
    if fresh and not initial: email_alert(fresh)
    # Commit state only AFTER alert succeeds, to permit retry on email error.
    STATE.write_text(json.dumps({'seen':sorted(known|{r['id'] for r in matched}),'items':values},ensure_ascii=False,indent=2))
    print(f'Checked {len(rows)} records, {len(matched)} matching 34, {len(fresh)} unseen; initial={initial}')

if __name__=='__main__':main()
