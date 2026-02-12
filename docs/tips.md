## Uninstall K3s :
```bash
sudo /usr/local/bin/k3s-uninstall.sh
sudo reboot
```


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





 # repartir à 0 :

 helm -n pompetrack-core uninstall pompetrack-core || true
 helm -n medplum uninstall medplum || true
 kubectl delete namespace pompetrack-core
 kubectl delete namespace medplum

 ./deploy/apply.sh

 kubectl get all -n medplum
 kubectl get all -n pompetrack-core