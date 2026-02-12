## 📌 CHECKPOINT – PompeTrack / K3s / Istio / Medplum

Contexte :

Je travaille sur un cluster **K3s** avec :

* Traefik (ingress controller)
* Istio 1.28.3 (sidecar injection active)
* Calico (NetworkPolicy strict)
* Helm umbrella charts
* Yunohost en frontal (TLS + SSO via nginx)

### 🎯 Objectif actuel

* Medplum **entièrement dans le mesh Istio (mTLS STRICT)**
* NetworkPolicies restrictives (deny-all + allow ciblés)
* Accès public via :

  * [https://app.phylcero.fr](https://app.phylcero.fr)
  * [https://api.phylcero.fr](https://api.phylcero.fr)
* TLS géré par Yunohost
* Traefik expose les services internes
* MinIO console accessible en LAN uniquement

---

## ✅ État actuel fonctionnel

* Istio mTLS STRICT actif sur `medplum` et `pompetrack-core`

* Postgres et Redis injectés dans le mesh

* Communication interne OK (curl intra-namespace → HTTP 200)

* Healthcheck API OK :
  curl [https://app.phylcero.fr/api/healthcheck](https://app.phylcero.fr/api/healthcheck) → 200 OK

* Assets JS servis correctement :
  curl [https://app.phylcero.fr/assets/index-XXXX.js](https://app.phylcero.fr/assets/index-XXXX.js) → 200 OK

* Ingress legacy supprimés

* IngressRoute Traefik actif pour medplum-app

---

## ❗ Problème restant

L’UI Medplum est vide dans le navigateur.

* HTML chargé
* JS chargé
* /api/healthcheck OK
* Pas de 502
* Pas de crash serveur

Headers observés :

* x-sso-wat: You've just been SSOed
* x-envoy-decorator-operation: medplum-app.medplum.svc.cluster.local:3000/*

Donc :

* Le trafic traverse bien Istio
* Un SSO nginx/Yunohost injecte des headers

Hypothèse :
Le SSO frontal (nginx auth_request / forward auth) interfère avec les requêtes SPA / API.

---

## 🧱 Architecture actuelle

Flux :

Navigateur
→ Yunohost nginx (TLS + SSO)
→ Traefik (K3s ingress)
→ Istio sidecar
→ medplum-app / medplum-server

mTLS STRICT interne

NetworkPolicies deny-all par défaut

---

## 📁 Structure projet

deploy/
charts/
medplum/
pompetrack-core/
namespaces/
medplum/
ingress/
netpol/
istio/
pompetrack-core/
ingress/
netpol/
istio/

---

## 🎯 Prochaine étape souhaitée

Analyser précisément :

1. Pourquoi l’UI est vide malgré :

   * JS chargé
   * API OK
2. Si le SSO Yunohost perturbe :

   * appels fetch internes
   * cookies
   * CORS
3. Si la config MEDPLUM_BASE_URL est correcte :
   MEDPLUM_BASE_URL=[https://app.phylcero.fr/api](https://app.phylcero.fr/api)

Je veux :

* Diagnostic structuré
* Étapes claires et ordonnées
* Pas de refactor massif
* On stabilise une architecture unique

---

Merci de repartir proprement de ce checkpoint et analyser l’état actuel avant toute modification.

---



















Voici un prompt “checkpoint” prêt à copier-coller pour repartir dans une nouvelle discussion, sans perdre le fil.

---

## CHECKPOINT — PompeTrack / K3s / Traefik / Istio / Yunohost / Medplum (état OK)

Contexte :

* Cluster **K3s** (Ubuntu 24.04)
* **Traefik** fourni par K3s
* **Istio 1.28.3** avec sidecar injection activée
* **Calico** avec NetworkPolicies restrictives (deny-all + allow ciblés)
* Déploiement via scripts `deploy/` (ex : `./deploy/apply.sh` ou `./deploy.apply.sh`)
* **Yunohost** en frontal : termine le TLS + SSO via nginx, reverse proxy vers le node K3s

Objectif :

* Avoir **Medplum** et **pompetrack-core** dans le mesh Istio, avec policies cohérentes (mTLS + netpol), et accès public via Yunohost.

État actuel (fonctionnel) :

* J’ai **tout supprimé** puis relancé un **`./deploy.apply.sh`** propre.
* Tout est **OK** :

  * UI Medplum s’affiche (plus de page blanche)
  * API Medplum OK (`/api/healthcheck` retourne 200)
  * Assets `/assets/*` OK
* Istio est normalement actif sur **les 2 namespaces** :

  * `medplum`
  * `pompetrack-core`
* Traefik est exposé en **LoadBalancer** avec EXTERNAL-IP = IP du node.

  * Accès HTTP interne vers Traefik via le **NodePort** (ex : `:31725` pour 80) depuis Yunohost.
* Côté Yunohost/nginx :

  * reverse proxy vers l’entrypoint Traefik (NodePort), TLS terminé côté Yunohost.

Incident résolu (cause racine) :

* La page blanche venait d’un **bundle JS invalide** à cause d’une valeur de **reCAPTCHA** injectée avec des guillemets en trop (`""KEY""`), et d’un **cache navigateur** (assets en cache 1 an).
* Correction : valeur de secret sans guillemets parasites + purge cache/hard reload → OK.

Ce que je veux dans la nouvelle discussion :

* Reprendre sur cette base **stable**.
* Vérifier proprement (sans refactor massif) :

  1. que Traefik ↔ Yunohost est cohérent (NodePort / proxy_pass)
  2. que le mesh Istio est bien effectif sur `medplum` et `pompetrack-core` (mTLS, PeerAuthentication, etc.)
  3. que les NetworkPolicies restent strictes mais fonctionnelles
* Garder une architecture unique et propre, étape par étape.

---














On arrête là. Le cerveau a aussi un `livenessProbe`, et là il est clairement en `BackOff`. 😄
Bonne décision.

---

## 1️⃣ Les fichiers `json6902`, on les garde ?

Non.

Tu es passé en `patchesStrategicMerge`, et ça fonctionne.
Les fichiers :

* `ingestion-probes-json6902.yaml`
* `minio-probes-json6902.yaml`

→ **ne servent plus à rien**.

Tu peux les supprimer pour garder ton projet propre :

```bash
rm deploy/post-renderer/pompetrack-core/*json6902.yaml
```

On garde uniquement :

* `ingestion-probes-patch.yaml`
* `minio-probes-patch.yaml`
* `kustomize.sh`

Un cluster propre commence par un repo propre.

---

# 🔁 Prompt de reprise pour demain

Copie-colle ça dans une nouvelle discussion :

---

## CHECKPOINT REPRISE — PompeTrack K3s + Istio + Post-Renderer

Contexte :

* K3s (Ubuntu 24.04)
* Istio 1.28.3 (sidecar injection via label `istio.io/rev=default`)
* Traefik (LoadBalancer + NodePort via Yunohost)
* NetworkPolicies strictes (deny-all + allow ciblés)
* Déploiement via `./deploy/apply.sh`
* Charts Helm :

  * medplum
  * pompetrack-core (minio + ingestion)

État actuel :

* Les namespaces `medplum` et `pompetrack-core` sont créés avec label Istio dès le départ.
* Un post-renderer Kustomize est utilisé pour injecter les probes :

  * `ingestion-probes-patch.yaml`
  * `minio-probes-patch.yaml`
* Le rendu Helm avec post-renderer injecte correctement :

  * livenessProbe
  * readinessProbe
  * startupProbe
  * timeoutSeconds: 3

Objectif pour aujourd’hui :

1. Vérifier qu’un `./deploy/apply.sh` complet démarre le cluster proprement.
2. S’assurer qu’il n’y a pas de restart multiple au boot.
3. Vérifier que Istio est bien actif sur tous les pods (istio-proxy présent).
4. Confirmer que mTLS STRICT fonctionne réellement.
5. Ne rien corriger en live : corriger uniquement les fichiers si nécessaire.

On avance étape par étape, sans refactor massif.

---

Demain on reprend proprement, calmement, méthodiquement.

Un cluster stable, c’est comme du yoga pour DevOps :
alignement, respiration… et pas de `kubectl panic`. 🧘‍♂️
