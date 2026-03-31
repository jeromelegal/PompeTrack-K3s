#!/usr/bin/env bash
set -euo pipefail

TMP_DIR="$(mktemp -d)"
cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

# 1) Helm envoie tous les manifests sur stdin
cat > "$TMP_DIR/all.yaml"

# 2) Kustomize wrapper
cat > "$TMP_DIR/kustomization.yaml" <<'YAML'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - all.yaml
patchesStrategicMerge:
  - medplum-probes-patch.yaml
  - medplum-storage-patch.yaml
YAML

# 3) Patch (copié depuis ton repo)
cp ./deploy/post-renderer/medplum/medplum-probes-patch.yaml "$TMP_DIR/medplum-probes-patch.yaml"
cp ./deploy/post-renderer/medplum/medplum-storage-patch.yaml "$TMP_DIR/medplum-storage-patch.yaml"

# 4) Build via kubectl kustomize (pas besoin d'installer kustomize)
kubectl kustomize "$TMP_DIR"
