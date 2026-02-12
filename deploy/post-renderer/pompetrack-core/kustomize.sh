#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

cat > "$TMP_DIR/all.yaml"

cat > "$TMP_DIR/kustomization.yaml" <<'YAML'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - all.yaml
patchesStrategicMerge:
  - ingestion-probes-patch.yaml
  - minio-probes-patch.yaml
YAML

cp ./deploy/post-renderer/pompetrack-core/ingestion-probes-patch.yaml "$TMP_DIR/ingestion-probes-patch.yaml"
cp ./deploy/post-renderer/pompetrack-core/minio-probes-patch.yaml "$TMP_DIR/minio-probes-patch.yaml"

kubectl kustomize "$TMP_DIR"
