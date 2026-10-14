#!/usr/bin/env python3
"""Veille Hérault (34) — projets-environnement.gouv.fr. Bibliothèque standard Python."""
import json
import os
import re
import smtplib
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, ElementTree

BASE = 'https://www.projets-environnement.gouv.fr'
API = BASE + '/api/explore/v2.1/catalog/datasets/projets-environnement-diffusion/records'
ROOT = Path(__file__).resolve().parent
STATE = ROOT / 'state.json'
FEED = ROOT / 'docs' / 'herault.xml'
LIMIT = 100
MAX_PAGES = 200  # garde-fou ; ne jamais accepter un balayage tronqué

MONTHS = {'janvier':1,'février':2,'fevrier':2,'mars':3,'avril':4,'mai':5,'juin':6,
          'juillet':7,'août':8,'aout':8,'septembre':9,'octobre':10,
          'novembre':11,'décembre':12,'decembre':12}

def norm(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip()

def get(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'JournalistEnvironmentWatch/1.1 (public data)',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response)

def records():
    offset = 0
    expected = None
    while True:
        if offset >= MAX_PAGES * LIMIT:
            raise RuntimeError('Limite de pagination atteinte : scan incomplet')
        url = API + '?' + urllib.parse.urlencode({'limit': LIMIT, 'offset': offset})
        result = get(url)
        batch = result.get('results')
        total = result.get('total_count')
        if not isinstance(batch, list) or not isinstance(total, int):
            raise ValueError('Réponse API incomplète ou inattendue')
        if expected is None:
            expected = total
        if total != expected:
            raise RuntimeError('Le nombre de dossiers a changé pendant le balayage ; relancer')
        if not batch and offset < total:
            raise RuntimeError('Page vide avant la fin du balayage')
        yield from batch
        offset += len(batch)
        if offset >= total:
            break

def selected(row):
    fields = row.get('fields', row)
    if not isinstance(fields, dict):
        return False
    location = norm(fields.get('dc_location')).lower()
    return bool(re.search(r'(?<!\d)34\s*[-–—]\s*h[ée]rault\b', location))

def first(fields, *names):
    for name in names:
        for key, value in fields.items():
            if key.lower() == name.lower() and value not in (None, ''):
                return norm(value)
    return ''

def parse_date(value):
    """Renvoie une date UTC pour ISO ou date française, sinon None.
    N'invente jamais une date en utilisant la date de génération du flux.
    """
    value = norm(value)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        parsed = None
    if parsed is None:
        match = re.fullmatch(r'(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{4})(?:\s+(\d{1,2}):(\d{2}))?', value)
        if not match or match.group(2).lower() not in MONTHS:
            return None
        try:
            parsed = datetime(int(match.group(3)), MONTHS[match.group(2).lower()],
                              int(match.group(1)), int(match.group(4) or 0),
                              int(match.group(5) or 0))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed = parsed.astimezone(timezone.utc)
    if not (datetime(1990,1,1,tzinfo=timezone.utc) <= parsed <= datetime.now(timezone.utc)+timedelta(days=1)):
        return None
    return parsed

def convert(row):
    fields = row.get('fields', row)
    rid = first(fields, 'recordsid', 'recordsid2') or norm(row.get('recordid'))
    title = first(fields, 'dc_title', 'titre', 'title') or 'Projet environnemental'
    town = first(fields, 'location_ville', 'commune', 'ville')
    description = first(fields, 'descriptif_du_projet', 'dc_description_abstract', 'description')
    # dc_date = « Date de diffusion » dans le catalogue public.
    # date_avis_publication est la date de l'avis, événement différent.
    diffusion_raw = first(fields, 'dc_date', 'date_de_diffusion')
    avis_raw = first(fields, 'date_avis_publication')
    diffusion = parse_date(diffusion_raw)
    avis = parse_date(avis_raw)
    link = (BASE + '/page/fiche/?q=' + urllib.parse.quote('recordsid:' + rid)) if rid else BASE
    return {
        'id': rid or title+'|'+town, 'title': title, 'town': town,
        'date': diffusion.date().isoformat() if diffusion else '',
        'date_type': 'diffusion' if diffusion else 'inconnue',
        'avis_date': avis.date().isoformat() if avis else '',
        'description': description[:1000], 'link': link,
    }

def write_feed(entries):
    FEED.parent.mkdir(parents=True, exist_ok=True)
    rss = Element('rss', version='2.0')
    channel = SubElement(rss, 'channel')
    metadata = {
        'title': 'Veille projets environnementaux — Hérault (34)',
        'link': BASE,
        'description': 'Projets du 34 dans le jeu officiel projets-environnement-diffusion ; source distincte du portail des avis environnementaux.',
        'language': 'fr-fr',
        'lastBuildDate': format_datetime(datetime.now(timezone.utc)),
    }
    for key, value in metadata.items():
        SubElement(channel, key).text = value
    # Classement par date de diffusion disponible, non par date de génération.
    sorted_entries = sorted(entries, key=lambda e: (e.get('date') or '', e.get('id') or ''), reverse=True)
    for entry in sorted_entries[:300]:
        item = SubElement(channel, 'item')
        SubElement(item, 'title').text = entry['title'] + (' — '+entry['town'] if entry.get('town') else '')
        SubElement(item, 'link').text = entry['link']
        SubElement(item, 'guid', isPermaLink='false').text = entry['id']
        desc = entry.get('description') or 'Fiche projet environnemental'
        if entry.get('avis_date'):
            desc += '\nDate de publication de l’avis : ' + entry['avis_date']
        SubElement(item, 'description').text = desc
        date = parse_date(entry.get('date'))
        if date:
            SubElement(item, 'pubDate').text = format_datetime(date)
    ElementTree(rss).write(FEED, encoding='utf-8', xml_declaration=True)

def email_alert(items):
    required = ('SMTP_HOST','SMTP_USER','SMTP_PASSWORD','ALERT_TO')
    if not all(os.getenv(key) for key in required):
        raise RuntimeError('Secrets SMTP manquants : impossible de garantir les alertes')
    message = EmailMessage()
    message['Subject'] = f'Veille environnementale 34 — {len(items)} nouveau(x) dossier(s)'
    message['From'] = os.environ['SMTP_USER']
    message['To'] = os.environ['ALERT_TO']
    message.set_content('\n\n'.join(
        f"{entry['title']} | {entry.get('town','')}\n"
        f"Date de diffusion : {entry.get('date') or 'non renseignée'}\n"
        f"Date de l’avis : {entry.get('avis_date') or 'non renseignée'}\n"
        f"{entry['link']}\n{entry.get('description','')}" for entry in items
    ))
    with smtplib.SMTP_SSL(os.environ['SMTP_HOST'], int(os.getenv('SMTP_PORT','465')),
                          timeout=30, context=ssl.create_default_context()) as smtp:
        smtp.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
        smtp.send_message(message)

def main():
    rows = list(records())
    if not rows:
        raise RuntimeError('Aucun dossier dans l’API : contrôle non valide')
    matched = [convert(row) for row in rows if selected(row)]
    if not matched:
        raise RuntimeError('Aucun dossier du 34 : vérifier le schéma et le filtrage')
    if len({entry['id'] for entry in matched}) != len(matched):
        raise RuntimeError('Identifiants de dossiers en double : contrôle non valide')
    initial = not STATE.exists()
    existing = json.loads(STATE.read_text(encoding='utf-8')) if not initial else {'seen':[], 'items':[]}
    known = set(existing['seen'])
    fresh = [entry for entry in matched if entry['id'] not in known]
    entries = {entry['id']: entry for entry in existing['items']}
    for entry in matched:
        entries[entry['id']] = entry
    values = list(entries.values())
    # L'envoi précède la mise à jour du fichier d'état pour conserver la possibilité de retenter.
    if fresh and not initial:
        email_alert(fresh)
    write_feed(values)
    STATE.write_text(json.dumps({'seen': sorted(known | {entry['id'] for entry in matched}),
                                 'items': values}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Contrôle terminé : {len(rows)} dossiers nationaux, {len(matched)} dossiers 34, '
          f'{len(fresh)} nouveaux, premier lancement={initial}')
    print('Ce programme détecte les NOUVEAUX identifiants, pas les modifications des dossiers existants.')

if __name__ == '__main__':
    main()
