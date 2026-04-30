## Uninstall K3s :
```bash
sudo /usr/local/bin/k3s-uninstall.sh
sudo reboot
```
---

## Install K3s :
```bash
 curl -sfL https://get.k3s.io | sh -s - server   --flannel-backend=none   --disable-network-policy
 sudo nano /etc/rancher/k3s/config.yaml
```

 sudo systemctl restart k3s
 mkdir -p ~/.kube
 sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
 sudo chown "$USER":"$USER" ~/.kube/config
 chmod 600 ~/.kube/config

---
## Supprimer TOUT sur K3s et partir vraiment de 0:

```bash
sudo systemctl stop k3s
sudo rm -rf /var/lib/rancher/k3s/agent/containerd
sudo systemctl start k3s
```


---
## Repartir à 0 :

```bash
helm -n pompetrack-core uninstall pompetrack-core || true
helm -n medplum uninstall medplum || true
helm -n airflow uninstall airflow || true
helm -n monitoring uninstall monitoring || true
kubectl delete namespace pompetrack-core
kubectl delete namespace medplum
kubectl delete namespace airflow
kubectl delete namespace monitoring
kubectl delete namespace pg-backups

./deploy/apply.sh

./deploy/apply_airflow.sh
kub 
kubectl get all -n medplum
kubectl get all -n pompetrack-core
```

```bash
helm upgrade monitoring prometheus-community/kube-prometheus-stack   -n monitoring   -f deploy/charts/monitoring/values.yaml
```

---
# DAGS Airflow :

1. éditer les dags dans `apps/dags/`

2. copie des fichiers dans le PVC par le dag-processor :
```bash
POD=$(kubectl -n airflow get pod -l component=dag-processor -o jsonpath='{.items[0].metadata.name}')
kubectl -n airflow cp apps/dags/. $POD:/opt/airflow/dags/
```

3. restart le dag-processor :
```bash
kubectl -n airflow rollout restart deployment airflow-dag-processor
```

---
# Commande **magique** pour trouver les configs par défaut des charts helm :

Exemple pour Airflow
```bash
helm show values apache-airflow/airflow > default-values.yaml
```

## Open WebUI tools via mcpo

L'agent backend expose aussi ses outils internes en serveur MCP stdio:

```bash
python -m app.mcp_server
```

Le chart `llm-agent` lance `agent-backend-mcpo`, qui enveloppe ce serveur avec `mcpo` et publie un serveur OpenAPI compatible avec l'onglet Tools d'Open WebUI:

```text
http://agent-backend-mcpo:8000
```

Pour un tool server global, ajoute-le dans Open WebUI depuis Admin Settings -> Tools:

1. Ajouter un serveur de type OpenAPI.
2. Utiliser l'URL interne `http://agent-backend-mcpo:8000`.
3. Configurer l'authentification avec la meme valeur que le secret Kubernetes `backend-api-key`.
4. Dans un chat, ouvrir + -> Integrations -> Tools et activer les outils de l'agent.

Pour un tool server utilisateur ajoute depuis Settings -> Tools, les requetes partent du navigateur. Il faut donc utiliser l'URL exposee par Traefik, pas le DNS Kubernetes:

```text
http://agent-tools.192.168.2.88.nip.io
```

Dans ce mode:

1. Ajouter un serveur de type OpenAPI.
2. Utiliser `http://agent-tools.192.168.2.88.nip.io`.
3. Configurer l'authentification avec la meme valeur que le secret Kubernetes `backend-api-key`.
4. Dans un chat, ouvrir + -> Integrations -> Tools et activer les outils de l'agent.

Les outils exposes sont `web_search`, `scrape_url`, `rag_search`, `workspace_list` et `workspace_read`.

Attention: les Tools Open WebUI sont optionnels. Le modele peut les ignorer, et certains modeles gerent mal le tool calling. Pour utiliser le backend agentique complet, configure aussi l'agent comme provider OpenAI-compatible avec l'URL interne:

```text
http://agent-backend:8000/v1
```

Si l'URL est saisie depuis un ecran utilisateur qui appelle depuis le navigateur, utiliser plutot l'URL Traefik:

```text
http://agent-backend.192.168.2.88.nip.io/v1
```

Les modeles exposes par ce provider sont prefixes par `agent-` pour les distinguer des modeles Ollama directs, par exemple `agent-medgemma:27b`. Choisir ce modele force le passage par le graphe agentique planner/researcher/executor/critic, qui peut appeler Qdrant via `rag_search`.

---

## Verifs istio :

```bash
# 1) Vérif simple : est-ce qu'il y a des sidecars istio-proxy ?
kubectl -n medplum get pods -o jsonpath='{range .items[*]}{.metadata.name}{" => "}{range .spec.containers[*]}{.name}{" "}{end}{"\n"}{end}' | sort
kubectl -n pompetrack-core get pods -o jsonpath='{range .items[*]}{.metadata.name}{" => "}{range .spec.containers[*]}{.name}{" "}{end}{"\n"}{end}' | sort

# 2) Vérif Istio "source de vérité" : quels proxies Istio voit ?
istioctl proxy-status 2>/dev/null || true

# 3) Vérif des labels d'injection sur namespaces (tu l'as déjà partiellement, on revalide complet)
kubectl get ns --show-labels | egrep '^(NAME|medplum|pompetrack-core|istio-system)'

# 4) Bonus très utile : est-ce que l’API server a bien les webhooks d’injection ?
kubectl get mutatingwebhookconfiguration | egrep -i 'istio|sidecar|inject' || true

```
---
## Prouver si istio est dans un pod :

```bash
POD=medplum-app-7cd789c666-wjkhc
NS=medplum

# 1) Liste brute des containers (devrait inclure istio-proxy si sidecar)
kubectl -n $NS get pod $POD -o jsonpath='{.spec.containers[*].name}{"\n"}'

# 2) Même chose mais en "yaml grep"
kubectl -n $NS get pod $POD -o yaml | egrep -n 'name: istio-proxy|istio\.io|sidecar\.istio|proxyMetadata' || true

# 3) Describe (souvent le plus parlant)
kubectl -n $NS describe pod $POD | egrep -n 'istio|envoy|proxy|sidecar' || true

# 4) Vérifier aussi les initContainers (au cas où)
kubectl -n $NS get pod $POD -o jsonpath='{.spec.initContainers[*].name}{"\n"}'

```

---

# 1) Plan générique : ajouter un nouveau pod “qui vit dans le cluster”

## Étape A — Où il vit (namespace + injection Istio)

1. Choisir le namespace :

* Si c’est un composant PompeTrack “core” : `pompetrack-core`
* Si c’est lié Medplum : `medplum`
* Sinon, crée un namespace dédié (recommandé si tu veux garder des policies nettes).

2. Activer l’injection Istio :

* Tu es en mode révision : label `istio.io/rev=default` sur le namespace.
* Donc pour un nouveau namespace : `kubectl label ns <ns> istio.io/rev=default`

3. Déployer le workload avec un `Deployment` + `Service` (ClusterIP).

* **Sans Service**, tu peux communiquer par IP de pod, mais tu vas perdre l’intérêt du routage stable et d’Istio (SNI, policies, observabilité).

## Étape B — NetworkPolicies minimales (sinon ton pod est “en prison”)

Avec tes `deny-all`, un pod nouvellement ajouté doit au minimum avoir :

* **Egress DNS** (sinon pas de résolution `*.svc.cluster.local`)
* **Egress vers istiod** (sinon le proxy Istio ne reçoit pas la config)
* Puis **egress/ingress applicatifs** selon les flux.

👉 Dans ton cluster, tu as déjà des policies “namespace-wide” (`podSelector: {}`) pour DNS et istiod dans `medplum` et `pompetrack-core`.
Donc si tu ajoutes le pod **dans un de ces namespaces**, il héritera déjà de :

* `allow-dns-egress`
* `allow-egress-to-istiod`
  …mais restera bloqué pour le reste tant que tu n’ajoutes pas les règles applicatives.

## Étape C — Exposition (facultatif)

* Si ton pod n’a pas besoin d’être accessible depuis l’extérieur : **pas de Traefik**, pas de Yunohost, rien.
* Si tu veux l’exposer :

  * Ajouter une **IngressRoute** Traefik (Host/Path) + éventuellement Middleware (auth/IP allowlist/stripPrefix).
  * Et ajouter une **NetworkPolicy ingress** “Traefik → ton pod”.

---

# 2) Plan générique : faire communiquer un pod avec un autre (HTTP GET/POST)

Dans ton modèle, ça se fait en 4 briques :

## A — Service DNS

* Le pod client parle à `http://<service>.<namespace>.svc.cluster.local:<port>/...`
* Donc le pod serveur doit avoir un `Service` stable.

## B — NetworkPolicies (Calico) : autoriser le flux L3/L4

Tu as un deny-all, donc il faut :

1. **Egress** sur le pod client (vers le pod serveur, sur le port TCP du service)
2. **Ingress** sur le pod serveur (depuis le pod client, sur le même port)

La forme typique (conceptuellement) :

* `client-egress-to-server` : `podSelector: clientLabels` + `to: podSelector serverLabels` + `ports: <port>`
* `server-ingress-from-client` : `podSelector: serverLabels` + `from: podSelector clientLabels` + `ports: <port>`

⚠️ Pour du **cross-namespace**, tu ajoutes en plus un `namespaceSelector` dans `from`/`to`.

## C — Istio mTLS + AuthZ (L7)

Chez toi, Istio est actif et mTLS est en place. Donc selon tes `AuthorizationPolicy`, un flux peut être bloqué même si NetPol autorise.

Règle de base :

* Si tu as une policy Istio “ALLOW only …”, il faut ajouter le **nouveau service account** ou les **principals** (identité SPIFFE) autorisés.
* Si tu n’as pas d’AuthorizationPolicy restrictive sur la cible, Istio ne bloquera pas (mais mTLS chiffrera).

## D — ServiceAccount (identité stable)

Pour faire des règles Istio propres, donne à ton nouveau pod un **ServiceAccount dédié**.
Ensuite tu peux autoriser :

* `source.principal` = `cluster.local/ns/<ns>/sa/<sa-name>`

---

# 3) Plan spécifique : ajouter un pod qui appelle les endpoints de `ingestion`

### Ce qu’on sait factuellement sur `ingestion`

Dans `pompetrack-core` tu as :

* pod `ingestion` avec label `app=ingestion`
* service `ingestion` sur **port 80/TCP**
* namespace `pompetrack-core` a `deny-all` + allow DNS/istiod + règles MinIO + Traefik console.
  ➡️ **Je ne vois aucune NetworkPolicy qui autorise l’accès à `ingestion:80`** dans ce que tu as collé.

Donc si aujourd’hui quelque chose arrive à joindre `ingestion`, c’est soit :

* parce que le client est dans le même pod (non),
* soit parce qu’il n’y a pas de policy “ingress” qui sélectionne `ingestion` (et donc `deny-all` sélectionne tout, donc *ça devrait bloquer*),
* soit parce que le trafic passe d’une manière non couverte (peu probable),
* soit parce que tu ne l’utilises pas encore en intra-cluster.

Bref : pour ton besoin, il faudra **ajouter** les règles.

---

## 3.1. Je veux ajouter un nouveau pod “caller” dans `pompetrack-core` qui appelle `http://ingestion/...`

### A — Déploiement minimal côté “caller”

* Un Deployment
* Un ServiceAccount dédié (ex: `caller-sa`)
* Labels clairs (ex: `app=caller`)

### B — NetworkPolicies à ajouter (dans `pompetrack-core`)

1. **Egress** : autoriser `caller` → `ingestion` sur TCP/80
2. **Ingress** : autoriser `ingestion` à recevoir depuis `caller` sur TCP/80

Concrètement (logique selectors de ton cluster) :

* Cible `ingestion` : label `app=ingestion`
* Source `caller` : label `app=caller`

Donc deux netpols du style :

* `allow-egress-caller-to-ingestion` (podSelector app=caller, to podSelector app=ingestion, port 80)
* `allow-ingestion-ingress-from-caller` (podSelector app=ingestion, from podSelector app=caller, port 80)

### C — Istio AuthorizationPolicy (si tu veux un contrôle “propre”)

Tu n’as pas montré de policy Istio sur `ingestion`. Si tu veux un modèle “zéro confiance” (recommandé), tu ajoutes :

* Une `AuthorizationPolicy` **sur ingestion** qui n’autorise que :

  * le service account du caller (`source.principal`)
  * et éventuellement Traefik si ingestion est exposé (pas forcément)

### D — Est-ce qu’il faut Traefik / IngressRoute ?

Non, **pas du tout** pour un flux interne cluster.
Traefik sert à l’entrée depuis l’extérieur (Yunohost → Traefik → service).
Pour “pod → ingestion”, tu passes par le **Service K8s** directement.

---

## 3.2. Variante : le caller est dans un autre namespace

Si ton nouveau pod est dans `medplum` (ou un ns dédié), alors tes netpols doivent inclure :

* un `namespaceSelector` (matchLabels `kubernetes.io/metadata.name: <ns-source>`)
* en plus du `podSelector` source.

---

# Résumé ultra concret (en 3 checklists)

## Checklist 1 — Ajouter un pod

* [ ] Namespace choisi + label `istio.io/rev=default`
* [ ] Deployment + ServiceAccount dédié + labels
* [ ] Service (ClusterIP) si d’autres doivent l’appeler
* [ ] NetworkPolicies : DNS + istiod déjà OK si dans `medplum` / `pompetrack-core`
* [ ] Ajouter les policies applicatives (ingress/egress) nécessaires

## Checklist 2 — Pod A appelle Pod B (HTTP)

* [ ] Pod B a un Service
* [ ] NetPol : egress A→B (port) + ingress B←A (port)
* [ ] Istio : AuthorizationPolicy sur B (optionnel mais conseillé) basée sur `source.principal` (SA)

## Checklist 3 — Pod “caller” appelle `ingestion`

* [ ] Labels caller + SA caller
* [ ] NetPol egress caller → ingestion:80
* [ ] NetPol ingress ingestion ← caller:80
* [ ] (Optionnel recommandé) AuthorizationPolicy sur ingestion autorisant le SA caller

---

# Postgres :

```bash
# Info
kubectl -n medplum exec -it $(kubectl -n medplum get pod -l app.kubernetes.io/name=postgresql -o jsonpath='{.items[0].metadata.name}') -- psql -U medplum -d medplum -c "\conninfo"


# Liste des roles
kubectl -n medplum exec -it $(kubectl -n medplum get pod -l app.kubernetes.io/name=postgresql -o jsonpath='{.items[0].metadata.name}') -- psql -U medplum -c "\du"
```
