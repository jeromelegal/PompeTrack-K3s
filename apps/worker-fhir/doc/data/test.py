import json

file = "data.json"

with open(file, "r") as f:
    health = json.load(f)
    
health["data"].keys()

metrics = health["data"]["metrics"]
workouts = health["data"]["workouts"]
stateOfMind = health["data"]["stateOfMind"]

names = []
for i in metrics:
    names.append(i['name'])
    
def split_json(json_file):
    for k in json_file["data"].keys():
        if k == "metrics":
            metrics = json_file["data"]["metrics"]
        elif k == "workouts":
            workouts = json_file["data"]["workouts"]
        elif k == "stateOfMind":
            stateofmind = json_file["data"]["stateOfMind"]
        else:
            print(f"Nouvelle catégorie: {k}.")
    return metrics, workouts, stateofmind

metrics, workouts, stateofmind = split_json(health)

with open("metrics.json", "w") as f:
    json.dump(metrics, f, indent=2)
    
with open("workouts.json", "w") as f:
    json.dump(workouts, f, indent=2)
    
with open("stateofmind.json", "w") as f:
    json.dump(stateofmind, f, indent=2)