from pydantic import BaseModel, ConfigDict

from app.models.enums import Role


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str


class MembershipOut(BaseModel):
    id: int
    user_id: int
    team_id: int
    team_name: str
    role: Role


class MeOut(BaseModel):
    user: UserOut
    memberships: list[MembershipOut]
