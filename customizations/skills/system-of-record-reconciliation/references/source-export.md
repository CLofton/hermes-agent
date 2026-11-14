# Exporting the complete dataset from a client-rendered app

Phase 1 of any reconciliation: get every row out of the source without a UI crawl. Applies to SPAs backed by a hosted database (Supabase-style) and similar bundles.

## Read the bundle before clicking anything

A page that renders a sign-in wall still ships its API contract in the JS bundle.

```bash
curl -sS -L "$URL" -o index.html
# index.html names the entrypoint, e.g. /assets/index-XXXX.js
curl -sS "https://host/assets/index-XXXX.js" -o app.js
```

Then mine `app.js` for:

- **The backend origin** — `grep -oE 'https://[a-z0-9.-]+\.supabase\.co'`
- **The embedded client key** — `grep -oE 'eyJ[A-Za-z0-9_.-]{60,}'` (JWTs). Decode the middle segment to learn the role: a payload of `{role: 'anon'}` is a client key.
- **Table names** — `grep -oE '\.from\("[a-z0-9_]+"\)' app.js | sort | uniq -c`
- **Column metadata** — the bundle usually carries the display schema (`{key:'field', label:'Field', group:'...'}`). Extract it to get human labels and the app's own column order for free.

## Confirm what the client key can actually read

An `anon` key is often left with permissive row-level security. Test with an exact-count header before assuming you need a login:

```bash
curl -sS "$API/rest/v1/schools?select=*&limit=1" \
  -H "apikey: $KEY" -H "Authorization: Bearer $KEY" \
  -H "Prefer: count=exact" -D - -o /dev/null | grep -i content-range
# Content-Range: 0-0/281   -> readable, 281 rows
```

If a PROTECTED table returns 200 with `Content-Range: */0`, that is row-level security returning zero rows — not an empty table. Distinguish the two or you will report a populated table as empty.

**A client-readable key on internal business data is a finding in its own right.** Report it: the key ships to every browser that loads the page.

## Enumerate hidden tables via PostgREST hints

Requesting an unknown table returns a suggestion naming a real one:

```
GET /rest/v1/tasks  -> 404 {"hint": "Perhaps you meant the table 'public.profiles'"}
```

Probe a wordlist of candidate names and harvest every `Perhaps you meant` value. This recovers views and internal tables the bundle never mentions. GraphQL introspection on the same project usually returns an empty schema for anonymous callers — do not conclude "no schema" from it.

## Get the authenticated token from the browser, never by typing credentials

If protected tables matter, use an already-signed-in browser session: read the client's own persisted session out of `localStorage` (Supabase stores `sb-<ref>-auth-token` as JSON) and reuse its `access_token`.

- Write the token to `~/.hermes/secrets/<name>-token.json` with `chmod 600`; never print it.
- Decode the payload to confirm `role: 'authenticated'` and the expected email before using it.
- Do not sign in on the user's behalf and do not click through an OAuth consent screen — that is the user's authorization decision. Use a session that already exists, or ask.

## Paginate deliberately and assert the total

```python
req = Request(f'{API}/rest/v1/{table}?select=*',
              headers={**auth, 'Range-Unit': 'items', 'Range': f'{start}-{end}'})
```

Page in chunks, stop on a short page, and compare the collected count to the `Content-Range` total. A silent cap at 1,000 rows is the common failure; declaring a total you did not actually page to is the worse one.

## Related data

Computed UI state (alerts, rollups, derived badges) is often **not stored**. Either reproduce the rule definitions from the bundle, or drive the UI and scrape the rendered groups — and say which you did. Scraping a panel means enumerating each expandable group; verify the scraped counts sum to the badge the app displays, so the export is provably complete.
