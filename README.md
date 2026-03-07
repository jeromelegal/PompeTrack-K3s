=======
# PompeTrack-K3S
Personal Pompe disease tracking application

(originaly recorded on my self-hosted Gitlab)

> Why doing that ?
I found the medical monitoring not really efficient, i mean it's light, and i can't track the disease progression.
So i make this app, and i will add several metrics from my body and my strenght to track in time.

> What will i track ?
I want to add "official" metrics from the hospital, body measures (to reveal muscles reduction), body strenght (legs and arms for my disease) with a custom device, vital-signs, and all "Health" metrics from my *iPhone 12 mini*.

> How is the monitoring ?
By searching for heath softwares, i found "FHIR" format which is an interoperability format, and finally found [Medplum](https://www.medplum.com/) which is the perfect "health-core" to record all data efficiently.

> What in that project ?
So i use [Medplum](https://www.medplum.com/) to have a serious health data format, Streamlit to ingest data in the app and Streamlit to realize tracking by graphs.

---
---
## Requirements :

### 1 - Global system :
* VM Ubuntu-server 24.04 (dedicated)
* Using K3s **without Flannel** :
    - If necessery delete K3S : *sudo /usr/local/bin/k3s-uninstall.sh*
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

* Yunohot Domain :
My domain name `https://medplum.phylcero.fr` is managed by my personal **Yunohost** with tls management too.

---
---

## Architecture :

### 1. Description :

Four namespaces :
* mepdlum : installed by `helm umbrella` (official repo)
    - medplum-server
    - medplum-app (server UI)
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
    - worker-stream -> retrieve datas for streamlit graphs

* airflow : installed by `helm umbrella`
    - orchestrator : detects if data are uploaded on minio and processes them
    - 4 DAGS
    - postgresql -> dedicated postgresql
    - statsd -> airflow monitoring
    - postgresql_exporter (monitoring)

* monitoring : installed by `helm umbrella`
    - kube-prometheus-stack (official repo) :
      * alertmanager
      * grafana
      * prometheus
      * prometheus operator


> Global architecture graph :
[Archi_Cluster](docs/Archi_Cluster.md)



---
### 2. Network :
Here are specific network descriptions (AI realized)
- [Global architecture](docs/Archi_flux_1.md)
- [Network Policies](docs/Archi_flux_2.md)
- [Istio security](docs/Archi_flux_3.md)
- [Routage](docs/routage_TO_IMPROVE.md)

---
### 3. Folders structure :

* `apps/` :
Like i said before, it contains specific containers.

* `deploy`:
We can found 3 main folders : 
  - charts -> contains helm umbrellas for each namespaces 
  - namespaces -> contains **rules** (ingress, istio and netpol)
  - secrets -> order by namespaces

Others folders :
  - outputs -> only one file `medplum-ids.env`, contains containers medplum IDs which are required for OAUTh between each pods
  - post-renderer -> contains specific scripts to improve deployment

```bash
.
├── apps
│   └── *containers*
├── deploy
│   ├── apply.sh
│   ├── charts
│   │   ├── airflow
│   │   │   ├── Chart.lock
│   │   │   ├── charts
│   │   │   │   └── **
│   │   │   ├── Chart.yaml
│   │   │   ├── templates
│   │   │   │   └── **
│   │   │   └── values.yaml
│   │   ├── medplum
│   │   │   ├── Chart.lock
│   │   │   ├── charts
│   │   │   │   └── **
│   │   │   ├── Chart.yaml
│   │   │   ├── templates
│   │   │   │   └── **
│   │   │   └── values.yaml
│   │   ├── monitoring
│   │   │   ├── Chart.lock
│   │   │   ├── charts
│   │   │   │   └── **
│   │   │   ├── Chart.yaml
│   │   │   ├── templates
│   │   │   │   └── **
│   │   │   └── values.yaml
│   │   └── pompetrack-core
│   │       ├── charts
│   │       │   └── **
│   │       ├── Chart.yaml
│   │       ├── templates
│   │       │   └── **
│   │       └── values.yaml
│   ├── namespaces
│   │   ├── airflow
│   │   │   ├── 00-namespace.yaml
│   │   │   ├── ingress
│   │   │   │   └── **
│   │   │   ├── istio
│   │   │   │   └── **
│   │   │   └── netpol
│   │   │       └── **
│   │   ├── medplum
│   │   │   ├── 00-namespace.yaml
│   │   │   ├── ingress
│   │   │   │   └── **
│   │   │   ├── istio
│   │   │   │   └── **
│   │   │   ├── netpol
│   │   │   │   └── **
│   │   │   └── services
│   │   │       └── **
│   │   ├── monitoring
│   │   │   ├── 00-namespace.yaml
│   │   │   ├── ingress
│   │   │   │   └── **
│   │   │   ├── istio
│   │   │   │   └── **
│   │   │   └── netpol
│   │   │       └── **
│   │   └── pompetrack-core
│   │       ├── 00-namespace.yaml
│   │       ├── ingress
│   │       │   └── **
│   │       ├── istio
│   │       │   └── **
│   │       └── netpol
│   │           └── **
│   ├── outputs
│   │   └── pompetrack-core
│   │       └── **
│   ├── post-renderer
│   │   ├── medplum
│   │   │   └── **
│   │   └── pompetrack-core
│   │       └── **
│   └── secrets
│       ├── airflow
│       │   └── **
│       ├── medplum
│       │   └── **
│       ├── medplum-config
│       │   └── **
│       ├── monitoring
│       │   └── **
│       ├── pompetrack-core
│       │   └── **
│       └── registry
│           └── **
├── docs
│   └── **
├── LICENSE
└── README.md
```

---
---
## Deployment :

I wanted an automatic and idempotent deployment, so i make a deployment script : `deploy/apply.sh`
It deploys all cluster in order, per namespace :
  - create namespace
  - applies netpol rules
  - applies istio rules
  - creates secrets
  - install helm umbrella


* Secrets specificities :
each namespace secrets are initialy `*.env` file, the script automaticaly transform them in *Kubernetes* secrets
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
│   ├── pompetrack-postgres-auth.env
│   ├── recaptcha-secret-key.env
│   └── recaptcha-site-key.env
├── medplum-config
│   └── generate-worker-fhir-medplum-client.sh
├── monitoring
│   ├── grafana-admin-secret.env
│   ├── init-secrets.sh
│   └── minio-prom-credentials.env
├── pompetrack-core
│   ├── ingestion-medplum-client.env
│   ├── init-secrets.sh
│   ├── medplum-client-ids.env
│   ├── minio-airflow-logs-creds.env
│   ├── minio-app-creds.env
│   ├── minio-console-creds.env
│   ├── minio-pg-creds.env
│   ├── minio-prom-credentials.env
│   ├── minio-root.env
│   ├── streamlit-medplum-client.env
│   ├── worker-fhir-medplum-client.env
│   ├── worker-sqlite-medplum-client.env
│   └── worker-stream-medplum-client.env
└── registry
    ├── init-secrets.sh
    └── registry-token.env
```










