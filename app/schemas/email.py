from pydantic import BaseModel, EmailStr


class EmailTestRequest(BaseModel):
    email: EmailStr  # Pydantic od razu zweryfikuje, czy string jest poprawnym adresem e-mail!
