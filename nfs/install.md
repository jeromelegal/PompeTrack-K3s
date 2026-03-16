## Create namespace :

```bash
kubectl create namespace nfs-provisioner
```

## Add helm repo :

```bash
helm repo add nfs-subdir-external-provisioner https://kubernetes-sigs.github.io/nfs-subdir-external-provisioner/
helm repo update
```

## Install provisioner :

```bash
helm install nfs-subdir-external-provisioner nfs-subdir-external-provisioner/nfs-subdir-external-provisioner \
  --namespace nfs-provisioner \
  --set nfs.server=192.168.2.26 \
  --set nfs.path=/pompetrack-data \
  --set storageClass.name=nfs-client \
  --set storageClass.archiveOnDelete=false 
```

## Verify :

```bash
kubectl get pods -n nfs-provisioner  
kubectl get storageclass      
```

## Delete :

```bash
helm uninstall nfs-subdir-external-provisioner -n nfs-provisioner
```