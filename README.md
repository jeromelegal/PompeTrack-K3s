<<<<<<< HEAD
# pompetrack-k3s



## Getting started

To make it easy for you to get started with GitLab, here's a list of recommended next steps.

Already a pro? Just edit this README.md and make it your own. Want to make it easy? [Use the template at the bottom](#editing-this-readme)!

## Add your files

* [Create](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#create-a-file) or [upload](https://docs.gitlab.com/ee/user/project/repository/web_editor.html#upload-a-file) files
* [Add files using the command line](https://docs.gitlab.com/topics/git/add_files/#add-files-to-a-git-repository) or push an existing Git repository with the following command:

```
cd existing_repo
git remote add origin https://git.phylcero.fr/garth/pompetrack-k3s.git
git branch -M main
git push -uf origin main
```

## Integrate with your tools

* [Set up project integrations](https://git.phylcero.fr/garth/pompetrack-k3s/-/settings/integrations)

## Collaborate with your team

* [Invite team members and collaborators](https://docs.gitlab.com/ee/user/project/members/)
* [Create a new merge request](https://docs.gitlab.com/ee/user/project/merge_requests/creating_merge_requests.html)
* [Automatically close issues from merge requests](https://docs.gitlab.com/ee/user/project/issues/managing_issues.html#closing-issues-automatically)
* [Enable merge request approvals](https://docs.gitlab.com/ee/user/project/merge_requests/approvals/)
* [Set auto-merge](https://docs.gitlab.com/user/project/merge_requests/auto_merge/)

## Test and Deploy

Use the built-in continuous integration in GitLab.

* [Get started with GitLab CI/CD](https://docs.gitlab.com/ee/ci/quick_start/)
* [Analyze your code for known vulnerabilities with Static Application Security Testing (SAST)](https://docs.gitlab.com/ee/user/application_security/sast/)
* [Deploy to Kubernetes, Amazon EC2, or Amazon ECS using Auto Deploy](https://docs.gitlab.com/ee/topics/autodevops/requirements.html)
* [Use pull-based deployments for improved Kubernetes management](https://docs.gitlab.com/ee/user/clusters/agent/)
* [Set up protected environments](https://docs.gitlab.com/ee/ci/environments/protected_environments.html)

***

# Editing this README

When you're ready to make this README your own, just edit this file and use the handy template below (or feel free to structure it however you want - this is just a starting point!). Thanks to [makeareadme.com](https://www.makeareadme.com/) for this template.

## Suggestions for a good README

Every project is different, so consider which of these sections apply to yours. The sections used in the template are suggestions for most open source projects. Also keep in mind that while a README can be too long and detailed, too long is better than too short. If you think your README is too long, consider utilizing another form of documentation rather than cutting out information.

## Name
Choose a self-explaining name for your project.

## Description
Let people know what your project can do specifically. Provide context and add a link to any reference visitors might be unfamiliar with. A list of Features or a Background subsection can also be added here. If there are alternatives to your project, this is a good place to list differentiating factors.

## Badges
On some READMEs, you may see small images that convey metadata, such as whether or not all the tests are passing for the project. You can use Shields to add some to your README. Many services also have instructions for adding a badge.

## Visuals
Depending on what you are making, it can be a good idea to include screenshots or even a video (you'll frequently see GIFs rather than actual videos). Tools like ttygif can help, but check out Asciinema for a more sophisticated method.

## Installation
Within a particular ecosystem, there may be a common way of installing things, such as using Yarn, NuGet, or Homebrew. However, consider the possibility that whoever is reading your README is a novice and would like more guidance. Listing specific steps helps remove ambiguity and gets people to using your project as quickly as possible. If it only runs in a specific context like a particular programming language version or operating system or has dependencies that have to be installed manually, also add a Requirements subsection.

## Usage
Use examples liberally, and show the expected output if you can. It's helpful to have inline the smallest example of usage that you can demonstrate, while providing links to more sophisticated examples if they are too long to reasonably include in the README.

## Support
Tell people where they can go to for help. It can be any combination of an issue tracker, a chat room, an email address, etc.

## Roadmap
If you have ideas for releases in the future, it is a good idea to list them in the README.

## Contributing
State if you are open to contributions and what your requirements are for accepting them.

For people who want to make changes to your project, it's helpful to have some documentation on how to get started. Perhaps there is a script that they should run or some environment variables that they need to set. Make these steps explicit. These instructions could also be useful to your future self.

You can also document commands to lint the code or run tests. These steps help to ensure high code quality and reduce the likelihood that the changes inadvertently break something. Having instructions for running tests is especially helpful if it requires external setup, such as starting a Selenium server for testing in a browser.

## Authors and acknowledgment
Show your appreciation to those who have contributed to the project.

## License
For open source projects, say how it is licensed.

## Project status
If you have run out of energy or time for your project, put a note at the top of the README saying that development has slowed down or stopped completely. Someone may choose to fork your project or volunteer to step in as a maintainer or owner, allowing your project to keep going. You can also make an explicit request for maintainers.
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
### 3. Update depandency helm :

```
helm dependency update deploy/charts/medplum
```
---
### 4. Install de umbrella helm :

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
### 5. Installation Minio (helm) :

* Création du namespace *pompetrack-core* :

```
cd ~/pompetrack-health/PompeTrack-K3S
kubectl create namespace pompetrack-core
```
---
* Création des secrets contenant :

commandes :
```
./deploy/secrets/pompetrack-core/init-secrets.sh
```

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
### 6. Création des buckets :

```
kubectl apply -n pompetrack-core -f infra/minio/minio-init-job.yaml
```

**Vérifivation :**
```
kubectl logs -n pompetrack-core job/minio-init
```

---
### 7. Config accès Minio sur LAN :

```
kubectl apply -n pompetrack-core -f infra/minio/lan-only-minio.yaml
kubectl apply -n pompetrack-core -f infra/minio/minio-console-ingressroute.yaml
```

**Vérification :**
http://minio.lan/login

---
### 8. Etat final :

```
kubectl get pods -A
kubectl get ingress -A
```

---
---
## B. Sécurités :

### 1. Configuration Calico :

```
# DNS d’abord
kubectl apply -f infra/netpol/02-allow-dns-egress-medplum.yaml
kubectl apply -f infra/netpol/02-allow-dns-egress-minio.yaml

# DENY ALL
kubectl apply -f infra/netpol/01-medplum-deny-all.yaml
kubectl apply -f infra/netpol/01-minio-deny-all.yaml

# Traefik -> apps
kubectl apply -f infra/netpol/03-allow-traefik-to-medplum-app.yaml
kubectl apply -f infra/netpol/03-allow-traefik-to-medplum-server.yaml
kubectl apply -f infra/netpol/06-allow-traefik-to-minio-console.yaml

# DB/Redis
kubectl apply -f infra/netpol/04-allow-medplum-egress-to-postgres-redis.yaml
kubectl apply -f infra/netpol/04-allow-postgres-redis-ingress-from-medplum.yaml

# Minio API
kubectl apply -f infra/netpol/05-allow-medplum-egress-to-minio-api.yaml
kubectl apply -f infra/netpol/05-allow-minio-api-ingress.yaml

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
### 3. Mesher un namespace :





---
### Création d'un deployment pour un container :
*exemple pour 'ingestion'*

* 1. Création d'un ServiceAccount :

```bash
kubectl -n pompetrack-core create serviceaccount ingestion
```

* vérification
```bash
kubectl -n pompetrack-core get sa ingestion -o yaml
```
Lors de la création du `deployment`, il faudra préciser :
```yaml
spec:
  serviceAccountName: ingestion
```

* 2. Créer répertoire 'ingestion' dans `apps` :

Copier les fichiers requis :
- Dockerfile
- requirements.tx
- entrypoint.sh
- divers scripts
- ...

* 3. Réaliser un **build** de l'image :

Dans un terminal, se placer dans le répertoire contenant `Dockerfile`

```bash
docker build -t pompetrack/ingestion:0.1.1 .
```

* 4. Enregistrer l'image dans K3s :

```bash
docker save pompetrack/ingestion:0.1.0 | sudo k3s ctr images import -
```

Vérification :
```bash
sudo k3s ctr images ls | grep -E "pompetrack/ingestion" || true
```

>>>>>>> 5317d4a (First commit)
