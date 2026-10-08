from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict, Field


# Bazowy schemat z wspólnymi polami
class UserBase(BaseModel):
    email: EmailStr


# DTO używane przy rejestracji (input z formularza/JSON)
class UserCreate(UserBase):
    password: str = Field(..., max_length=72,
                          description="Hasło nie może być dłuższe niż 72 znaki")


# Response DTO zwracany przez API (brak pola password!)
class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Schematy dla JWT Tokenów
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int | None = None
