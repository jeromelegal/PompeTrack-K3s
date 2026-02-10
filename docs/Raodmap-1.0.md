# PompeTrack K3s — Roadmap Checklist

Date checkpoint : 2026-02-08  
Cluster : K3s (VM "medplum" : 192.168.2.88)  
TLS : géré par Yunohost (reverse proxy vers la VM)  
Namespaces présents : `medplum`, `pompetrack-core`, `calico-system`, `istio-system`, `tigera-operator`  
État : 
- les TLS sont gérés par Yunohost qui redirige vers la VM 'medplum' : 192.168.2.88
- umbrella helm pour installation de medplum-server, medplum-app, postgres, redis
- meplum-server opérationnel sous api.phylcero.fr
- medplum-app opérationnel sous app.phylcero.fr
- reCAPTCHA google opérationnel
- Minio déployé et fonctionnel
- minio-init-job qui créé les buckets au boot
- NetworkPolicy appliquée : deny-all sauf DNS, accès medplum sur Yunohost, accès minio console sur LAN
- istio installé mais non présent sur namespace

---

## 0) Pre-flight (à refaire avant chaque grosse étape)

### 0.1 — Contexte kubectl
- [ ] Vérifier le contexte
```bash
kubectl config current-context
kubectl get nodes -o wide
````

### 0.2 — État des namespaces et workloads

* [ ] Vérifier les namespaces

```bash
kubectl get ns
```

* [ ] Vérifier les pods clés (adapter si besoin)

```bash
kubectl -n medplum get pods -o wide
kubectl -n pompetrack-core get pods -o wide
kubectl -n istio-system get pods -o wide
```

### 0.3 — “Brique réseau” (Calico) et policies

* [ ] Vérifier que Calico tourne

```bash
kubectl -n calico-system get pods -o wide
kubectl -n tigera-operator get pods -o wide
```

* [ ] Lister les NetworkPolicies (état actuel)

```bash
kubectl -n medplum get netpol
kubectl -n pompetrack-core get netpol
```

---

## Phase A — Stabiliser la plateforme (sécurité + “qui parle à qui”)

### A1 — Inventaire des flux (source → cible)

Objectif : produire une liste simple des flux autorisés.

* [ ] Flux “déjà OK” (checkpoint)

  * Yunohost → (Traefik/Ingress) → `medplum-server` (`api.phylcero.fr`)
  * Yunohost → (Traefik/Ingress) → `medplum-app` (`app.phylcero.fr`)
  * MinIO (console) accessible LAN-only
  * DNS egress autorisé
  * Tout le reste : deny-all

Critère de validation :

* [ ] Tu peux expliquer en 30 secondes quels flux sont autorisés et pourquoi.

---

### A2 — Secrets : standardisation + visibilité

Objectif : tous les secrets nécessaires existent, nommés proprement, et utilisés via envFrom/secretKeyRef.

* [ ] Lister les secrets (inventaire)

```bash
kubectl -n medplum get secret
kubectl -n pompetrack-core get secret
```

* [ ] Vérifier les références aux secrets dans les deployments/statefulsets

```bash
kubectl -n medplum get deploy,sts -o yaml | grep -n "secretKeyRef" -n
kubectl -n pompetrack-core get deploy,sts -o yaml | grep -n "secretKeyRef" -n
```

Critère de validation :

* [ ] Aucun mot de passe en clair dans des manifests appliqués.
* [ ] Tous les pods critiques démarrent sans “missing key in secret”.

Option “rollout auto sur changement de secret” (si tu continues sur checksums) :

* [ ] Les Deployments concernés ont une annotation checksum (pattern maison).

---

### A3 — Backups (à planifier tôt, tester plus tard)

Objectif : définir la stratégie même si tu n’implémentes pas encore.

* [ ] Décider : backups PostgreSQL vers MinIO (bucket `backups/`) OU volume local + export.
* [ ] Lister les PV/PVC pour postgres (si PVC)

```bash
kubectl -n medplum get pvc -o wide
```

Critère de validation :

* [ ] Un chemin de backup est défini (même si pas encore automatisé).

---

## Phase B — Déployer les composants “PompeTrack” manquants (sans casser Medplum)

> Stratégie : on déploie d’abord les services, on valide les flux **sans Istio strict**, puis on mesh progressivement.

### B1 — Namespace(s) de travail

Objectif : ranger proprement.

* [ ] Confirmer que tout ce qui n’est pas Medplum va dans `pompetrack-core` au début.

```bash
kubectl get ns pompetrack-core
```

Critère de validation :

* [ ] Pas de nouveaux services “produit” dans `medplum` (sauf dépendances Medplum).

---

### B2 — Déployer `ingestion` (FastAPI)

Objectif : un service interne qui parle à MinIO et orchestre l’entrée des fichiers.

* [ ] Déployer `ingestion` (Deployment + Service ClusterIP)
* [ ] Ajouter une route Ingress (si besoin exposée)
* [ ] Ajouter NetPol minimale (ingress depuis streamlit / egress vers MinIO + DNS)

Commandes de validation :

```bash
kubectl -n pompetrack-core get deploy,svc,pods -o wide
kubectl -n pompetrack-core describe deploy ingestion
kubectl -n pompetrack-core logs deploy/ingestion --tail=200
```

Test fonctionnel (exemple) :

* [ ] Port-forward et test health

```bash
kubectl -n pompetrack-core port-forward svc/ingestion 8081:<PORT_SVC>
curl -i http://127.0.0.1:8081/health || true
```

Critères de validation :

* [ ] `ingestion` Ready=1/1
* [ ] Accès MinIO OK (via logs ou endpoint de test)
* [ ] NetPol ne bloque pas les flux prévus

---

### B3 — Déployer `streamlit` (UI)

Objectif : UI qui upload et affiche.

* [ ] Déployer `streamlit` (Deployment + Service)
* [ ] Route Ingress (si tu veux l’exposer via Yunohost/TLS)
* [ ] NetPol : `streamlit` → `ingestion` (+ DNS)

Validation :

```bash
kubectl -n pompetrack-core get pods -o wide
kubectl -n pompetrack-core logs deploy/streamlit --tail=200
```

Critères :

* [ ] UI accessible
* [ ] Upload déclenche bien un appel à `ingestion`

---

### B4 — Déployer `worker-stream`

Objectif : traitement/visualisation (Streamlit → worker-stream → Medplum).

* [ ] Déployer worker (Deployment + Service ClusterIP)
* [ ] Secrets (token Medplum, config)
* [ ] NetPol : streamlit → worker-stream, worker-stream → medplum-server, + DNS

Validation :

```bash
kubectl -n pompetrack-core logs deploy/worker-stream --tail=200
```

Critères :

* [ ] Le worker peut joindre `medplum-server` (HTTP 200 sur endpoint cible)
* [ ] Les scopes/perms Medplum sont corrects (pas de 401/403)

---

### B5 — Déployer `orchestration` (Airflow)

Objectif : scheduler de pipeline (worker-sqlite, worker-fhir).

* [ ] Déployer Airflow (stack minimale)
* [ ] Metrics/logs OK
* [ ] NetPol : Airflow → workers (+ DNS)

Validation :

```bash
kubectl -n <NS_AIRFLOW> get pods -o wide
kubectl -n <NS_AIRFLOW> logs <POD> --tail=200
```

Critères :

* [ ] UI Airflow accessible (option)
* [ ] DAG “pompe-pipeline” visible et “triggerable”

---

### B6 — Déployer `worker-sqlite` + `worker-fhir`

Objectif : transformer source (spiromètre sqlite) → JSON → FHIR → push Medplum.

* [ ] Déployer les 2 workers
* [ ] NetPol :

  * worker-sqlite → MinIO (+ DNS)
  * worker-fhir → MinIO + medplum-server (+ DNS)

Validation :

```bash
kubectl -n pompetrack-core logs deploy/worker-sqlite --tail=200
kubectl -n pompetrack-core logs deploy/worker-fhir --tail=200
```

Critères :

* [ ] JSON généré et stocké (MinIO)
* [ ] FHIR push OK (Medplum reçoit des ressources attendues)

---

## Phase C — Istio : activer progressivement (commencer par `pompetrack-core`)

> Important : utilisation de “revision-based” : `istio.io/rev=default`.

---

### C1 — Activer l’injection sur `pompetrack-core` (seulement)

* [ ] Activer injection

```bash
kubectl label namespace pompetrack-core istio.io/rev=default --overwrite
kubectl label namespace pompetrack-core istio-injection- 2>/dev/null || true
kubectl get ns pompetrack-core -L istio-injection -L istio.io/rev
```
Attendu : REV=default

* [ ] Redémarrer les pods du namespace pour injecter

```bash
kubectl -n pompetrack-core rollout restart deploy
kubectl -n pompetrack-core rollout restart statefulset 2>/dev/null || true
kubectl -n pompetrack-core get pods -w
```

Validation :

* [ ] Chaque pod a 2 containers (app + istio-proxy)

```bash
kubectl -n pompetrack-core get pods \
  -o jsonpath='{range .items[*]}{.metadata.name}{" => "}{range .spec.containers[*]}{.name}{" "}{end}{"\n"}{end}'
```

Critères :

* [ ] `istio-proxy` présent partout dans `pompetrack-core`
* [ ] Pas de crashloops liés réseau/probes

Vérification que la "data plane" Istio voit tes pods

Si `istioctl` est dispo :

```bash
istioctl proxy-status
istioctl analyze -n pompetrack-core
```

Si `istioctl` n'est pas dispo, on peut déjà valider via :

```bash
kubectl -n pompetrack-core describe pod <UN_POD> | grep -i sidecar -n || true
kubectl -n pompetrack-core logs <UN_POD> -c istio-proxy --tail=50
```

---

### C2 — mTLS : PERMISSIVE d’abord

Objectif : observer sans tout casser.

* [ ] Appliquer PeerAuthentication PERMISSIVE (namespace `pompetrack-core`)

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: pompetrack-core
spec:
  mtls:
    mode: PERMISSIVE
```

Validation :

* [ ] Les flux existants fonctionnent toujours (streamlit↔ingestion, workers↔medplum)
* [ ] Pas d’explosion de 503 côté mesh

---

### C3 — Passer en STRICT quand tout le namespace est maillé

* [ ] Passer PeerAuthentication en STRICT

```yaml
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata:
  name: default
  namespace: pompetrack-core
spec:
  mtls:
    mode: STRICT
```

Validation :

* [ ] Toujours OK fonctionnellement
* [ ] Plus aucun pod “hors mesh” dans `pompetrack-core`

---

### C4 — AuthorizationPolicy : démarrer simple

Objectif : réduire la surface : “seuls X peuvent appeler Y”.

Exemples (à adapter à tes labels réels) :

* [ ] Autoriser `streamlit` → `ingestion` uniquement
* [ ] Autoriser `worker-stream` → `medplum-server`
* [ ] Autoriser `ingestion` → `minio`

⚠️ Prérequis : avoir des labels stables (app.kubernetes.io/name, etc.).
Découverte labels :

```bash
kubectl -n pompetrack-core get pod --show-labels
kubectl -n medplum get pod --show-labels
```

Critère :

* [ ] Une fois les policies en place, un pod non autorisé ne peut plus joindre la cible (test curl interne).

---

### C5 — Étendre Istio à d’autres namespaces (après validation)

Ordre recommandé :

1. `pompetrack-core`
2. `pompetrack-workers` (si tu le sépares)
3. `orchestration` (Airflow)
4. `medplum` en dernier

Critère :

* [ ] Chaque extension se fait namespace par namespace, avec rollback possible.

---

## Phase D — Backups & Restore (preuve de solidité)

### D1 — CronJob backup PostgreSQL

* [ ] Déployer CronJob qui dump Postgres vers MinIO (ou stockage défini)
* [ ] Vérifier exécution + présence des dumps

Validation :

```bash
kubectl -n medplum get cronjob
kubectl -n medplum get job --sort-by=.metadata.creationTimestamp
kubectl -n medplum logs job/<JOB_NAME> --tail=200
```

Critère :

* [ ] Au moins 1 dump exploitable existe.

### D2 — Test de restauration (le “vrai” test)

* [ ] Restaurer dans une DB de test OU environnement de test
* [ ] Vérifier que Medplum redémarre et retrouve les données

Critère :

* [ ] Tu peux refaire la procédure en “runbook” sans improvisation.

---

## Commandes utiles (debug rapide)

### Pods / events / logs

```bash
kubectl -n <NS> get pods -o wide
kubectl -n <NS> describe pod <POD>
kubectl -n <NS> logs <POD> -c <CONTAINER> --tail=200
kubectl -n <NS> get events --sort-by=.lastTimestamp | tail -n 30
```

### Tester DNS depuis un namespace

```bash
kubectl -n <NS> run -it --rm dnsutils --image=registry.k8s.io/e2e-test-images/jessie-dnsutils:1.3 --restart=Never -- nslookup kubernetes.default
```

### Tester un service interne

```bash
kubectl -n <NS> run -it --rm curl --image=curlimages/curl:8.6.0 --restart=Never -- \
  curl -sS -i http://<SERVICE>.<NS>.svc.cluster.local:<PORT>/health || true
```

### Istio (si istioctl dispo)

```bash
istioctl proxy-status || true
istioctl analyze -n pompetrack-core || true
```

---

## Définition “DONE” globale (PompeTrack sur K3s)

* [ ] Upload via Streamlit → ingestion OK
* [ ] Ingestion stocke dans MinIO OK
* [ ] Pipeline orchestration déclenche workers OK
* [ ] worker-sqlite produit JSON OK
* [ ] worker-fhir push Medplum OK
* [ ] Réseau : NetPol deny-all + exceptions OK
* [ ] Istio : mTLS STRICT sur namespaces PompeTrack OK
* [ ] Authz Istio : seuls flux nécessaires autorisés
* [ ] Backups + restore testés (preuve)




