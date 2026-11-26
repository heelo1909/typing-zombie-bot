#!/usr/bin/env bash
# Starts a separate Chrome profile with the DevTools Protocol enabled (port 9222),
# then makes sure the game URL is open in a tab.
# Chrome 136+ refuses remote debugging on the default profile, hence --user-data-dir.
# Usage: ./launch_chrome.sh [url]      (default: the Tommy Q game page)
#        HEADLESS=1 PORT=9333 ./launch_chrome.sh "file://$PWD/mock/tommyq_mock.html"
set -euo pipefail
URL="${1:-https://www.typing.com/student/game/tommyq}"
PORT="${PORT:-9222}"
PROFILE_DIR="${PROFILE_DIR:-$HOME/.zombiebot-chrome}"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
EXTRA=()
if [[ "${HEADLESS:-0}" == "1" ]]; then EXTRA+=(--headless=new --window-size=1100,700); fi

"$CHROME" --remote-debugging-port="$PORT" --user-data-dir="$PROFILE_DIR" \
  --no-first-run --no-default-browser-check \
  --disable-background-timer-throttling --disable-renderer-backgrounding \
  --disable-backgrounding-occluded-windows ${EXTRA[@]+"${EXTRA[@]}"} "$URL" \
  >"$PROFILE_DIR.log" 2>&1 &
CHROME_PID=$!

for _ in $(seq 1 30); do
  curl -s "http://127.0.0.1:$PORT/json/version" >/dev/null 2>&1 && break
  sleep 0.5
done
# Managed Chrome installs may show a profile picker instead of the URL: open a tab via CDP.
BASE_URL="${URL%%\?*}"
if ! curl -s "http://127.0.0.1:$PORT/json/list" | grep -q "\"url\": \"$BASE_URL"; then
  ENC=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe=":/"))' "$URL")
  curl -s -X PUT "http://127.0.0.1:$PORT/json/new?$ENC" >/dev/null
fi
echo "Chrome running (pid $CHROME_PID) with DevTools on port $PORT; profile $PROFILE_DIR"
