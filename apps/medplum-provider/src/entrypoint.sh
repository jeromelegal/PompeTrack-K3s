#!/bin/sh
if [ -n "$MEDPLUM_CLIENT_ID_FILE" ] && [ -f "$MEDPLUM_CLIENT_ID_FILE" ]; then
  export MEDPLUM_CLIENT_ID="$(tr -d '\r\n' < "$MEDPLUM_CLIENT_ID_FILE")"
fi
if [ -n "$MEDPLUM_CLIENT_SECRET_FILE" ] && [ -f "$MEDPLUM_CLIENT_SECRET_FILE" ]; then
  export MEDPLUM_CLIENT_SECRET="$(tr -d '\r\n' < "$MEDPLUM_CLIENT_SECRET_FILE")"
fi

exec "$@"
