import jwt
import secrets

secret = secrets.token_hex(32)
print(f"SECRET: {secret}")

token = jwt.encode(
    {
        "sub": "strength-device-v1",
        "scopes": ["ingest:strenght"],
        "iss": "pompetrack-device",
    },
    secret,
    algorithm="HS256"
)
print(f"TOKEN: {token}")