Au 08/02/2026, on a :

-Un projet sous Compose entièrement fonctionnel

Sur K3s:
* Namespeces présent : `medplum`, `pompetrack-core`, `calico-system`, `istio-system`, `tigera-operator`
- les TLS sont gérés par Yunohost qui redirige vers la VM 'medplum' : 192.168.2.88
- umbrella helm pour installation de medplum-server, medplum-app, postgres, redis
- meplum-server opérationnel sous api.phylcero.fr
- medplum-app opérationnel sous app.phylcero.fr
- reCAPTCHA google opérationnel
- Minio déployé et fonctionnel
- minio-init-job qui créé les buckets au boot
- NetworkPolicy appliquée : deny-all sauf DNS, accès medplum sur Yunohost, accès minio console sur LAN
- istio installé mais non présent sur namespace