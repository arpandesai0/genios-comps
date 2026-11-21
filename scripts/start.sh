#!/bin/sh
# Validate the data folder, then start the API and web UI with docker compose.
# Usage: scripts/start.sh /path/to/data   (normally via: make start DIR=/path/to/data)
set -eu
unset CDPATH  # so `cd` never prints a directory and corrupts $dir

usage="usage: make start DIR=/path/to/data (a folder with companies.json and fx_rates.json)"
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

echo "Data folder: $dir"
echo "UI:  http://localhost:3000"
echo "API: http://localhost:8000/api/health"
DIR="$dir" exec docker compose up --build
