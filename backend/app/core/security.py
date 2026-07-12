from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional
from jose import JWTError, jwt
import bcrypt

# JWT configurations
SECRET_KEY = "assetflow-hackathon-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def hash_password(password: str) -> str:
    return get_password_hash(password)


def create_access_token(
    data: Optional[dict] = None,
    subject: Optional[Union[str, Any]] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    to_encode = {}
    if data is not None:
        to_encode = data.copy()
    elif subject is not None:
        to_encode = {"sub": str(subject)}

    if "exp" not in to_encode:
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=ACCESS_TOKEN_EXPIRE_MINUTES
            )
        to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


# ===========================================================================
# Principal / header-based auth seam for the self-contained workflow modules.
#
# The Booking / Maintenance / Asset-Audit / Notifications / Activity-Log /
# Dashboard / Reports modules consume ``Principal`` and ``get_current_user``
# from here (``from app.core.security import Principal, get_current_user``).
# They identify the caller from the frontend's forwarded identity headers:
#
#     X-User-Id     -- string principal id (string-FK contract, e.g. EMP-1001)
#     X-User-Role   -- one of app.core.enums.Role
#     Authorization -- "Bearer demo.<id>.<role>" (fallback source)
#
# This is intentionally separate from the JWT/User seam in
# ``app.core.dependencies`` used by the /api/v1 organization routers — the two
# auth systems coexist; nothing above is affected.
# ===========================================================================
from fastapi import HTTPException, Request, status  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from app.core.enums import Role  # noqa: E402


class Principal(BaseModel):
    """The authenticated caller, derived from the request's identity headers."""

    id: str
    role: Role
    department_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    def has_role(self, *roles: "Role") -> bool:
        return self.is_admin or self.role in roles


def _role_from_str(raw: Optional[str]) -> Optional[Role]:
    if not raw:
        return None
    try:
        return Role(raw.strip().lower())
    except ValueError:
        return None


def _principal_from_bearer(token: str):
    """Parse the demo bearer token ``demo.<id>.<role>`` into (id, role)."""
    if not token.lower().startswith("bearer "):
        return None, None
    parts = token[7:].strip().split(".")
    if len(parts) >= 3 and parts[0] == "demo":
        return parts[1], _role_from_str(parts[-1])
    return None, None


def get_current_user(request: Request) -> "Principal":
    """Resolve the workflow-module principal from the request's identity headers."""
    user_id = request.headers.get("X-User-Id")
    role = _role_from_str(request.headers.get("X-User-Role"))

    if not user_id or role is None:
        bearer_id, bearer_role = _principal_from_bearer(
            request.headers.get("Authorization", "")
        )
        user_id = user_id or bearer_id
        role = role or bearer_role

    if not user_id or role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Principal(
        id=user_id,
        role=role,
        email=request.headers.get("X-User-Email"),
        name=request.headers.get("X-User-Name"),
    )
