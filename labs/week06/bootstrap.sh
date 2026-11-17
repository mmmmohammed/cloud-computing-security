#!/usr/bin/env bash
# user-data equivalent: runs once, at first boot, before anything is served.
#
# On a real instance this is where patching, the logging agent and the packages
# go. Here it prepares the document root and records what was done, so the build
# record can prove the server was built by script rather than by hand.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
RUNTIME="$ROOT/runtime"
SITE="$ROOT/site"

echo "[bootstrap] 1/4 preparing document root at $SITE"
mkdir -p "$SITE" "$RUNTIME/logs"

echo "[bootstrap] 2/4 checking the page exists"
test -f "$SITE/index.html" || { echo "[bootstrap] FATAL: no index.html in $SITE"; exit 1; }

echo "[bootstrap] 3/4 writing the build stamp"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$RUNTIME/bootstrapped_at"
hostname > "$RUNTIME/bootstrapped_on" 2>/dev/null || echo "localhost" > "$RUNTIME/bootstrapped_on"

echo "[bootstrap] 4/4 nothing to install — nginx is already present on this host"
echo "[bootstrap] done"
