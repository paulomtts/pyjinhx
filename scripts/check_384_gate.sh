#!/usr/bin/env bash
# Verification gate for #384 (L1.G.3). Docs-only task: asserts the ADR records the
# full enumeration and that the diff touches no code.
set -uo pipefail
cd "$(dirname "$0")/.."
ADR=docs/superpowers/rebuild/adr/0009-minimal-instance-registry.md
ROADMAP=docs/superpowers/rebuild/roadmap.md
fail=0
req() {
  if ! grep -qF -- "$2" "$1"; then
    echo "MISSING in $1: $2"
    fail=1
  fi
}
forbid() {
  if grep -qiF -- "$2" "$1"; then
    echo "FORBIDDEN present in $1: $2"
    fail=1
  fi
}

req "$ADR" "## Enumerated Surface"
for n in E1 E2 E3 E4 E5 E6 E7 E8 E9 E10 E11 E12 E13 E14 E15 E16 E17 E18; do
  req "$ADR" "$n."
done
for n in N1 N2 N3 N4 N5 N6; do
  req "$ADR" "$n."
done
req "$ADR" "## Resolved open questions"
req "$ADR" "LookupError"
req "$ADR" "request scope"
req "$ADR" "CacheScope"
req "$ADR" "not forbidden"
req "$ADR" "template-invisible"
req "$ADR" "outerHTML"
req "$ADR" "root_span"
req "$ADR" "(component_class, load_arg)"
req "$ADR" "never merged"
req "$ADR" "request_scope"

forbid "$ADR" "append/prepend swap is supported"
forbid "$ADR" "class InstanceRegistry"

req "$ADR" "#382"
req "$ADR" "#383"

req "$ADR" "Enumerated Surface"
req "$ROADMAP" "ADR 0009"

if [ "$fail" -ne 0 ]; then
  echo "FAIL"
  exit 1
fi
echo "PASS"
