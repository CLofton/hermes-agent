# Drift classification

The classifier that turns a raw two-system diff into `format_only` / `target_ahead` / `source_gap` / `real_conflict`. Run this BEFORE quoting any conflict count.

## Canonicalise, then compare

```python
MONTHS = ['january','february','march','april','may','june','july',
          'august','september','october','november','december']
SYNONYM_GROUPS = [
    {'active', 'already started', 'already active'},
    {'complete', 'completed', 'done'},
    {'pending', 'not started', 'waiting'},
    {'unassigned', 'none', '', '—', '-'},
]
EMPTY = ('', 'none', 'null', 'tbd', 'n/a', '—', '-')

def canonical(v, field):
    s = str(v or '').strip()
    if s.lower() in EMPTY:
        return ('empty', '')
    low = ' '.join(s.lower().split())

    # month fields: accept 'August', '2025-08-01 00:00:00', 'Sept 2025', 'Early September 2025'
    if field.endswith('_month'):
        m = re.match(r'^(\d{4})-(\d{2})-\d{2}', s)
        if m:
            return ('month', (MONTHS[int(m.group(2)) - 1], m.group(1)))
        for mo in MONTHS:
            if mo in low or mo[:3] in low:
                y = re.search(r'(20\d{2})', low)
                return ('month', (mo, y.group(1) if y else None))

    # quarter fields: '2026 Q3' == 'Q3 2026'
    m = re.match(r'^(20\d{2})\s*q([1-4])$', low) or re.match(r'^q([1-4])\s*(20\d{2})$', low)
    if m:
        return ('quarter', ''.join(sorted(m.groups())))

    # slashed dates -> ISO so '05/15/2025' == '2025-05-15'
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', s)
    if m:
        mo, dy, yr = m.groups()
        return ('date', f'{yr}-{int(mo):02d}-{int(dy):02d}')

    for grp in SYNONYM_GROUPS:
        if low in grp:
            return ('syn', sorted(grp)[0])
    return ('raw', low)

def same(a, b, field):
    ta, va = canonical(a, field)
    tb, vb = canonical(b, field)
    if va == vb:
        return 'identical'
    if ta == tb == 'raw':
        short, long_ = sorted([va, vb], key=len)
        if len(short) >= 25 and long_.startswith(short):
            return 'truncation'          # one side cut off mid-string
        if long_.replace('\u200b', '') == short:
            return 'zero-width'          # invisible char, identical text
    if ta == tb == 'month' and va[0] == vb[0] and (va[1] is None or vb[1] is None or va[1] == vb[1]):
        return 'month-partial'           # 'August' vs 'August 2025'
    return None
```

## Assign the buckets

```python
for sid in shared_ids:
    for field, source_value in source[sid].items():
        target_value = target[sid].get(field)
        if same(source_value, target_value, field):
            if str(source_value) != str(target_value):
                record(sid, field, 'format_only', reason=...)
            continue
        ts, _ = canonical(source_value, field)
        tt, _ = canonical(target_value, field)
        if ts == 'empty' and tt != 'empty':
            record(sid, field, 'target_ahead')
        elif ts != 'empty' and tt == 'empty':
            record(sid, field, 'source_gap')
        else:
            record(sid, field, 'real_conflict')
```

## Notes that matter

- Compare the **canonical** form for equality but keep the **raw** pair on every record — the human reviewing a decision needs to see the actual strings.
- Zero-width and truncation cases are `format_only` in substance. A `\u200b` in a text field is data corruption worth a separate cleanup pass, not a value disagreement.
- Field-aware canonicalisation beats generic normalisation: applying month logic to a free-text notes column turns real conflicts into false matches.
- Audit-stamp fields (`created_at`, `updated_at`) will always land in `real_conflict` and should be routed to a policy bucket, not adjudicated.
- Print the absorbed-reason counts (`format`, `truncation`, `zero-width`, `month-partial`). The distribution is the fastest evidence that your canonicaliser is doing real work rather than hiding disagreements.
