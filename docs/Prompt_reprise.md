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


## Etat Traefik : 

```bash
garth@medplum:~/pompetrack-health/pompetrack-k3s$ kubectl -n kube-system get svc,deploy,pods -l app.kubernetes.io/name=traefik -o wide
NAME              TYPE           CLUSTER-IP     EXTERNAL-IP    PORT(S)                      AGE     SELECTOR
service/traefik   LoadBalancer   10.43.219.17   192.168.2.88   80:31725/TCP,443:31134/TCP   3d19h   app.kubernetes.io/instance=traefik-kube-system,app.kubernetes.io/name=traefik

NAME                      READY   UP-TO-DATE   AVAILABLE   AGE     CONTAINERS   IMAGES                                   SELECTOR
deployment.apps/traefik   1/1     1            1           3d19h   traefik      rancher/mirrored-library-traefik:3.5.1   app.kubernetes.io/instance=traefik-kube-system,app.kubernetes.io/name=traefik

NAME                          READY   STATUS    RESTARTS       AGE     IP                NODE      NOMINATED NODE   READINESS GATES
pod/traefik-6f5f87584-gmz6w   1/1     Running   10 (54m ago)   3d19h   192.168.180.178   medplum   <none>           <none>
garth@medplum:~/pompetrack-health/pompetrack-k3s$ kubectl -n kube-system get svc traefik -o yaml | sed -n '1,220p'
apiVersion: v1
kind: Service
metadata:
  annotations:
    meta.helm.sh/release-name: traefik
    meta.helm.sh/release-namespace: kube-system
  creationTimestamp: "2026-02-09T14:30:41Z"
  finalizers:
  - service.kubernetes.io/load-balancer-cleanup
  labels:
    app.kubernetes.io/instance: traefik-kube-system
    app.kubernetes.io/managed-by: Helm
    app.kubernetes.io/name: traefik
    helm.sh/chart: traefik-37.1.1_up37.1.0
  name: traefik
  namespace: kube-system
  resourceVersion: "347062"
  uid: c0759fc6-caa6-46a4-9233-5621b1ccdb78
spec:
  allocateLoadBalancerNodePorts: true
  clusterIP: 10.43.219.17
  clusterIPs:
  - 10.43.219.17
  externalTrafficPolicy: Cluster
  internalTrafficPolicy: Cluster
  ipFamilies:
  - IPv4
  ipFamilyPolicy: PreferDualStack
  ports:
  - name: web
    nodePort: 31725
    port: 80
    protocol: TCP
    targetPort: web
  - name: websecure
    nodePort: 31134
    port: 443
    protocol: TCP
    targetPort: websecure
  selector:
    app.kubernetes.io/instance: traefik-kube-system
    app.kubernetes.io/name: traefik
  sessionAffinity: None
  type: LoadBalancer
status:
  loadBalancer:
    ingress:
    - ip: 192.168.2.88
      ipMode: VIP
```

## Etat istio :

```bash
garth@medplum:~/pompetrack-health/pompetrack-k3s$ kubectl get ns --show-labels | egrep '^(NAME|medplum|pompetrack-core)'
kubectl -n medplum get pods -o jsonpath='{range .items[*]}{.metadata.name}{" => "}{range .spec.containers[*]}{.name}{" "}{end}{"\n"}{end}' | head -n 50
kubectl -n pompetrack-core get pods -o jsonpath='{range .items[*]}{.metadata.name}{" => "}{range .spec.containers[*]}{.name}{" "}{end}{"\n"}{end}' | head -n 50
NAME              STATUS   AGE     LABELS
medplum           Active   54m     istio.io/rev=default,kubernetes.io/metadata.name=medplum
pompetrack-core   Active   54m     istio.io/rev=default,kubernetes.io/metadata.name=pompetrack-core
medplum-7f5c5fbc7c-d4qq8 => medplum 
medplum-app-7cd789c666-wjkhc => medplum-app 
medplum-postgresql-0 => postgresql 
medplum-redis-master-0 => redis 
ingestion-868c48844d-hxb8k => ingestion 
minio-init-x8kv6 => mc 
pompetrack-core-minio-6547d86bf6-jr7bb => minio 
```

## Etat mTLS :

```bash
garth@medplum:~/pompetrack-health/pompetrack-k3s$ kubectl -n medplum get peerauthentication,authorizationpolicy,requestauthentication,destinationrule -o wide
kubectl -n pompetrack-core get peerauthentication,authorizationpolicy,requestauthentication,destinationrule -o wide
NAME                                                              MODE         AGE
peerauthentication.security.istio.io/default                      STRICT       55m
peerauthentication.security.istio.io/medplum-app-permissive       PERMISSIVE   55m
peerauthentication.security.istio.io/medplum-service-permissive   PERMISSIVE   55m
NAME                                                                             MODE     AGE
peerauthentication.security.istio.io/minio-mtls-strict-with-console-permissive   STRICT   55m
peerauthentication.security.istio.io/mtls                                        STRICT   55m

NAME                                                                           ACTION   AGE
authorizationpolicy.security.istio.io/minio-allow-only-ingestion-and-console   ALLOW    55m
garth@medplum:~/pompetrack-health/pompetrack-k3s$ 

```



























---













kubectl -n pompetrack-core delete job minio-init --ignore-not-found
kubectl -n pompetrack-core apply -f deploy/charts/pompetrack-core/templates/minio-init-job.yaml

POD=$(kubectl -n pompetrack-core get pod -l job-name=minio-init -o jsonpath='{.items[0].metadata.name}')
kubectl -n pompetrack-core logs "$POD" --all-containers=true
