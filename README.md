# PompeTrack-K3S
Personal Pompe disease tracking application.

(originally recorded on my self-hosted Gitlab)

> Why doing that ?
I found the medical monitoring not really efficient. It is useful, but too light for tracking disease progression day after day.
So i make this app, and i add several metrics from my body, my strength, my symptoms, my treatments and my devices to track them over time.

> What will i track ?
I want to add "official" metrics from the hospital, body measures (to reveal muscle reduction), body strength (legs and arms for my disease) with a custom device, vital signs, spirometry, symptoms, medication, and all useful "Health" metrics from my *iPhone 12 mini*.

> How is the monitoring ?
By searching for health softwares, i found "FHIR" format which is an interoperability format, and finally found [Medplum](https://www.medplum.com/) which is the perfect "health-core" to record all data efficiently.

> What in that project ?
So i use [Medplum](https://www.medplum.com/) to have a serious health data format, Streamlit to ingest and visualize data, Airflow to orchestrate data pipelines, MinIO/PostgreSQL for storage, Prometheus/Grafana for monitoring, and a local LLM agent to provide health-coach summaries, Telegram interactions, and Open WebUI tools.

---
---
## Requirements :

### 1 - Global system :
* VM Ubuntu-server 24.04 (dedicated)
* `kubectl`, `helm`, `docker`
* K3s, Calico, Traefik, Istio and NFS/PVC storage
* Using K3s **without Flannel** :
    - If necessary delete K3S : *sudo /usr/local/bin/k3s-uninstall.sh*
    - K3s install without Flannel :

```bash
curl -sfL https://get.k3s.io | sh -s - server \
  --flannel-backend=none \
  --disable-network-policy
```

* If you've Permission issue on : *k3s.yaml*
```bash
sudo nano /etc/rancher/k3s/config.yaml
```

Write :
```bash
write-kubeconfig-mode: "0644"
```
Record, and close.

Restart K3S
```bash
sudo systemctl restart k3s
```

* Install a user on kubeconfig :
```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown "$USER":"$USER" ~/.kube/config
chmod 600 ~/.kube/config
```

* Verify :
```bash
kubectl get nodes -o wide
ip link | egrep -i 'flannel|cali|vxlan|cilium' || true
```

* Calico install (Helm)
```bash
helm repo add projectcalico https://docs.tigera.io/calico/charts
helm repo update
helm install calico projectcalico/tigera-operator --namespace tigera-operator --create-namespace
```

* Verify :
```bash
kubectl get pods -n tigera-operator
kubectl get pods -n calico-system
```
---
### 2 - Specific settings :

* Container registry 
In `apps/` folder you can found *specific* containers code that need to be built.
I use my personal Gitlab Registry to build and expose Docker images.
Gitlab CI file is : `.gitlab-ci.yml`

* Yunohost Domain :
My domain name `https://medplum.phylcero.fr` is managed by my personal **Yunohost** with tls management too.

* LAN routing :
Most internal UIs are exposed through Traefik `IngressRoute` objects on `.lan` hostnames and `192.168.2.88.nip.io` hostnames.

* Telegram :
The `llm-agent` namespace can use a Telegram bot token and allowed chat ids to expose health-coach commands and reminders.

---
---

## Architecture :

### 1. Description :

Six namespaces :
* medplum : installed by `helm umbrella` (official repo + local provider)
    - medplum API server
    - medplum-app (server UI)
    - medplum-provider (custom provider app)
    - postgresql 
    - redis
    - postgresql_exporter (added for monitoring)
    - redis_exporter (added for monitoring)

* pompetrack-core : includes specific containers from *registry*
    - minio (+ minio-init job)
    - ingestion -> custom Minio-api 
    - streamlit -> recording manual values and pains / data tracking graphs
    - worker-fhir -> transform raw data to fhir for medplum
    - worker-sqlite -> specific worker for spirometer device
    - worker-stream -> retrieve data for streamlit graphs
    - postgresql -> local reference database for streamlit/worker data

* airflow : installed by `helm umbrella`
    - orchestrator : detects if data are uploaded on minio and processes them
    - DAGs for iPhone, manual, medication, spirometer, sqlite and strength pipelines
    - postgresql -> dedicated postgresql
    - statsd -> airflow monitoring
    - postgresql_exporter (monitoring)

* monitoring : installed by `helm umbrella`
    - kube-prometheus-stack (official repo) :
      * alertmanager
      * grafana
      * prometheus
      * prometheus operator

* pg-backups : applied with Kubernetes manifests
    - CronJobs for PostgreSQL backups
    - backup scripts stored in ConfigMap
    - dedicated network policies to reach PostgreSQL databases and MinIO

* llm-agent : installed by `helm umbrella`
    - qdrant -> vector database for local RAG
    - searxng -> local web search backend
    - agent-backend -> OpenAI-compatible agent API and health-coach backend
    - agent-backend-mcpo -> MCP tools exposed as OpenAPI for Open WebUI
    - open-webui -> chat UI
    - streamlit-agent-llm -> admin/debug UI for the agent
    - telegram-health-bot -> Telegram bot for health-coach commands
    - health-coach-daily / health-coach-weekly CronJobs
    - health-evening-questions CronJob
    - telegram-reminder-runner CronJob for persistent daily reminders


> Global architecture graph :
[Archi_Cluster](docs/Archi_Cluster.md)



---
### 2. Network :
Here are specific network descriptions (AI realized)
- [Global architecture](docs/Archi_flux_1.md)
- [Network Policies](docs/Archi_flux_2.md)
- [Istio security](docs/Archi_flux_3.md)
- [Routage](docs/routage.md)
- [Telegram interactions](docs/telegram-interactions.md)
- [Operational tips](docs/tips.md)

---
### 3. Folders structure :

* `apps/` :
Like i said before, it contains specific containers and DAGs:
  - `ingestion` -> custom MinIO ingestion API
  - `streamlit` -> manual entries, graphs, calendar and health dashboards
  - `worker-fhir` -> FHIR conversion pipelines
  - `worker-sqlite` -> spirometer sqlite extraction
  - `worker-stream` -> data API for Streamlit
  - `agent-backend` -> LLM agent, MCP tools, health coach and Telegram bot
  - `streamlit-agent-llm` -> agent admin UI
  - `medplum-provider` -> custom Medplum provider app
  - `pg-backup` -> PostgreSQL backup image
  - `pgsql-pompetrack-core` -> local PostgreSQL bootstrap image
  - `dags` -> Airflow DAGs copied to the Airflow PVC

* `deploy`:
We can found 3 main folders : 
  - charts -> contains helm umbrellas for each namespaces 
  - namespaces -> contains **rules** (ingress, istio and netpol)
  - secrets -> order by namespaces

Others folders :
  - outputs -> contains `medplum-ids.env`, with Medplum client IDs required for OAuth between pods
  - post-renderer -> contains specific scripts to improve deployment
  - versions.sh / sync-medplum-version.sh -> synchronize Medplum chart/image versions

```bash
.
├── apps
│   ├── agent-backend
│   ├── dags
│   ├── ingestion
│   ├── medplum-provider
│   ├── pg-backup
│   ├── pgsql-pompetrack-core
│   ├── streamlit
│   ├── streamlit-agent-llm
│   ├── worker-fhir
│   ├── worker-sqlite
│   └── worker-stream
├── deploy
│   ├── apply.sh
│   ├── apply_airflow.sh
│   ├── apply_llm-agent.sh
│   ├── apply_monitoring.sh
│   ├── apply_pg-backups.sh
│   ├── apply_pompetrack-core.sh
│   ├── charts
│   │   ├── airflow
│   │   ├── llm-agent
│   │   ├── medplum
│   │   ├── monitoring
│   │   ├── pg-backups
│   │   └── pompetrack-core
│   ├── namespaces
│   │   ├── airflow
│   │   │   ├── ingress
│   │   │   ├── istio
│   │   │   └── netpol
│   │   ├── llm-agent
│   │   │   ├── ingress
│   │   │   ├── istio
│   │   │   └── netpol
│   │   ├── medplum
│   │   │   ├── ingress
│   │   │   ├── istio
│   │   │   ├── netpol
│   │   │   └── services
│   │   ├── monitoring
│   │   │   ├── ingress
│   │   │   ├── istio
│   │   │   └── netpol
│   │   ├── pg-backups
│   │   │   ├── istio
│   │   │   └── netpol
│   │   └── pompetrack-core
│   │       ├── ingress
│   │       ├── istio
│   │       └── netpol
│   ├── outputs
│   │   └── pompetrack-core
│   ├── post-renderer
│   │   ├── medplum
│   │   └── pompetrack-core
│   └── secrets
│       ├── airflow
│       ├── llm-agent
│       ├── medplum
│       ├── medplum-config
│       ├── monitoring
│       ├── pg-backups
│       ├── pompetrack-core
│       └── registry
├── docs
│   └── **
├── nfs
│   └── install.md
├── LICENSE
└── README.md
```

---
---
## Deployment :

I wanted an automatic and idempotent deployment, so i make a deployment script : `deploy/apply.sh`
It deploys all cluster in order, per namespace :
  - create namespace
  - apply pg-backups RBAC
  - apply Medplum services
  - applies netpol rules
  - applies istio rules
  - creates secrets
  - install or upgrade helm umbrellas
  - bootstrap Medplum client IDs
  - publish `medplum-ids` ConfigMaps
  - copy Airflow DAGs to the Airflow PVC
  - apply pg-backups CronJobs

Global deployment:

```bash
./deploy/apply.sh
```

Targeted deployment scripts also exist:

```bash
./deploy/apply_pompetrack-core.sh
./deploy/apply_llm-agent.sh
./deploy/apply_monitoring.sh
./deploy/apply_pg-backups.sh
```

After a code change in an app image, rebuild and push the image first, then run the matching Helm upgrade or apply script.

For the LLM agent namespace:

```bash
helm upgrade --install llm-agent deploy/charts/llm-agent \
  -f deploy/charts/llm-agent/values.yaml \
  -n llm-agent
```


* Secrets specificities :
each namespace secrets are initially `*.env` files, the script automatically transforms them into *Kubernetes* secrets
here are what we need :

```bash
deploy/secrets/
├── airflow
│   ├── airflow-admin.env
│   ├── airflow-api-secret-key.env
│   ├── airflow-connections.env
│   ├── airflow-fernet-key.env
│   ├── airflow-git-https.env
│   ├── airflow-medplum-client.env
│   ├── airflow-metadata.env
│   ├── airflow-postgresql-auth.env
│   ├── airflow-webserver-secret-key.env
│   ├── init-secrets.sh
│   └── minio-airflow-logs-creds.env
├── medplum
│   ├── init-secrets.sh
│   ├── medplum-superadmin.env
│   ├── minio-medplum-credentials.env
│   ├── patient-infos.env
│   ├── pompetrack-postgres-auth.env
│   ├── practitioner-infos.env
│   ├── provider-medplum-client.env
│   ├── recaptcha-secret-key.env
│   └── recaptcha-site-key.env
├── llm-agent
│   ├── agent-medplum-client.env
│   ├── backend-api-key.env
│   ├── init-secrets.sh
│   ├── open-webui-key.env
│   └── telegram-bot.env
├── medplum-config
│   ├── devices.json
│   └── generate-worker-fhir-medplum-client.sh
├── monitoring
│   ├── alertmanager-telegram-bot.env
│   ├── grafana-admin-secret.env
│   ├── init-secrets.sh
│   └── minio-prom-credentials.env
├── pg-backups
│   └── secret.yaml
├── pompetrack-core
│   ├── ingestion-medplum-client.env
│   ├── init-secrets.sh
│   ├── light-jwt-secret.env
│   ├── medplum-client-ids.env
│   ├── minio-airflow-logs-creds.env
│   ├── minio-app-creds.env
│   ├── minio-console-creds.env
│   ├── minio-medplum-credentials.env
│   ├── minio-pg-creds.env
│   ├── minio-prom-credentials.env
│   ├── minio-root.env
│   ├── postgresql-auth.env
│   ├── streamlit-medplum-client.env
│   ├── worker-fhir-medplum-client.env
│   ├── worker-sqlite-medplum-client.env
│   └── worker-stream-medplum-client.env
└── registry
    ├── init-secrets.sh
    └── registry-token.env
```






