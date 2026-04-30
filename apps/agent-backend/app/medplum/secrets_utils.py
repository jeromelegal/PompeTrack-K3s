import os

# Function to read secret from file
def read_secret_from_file(secret_file_name):
    """Reading client ID and secret from environment variables or secrets."""
    pathfile = f"/var/run/secrets/{secret_file_name}"
    if not os.path.exists(pathfile):
        raise FileNotFoundError(f"Secret file not found: {pathfile}")
    with open(pathfile, "r") as f:
        return f.read().strip()