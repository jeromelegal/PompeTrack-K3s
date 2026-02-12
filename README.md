=======
# PompeTrack-K3S
Personal Pompe disease tracking application


---
---
## Prérequis :

* VM Ubuntu-server 24.04
If necessery delete K3S : *sudo /usr/local/bin/k3s-uninstall.sh*
* Installation de K3S avec Flannel désactivé
```
curl -sfL https://get.k3s.io | sh -s - server \
  --flannel-backend=none \
  --disable-network-policy
```
* Si problème de droits sur *k3s.yaml*
```
sudo nano /etc/rancher/k3s/config.yaml
```
Ecrire :
```
write-kubeconfig-mode: "0644"
```
Redémarrer K3S
```
sudo systemctl restart k3s
```
* Installer un kubeconfig utilisateur :
```
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown "$USER":"$USER" ~/.kube/config
chmod 600 ~/.kube/config
```

* Vérifications :
```
kubectl get nodes -o wide
ip link | egrep -i 'flannel|cali|vxlan|cilium' || true
```
* Installation de Calico (Helm)
```
helm repo add projectcalico https://docs.tigera.io/calico/charts
helm repo update
helm install calico projectcalico/tigera-operator --namespace tigera-operator --create-namespace
```
* Varifications :
```
kubectl get pods -n tigera-operator
kubectl get pods -n calico-system
```


---
---

## A - Installation base : Medplum + Redis + PosgreSQL + Minio + Traefik
### 1. Création du namespace *medplum*  :

```
cd ~/pompetrack-health/PompeTrack-K3S
kubectl create namespace medplum
```
---
### 2. Création des secrets contenant les reCAPTCHA (dans secrets.env) :

commande :
```
./deploy/secrets/medplum/init-secrets.sh
```
---
### 3. Update dependency helm :

```
helm dependency update deploy/charts/medplum
```
---
### 4. Install de *Meplum* par umbrella helm :

```
helm install medplum deploy/charts/medplum -f deploy/charts/medplum/values-medplum.yaml -n medplum
```
Vérification :
**!!! Possible restart/crash de medplum, tant que postgres et redis ne sont pas démarrés !!!**
```
kubectl get pods -n medplum
kubectl get svc -n medplum
kubectl get ingress -n medplum
```

---
### 5. Installation "pompetrack-core" (helm) :

* Création du namespace *pompetrack-core* :

```
cd ~/pompetrack-health/PompeTrack-K3S
kubectl create namespace pompetrack-core
```
---
* Création des secrets :

```
./deploy/secrets/pompetrack-core/init-secrets.sh
```

* Update helm et install umbrella
```
helm repo add pompetrack-core https://charts.min.io
helm repo update

helm install pompetrack-core deploy/charts/pompetrack-core \
  -f deploy/charts/pompetrack-core/values-minio.yaml -n pompetrack-core
```

**Vérification :**

```
kubectl get pods -n pompetrack-core
kubectl get svc -n pompetrack-core
```

---

* Option console Minio sur le LAN intégrée :
http://minio.lan/login

---
### 8. Etat final :

```
kubectl get pods -A
kubectl get ingress -A
```

---
---
## B. Network :

```bash

```

## B. Sécurités :

### 1. Configuration Calico :

* Namespace : medplum

```bash
# DNS d’abord
kubectl apply -f deploy/namespaces/medplum/netpol/01-medplum-allow-dns-egress.yaml

# DENY ALL
kubectl apply -f deploy/namespaces/medplum/netpol/02-medplum-deny-all.yaml

# Istio

# Ingress 
kubectl appy -f deploy/namespaces/medplum/netpol/03-medplum-allow-postgres-redis-ingress-from-medplum.yaml

# Traefik -> apps
kubectl apply -f deploy/namespaces/medplum/netpol/04-medplum-allow-traefik-to-medplum-app.yaml
kubectl apply -f deploy/namespaces/medplum/netpol/05-medplum-allow-traefik-to-medplum-server.yaml

# DB/Redis
kubectl apply -f deploy/namespaces/medplum/netpol/06-medplum-allow-medplum-egress-to-postgres-redis.yaml
```

* Namespace : pompetrack-core

```bash
# DNS d’abord
kubectl apply -f deploy/namespaces/pompetrack-core/netpol/01-pompetrack-core-allow-dns.yaml

# DENY ALL
kubectl apply -f deploy/namespaces/pompetrack-core/netpol/02-pompetrack-core-deny-all.yaml

# Istio
kubectl apply -f deploy/namespaces/pompetrack-core/netpol/03-pompetrack-core-allow-egress-istiod.yaml

# Ingress 
kubectl apply -f deploy/namespaces/pompetrack-core/ingress/01-pompetrack-core-minio-console-ingressroute.yaml
kubectl apply -f deploy/namespaces/pompetrack-core/ingress/02-pompetrack-core-lan-only-minio.yaml

# Traefik -> apps
kubectl apply -f deploy/namespaces/pompetrack-core/netpol/04-pompetrack-core-allow-traefik-to-minio-console.yaml

# Minio API
kubectl apply -f deploy/namespaces/pompetrack-core/netpol/05-pompetrack-core-allow-minio-api-ingress.yaml

```

---
### 2. Installation ISTIO minimal :
* Installation CLI :
```
curl -L https://istio.io/downloadIstio | sh -
cd istio-*
export PATH=$PWD/bin:$PATH
istioctl version
```
* Créer le namespace :
```
kubectl create namespace istio-system
```
* Installation de Istio minimal :
```
istioctl install -y --set profile=minimal
```
**Si Warning : detected Calico CNI with 'bpfConnectTimeLoadBalancing=TCP'; this must be set to 'bpfConnectTimeLoadBalancing=Disabled' in the Calico configuration**
* Fix recommandé par Calico :
```
kubectl patch felixconfiguration default --type merge -p '{"spec":{"bpfConnectTimeLoadBalancing":"Disabled"}}'
```

---
### 3. Mesher un namespace : `pompetrack-core`

```bash
kubectl apply -f deploy/namespaces/pompetrack-core/istio/
```





---
## Partie Registry :

* 2. Créer répertoire 'ingestion' dans `apps` :

Copier les fichiers requis :
- Dockerfile
- requirements.tx
- entrypoint.sh
- divers scripts
- ...

**Registry** : registry créé en local sur Gitlab
* 3. Commit / push sur projet gitlab :

Projet créer sur Gitlab local : https://git.phylcero.fr/garth/pompetrack

- Gestion automatique des images des conteneurs par **CI** (fichier à la racine : *.gitlab-ci.yml)
- Création des images sur modification dans le dossier approprié
- Règle de création du tag "latest" pour la dernière image créée

* 4. Appel des images du registry local sur K3s :

Exemple pour *ingestion*
```bash
registry.phylcero.fr/garth/pompetrack/ingestion:latest
```

* Pull images de registry par le CI :

Dans la CI on se loggue au registry :
- docker login -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD" "$CI_REGISTRY"

Les variables sont attendues par Gitlab, au préalable il faut créer des creds par *token* côté gitlab, puis les enregistrer dans K3s :

Create secrets on K3s :

```bash
kubectl -n pompetrack-core create secret docker-registry gitlab-registry-creds \
  --docker-server=registry.phylcero.fr \
  --docker-username='gitlab+deploy-token-2' \
  --docker-password='gldt-*************' \
  --docker-email='root@phylcero.fr'
```
Lier au ServiceAccount `ingestion`:

```bash
kubectl -n pompetrack-core patch serviceaccount ingestion \
  -p '{"imagePullSecrets":[{"name":"gitlab-registry-creds"}]}'
```




---
Tools informations :

* Istio :
“Istio version: 1.28.3”
“istioctl installé dans /usr/local/bin (symlink vers ~/tools/istio/istio-1.28.3/bin/istioctl)