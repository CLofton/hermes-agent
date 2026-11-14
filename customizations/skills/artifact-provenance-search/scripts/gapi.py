#!/usr/bin/env python3
"""Minimal Gmail + Drive retrieval over the Google REST API.

Use when no wrapper ($GAPI, drive helper) is on PATH, or when you want the calls
inline in one process (attachment tokens are single-shot, so fetching a message
and downloading its attachment must happen in the same run).

Auth: ~/.hermes/google_token.json -> ["token"]. On 401, run the google-workspace
setup.py --check under the Hermes venv python to refresh the file, then retry.

Usage:
  gapi.py gsearch 'QUERY' [MAX]        Gmail search -> id | date | from | subject | attachment names
  gapi.py gget ID                      Headers + plain-text body + attachment names
  gapi.py gatt ID [OUTDIR]            Download every attachment of ID (default .)
  gapi.py glabels ID                   Which labels a message carries (archive split)
  gapi.py dsearch 'QUERY' [MAX]        Drive search (name/fullText/trashed/parents)
  gapi.py dls FOLDER_ID                List a folder's children
  gapi.py dexport ID [MIME]            Native Doc/Sheet/Slide -> text (default text/plain)
  gapi.py dmedia ID OUT                Binary download (PDF, xlsx, images...)
"""
import base64, json, os, sys, urllib.parse, urllib.request

TOKEN_PATH = os.path.expanduser('~/.hermes/google_token.json')
H = {'Authorization': 'Bearer ' + json.load(open(TOKEN_PATH))['token']}
GMAIL = 'https://gmail.googleapis.com/gmail/v1/users/me'
DRIVE = 'https://www.googleapis.com/drive/v3/files'


def call(url, **params):
    if params:
        url += '?' + urllib.parse.urlencode(params)
    try:
        return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=120))
    except urllib.error.HTTPError as e:
        raise SystemExit(f'HTTP {e.code}: {e.read().decode()[:400]}')


def raw(url):
    try:
        return urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=180).read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f'HTTP {e.code}: {e.read().decode()[:400]}')


def headers(msg):
    return {h['name'].lower(): h['value'] for h in msg['payload'].get('headers', [])}


def walk(part, out):
    """Recurse: attachments are nested, and inline parts put the id in body."""
    fn, bid = part.get('filename'), part.get('body', {}).get('attachmentId')
    if fn and bid:
        out.append((fn, bid))
    for p in part.get('parts') or []:
        walk(p, out)


def text_of(payload):
    chunks = []
    def rec(p):
        if p.get('mimeType') == 'text/plain' and p.get('body', {}).get('data'):
            chunks.append(base64.urlsafe_b64decode(p['body']['data'] + '==').decode('utf-8', 'ignore'))
        for c in p.get('parts') or []:
            rec(c)
    rec(payload)
    return ''.join(chunks)


def main(argv):
    if len(argv) < 2:
        raise SystemExit(__doc__)
    cmd, args = argv[1], argv[2:]

    if cmd == 'gsearch':
        res = call(f'{GMAIL}/messages', q=args[0], maxResults=int(args[1]) if len(args) > 1 else 20)
        msgs = res.get('messages', [])
        print(f'# {len(msgs)} hits (resultSizeEstimate={res.get("resultSizeEstimate")} is unreliable)')
        for m in msgs:
            d = call(f'{GMAIL}/messages/{m["id"]}', format='full')  # metadata omits headers
            h = headers(d)
            atts = []
            walk(d['payload'], atts)
            print(' | '.join([m['id'], h.get('date', '')[:31], h.get('from', '')[:40],
                              h.get('subject', '')[:70], ';'.join(a for a, _ in atts)[:60]]))

    elif cmd == 'gget':
        d = call(f'{GMAIL}/messages/{args[0]}', format='full')
        h = headers(d)
        atts = []
        walk(d['payload'], atts)
        print(json.dumps({k: h.get(k) for k in ('date', 'from', 'to', 'cc', 'subject')}, indent=1))
        print('ATTACHMENTS:', [a for a, _ in atts])
        print('---')
        print(text_of(d['payload'])[:6000])

    elif cmd == 'gatt':
        mid = args[0]
        outdir = args[1] if len(args) > 1 else '.'
        d = call(f'{GMAIL}/messages/{mid}', format='full')  # same run: tokens are single-shot
        atts = []
        walk(d['payload'], atts)
        os.makedirs(outdir, exist_ok=True)
        for fn, aid in atts:
            data = call(f'{GMAIL}/messages/{mid}/attachments/{urllib.parse.quote(aid, safe="")}')
            path = os.path.join(outdir, os.path.basename(fn))
            open(path, 'wb').write(base64.urlsafe_b64decode(data['data'] + '=='))
            print(path, os.path.getsize(path))

    elif cmd == 'glabels':
        d = call(f'{GMAIL}/messages/{args[0]}', format='minimal')
        labs = d.get('labelIds', [])
        archived = not ({'INBOX', 'TRASH', 'SPAM', 'CHAT'} & set(labs))
        print(json.dumps({'labelIds': labs, 'archived': archived}))

    elif cmd == 'dsearch':
        res = call(DRIVE, q=args[0], pageSize=int(args[1]) if len(args) > 1 else 25,
                   fields='files(id,name,mimeType,modifiedTime,webViewLink,parents)',
                   supportsAllDrives='true', includeItemsFromAllDrives='true',
                   orderBy='modifiedTime desc')
        for f in res.get('files', []):
            print(f"{f['modifiedTime'][:10]} | {f['name'][:75]} | {f['mimeType']} | {f['id']}")

    elif cmd == 'dls':
        res = call(DRIVE, q=f"'{args[0]}' in parents and trashed=false", pageSize=100,
                   fields='files(id,name,mimeType,modifiedTime)', supportsAllDrives='true',
                   includeItemsFromAllDrives='true', orderBy='modifiedTime desc')
        for f in res.get('files', []):
            print(f"{f['modifiedTime'][:10]} | {f['name'][:75]} | {f['mimeType']} | {f['id']}")

    elif cmd == 'dexport':
        mime = args[1] if len(args) > 1 else 'text/plain'  # alt=media 403s on natives
        print(raw(f'{DRIVE}/{args[0]}/export?mimeType={urllib.parse.quote(mime)}').decode('utf-8', 'ignore'))

    elif cmd == 'dmedia':
        data = raw(f'{DRIVE}/{args[0]}?alt=media&supportsAllDrives=true')
        open(args[1], 'wb').write(data)
        print(args[1], len(data))

    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main(sys.argv)
