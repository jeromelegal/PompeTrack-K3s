#!/bin/sh
if [ -n "$TOKEN_FILE" ] && [ -f "$TOKEN_FILE" ]; then
  export TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
fi
if [ -n "$STREAMLIT_ID_FILE" ] && [ -f "$STREAMLIT_ID_FILE" ]; then
  export STREAMLIT_ID="$(tr -d '\r\n' < "$STREAMLIT_ID_FILE")"
fi
if [ -n "$STREAMLIT_SECRET_FILE" ] && [ -f "$STREAMLIT_SECRET_FILE" ]; then
  export STREAMLIT_SECRET="$(tr -d '\r\n' < "$STREAMLIT_SECRET_FILE")"
fi

exec "$@"