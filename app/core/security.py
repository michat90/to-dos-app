from datetime import datetime, timedelta, timezone
import bcrypt
from jose import JWTError, jwt
import uuid

from app.core.config import settings

# ---------------------------------------------------------------------------
# Obsługa haseł (Czysty bcrypt bez passlib)
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Generuje bezpieczny hash z surowego hasła."""
    pwd_bytes = password.encode("utf-8")[:72]  # Przycięcie bajtów dla bcrypt
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Weryfikuje surowe hasło z hashem z bazy."""
    pwd_bytes = plain_password.encode("utf-8")[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(pwd_bytes, hashed_bytes)


# ---------------------------------------------------------------------------
# Obsługa Tokenów JWT
# ---------------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({
        "exp": expire,
        "jti": str(uuid.uuid4())
    })  # Dodanie unikalnego identyfikatora tokenu (jti)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None
