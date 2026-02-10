#!/usr/bin/env bash
set -euo pipefail

NAMESPACE=pompetrack-core
SECRETS_DIR=deploy/secrets/"$NAMESPACE"

for file in "$SECRETS_DIR"/*.env; do
  name="$(basename "$file" .env)"

  kubectl -n "$NAMESPACE" create secret generic "$name" \
    --from-env-file="$file" \
    --dry-run=client -o yaml \
  | kubectl apply -f -
done