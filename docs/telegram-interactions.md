# Interactions Telegram avec le coach santé

Cette page décrit les actions possibles depuis le bot Telegram du projet. Le bot sert à consulter les données santé récentes, lancer des revues LLM, gérer une mémoire utilisateur explicite, donner du feedback, et poser des questions en mode prudent.

Le bot répond uniquement aux chats autorisés par `telegram_allowed_chat_ids`. Les notifications automatiques sont envoyées aux chats configurés dans `notify_chat_ids`.

## Démarrer et identifier le chat

Envoyer `/start` ou `/help` affiche l'aide complète du bot.

Pour récupérer l'identifiant Telegram du chat courant:

```text
/id
```

Cet ID sert ensuite à verrouiller l'accès au bot dans le secret Kubernetes.

## Consulter les revues santé

La commande la plus simple est `/latest`. Elle affiche la dernière revue santé en version courte, avec:

- confiance dans les données;
- watchlist personnalisée;
- anomalies personnelles détectées;
- points de vigilance;
- extrait compact du résumé coach;
- lien vers `/details`;
- invitation à donner un feedback.

Exemples:

```text
/latest
/details
```

Pour consulter l'historique:

```text
/reviews 7
/review 2026-05-05
/review <review_id>
```

`/reviews` accepte une limite numérique. La valeur est bornée pour éviter de demander trop d'éléments d'un coup.

## Synthèses déterministes

Ces commandes ne demandent pas forcément au LLM de raisonner librement. Elles affichent une vue structurée produite à partir des features santé calculées par le backend.

```text
/today
/week
/trends
/watchlist
/features
```

`/today` est utile pour un point rapide sur les dernières 24h. `/week` donne une vue 7 jours. `/trends` met l'accent sur les tendances récentes. `/watchlist` se concentre sur les signaux suivis explicitement.

## Vues par domaine

Pour éviter de poser une question libre quand on veut juste une catégorie précise:

```text
/meds
/symptoms
/spirometry
/workouts
```

Ces commandes sont pensées pour un usage rapide depuis mobile:

- `/meds` affiche les prises ou administrations médicamenteuses récentes;
- `/symptoms` affiche les symptômes récents;
- `/spirometry` affiche les mesures respiratoires récentes;
- `/workouts` affiche les entraînements récents.

## Revues à la demande

Le bot peut déclencher une revue LLM sans attendre les CronJobs.

```text
/coach
/weekly-review
```

`/coach` lance une revue santé quotidienne sur la fenêtre récente configurée côté backend.

`/weekly-review` lance un bilan plus large, prévu pour les tendances lentes: humeur, activité, douleur récurrente, spirométrie, adhérence médicament, objectifs légers.

`/coach` lance maintenant un bilan de la journée précédente, pensé pour le matin avec des conseils pour la journée qui démarre.

`/bilans off` désactive les bilans automatiques planifiés. `/bilans on` les réactive. `/bilans status` affiche l'état courant.

Ces commandes peuvent prendre un peu de temps car elles appellent le backend agentique et le modèle.

## Questions du soir

Le mode question du soir sert à obtenir 1 à 3 questions ciblées selon les données de la journée.

```text
/evening
```

Exemples de questions attendues:

- fatigue élevée détectée, veux-tu noter ton niveau de récupération ?
- pas de prise médicament enregistrée aujourd'hui, oubli ou donnée manquante ?
- pas de symptôme renseigné récemment, rien à signaler ou suivi incomplet ?

Le CronJob `health-evening-questions` peut aussi envoyer ces questions automatiquement selon la configuration Helm.

## Rappels quotidiens

Le bot peut créer, lister et supprimer des rappels quotidiens persistants. Les rappels sont stockés côté backend dans SQLite et envoyés par le CronJob `telegram-reminder-runner`, qui tourne toutes les minutes.

Créer un rappel:

```text
/remind daily 19:00 faire les exercices
```

Lister les rappels actifs:

```text
/reminders
```

Supprimer un rappel:

```text
/delreminder rem-123456abcd
```

Le bot comprend aussi quelques formulations naturelles, par exemple:

```text
rappelle-moi de faire les exercices tous les jours à 19:00
supprime le rappel exercices
```

Les rappels utilisent la timezone configurée par `reminders.timeZone` dans le chart Helm, `Europe/Paris` par défaut.

## Alertes configurables

Les alertes sont des règles déterministes, séparées du raisonnement libre du LLM.

```text
/alerts
/alerts notify
```

Règles actuelles:

- spirométrie en baisse sur la fenêtre récente;
- symptôme récent marqué sévère;
- données absentes ou anciennes depuis 3 jours;
- médicament non vu récemment.

`/alerts` affiche le résultat dans le chat. `/alerts notify` déclenche aussi une notification Telegram douce, sans vibration si le client Telegram la respecte.

## Mémoire utilisateur explicite

La mémoire utilisateur est visible et modifiable depuis Telegram. Elle contient notamment:

- ton souhaité;
- style de réponse;
- sensibilité des alertes;
- horaires de notification;
- objectifs actifs;
- symptômes prioritaires;
- sujets sensibles.

Afficher la mémoire:

```text
/prefs
```

Modifier une préférence simple:

```text
/setpref tone bienveillant_concis
/setpref answerStyle tres_concis
/setpref alertSensitivity lower
```

Modifier les horaires:

```text
/setpref daily 06:30
/setpref evening 19:30
/setpref weekly 08:00 Sunday
```

Modifier une liste:

```text
/setpref sensitiveTopics sujet1,sujet2
/setpref activeGoals marcher 3 fois cette semaine,renseigner symptômes 5 jours sur 7
```

Gérer les symptômes prioritaires:

```text
/addsymptom fatigue
/delsymptom fatigue
```

La mémoire est stockée côté backend dans la base SQLite d'état de l'agent.

## Feedback après revue

Après une revue, le bot propose une boucle de feedback.

```text
/feedback useful
/feedback long trop détaillé pour le matin
/feedback false-positive douleur lombaire pas pertinente aujourd'hui
```

Effets actuels:

- `useful` conserve un niveau de sensibilité normal;
- `long` ajuste le style vers des réponses plus concises;
- `false-positive` abaisse la sensibilité des alertes pour limiter les faux positifs.

Le feedback est enregistré avec la dernière revue connue quand elle est disponible.

## Actions guidées

Le bot peut proposer des actions selon les données récentes et la mémoire utilisateur:

```text
/actions
```

Actions typiques:

- lancer une revue longue;
- poser une question clinique prudente;
- préparer une note symptôme;
- clarifier une prise médicament;
- consulter la watchlist personnalisée.

Ces actions sont des raccourcis conversationnels. Elles évitent de devoir connaître toutes les commandes par coeur.

## Brouillons de notes

Le bot peut préparer une note structurée:

```text
/note symptom fatigue intensité 6/10 après effort
/note medication prise confirmée vers 08:30
```

Important: actuellement, ces notes ne sont pas écrites automatiquement dans Medplum. Le bot prépare seulement un brouillon lisible et structuré. Une validation explicite pourra être ajoutée plus tard avant écriture.

## Questions libres et mode clinique prudent

Pour une question libre au LLM:

```text
/ask Peux-tu résumer ma semaine ?
```

Un message envoyé sans commande est aussi traité comme une question libre.

Pour une question santé nécessitant plus de prudence:

```text
/why Pourquoi je suis fatigué ?
```

Le mode clinique prudent force une réponse sans diagnostic, structurée autour de:

- observations disponibles;
- hypothèses prudentes non causales;
- données manquantes;
- signaux d'alerte justifiant un avis médical;
- questions utiles à se poser.

Le bot détecte aussi automatiquement certaines questions santé envoyées sans commande, par exemple une question contenant à la fois un marqueur de question et un terme comme fatigue, douleur, souffle, respiration, médicament, symptôme, coeur ou sommeil.

## Tableau récapitulatif des commandes

| Commande | Exemple | Usage |
|---|---|---|
| `/start` | `/start` | Affiche l'aide du bot. |
| `/help` | `/help` | Affiche l'aide du bot. |
| `/id` | `/id` | Affiche le chat ID Telegram courant. |
| `/latest` | `/latest` | Affiche la dernière revue santé en version courte. |
| `/details` | `/details` | Affiche la dernière revue santé complète. |
| `/reviews` | `/reviews 7` | Liste les dernières revues stockées. |
| `/review` | `/review 2026-05-05` | Affiche une revue par date ou par `review_id`. |
| `/today` | `/today` | Synthèse déterministe des dernières 24h. |
| `/week` | `/week` | Synthèse déterministe des 7 derniers jours. |
| `/trends` | `/trends` | Tendances récentes. |
| `/watchlist` | `/watchlist` | Suivi personnalisé des signaux prioritaires. |
| `/meds` | `/meds` | Médicaments récents. |
| `/symptoms` | `/symptoms` | Symptômes récents. |
| `/spirometry` | `/spirometry` | Spirométrie récente. |
| `/workouts` | `/workouts` | Entraînements récents. |
| `/evening` | `/evening` | Questions ciblées du soir. |
| `/alerts` | `/alerts` | Évalue les alertes configurables. |
| `/weekly-review` | `/weekly-review` | Lance un bilan hebdomadaire à la demande. |
| `/remind` | `/remind daily 19:00 faire les exercices` | Crée un rappel quotidien Telegram. |
| `/reminders` | `/reminders` | Liste les rappels actifs. |
| `/delreminder` | `/delreminder rem-123456abcd` | Supprime un rappel. |
| `/prefs` | `/prefs` | Affiche la mémoire utilisateur explicite. |
| `/setpref` | `/setpref tone bienveillant_concis` | Modifie une préférence utilisateur. |
| `/addsymptom` | `/addsymptom fatigue` | Ajoute un symptôme prioritaire. |
| `/delsymptom` | `/delsymptom fatigue` | Retire un symptôme prioritaire. |
| `/feedback` | `/feedback useful` | Enregistre un feedback sur une revue. |
| `/actions` | `/actions` | Propose des actions guidées selon les données récentes. |
| `/note` | `/note symptom fatigue 6/10` | Prépare un brouillon de note symptôme ou médicament. |
| `/why` | `/why Pourquoi je suis fatigué ?` | Lance une réponse clinique prudente sans diagnostic. |
| `/features` | `/features` | Affiche les features santé récentes. |
| `/coach` | `/coach` | Lance une nouvelle revue santé quotidienne. |
| `/ask` | `/ask Résume ma semaine` | Pose une question libre au LLM. |
