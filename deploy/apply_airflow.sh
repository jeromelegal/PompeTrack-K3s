#!/usr/bin/env bash
set -euo pipefail

helm -n airflow uninstall airflow || true
kubectl delete namespace airflow

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

# Namespaces create
echo "==> Namespaces (must come first for Istio injection)"
apply_file_if_exists deploy/namespaces/airflow/00-namespace.yaml

# Safety: ensure namespaces exist even if YAML missing
kubectl get ns airflow >/dev/null 2>&1 || kubectl apply -f deploy/namespaces/airflow/00-namespace.yaml

# Net Policies
echo "==> Netpol (strict baseline + targeted allows)"
apply_dir_ordered deploy/namespaces/airflow/netpol

# Istio policies
echo "==> Istio policies (PeerAuth/Authz)"
apply_dir_ordered deploy/namespaces/airflow/istio

# Helm update
echo "==> Helm deps"
helm dependency update deploy/charts/medplum || true

# Ids medplum create
echo "==> Medplum bootstrap (project + worker-fhir client)"
./deploy/secrets/medplum-config/generate-worker-fhir-medplum-client.sh

# Secrets scripts
echo "==> Airflow secrets"
./deploy/secrets/airflow/init-secrets.sh

## Helm umbrella Airflow namespace
echo "==> Helm install/upgrade airflow"
helm upgrade --install airflow deploy/charts/airflow \
  -f deploy/charts/airflow/values.yaml \
  -n airflow 

# Ingress policies
echo "==> Ingress (Traefik objects - always reapplied)"
apply_dir_ordered deploy/namespaces/airflow/ingress

# Copy DAGs to Airflow PVC
echo "==> Copy DAGs to Airflow PVC"
POD=$(kubectl -n airflow get pod -l component=dag-processor -o jsonpath='{.items[0].metadata.name}')
kubectl -n airflow cp apps/dags/. $POD:/opt/airflow/dags/

# Verify
echo "==> Done"
kubectl get pods -n airflow
