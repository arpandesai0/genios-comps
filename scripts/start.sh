#!/bin/sh
# Validate the data folder, then start the services with docker compose.
# Usage: scripts/start.sh /path/to/data [service ...]   (normally via: make start DIR=/path/to/data [SERVICES="api"])
# With no services named, every service starts (api and web). Naming services starts only those, e.g.
# SERVICES=api for local testing and evals without the front end.
set -eu
unset CDPATH  # so `cd` never prints a directory and corrupts $dir

usage="usage: make start DIR=/path/to/data [SERVICES=\"api web\"] (DIR: a folder with companies.json and fx_rates.json)"
fail() { echo "$1" >&2; exit 1; }
[ -n "${1:-}" ] || fail "$usage"

# Expand a leading ~ (zsh does not expand it in DIR=~/... arguments).
case "$1" in
  "~") raw="$HOME" ;;
  "~"/*) raw="$HOME/${1#"~"/}" ;;
  *) raw="$1" ;;
esac

dir=$(cd "$raw" 2>/dev/null && pwd) || fail "DIR '$1' is not a folder. $usage"
case "$dir" in
  *:*) fail "DIR '$dir' contains ':', which docker compose cannot mount. Move or link the folder elsewhere." ;;
esac
for f in companies.json fx_rates.json; do
  [ -f "$dir/$f" ] || fail "Missing $dir/$f. $usage"
done

shift
known=$(DIR="$dir" docker compose config --services)
for svc in "$@"; do
  echo "$known" | grep -qx "$svc" || fail "Unknown service '$svc'. Services: $(echo $known)."
done

echo "Data folder: $dir"
echo "Services: ${*:-all ($(echo $known))}"
if [ $# -eq 0 ] || echo " $* " | grep -q " web "; then echo "UI:  http://localhost:3000"; fi
echo "API: http://localhost:8000/api/health"
DIR="$dir" exec docker compose up --build "$@"
