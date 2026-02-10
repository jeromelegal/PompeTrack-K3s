
 sudo /usr/local/bin/k3s-uninstall.sh
 sudo reboot


 curl -sfL https://get.k3s.io | sh -s - server   --flannel-backend=none   --disable-network-policy
 sudo nano /etc/rancher/k3s/config.yaml


 sudo systemctl restart k3s
 mkdir -p ~/.kube
 sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
 sudo chown "$USER":"$USER" ~/.kube/config
 chmod 600 ~/.kube/config