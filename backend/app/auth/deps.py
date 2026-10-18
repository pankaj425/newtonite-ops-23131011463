from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.errors import unauthorized
from app.auth.security import TokenError, decode_access_token
from app.db import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise unauthorized("Missing bearer token")
    try:
        user_id = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise unauthorized(str(exc)) from exc

    user = db.get(User, user_id)
    if user is None:
        raise unauthorized("User no longer exists")
    return user
