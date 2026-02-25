#!/usr/bin/env bash
set -euo pipefail

NAMESPACE=airflow
RELEASE_NAME=airflow
SECRETS_DIR=deploy/secrets/"$NAMESPACE"

# -----------------------------
# 1️⃣ Gestion des .env (comme avant ✅)
# -----------------------------
for file in "$SECRETS_DIR"/*.env; do
  [ -f "$file" ] || continue

  name="$(basename "$file" .env)"

  echo "Creating/Updating secret from env: $name"

  kubectl -n "$NAMESPACE" create secret generic "$name" \
    --from-env-file="$file" \
    --dry-run=client -o yaml \
  | kubectl apply -f -

  kubectl -n "$NAMESPACE" label secret "$name" \
    app.kubernetes.io/managed-by=Helm \
    --overwrite

  kubectl -n "$NAMESPACE" annotate secret "$name" \
    meta.helm.sh/release-name="$RELEASE_NAME" \
    meta.helm.sh/release-namespace="$NAMESPACE" \
    --overwrite
done


# -----------------------------
# 2️⃣ Gestion des .key (SSH git propre ✅)
# -----------------------------
for file in "$SECRETS_DIR"/*.key; do
  [ -f "$file" ] || continue

  name="$(basename "$file" .key)"

  echo "Creating/Updating secret from key: $name"

  kubectl -n "$NAMESPACE" create secret generic "$name" \
    --from-file=gitSshKey="$file" \
    --dry-run=client -o yaml \
  | kubectl apply -f -

  kubectl -n "$NAMESPACE" label secret "$name" \
    app.kubernetes.io/managed-by=Helm \
    --overwrite

  kubectl -n "$NAMESPACE" annotate secret "$name" \
    meta.helm.sh/release-name="$RELEASE_NAME" \
    meta.helm.sh/release-namespace="$NAMESPACE" \
    --overwrite
done
