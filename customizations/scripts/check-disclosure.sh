#!/usr/bin/env bash
# Disclosure guard. Fails if anything personal, confidential or credential-like
# is added to this tree. Run before every commit; wire into CI/pre-commit.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 2

fail=0
note() { printf '  %s\n' "$1"; }
bad()  { printf '  FAIL: %s\n' "$1"; fail=1; }

echo "== 1. credential patterns =="
CRED='(-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|gh[pousr]_[A-Za-z0-9]{30,}|xox[abposr]-[A-Za-z0-9-]{10,}|[0-9]{8,10}:AA[A-Za-z0-9_-]{30,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.)'
hits=$(grep -rInE --binary-files=without-match "$CRED" . 2>/dev/null)
if [ -n "$hits" ]; then bad "credential-shaped string:"; echo "$hits" | head -20; else note "none"; fi

echo "== 2. live-looking API keys =="
# sk-<real> but allow documentation placeholders such as sk-xxx...xxxx
hits=$(grep -rInE --binary-files=without-match '\bsk-[A-Za-z0-9_-]{20,}' . 2>/dev/null | grep -vE 'x{3,}|\.\.\.|<|YOUR|example')
if [ -n "$hits" ]; then bad "api key shaped:"; echo "$hits" | head -20; else note "none"; fi

echo "== 3. identity and org leakage =="
ID='(?i)(zollege|lofton|kevincolten|robpwatkins|luke5anch3z|andrea[ _]orjuela)'
hits=$(grep -rInE --binary-files=without-match "$ID" . 2>/dev/null | grep -v '^\./scripts/check-disclosure.sh')
if [ -n "$hits" ]; then bad "protected identifier:"; echo "$hits" | head -20; else note "none"; fi

echo "== 4. non-placeholder emails / phones / internal hosts =="
hits=$(grep -rInE --binary-files=without-match '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' . 2>/dev/null \
       | grep -vE '@example\.(com|invalid|test)')
if [ -n "$hits" ]; then bad "email outside example.com:"; echo "$hits" | head -20; else note "none"; fi
hits=$(grep -rInE --binary-files=without-match '\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b|\+1-?[0-9]{3}-?[0-9]{3}-?[0-9]{4}' . 2>/dev/null \
       | grep -v '555-0100')
if [ -n "$hits" ]; then bad "phone/SSN shape:"; echo "$hits" | head -20; else note "none"; fi
hits=$(grep -rInE --binary-files=without-match '\b[0-9]{10,17}\b' . 2>/dev/null | grep -vE '100123456789|1234567890|20260[0-9]{8}')
if [ -n "$hits" ]; then bad "account-number shape:"; echo "$hits" | head -20; else note "none"; fi

echo "== 5. binaries must be explicitly reviewed =="
ALLOW="skills/engineering-swarm/scripts/package/mermaid-diagram.png"
while IFS= read -r f; do
  rel=${f#./}
  case " $ALLOW " in *" $rel "*) note "reviewed binary: $rel" ;; *) bad "unreviewed binary: $rel" ;; esac
done < <(find . -type f ! -name '*.md' ! -name '*.py' ! -name '*.json' ! -name '*.sh' \
              ! -name '*.mmd' ! -name '*.yaml' ! -name '*.yml' ! -name '*.txt' \
              ! -name '.gitignore' ! -path './.git/*')

echo "== 6. gitleaks =="
if command -v gitleaks >/dev/null 2>&1; then
  if gitleaks dir . --no-banner --redact 2>&1 | tail -5; then note "gitleaks clean"; else bad "gitleaks findings above"; fi
else
  note "gitleaks not installed - skipped (patterns 1-4 still applied)"
fi

echo
if [ "$fail" -ne 0 ]; then echo "DISCLOSURE GUARD: FAILED"; exit 1; fi
echo "DISCLOSURE GUARD: PASSED"
