import os

def read_secret_from_file(secret_file_name):
    pathfile = f"/var/run/secrets/{secret_file_name}"
    if not os.path.exists(pathfile):
        raise FileNotFoundError(f"Secret file not found: {pathfile}")
    with open(pathfile, "r") as f:
        return f.read().strip()