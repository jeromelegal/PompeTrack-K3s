#!/usr/bin/env bash
set -euo pipefail

apply_dir() {
  local dir="$1"
  if [ -d "$dir" ] && ls -1 "$dir"/*.yaml >/dev/null 2>&1; then
    echo "==> apply: $dir"
    kubectl apply -f "$dir"
  else
    echo "==> skip (empty): $dir"
  fi
}

echo "==> Namespaces"
kubectl get ns medplum >/dev/null 2>&1 || kubectl create ns medplum
kubectl get ns pompetrack-core >/dev/null 2>&1 || kubectl create ns pompetrack-core

echo "==> Secrets"
./deploy/secrets/medplum/init-secrets.sh
./deploy/secrets/pompetrack-core/init-secrets.sh

echo "==> Helm deps"
helm dependency update deploy/charts/medplum || true

echo "==> Helm install/upgrade"
helm upgrade --install medplum deploy/charts/medplum -f deploy/charts/medplum/values-medplum.yaml -n medplum
helm upgrade --install pompetrack-core deploy/charts/pompetrack-core -f deploy/charts/pompetrack-core/values-minio.yaml -n pompetrack-core

echo "==> Netpol (order matters)"
apply_dir deploy/namespaces/medplum/netpol
apply_dir deploy/namespaces/pompetrack-core/netpol

echo "==> Istio policies"
apply_dir deploy/namespaces/medplum/istio
apply_dir deploy/namespaces/pompetrack-core/istio

echo "==> Ingress (Traefik objects - always reapplied)"
apply_dir deploy/namespaces/medplum/ingress
apply_dir deploy/namespaces/pompetrack-core/ingress

echo "==> Done"
kubectl get pods -n medplum
kubectl get pods -n pompetrack-core