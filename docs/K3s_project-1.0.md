# PompeTrack – Cartographie namespaces, mapping Compose→Kubernetes, rôle d’Istio

> Basé sur :
> * le projet Compose
> * le descriptif fonctionnel (presentation_V1.md)
> * le schéma V1.5 (PompeTrack-V1.pdf)

---

## 1- Ce que “namespace” veut dire :

Un **namespace** Kubernetes est une **frontière logique** pour :

* organiser les objets (Deployments, Services, Jobs, Secrets, etc.)
* appliquer des règles (RBAC, quotas, NetworkPolicies)
* appliquer des règles Istio (mTLS, AuthorizationPolicy) par “zone”

✅ Un namespace regroupe en général **plusieurs** composants qui vont ensemble (un “domaine fonctionnel”).

---

## 2- Cartographie recommandée des namespaces (PompeTrack)

### A. `istio-system`

* Istio control-plane (istiod)
* (optionnel plus tard) addons Istio

### B. `medplum`

**Domaine : dossier médical / FHIR**

* `medplum-server` (API FHIR)
* `medplum-app` (UI)
* `medplum-chart` (si encore utilisé)
* `postgres` (BDD Medplum)
* `redis`

### C. `pompetrack-core`

**Domaine : ingestion + stockage objet + services cœur**

* `ingestion` (FastAPI : endpoints d’upload/download vers MinIO, entrypoint “data in”)
* `minio` (buckets raw/processed/reports, etc.)
* `minio-init-job` (Job/CronJob)
* `streamlit` (UI entrées manuelles / UI suivi des données)

### D. `pompetrack-workers`

**Domaine : traitements batch / ETL**

* `worker-fhir` (convert → FHIR → push Medplum)
* `worker-stream` (lecture Medplum → renvoi vers Streamlit)
* `worker-sqlite` (sqlite spiromètre → json normalisé)

### E. `orchestration`

**Domaine : orchestration / scheduling**

* `airflow` (webserver/scheduler/workers)
* `postgres` BDD Airflow (Postgres dédiée)
* `flower`

### F. `observability`

**Domaine : supervision**

* `prometheus`
* `grafana`
* `cAdvisor`
* `node_exporter`
* `postgres_exporter`
* `redis_exporter`
* `statsd-exporter`
* (optionnel) Loki/Tempo plus tard

### G. `security`

**Domaine : secrets / auth / infra**

* `vault` 
* autres composants de sécurité si tu en ajoutes

---

## 3- Correspondance Docker Compose → Kubernetes

### Table de conversion “concepts”

* **service Compose** → **Deployment** (ou StatefulSet) + **Service (ClusterIP)**
* **container** → **container dans un Pod**
* **réseau Compose** → **réseau cluster + DNS + Services**
* **depends_on** → **readiness/liveness + initContainers + retries**
* **volumes** → **PVC (PersistentVolumeClaim)**
* **env / secrets** → **ConfigMap / Secret**
* **cron** → **CronJob**

### Mapping “tes composants”

#### Entrées utilisateur / UI

* Streamlit (UI + upload mesures + dashboards)

  * K3s : Deployment `streamlit` + Service `streamlit`
  * Namespace : `pompetrack-core`

#### Ingestion

* `ingestion` (FastAPI + Gunicorn)

  * K3s : Deployment `ingestion` + Service `ingestion`
  * Namespace : `pompetrack-core`

#### Stockage objet

* MinIO

  * K3s : StatefulSet `minio` + Service `minio`
  * Buckets init : Job/CronJob `minio-init`
  * Namespace : `pompetrack-core`

#### Orchestration

* Airflow / flower

  * K3s : chart Helm ou manifests : Deployments + Services + PVC
  * Namespace : `orchestration`

#### Workers

* `worker-fhir`, `worker-stream`, `worker-sqlite`

  * K3s : Deployments
  * Namespace : `pompetrack-workers`

#### FHIR / Dossier médical

* Medplum server/app (+ chart)

  * K3s : umbrella Helm Medplum 
  * Namespace : `medplum`

#### Bases de données

* PostgreSQL

  * K3s : StatefulSet + PVC
  * Namespace : `medplum` (pour Medplum) et `orchestration` (pour Airflow)

#### Redis 

* Redis

  * K3s : Deployment/StatefulSet + Service
  * Namespace : `medplum` (umbrella helm)

#### Observabilité

* Prometheus / Grafana

  * K3s : charts Helm (kube-prometheus-stack)
  * Namespace : `observability`

* `cAdvisor`, `node_exporter`, `postgres_exporter`, `redis_exporter`, `statsd-exporter`

  * K3s : Jobs
  * Namespace : `observability`

---

## 4- Où Istio intervient (et où il n’intervient pas)

### Istio intervient (objectif)

#### 4.1 Chiffrement + identité **entre Pods** (east-west)

* Tout trafic **service-to-service** entre namespaces peut être automatiquement en mTLS.
* Liste des communications :

  * `streamlit` → `ingestion`
  * `ingestion` → `minio`
  * `worker-fhir` → `ingestion` (pour parler à MinIO via l’API ingestion)
  * `worker-fhir` → `medplum-server`
  * `worker-stream` → `medplum-server`
  * `streamlit` → `worker-stream`
  * `medplum-app` → `medplum-server`
  * `medplum-server` → `postgres`
  * `medplum-server` → `redis`
  * `airflow` → `ingestion`
  * `sqlite` → `ingestion`
  * `prometheus` → `grafana`
  * `prometheus` → `cadvisor`
  * `prometheus` → `node_exporter`
  * `prometheus` → `postgres_exporter`
  * `prometheus` → `flower`
  * `prometheus` → `redis_exporter`
  * `prometheus` → `statsd-exporter`
  * `node_exporter` → `??`
  * `postgres_exporter` → `postgres` (medplum)
  * `postgres_exporter` → `postgres-arflow`
  * `flower` → `airflow`
  * `redis_exporter` → `redis`
  * `statsd-exporter` → `airflow`

#### 4.2 Politiques d’accès (qui a le droit de parler à qui)

Avec `AuthorizationPolicy`, tu peux dire :

* seul `pompetrack-workers/worker-fhir` a le droit d’appeler `medplum/medplum-server`
* seul `pompetrack-core/streamlit` a le droit d’appeler `pompetrack-workers/worker-stream`

#### 4.3 Observabilité de trafic

* métriques, latences, erreurs par service

### Istio n’intervient pas (ou pas automatiquement)

#### 4.4 TLS “internet → cluster” (north-south)

* Ton TLS externe est géré par **Yunohost + Traefik** aujourd’hui.
* Istio n’est pas obligatoire ici.
* Tu peux garder Traefik comme Ingress public.

#### 4.5 Auth applicative (JWT “utilisateur”)

* Istio ne remplace pas tes JWT applicatifs.
* Istio sécurise **les services entre eux**.
* Les JWT restent utiles pour :

  * sessions utilisateur
  * permissions métier
  * API publiques

#### 4.6 Stockage / buckets / BDD

* Istio ne gère pas tes backups, tes schémas Postgres, tes buckets MinIO.

---

## 5- Flux principaux (résumé lisible)

### Ingestion de données

1. iPhone / fichiers / UI Streamlit → `pompetrack-core/ingestion`
2. `ingestion` → MinIO (raw-iphone, raw-manual, raw-db-spirometer, etc.)

### Traitements

3. Airflow (`orchestration`) détecte fichiers → déclenche workers (`pompetrack-workers`)
4. `worker-sqlite` : sqlite → json normalisé → MinIO raw-spirometer
5. `worker-fhir` : json → FHIR → `medplum/medplum-server` + (optionnel) MinIO processed-fhir

### Restitution

6. Streamlit → `worker-stream`
7. `worker-stream` → `medplum-server` → renvoie à Streamlit pour graphes

---

## 6- Règle d’or (pour ne pas se perdre)

* Namespace = “domaine fonctionnel” (pas un container)
* Deployment = “comment tourner”
* Pod = “ce qui tourne réellement”
* Service = “nom DNS stable pour joindre des pods”
* Istio = “sécuriser + observer le trafic entre services”

---

## 7- Références (officielles, schémas)

* Kubernetes – Namespaces : [https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/](https://kubernetes.io/docs/concepts/overview/working-with-objects/namespaces/)
* Kubernetes – Services & networking : [https://kubernetes.io/docs/concepts/services-networking/](https://kubernetes.io/docs/concepts/services-networking/)
* Istio – Architecture : [https://istio.io/latest/docs/ops/deployment/architecture/](https://istio.io/latest/docs/ops/deployment/architecture/)
