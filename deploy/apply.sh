#!/usr/bin/env bash
set -euo pipefail

apply_dir_ordered() {
  local dir="$1"
  if [ -d "$dir" ] && ls -1 "$dir"/*.yaml >/dev/null 2>&1; then
    echo "==> apply (ordered): $dir"
    # Ordre lexical (00-, 01-, 02-...) = déterministe
    while IFS= read -r f; do
      kubectl apply -f "$f"
    done < <(ls -1 "$dir"/*.yaml | sort)
  else
    echo "==> skip (empty): $dir"
  fi
}

apply_file_if_exists() {
  local f="$1"
  if [ -f "$f" ]; then
    echo "==> apply file: $f"
    kubectl apply -f "$f"
  else
    echo "==> skip (missing): $f"
  fi
}

echo "==> Namespaces (must come first for Istio injection)"
apply_file_if_exists deploy/namespaces/medplum/00-namespace.yaml
apply_file_if_exists deploy/namespaces/pompetrack-core/00-namespace.yaml

# Safety: ensure namespaces exist even if YAML missing
kubectl get ns medplum >/dev/null 2>&1 || kubectl apply -f deploy/namespaces/medplum/00-namespace.yaml
kubectl get ns pompetrack-core >/dev/null 2>&1 || kubectl apply -f deploy/namespaces/pompetrack-core/00-namespace.yaml

echo "==> Netpol (strict baseline + targeted allows)"
apply_dir_ordered deploy/namespaces/medplum/netpol
apply_dir_ordered deploy/namespaces/pompetrack-core/netpol

echo "==> Istio policies (PeerAuth/Authz)"
apply_dir_ordered deploy/namespaces/medplum/istio
apply_dir_ordered deploy/namespaces/pompetrack-core/istio

echo "==> Secrets"
./deploy/secrets/medplum/init-secrets.sh
./deploy/secrets/pompetrack-core/init-secrets.sh
./deploy/secrets/registry/init-secrets.sh

echo "==> Helm deps"
helm dependency update deploy/charts/medplum || true

echo "==> Helm install/upgrade medplum (with post-renderer patches)"
helm upgrade --install medplum deploy/charts/medplum \
  -f deploy/charts/medplum/values-medplum.yaml \
  -n medplum \
  --post-renderer ./deploy/post-renderer/medplum/kustomize.sh

echo "==> Medplum bootstrap (project + worker-fhir client)"
./deploy/secrets/medplum-config/generate-worker-fhir-medplum-client.sh

echo "==> Helm install/upgrade pompetrack-core (with post-renderer patches)"
helm upgrade --install pompetrack-core deploy/charts/pompetrack-core \
  -f deploy/charts/pompetrack-core/values-minio.yaml \
  -n pompetrack-core \
  --post-renderer ./deploy/post-renderer/pompetrack-core/kustomize.sh

echo "==> Ingress (Traefik objects - always reapplied)"
apply_dir_ordered deploy/namespaces/medplum/ingress
apply_dir_ordered deploy/namespaces/pompetrack-core/ingress

echo "==> Done"
kubectl get pods -n medplum
kubectl get pods -n pompetrack-core
