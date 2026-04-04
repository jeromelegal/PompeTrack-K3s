import requests



WORKER_URL = "http://localhost:8000/api/medication/"

def create_medication():
    return requests.get(
        WORKER_URL,
        headers={"Content-Type": "application/json"},
    )
