# Stratégie pour l'interfaçage RAW => FHIR :

## Actions à réaliser :

* Générer des templates "génériques" 
    ex: "iphone-metrics" a besoin de 3 templates

* Créer un dictionnaire avec "name", "template" et "constants" dans un fichier JSON :
    - "name": nom de la mesure, du test
    - "template": nom du fichier template qui contient les éléments nécessaires au FHIR
    - "constants": contient les éléments générique au "name"
* Charger le fichier json dans Redis au boot et interroger Redis  afin de récupérer les infos

* Condition si "name" non trouvé, proposer de renseigner ou créer un "template"

* Intégrer une recherche de la "category" et du "code" de l'observation

* Fonction de création de "template" :
    * Entrer le nom du template
    * Proposer les entrées nécessaires (yes/no)
    * demander "name" pour l'ajouter au dictionnaire




## Exemple du fichier json DICTIONNAIRE de Metadata :

```json
[
  {
    "name": "headphone_audio_exposure",
    "template": "simple_measure.json",
    "constants": 
      {
        "cat_system": "http://terminology.hl7.org/CodeSystem/observation-category",
        "cat_code": "social-history",
        "cat_display": "Social History",
        "code_system": "https://medplum.phylcero.fr/run",
        "code_code": "headphone_audio_exposure",
        "code_display": "Headphone Audio Exposure",
        "code_text": "Exposition sonore",
        "patient_id": "1797fcc2-2d95-47d6-9045-c188d9e1d02a",
        "device_id": "c9dea642-a030-4484-8b17-3cc0d0fdb9b0",
        "tag_system": "http://phylcero.fr/fhir/StructureDefinition/observation-group",
        "tag_code": "metrics"
      }
  },
  {
    "name": "heart_rate",
    "template": "heart_rate.json",
    "constants": 
      {
        "cat_system": "http://terminology.hl7.org/CodeSystem/observation-category",
        "cat_code": "vital-signs",
        "cat_display": "Vital Signs",
        "code_system": "http://loinc.org",
        "code_code": "8867-4",
        "code_display": "Heart rate --avg",
        "patient_id": "1797fcc2-2d95-47d6-9045-c188d9e1d02a",
        "device_id": "c9dea642-a030-4484-8b17-3cc0d0fdb9b0",
        "code_system[0]":"https://medplum.phylcero.fr/run",
        "code_code[0]": "Heart-rate-min",
        "code_display[0]": "Heart rate minimum (day)",
        "code_system[1]": "https://medplum.phylcero.fr/run",
        "code_code[1]": "Heart-rate-max",
        "code_display[1]": "Heart rate maximum (day)",
        "tag_system": "http://phylcero.fr/fhir/StructureDefinition/observation-group",
        "tag_code": "metrics"
      }
  },
  {
    "name": "resting_heart_rate",
    "template": "simple_measure.json",
    "constants": 
      {
        "cat_system": "http://terminology.hl7.org/CodeSystem/observation-category",
        "cat_code": "vital-signs",
        "cat_display": "Vital Signs",
        "code_system": "http://loinc.org",
        "code_code": "40443-4",
        "code_display": "Heart rate --resting",
        "code_text": "Fréquence cardiaque au repos",
        "patient_id": "1797fcc2-2d95-47d6-9045-c188d9e1d02a",
        "device_id": "c9dea642-a030-4484-8b17-3cc0d0fdb9b0",
        "tag_system": "http://phylcero.fr/fhir/StructureDefinition/observation-group",
        "tag_code": "metrics"
      }
  }
]
```

## Workflow : 

1. fichier raw
2. à partir du "name" du raw, on cherche dans Redis son template et mapping (si existant)
3.a : NON existant, on déclenche la création du template et mapping, puis enregistrement
3.b : existant, on récupère le template et le mapping
4. création d'un dictionnaire avec les entrées remplies
5. transformation en FHIR avec la fonction existante : `to_fhir_observation`
6. upload sur Medplum







