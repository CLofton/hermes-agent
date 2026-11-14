#!/usr/bin/env python3
import argparse, json, subprocess
from pathlib import Path

# Fixed role routes (unchanged behavior).
ROUTES = {
    'code-default': {'profile': 'luna', 'model': 'openai/gpt-5.6-luna'},
    'step-up': {'profile': 'sonnet', 'model': 'anthropic/claude-sonnet-5'},
    'premium': {'profile': 'secondary', 'model': 'anthropic/claude-opus-5'},
    'value': {'profile': 'glmvalue', 'model': 'z-ai/glm-5.3-flash'},
    'test-logic': {'profile': 'deepseek', 'model': 'deepseek/deepseek-v4-flash'},
    'architecture': {'profile': 'qwen', 'model': 'qwen/qwen3.8-27b'},
    'review': {'profile': 'grokreview', 'model': 'x-ai/grok-4.6'},
    'design': {'profile': 'kimidesign', 'model': 'moonshotai/kimi-k3'},
    'fast': {'profile': 'geminifast', 'model': 'google/gemini-3.7-flash'},
}

# Full OpenRouter catalog (all 437 models) made dispatchable via --model.
CANDIDATES = [
    Path.home()/'.hermes/skills/autonomous-ai-agents/openrouter-agent-fleet/scripts/openrouter-catalog.json',
    Path.home()/'Downloads/hermes-engineering-swarm-v2 2/openrouter-catalog.json',
]
# A profile that carries an OPENROUTER_API_KEY and can dispatch arbitrary models.
DEFAULT_DISPATCH_PROFILE = 'qwen'


def load_catalog():
    for p in CANDIDATES:
        if p.exists():
            return json.loads(p.read_text())
    return None


def search(query, catalog, limit=40):
    q = query.lower()
    out = []
    for m in catalog.get('models', []):
        hay = (m.get('id', '') + ' ' + (m.get('name') or '')).lower()
        if q in hay:
            out.append(m)
        if len(out) >= limit:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description='Dispatch a task to an OpenRouter model (fixed role or any of 437 catalog models).')
    ap.add_argument('task', nargs='?')
    ap.add_argument('--role', choices=sorted(ROUTES))
    ap.add_argument('--model', help='Any OpenRouter model id (provider/slug) from the catalog, e.g. deepseek/deepseek-v4-flash')
    ap.add_argument('--profile', default=DEFAULT_DISPATCH_PROFILE, help='Hermes profile to dispatch with (default: %(default)s). Used only with --model.')
    ap.add_argument('--list', action='store_true', help='List fixed role routes')
    ap.add_argument('--catalog', action='store_true', help='Show catalog stats')
    ap.add_argument('--search', help='Search the OpenRouter catalog by id or name substring')
    ap.add_argument('--timeout', type=int, default=600)
    a = ap.parse_args()

    if a.catalog:
        c = load_catalog()
        if not c:
            print('no catalog found'); return
        print(json.dumps({k: c[k] for k in c if k != 'models'}, indent=2))
        return
    if a.search:
        c = load_catalog()
        if not c:
            print('no catalog found'); return
        hits = search(a.search, c)
        print(json.dumps(hits, indent=1))
        print(f'\n{len(hits)} match(es) for "{a.search}" — dispatch with: {Path(__file__).name} --model <id> "task"')
        return
    if a.list:
        print(json.dumps(ROUTES, indent=2))
        c = load_catalog()
        if c:
            print(f'\n(full OpenRouter catalog: {c["model_count"]} models — use --search or --model)')
        return
    if not a.task:
        ap.error('task (or --list/--search/--catalog) is required')

    # Resolve target profile + model.
    if a.model:
        profile, model = a.profile, a.model
        # optional: validate against catalog and surface price
        c = load_catalog()
        if c:
            hit = next((m for m in c.get('models', []) if m.get('id') == model), None)
            if hit:
                print(f"[dispatch] {model}  in=${hit.get('price_input_per_M')}/M out=${hit.get('price_output_per_M')}/M ctx={hit.get('context_length')}", flush=True)
            else:
                print(f"[warn] {model} not in local catalog (fetched {c.get('fetched_at')}); dispatching anyway.", flush=True)
    elif a.role:
        route = ROUTES[a.role]
        profile, model = route['profile'], route['model']
    else:
        ap.error('provide --model <id> or --role <name>')

    wrapper = Path.home()/'.local/bin'/profile
    cmd = [str(wrapper), 'chat', '-q', a.task, '--quiet', '-m', model, '--provider', 'openrouter']
    cp = subprocess.run(cmd, text=True, capture_output=True, timeout=a.timeout)
    if cp.stdout: print(cp.stdout.rstrip())
    if cp.stderr: print(cp.stderr.rstrip())
    raise SystemExit(cp.returncode)


if __name__ == '__main__': main()
