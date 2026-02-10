# Projet PompeTrack-Health - version K3S
---
**nota: schéma et explications du projet sur Compose, modificatiopns à prévoir sur K3S.**

## Explications archi globale :

Pour que je puisse te guider sans suppositions, décris juste ces éléments (même en vrac) :

* Les services : lesquels existent (API, worker, UI, ingestion, cron, etc.) ?
    - "ingestion FastAPI" : intègre l'API pour minio, reçoit des json de Streamlit (enregistrements manuels), possède des endpoints par buckets (raw-iphone, raw-db-spirometer,...)
    - "streamlit" : 
        1. Partie UI pour enregistrer des mesures manuelles (mensurations, mesures de forces,...), UI pour envoyer des fichiers sur les endpoints de 'ingestion'. 
        2. Partie de suivi des données, récupère les datas par worker-stream et réalise des graphs,...
    - "Minio" : stockage avec les différents buckets. API sur 'ingestion'. Prévision d'un cron pour sauvegarder les BDD de postgres.
    - "worker-fhir" : sur ordre de Airflow, récupère les fichiers dans les buckets et transforme les données au format FHIR, puis les poussent par batch dans medplum-server.
    - "worker-stream" : sur requête de Streamlit, interroge l'API de Medplum pour récupérer les données, fait le tri et les envoient à streamlit pour l'affichage (graphs, stats,...)
    - "worker-sqlite" (absent du schéma) : qui travaille entre les buckets 'raw-db-spirometer' et 'raw-spirometer', sur demande d'Airflow récupère les données d'une BDD sqlite et les transforme proprement en json (même format que raw-manual) et les upload dans le bucket 'raw-spirometer', on obtient le même format que les json de raw-manual et donc facilite le travail de 'worker-fhir'.
    - "Airflow" : DAGS créés, vérification de la présence de fichiers dans les buckets minio, si présent ordres vers 'worker-sqlite' et 'worker-fhir'.
    - "medplum-server" : api.phylcero.fr
    - "medplum-app" : UI du serveur Medplum ; app.phylcero.fr
    - "medplum-chart" : pas sur qu'il existe encore, c'était l'UI pour les médecins pour avoir tous les détails et graphs des patients
    - "postgresql" : BDD de Medplum et BDD d'Airflow
    - "REDIS" : avec "seed-redis" dans Compose servait indéniablement à la sécurité avec le stockage des Tokens, scopes, devices,... sécurisé en ACL.


* Les flux : qui appelle qui ? (ex: UI → API, API → Redis, API → Medplum, worker → API…)
    - "Streamlit" envoie des fichiers sur endpoints "ingestion"
    - "Streamlit" fait des requêtes à "worker-stream"
    - "worker-stream" fait des requêtes à l'API Medplum et envoie les données vers Streamlit
    - "ingestion" intègre l'API de Minio, tous les containers qui veulent get, download ou upload vers Minio passent par l'API "ingestion"
    - "worker-fhir" fait des get, download et upload à Minio en passant par l'API de "ingestion"
* Les “acteurs” JWT : tu as des users, des devices, des services internes ? (souvent il y a 2 types de tokens)
    - j'avais des "devices" par containers et des scopes associés, exemple "worker-fhir" a les scopes 'ingest:get', 'ingest:download', 'ingest:upload',...
* Où est l’entrée : Ingress Traefik ? Nginx ? Tu exposes quoi (API, UI) et sur quels domaines ?
    - Clairement, je ne sais pas, j'ai besoin d'aide et comprendre comment gérer cela sereinement et faire quelque chose de SECURE
* Redis : il sert à quoi exactement dans la version K3S (sessions, cache, “authority”, révocation…) ?
    - Bonne question, du coup si on part sur JWT + mTLS, je ne sais pas trop.... need help !


Tu veux quel niveau de complexité acceptable :
* (A) sans mesh (mTLS “point à point” = plus de boulot)
* (B) avec mesh (Linkerd/Istio) = plus “auto” mais plus d’infra
    ==> B, avec mesh, on fait un truc propre

Ensuite je te propose un plan concret (sans blabla) du style :

1. réseau (NetworkPolicies + services ClusterIP)
2. JWT (signing keys, rotation, “device tokens” vs “user tokens”)
3. mTLS (choix mesh ou non, certs, policies)
4. Redis (ACL + secrets + séparation des clés)
5. tests de vérif (comment prouver que ça marche et que c’est bien fermé)

⚠️ Petit point important : mTLS sans service mesh dans Kubernetes, c’est faisable mais plus pénible (certificats côté app, reload, rotation). À l’inverse, Linkerd te fait souvent un mTLS “transparent” assez facilement. Donc on choisira en fonction de ton seuil de douleur.

Balance ton schéma (même texte), et je te réponds avec une architecture cible + les premières briques YAML/config à poser.


==> voila le topo, comme préciser je transfert le projet Compose sur K3S et l'idée est de faire évoluer le projet, l'élever, l'adapter à K3S et du cour l'améliorer sur tous les points. Cela reste complètement pédagogique, j'apprends sur le tas.