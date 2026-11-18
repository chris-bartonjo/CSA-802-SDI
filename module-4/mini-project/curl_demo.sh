#!/usr/bin/env bash
# End-to-end cURL test against a live server. Starts the API, runs each call, saves curl_demo_output.txt, stops the API.
# Usage:  bash curl_demo.sh   (set PYTHON to choose an interpreter; API key is the local test value dev-key-123)
set -u
cd "$(dirname "$0")"
if [ -n "${PYTHON:-}" ]; then PY="$PYTHON"
elif [ -x ../../../.venv/bin/python ]; then PY=../../../.venv/bin/python   # inside the masters repo
else PY=python3; fi
BASE="http://127.0.0.1:5055"
KEY="dev-key-123"
OUT="curl_demo_output.txt"

"$PY" run.py >/dev/null 2>&1 &
SERVER=$!
trap 'kill $SERVER 2>/dev/null' EXIT
curl -s --retry 20 --retry-connrefused --retry-delay 1 "$BASE/api/health" >/dev/null

call() {  # call "<title>" <curl args...>
  local title="$1"; shift
  printf '\n### %s\n$ curl %s\n' "$title" "$*" | sed "s#$BASE##g"
  local resp code body
  resp=$(curl -s -w '\n%{http_code}' "$@")
  code=$(printf '%s' "$resp" | tail -n1)
  body=$(printf '%s' "$resp" | sed '$d')
  printf 'HTTP %s\n' "$code"
  printf '%s' "$body" | "$PY" -m json.tool 2>/dev/null || printf '%s\n' "$body"
}

{
  echo "Bookstore Integration API - cURL test run"
  call "1. Request without an API key (expect 401)" "$BASE/api/books"
  call "2. Get book details from Inventory (expect 200)" -H "X-API-Key: $KEY" "$BASE/api/books/B001"
  call "3. Place an order and pay through Sales (expect 201)" -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
       -d '{"customer":{"name":"Amina Wanjiru","email":"amina@example.com"},"items":[{"book_id":"B001","quantity":2},{"book_id":"B004","quantity":1}],"payment":{"method":"mpesa","token":"tok_test_123"},"delivery_address":"12 Moi Avenue, Nairobi"}' \
       "$BASE/api/orders"
  call "4. Stock after the order (expect 10)" -H "X-API-Key: $KEY" "$BASE/api/books/B001"
  call "5. Update the Delivery System (expect 200)" -X PUT -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
       -d '{"status":"dispatched","courier":"G4S Courier","tracking_number":"G4S-778812"}' "$BASE/api/deliveries/DEL-0001"
  call "6. Order an out-of-stock book (expect 409)" -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
       -d '{"customer":{"name":"Brian Otieno","email":"brian@example.com"},"items":[{"book_id":"B003","quantity":1}],"payment":{"method":"card","token":"tok_test_456"},"delivery_address":"4 Oginga Odinga St, Kisumu"}' \
       "$BASE/api/orders"
  call "7. Declined payment (expect 402)" -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
       -d '{"customer":{"name":"Brian Otieno","email":"brian@example.com"},"items":[{"book_id":"B002","quantity":1}],"payment":{"method":"card","token":"tok_declined"},"delivery_address":"4 Oginga Odinga St, Kisumu"}' \
       "$BASE/api/orders"
} > "$OUT"
cat "$OUT"
