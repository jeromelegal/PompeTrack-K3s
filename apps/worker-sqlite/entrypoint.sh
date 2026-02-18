#!/bin/sh
if [ -n "$TOKEN_FILE" ] && [ -f "$TOKEN_FILE" ]; then
  export TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
fi

exec "$@"
