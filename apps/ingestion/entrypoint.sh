#!/bin/sh
if [ -n "$MINIO_ACCESS_KEY_ID_FILE" ] && [ -f "$MINIO_ACCESS_KEY_ID_FILE" ]; then
  export MINIO_ACCESS_KEY_ID="$(tr -d '\r\n' < "$MINIO_ACCESS_KEY_ID_FILE")"
fi
if [ -n "$MINIO_SECRET_ACCESS_KEY_FILE" ] && [ -f "$MINIO_SECRET_ACCESS_KEY_FILE" ]; then
  export MINIO_SECRET_ACCESS_KEY="$(tr -d '\r\n' < "$MINIO_SECRET_ACCESS_KEY_FILE")"
fi
if [ -n "$CLIENT_ID_FILE" ] && [ -f "$CLIENT_ID_FILE" ]; then
  export CLIENT_ID="$(tr -d '\r\n' < "$CLIENT_ID_FILE")"
fi
if [ -n "$CLIENT_SECRET_FILE" ] && [ -f "$CLIENT_SECRET_FILE" ]; then
  export CLIENT_SECRET="$(tr -d '\r\n' < "$CLIENT_SECRET_FILE")"
fi

exec "$@"
