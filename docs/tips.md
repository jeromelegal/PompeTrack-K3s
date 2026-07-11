# Debug tips PompeTrack K3s

Ce fichier est un runbook de debug. Il privilegie les commandes utiles pendant un incident, les checks apres redeploiement, et les points de panne frequents.

## Vue rapide

Etat global:

```bash
kubectl get nodes -o wide
kubectl get ns
kubectl get pods -A | egrep 'medplum|pompetrack-core|airflow|monitoring|llm-agent|pg-backups'
kubectl get events -A --sort-by=.lastTimestamp | tail -80
```

Etat par namespace:

```bash
for ns in medplum pompetrack-core airflow monitoring llm-agent pg-backups; do
  echo "### $ns"
  kubectl -n "$ns" get deploy,sts,svc,ingressroute,cronjob,pod
done
```

Rollouts principaux:

```bash
kubectl -n medplum rollout status deploy/medplum-app --timeout=120s
kubectl -n medplum rollout status deploy/medplum-provider --timeout=120s
kubectl -n pompetrack-core rollout status deploy/streamlit --timeout=120s
kubectl -n airflow rollout status deploy/airflow-webserver --timeout=120s
kubectl -n llm-agent rollout status deploy/agent-backend --timeout=120s
kubectl -n llm-agent rollout status deploy/agent-backend-mcpo --timeout=120s
kubectl -n llm-agent rollout status deploy/open-webui --timeout=120s
kubectl -n llm-agent rollout status deploy/telegram-health-bot --timeout=120s
```

## Helm

Lister les releases:

```bash
helm list -A
helm -n medplum status medplum
helm -n pompetrack-core status pompetrack-core
helm -n airflow status airflow
helm -n monitoring status monitoring
helm -n llm-agent status llm-agent
```

Rendre un chart sans appliquer:

```bash
helm template llm-agent deploy/charts/llm-agent \
  -f deploy/charts/llm-agent/values.yaml \
  -n llm-agent >/tmp/llm-agent-rendered.yaml

helm template medplum deploy/charts/medplum \
  -f deploy/charts/medplum/values-medplum.yaml \
  -n medplum \
  --post-renderer ./deploy/post-renderer/medplum/kustomize.sh >/tmp/medplum-rendered.yaml
```

Verifier si un objet attendu est dans la release installee:

```bash
helm -n llm-agent get manifest llm-agent | rg 'telegram-reminder-runner|agent-backend-mcpo|open-webui'
helm -n medplum get manifest medplum | rg 'medplum-provider|medplum-app|postgresql'
```

Valeurs par defaut d'un chart externe:

```bash
helm show values apache-airflow/airflow > /tmp/airflow-default-values.yaml
helm show values prometheus-community/kube-prometheus-stack > /tmp/kps-default-values.yaml
```

## Redeploiement cible

Scripts utiles sans supprimer les PVC:

```bash
./deploy/apply_pompetrack-core.sh
./deploy/apply_llm-agent.sh
./deploy/apply_monitoring.sh
./deploy/apply_pg-backups.sh
```

Upgrade manuel llm-agent apres rebuild/push d'image:

```bash
helm upgrade --install llm-agent deploy/charts/llm-agent \
  -f deploy/charts/llm-agent/values.yaml \
  -n llm-agent
```

Upgrade manuel Medplum avec versions synchronisees:

```bash
source deploy/versions.sh
./deploy/sync-medplum-version.sh

helm dependency update deploy/charts/medplum || true
helm upgrade --install medplum deploy/charts/medplum \
  -f deploy/charts/medplum/values-medplum.yaml \
  --set global.medplumVersion="${MEDPLUM_VERSION}" \
  --set global.medplumProviderVersion="${MEDPLUM_PROVIDER_VERSION}" \
  --set global.medplumProviderImageTag="${MEDPLUM_PROVIDER_IMAGE_TAG}" \
  --set medplum.deployment.image.tag="${MEDPLUM_VERSION}" \
  -n medplum \
  --post-renderer ./deploy/post-renderer/medplum/kustomize.sh
```

## Logs utiles

Applications:

```bash
kubectl -n medplum logs deploy/medplum-app --tail=120
kubectl -n medplum logs deploy/medplum-provider --tail=120
kubectl -n pompetrack-core logs deploy/ingestion --tail=120
kubectl -n pompetrack-core logs deploy/worker-fhir --tail=120
kubectl -n airflow logs deploy/airflow-webserver --tail=120
kubectl -n llm-agent logs deploy/agent-backend --tail=120
kubectl -n llm-agent logs deploy/agent-backend-mcpo --tail=120
kubectl -n llm-agent logs deploy/telegram-health-bot --tail=120
```

Jobs/CronJobs:

```bash
kubectl -n llm-agent get jobs,pods -l app=telegram-reminder-runner -o wide
JOB=$(kubectl -n llm-agent get job -l app=telegram-reminder-runner --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')
kubectl -n llm-agent logs job/"$JOB" --tail=80

kubectl -n pg-backups get cronjob,job,pod
kubectl -n pg-backups logs job/<job-name> --tail=120
```

## Ingress Traefik

Lister les routes:

```bash
for ns in medplum pompetrack-core airflow monitoring llm-agent; do
  echo "### $ns"
  kubectl -n "$ns" get ingressroute
done
```

Tester une route en forcant le Host header:

```bash
curl -sS -o /tmp/open-webui.out -w '%{http_code} %{content_type}\n' \
  -H 'Host: open-webui.lan' http://192.168.2.88/

curl -sS -o /tmp/agent-backend.out -w '%{http_code} %{content_type}\n' \
  -H 'Host: agent-backend.lan' http://192.168.2.88/health
```

Si Traefik renvoie `404`, verifier d'abord:

```bash
kubectl -n <namespace> get ingressroute <name> -o yaml
kubectl -n <namespace> get svc,endpoints <service-name> -o wide
kubectl -n kube-system logs deploy/traefik --tail=120
```

Erreur classique: une regle `Host(...)` mal quotee fait rejeter toute la route.

## llm-agent, Open WebUI et MCPO

Checks de base:

```bash
kubectl -n llm-agent get deploy,svc,cronjob,pod -o wide
kubectl -n llm-agent get endpoints agent-backend agent-backend-mcpo open-webui searxng
curl -sS http://agent-backend.192.168.2.88.nip.io/health
```

Provider OpenAI-compatible:

```bash
KEY=$(kubectl -n llm-agent get secret backend-api-key -o jsonpath='{.data.secret_key}' | base64 -d)
curl -sS http://agent-backend.192.168.2.88.nip.io/v1/models \
  -H "Authorization: Bearer ${KEY}"
```

MCPO / Tools Open WebUI:

```bash
curl -sS http://agent-tools.192.168.2.88.nip.io/openapi.json \
  | rg 'web_search|rag_search|create_daily_telegram_reminder|telegram_reminders|delete_telegram_reminder'

curl -sS -X POST http://agent-tools.192.168.2.88.nip.io/telegram_reminders \
  -H "Authorization: Bearer ${KEY}" \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"telegram:automation","active_only":true}'
```

URLs a utiliser:

```text
OpenAI provider interne: http://agent-backend:8000/v1
OpenAI provider navigateur: http://agent-backend.192.168.2.88.nip.io/v1
Tools OpenAPI interne: http://agent-backend-mcpo:8000
Tools OpenAPI navigateur: http://agent-tools.192.168.2.88.nip.io
Modele agentique: agent-medgemma:27b
```

## pompetrack-core

Checks de base:

```bash
kubectl -n pompetrack-core get deploy,svc,endpoints,pod -o wide
kubectl -n pompetrack-core logs deploy/ingestion --tail=120
kubectl -n pompetrack-core logs deploy/worker-fhir --tail=120
kubectl -n pompetrack-core logs deploy/streamlit --tail=120
```

Tester les routes LAN:

```bash
curl -sS -o /tmp/streamlit.out -w '%{http_code} %{content_type}\n' \
  -H 'Host: streamlit.lan' http://192.168.2.88/

curl -sS -o /tmp/minio.out -w '%{http_code} %{content_type}\n' \
  -H 'Host: minio.lan' http://192.168.2.88/
```

Verifier PostgreSQL et MinIO cote services:

```bash
kubectl -n pompetrack-core get pvc
kubectl -n pompetrack-core get svc,endpoints pompetrack-core-postgresql pompetrack-core-minio pompetrack-core-minio-console
kubectl -n pompetrack-core describe pod -l app=worker-fhir
```

## Telegram et reminders

Verifier bot et secrets:

```bash
kubectl -n llm-agent get secret telegram-bot -o jsonpath='{.data.allowed_chat_ids}' | base64 -d; echo
kubectl -n llm-agent logs deploy/telegram-health-bot --tail=120
```

Commandes Telegram principales:

```text
/id
/latest
/features
/coach
/weekly-review
/bilans on|off|status
/remind daily 19:00 faire les exercices
/reminders
/delreminder rem-xxxxxxxxxx
/ask <question>
```

Tester l'API reminders sans envoyer de notification:

```bash
KEY=$(kubectl -n llm-agent get secret backend-api-key -o jsonpath='{.data.secret_key}' | base64 -d)

curl -sS -X POST http://agent-backend.192.168.2.88.nip.io/api/v1/reminders \
  -H "Authorization: Bearer ${KEY}" \
  -H 'Content-Type: application/json' \
  -d '{"userId":"telegram:test-e2e","chatId":"0","text":"test reminders","timeOfDay":"23:59"}'

curl -sS 'http://agent-backend.192.168.2.88.nip.io/api/v1/reminders?user_id=telegram%3Atest-e2e&active_only=true' \
  -H "Authorization: Bearer ${KEY}"
```

Supprimer le rappel de test:

```bash
RID=<reminder_id>
curl -sS -X DELETE "http://agent-backend.192.168.2.88.nip.io/api/v1/reminders/${RID}?user_id=telegram%3Atest-e2e" \
  -H "Authorization: Bearer ${KEY}"
```

Verifier le CronJob runner:

```bash
kubectl -n llm-agent get cronjob telegram-reminder-runner -o wide
kubectl -n llm-agent get jobs,pods -l app=telegram-reminder-runner -o wide
JOB=$(kubectl -n llm-agent get job -l app=telegram-reminder-runner --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1].metadata.name}')
kubectl -n llm-agent logs job/"$JOB" --tail=80
```

## Airflow DAGs

Copier les DAGs dans le PVC:

```bash
POD=$(kubectl -n airflow get pod -l component=dag-processor -o jsonpath='{.items[0].metadata.name}')
kubectl -n airflow cp apps/dags/. "$POD":/opt/airflow/dags/
kubectl -n airflow rollout restart deployment airflow-dag-processor
kubectl -n airflow rollout status deployment airflow-dag-processor --timeout=120s
```

Debug DAGs:

```bash
kubectl -n airflow logs deploy/airflow-scheduler --tail=160
kubectl -n airflow logs deploy/airflow-dag-processor --tail=160
kubectl -n airflow exec deploy/airflow-scheduler -- airflow dags list
```

## Monitoring

Grafana et Prometheus:

```bash
kubectl -n monitoring get pods,svc,ingressroute
kubectl -n monitoring logs deploy/monitoring-grafana --tail=120
kubectl -n monitoring get prometheus,servicemonitor,prometheusrule
```

Tester les routes:

```bash
curl -sS -o /tmp/grafana.out -w '%{http_code} %{content_type}\n' \
  -H 'Host: grafana.lan' http://192.168.2.88/

curl -sS -o /tmp/prometheus.out -w '%{http_code} %{content_type}\n' \
  -H 'Host: prometheus.lan' http://192.168.2.88/
```

Alertmanager Telegram:

```bash
kubectl -n monitoring get secret alertmanager-telegram-bot
kubectl -n monitoring logs statefulset/alertmanager-prometheus-alertmanager --tail=120
```


## Medplum et PostgreSQL

Medplum:

```bash
kubectl -n medplum get pods,svc,endpoints
kubectl -n medplum logs deploy/medplum-app --tail=160
kubectl -n medplum logs deploy/medplum-provider --tail=160
curl -sS -o /tmp/medplum.out -w '%{http_code} %{content_type}\n' https://medplum.phylcero.fr/
```

PostgreSQL Medplum:

```bash
POD=$(kubectl -n medplum get pod -l app.kubernetes.io/name=postgresql -o jsonpath='{.items[0].metadata.name}')
kubectl -n medplum exec -it "$POD" -c postgresql -- psql -U medplum -d medplum -c '\conninfo'
kubectl -n medplum exec -it "$POD" -c postgresql -- psql -U medplum -d medplum -c '\du'
```

PostgreSQL pompetrack-core:

```bash
POD=$(kubectl -n pompetrack-core get pod -l app=pompetrack-core-postgresql -o jsonpath='{.items[0].metadata.name}')
kubectl -n pompetrack-core exec -it "$POD" -- psql -U pompetrack -d pompetrack -c '\conninfo'
```

## pg-backups

```bash
kubectl -n pg-backups get cronjob,job,pod
kubectl -n pg-backups describe cronjob backup-db1
kubectl -n pg-backups logs job/<job-name> --tail=160
kubectl -n pg-backups get configmap backup-script -o yaml
kubectl -n pg-backups get secret backup-credentials -o yaml
```

## Istio

Sidecars injectes:

```bash
for ns in medplum pompetrack-core airflow monitoring llm-agent pg-backups; do
  echo "### $ns"
  kubectl -n "$ns" get pods -o jsonpath='{range .items[*]}{.metadata.name}{" => "}{range .spec.containers[*]}{.name}{" "}{end}{"\n"}{end}' | sort
done
```

Etat des proxies:

```bash
istioctl proxy-status 2>/dev/null || true
kubectl get ns --show-labels | egrep '^(NAME|medplum|pompetrack-core|airflow|monitoring|llm-agent|pg-backups|istio-system)'
kubectl get mutatingwebhookconfiguration | egrep -i 'istio|sidecar|inject' || true
```

Prouver si Istio est dans un pod:

```bash
NS=llm-agent
POD=$(kubectl -n "$NS" get pod -l app=agent-backend -o jsonpath='{.items[0].metadata.name}')

kubectl -n "$NS" get pod "$POD" -o jsonpath='{.spec.containers[*].name}{"\n"}'
kubectl -n "$NS" get pod "$POD" -o yaml | egrep -n 'name: istio-proxy|istio\.io|sidecar\.istio|proxyMetadata' || true
kubectl -n "$NS" describe pod "$POD" | egrep -n 'istio|envoy|proxy|sidecar' || true
```

## NetworkPolicies

Lister les policies:

```bash
for ns in medplum pompetrack-core airflow monitoring llm-agent pg-backups; do
  echo "### $ns"
  kubectl -n "$ns" get netpol
done
```

Debug d'un flux refuse:

```bash
kubectl -n <client-ns> get pod <client-pod> --show-labels
kubectl -n <server-ns> get pod <server-pod> --show-labels
kubectl -n <server-ns> get svc,endpoints <service-name> -o wide
kubectl -n <client-ns> exec -it <client-pod> -c <app-container> -- curl -v http://<service>.<server-ns>.svc.cluster.local:<port>/health
```

Modele mental:

```text
deny-all actif => il faut souvent deux regles:
1. egress du client vers le serveur
2. ingress du serveur depuis le client

cross-namespace => ajouter namespaceSelector + podSelector
Istio AuthorizationPolicy restrictive => autoriser aussi le serviceAccount source
```

## Images Docker

Build/push manuel:

```bash
docker build -t registry.phylcero.fr/garth/pompetrack/agent-backend:latest apps/agent-backend
docker push registry.phylcero.fr/garth/pompetrack/agent-backend:latest

docker build -t registry.phylcero.fr/garth/pompetrack/worker-fhir:latest apps/worker-fhir
docker push registry.phylcero.fr/garth/pompetrack/worker-fhir:latest
```

Verifier l'image tiree par un pod:

```bash
kubectl -n llm-agent get pod -l app=agent-backend -o jsonpath='{.items[0].status.containerStatuses[0].imageID}{"\n"}'
kubectl -n llm-agent rollout restart deploy/agent-backend deploy/agent-backend-mcpo deploy/telegram-health-bot
```

## Reset destructif

Ces commandes suppriment des donnees ou l'etat local du cluster. A utiliser seulement si c'est volontaire.

Desinstaller K3s:

```bash
sudo /usr/local/bin/k3s-uninstall.sh
sudo reboot
```

Vider le containerd local K3s:

```bash
sudo systemctl stop k3s
sudo rm -rf /var/lib/rancher/k3s/agent/containerd
sudo systemctl start k3s
```

Supprimer les releases applicatives:

```bash
helm -n pompetrack-core uninstall pompetrack-core || true
helm -n medplum uninstall medplum || true
helm -n airflow uninstall airflow || true
helm -n monitoring uninstall monitoring || true
helm -n llm-agent uninstall llm-agent || true

kubectl delete namespace pompetrack-core medplum airflow monitoring llm-agent pg-backups
```
