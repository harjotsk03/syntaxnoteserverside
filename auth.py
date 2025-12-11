# auth.py
from datetime import datetime, timedelta
from jose import jwt, JWTError
import bcrypt

SECRET_KEY = "SUPER_SECRET_KEY_CHANGE_THIS"
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 6

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_access_token(data: dict, expires_hours: int = TOKEN_EXPIRE_HOURS):
    expire = datetime.utcnow() + timedelta(hours=expires_hours)
    to_encode = {**data, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    """
    Decode and validate JWT token
    Raises JWTError if invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise Exception(f"Token validation failed: {str(e)}")