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










Parfait 👍 très bonne idée de faire un **checkpoint propre**.

Je te fais un état clair, structuré, que tu pourras copier-coller demain pour repartir sans rien casser.

---

# ✅ ✅ ✅ CHECKPOINT — Airflow sur K3s (21 février 2026)

## 🖥 Environnement

- VM Linux
- Cluster **k3s**
- Namespace : `airflow`
- Chart utilisé : `apache-airflow/airflow`
- Version chart : **1.19.0**
- Version Airflow : **3.1.7**
- Executor : ✅ **KubernetesExecutor**
- Postgres : ✅ embarqué (chart intégré, StatefulSet)

---

# ✅ État actuel du cluster

Commande :

```bash
kubectl get pods -n airflow
```

Résultat :

✅ airflow-api-server → Running  
✅ airflow-scheduler → Running  
✅ airflow-triggerer → Running  
✅ airflow-dag-processor → Running  
✅ airflow-postgresql-0 → Running  
✅ airflow-statsd → Running  

👉 Aucun crash  
👉 Aucun pod en Init  
👉 Aucune erreur visible  

Cluster sain ✅

---

# ✅ Configuration Helm actuelle

```bash
helm get values airflow -n airflow
```

Valeurs importantes :

```yaml
config:
  core:
    executor: KubernetesExecutor
    load_examples: "false"

postgresql:
  enabled: true
  auth:
    database: airflow
    username: airflow
    password: airflow

ingress:
  enabled: false

webserver:
  service:
    type: ClusterIP
```

---

# ✅ Vérification Executor

Commande exécutée :

```bash
kubectl exec -it deployment/airflow-scheduler -n airflow -- \
airflow config get-value core executor
```

Résultat :

```
KubernetesExecutor
```

👉 Confirmé.

---

# ✅ Ce qui fonctionne

✔ Base de données  
✔ Migrations  
✔ Scheduler  
✔ API Server  
✔ Triggerer  
✔ Executor configuré correctement  
✔ Aucun redéploiement nécessaire  

---

# ⚠️ Ce qui n’est PAS encore fait

1. ✅ Aucun DAG custom déployé
2. ✅ Aucun test réel de création de pod worker
3. ✅ Pas d’accès UI configuré (ClusterIP seulement)
4. ✅ Pas d’Ingress
5. ✅ Pas de port-forward actif

---

# 📌 Pourquoi http://localhost:8080 ne marche pas

Parce que :

```
webserver.service.type = ClusterIP
```

Donc le service n’est accessible **que depuis le cluster**.

Sur une VM, tu dois soit :

### Option A — Port-forward

```bash
kubectl port-forward svc/airflow-api-server -n airflow 8080:8080
```

Puis accéder à :

```
http://IP_DE_TA_VM:8080
```

(ou localhost si tu es en SSH tunnel)

---

### Option B — Changer en NodePort (plus simple pour VM)

Modifier values.yaml :

```yaml
webserver:
  service:
    type: NodePort
```

Puis :

```bash
helm upgrade airflow apache-airflow/airflow -n airflow -f values.yaml
```

---

# 🧠 Architecture actuelle (propre)

Tu es maintenant sur :

```
KubernetesExecutor
```

Donc :

- ❌ pas de Celery
- ❌ pas de Redis
- ✅ pods workers créés dynamiquement
- ✅ architecture simple
- ✅ adaptée à k3s

---

# 🚀 Pour reprendre demain

Demain, on fera uniquement :

1. Exposer proprement l’UI
2. Créer un DAG test
3. Vérifier qu’un pod worker est créé
4. Observer son cycle de vie

Sans réinstaller.
Sans uninstall.
Sans casser quoi que ce soit.

---

# ✅ État global

🎯 Installation propre  
🎯 Cluster sain  
🎯 Executor correct  
🎯 Aucune action destructive nécessaire  

---

Si tu veux, je peux aussi te faire :

- un schéma d’architecture clair
- ou un plan “Production ready” étape par étape

On reprend calmement demain 👌