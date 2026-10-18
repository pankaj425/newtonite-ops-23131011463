from pydantic import BaseModel, Field

from app.schemas.user import MembershipOut, UserOut


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
    memberships: list[MembershipOut]
