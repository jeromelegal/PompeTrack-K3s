**PROMPT DE REPRISE – Projet PompeTrack K3s + Istio**

Contexte :

Je travaille sur le projet personnel “PompeTrack on Kubernetes” sous K3s.

État actuel validé :

* Namespace `pompetrack-core`
* Injection Istio activée via label `istio.io/rev=default`
* NetworkPolicy avec `deny-all`
* Egress autorisé vers :

  * DNS
  * istiod (15012 / 15010)
* mTLS en mode STRICT dans `pompetrack-core`
* MinIO maillé (sidecar injecté)
* Exception mTLS PERMISSIVE sur port 9001 (console)
* AuthorizationPolicy :

  * ingestion (SA: ingestion) peut accéder à MinIO port 9000
  * port 9001 autorisé (console via Traefik hors-mesh)
* Console MinIO LAN fonctionne
* ingestion → MinIO API fonctionne

Objectif de la prochaine session :

Continuer la structuration propre et reproductible :

* Finaliser l’arborescence YAML versionnée
* Décider stratégie d’intégration Istio dans umbrella Helm
* Définir la méthode standard pour mailler les prochains namespaces (ex: medplum)
* Clarifier la stratégie multi-namespace (mesh partiel vs global)
* Éventuellement durcir l’accès console via IP au lieu d’ouverture totale du 9001

Merci de reprendre proprement à partir de cet état validé.
