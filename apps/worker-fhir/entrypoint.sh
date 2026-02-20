#!/bin/sh
if [ -n "$TOKEN_FILE" ] && [ -f "$TOKEN_FILE" ]; then
  export TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
fi
if [ -n "$CLIENT_ID_FILE" ] && [ -f "$CLIENT_ID_FILE" ]; then
  export CLIENT_ID="$(tr -d '\r\n' < "$CLIENT_ID_FILE")"
fi
if [ -n "$CLIENT_SECRET_FILE" ] && [ -f "$CLIENT_SECRET_FILE" ]; then
  export CLIENT_SECRET="$(tr -d '\r\n' < "$CLIENT_SECRET_FILE")"
fi
if [ -n "$TOKEN_AUDIENCE_AIRFLOW_FILE" ] && [ -f "$TOKEN_AUDIENCE_AIRFLOW_FILE" ]; then
  export TOKEN_AUDIENCE_AIRFLOW="$(tr -d '\r\n' < "$TOKEN_AUDIENCE_AIRFLOW_FILE")"
fi

exec "$@"
