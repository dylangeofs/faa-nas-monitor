#!/usr/bin/env python3
"""FAA NAS status -> ntfy push. Python 3.10+, no dependencies."""
import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET

FEED = 'https://nasstatus.faa.gov/api/airport-status-information'
SITE = 'https://nasstatus.faa.gov/'
STATE = Path(os.environ.get('FAA_STATE_FILE', 'faa_state.json'))
TOPIC = os.environ.get('NTFY_TOPIC', '').strip()
KINDS = {'ground_stop_list': 'Ground Stop', 'ground_delay_list': 'Ground Delay Program',
         'ground_delay_program_list': 'Ground Delay Program', 'airport_closure_list': 'Airport Closure',
         'arrival_departure_delay_list': 'Arrival/Departure Delay',
         'arrival_delay_list': 'Arrival Delay', 'departure_delay_list': 'Departure Delay'}

def tag(el):
    return re.sub(r'[^a-z0-9]+', '_', el.tag.rsplit('}', 1)[-1].lower()).strip('_')

def clean(s):
    return ' '.join(str(s).split())

def parse_events(raw):
    root = ET.fromstring(raw)
    if tag(root) != 'airport_status_information':
        raise ValueError('Unexpected FAA XML root; previous state retained')
    events = {}
    recognized = False
    for delay in root:
        if tag(delay) != 'delay_type':
            continue
        for group in delay:
            kind = KINDS.get(tag(group))
            if not kind:
                continue
            recognized = True
            for entry in group:
                if tag(entry) not in ('airport', 'ground_stop', 'ground_delay', 'airport_closure', 'delay'):
                    continue
                fields = {}
                for leaf in entry.iter():
                    if leaf is entry or len(leaf):
                        continue
                    value = clean(leaf.text or '')
                    if value and tag(leaf) not in ('update_time', 'last_updated', 'updated'):
                        fields[tag(leaf)] = value
                airport = next((fields.get(k) for k in ('arpt', 'airport', 'airport_code', 'iata') if fields.get(k)), 'NAS')
                airport = airport.upper()
                # Stable identity for a type/airport. Distinct closures at same airport
                # are differentiated by start and reason; changing end time is an update.
                ident = fields.get('advisory_number') or fields.get('advisory') or fields.get('id')
                if not ident and kind == 'Airport Closure':
                    ident = clean(fields.get('reason', '') + '|' + fields.get('start', ''))
                key = '|'.join((airport, kind, ident or ''))
                if key in events:
                    key += '|' + hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()[:12]
                events[key] = {'airport': airport, 'type': kind, 'fields': fields}
    # Empty feed is normal, but a changed schema must not trigger mass ENDED alerts.
    if not recognized and any(tag(e) == 'delay_type' for e in root.iter()):
        raise ValueError('Unrecognized FAA event schema; previous state retained')
    return events

def fetch():
    request = urllib.request.Request(FEED, headers={'User-Agent': 'FAA-NAS-Monitor/2.0', 'Accept': 'application/xml,text/xml'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()

def notify(title, message, priority=3):
    if not TOPIC:
        raise ValueError('Missing NTFY_TOPIC')
    payload = json.dumps({'topic': TOPIC, 'title': title[:100], 'message': message[:3500],
                          'priority': priority, 'click': SITE}).encode()
    req = urllib.request.Request('https://ntfy.sh/', data=payload,
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=20) as response:
        response.read()

def describe(item):
    fields = item['fields']
    keys = ('reason', 'start', 'end', 'reopen', 'avg', 'average', 'min', 'max', 'trend', 'status', 'message')
    chosen = [(k, fields[k]) for k in keys if k in fields]
    if not chosen:
        chosen = [(k, v) for k, v in fields.items() if k not in ('arpt', 'airport')][:8]
    return '\n'.join(f'{k.replace("_", " ").title()}: {v}' for k, v in chosen)[:2400] or 'See FAA NAS Status for details.'

def save(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_name(STATE.name + '.tmp')
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(STATE)

def check_once():
    current = parse_events(fetch())
    if not STATE.exists():
        save(current)
        logging.info('Baseline established (%d active events); no alerts sent', len(current))
        return
    previous = json.loads(STATE.read_text(encoding='utf-8'))
    changes = []
    for key, item in current.items():
        if key not in previous:
            changes.append(('NEW', item, 4))
        elif item != previous[key]:
            changes.append(('UPDATED', item, 3))
    for key, item in previous.items():
        if key not in current:
            changes.append(('ENDED', item, 3))
    for action, item, priority in changes:
        notify(f'{action}: {item["airport"]} {item["type"]}', describe(item), priority)
        logging.info('%s: %s %s', action, item['airport'], item['type'])
    save(current)
    logging.info('Checked %d active events; %d changes', len(current), len(changes))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test-push', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if not TOPIC:
        parser.error('Set NTFY_TOPIC first')
    if args.test_push:
        notify('FAA NAS Monitor Test', 'Your iPhone FAA NAS alerts are connected.')
    else:
        check_once()

if __name__ == '__main__':
    main()
