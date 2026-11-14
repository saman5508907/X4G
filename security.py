from pwdlib import PasswordHash
from itsdangerous import URLSafeSerializer
import os

password_hash = PasswordHash.recommended()
serializer = URLSafeSerializer(os.getenv("SECRET_KEY", "dev-only-change-me"), salt="paypilot-auth")

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    try:
        return password_hash.verify(password, hashed)
    except Exception:
        return False

def make_session(user_id: int) -> str:
    return serializer.dumps({"uid": user_id})

def read_session(token: str):
    try:
        data = serializer.loads(token)
        return int(data["uid"])
    except Exception:
        return None
