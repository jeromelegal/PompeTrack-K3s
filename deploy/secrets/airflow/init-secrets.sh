#!/usr/bin/env bash
set -euo pipefail

NAMESPACE=airflow
RELEASE_NAME=airflow
SECRETS_DIR=deploy/secrets/"$NAMESPACE"

for file in "$SECRETS_DIR"/*.env; do
  name="$(basename "$file" .env)"

  echo "Creating/Updating secret: $name"

  kubectl -n "$NAMESPACE" create secret generic "$name" \
    --from-env-file="$file" \
    --dry-run=client -o yaml \
  | kubectl apply -f -

  # Add Helm ownership metadata
  kubectl -n "$NAMESPACE" label secret "$name" \
    app.kubernetes.io/managed-by=Helm \
    --overwrite

  kubectl -n "$NAMESPACE" annotate secret "$name" \
    meta.helm.sh/release-name="$RELEASE_NAME" \
    meta.helm.sh/release-namespace="$NAMESPACE" \
    --overwrite

done
