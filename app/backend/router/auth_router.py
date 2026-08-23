from fastapi import APIRouter, Depends, HTTPException, status

from backend.database import db
from backend.deps import current_user
from backend.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    UserResponse,
)
from backend.security import create_access_token, hash_password, verify_password


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterRequest) -> AuthResponse:
    with db() as conn:
        exists = conn.execute("SELECT id FROM users WHERE email = ?", (payload.email.lower(),)).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="该邮箱已注册")
        cursor = conn.execute(
            "INSERT INTO users(email, password_hash, display_name, avatar_data) VALUES (?, ?, ?, ?)",
            (payload.email.lower(), hash_password(payload.password), payload.display_name.strip(), ""),
        )
        user_id = cursor.lastrowid
    user = UserResponse(id=user_id, email=payload.email.lower(), display_name=payload.display_name.strip(), avatar_data="")
    return AuthResponse(access_token=create_access_token(user_id, user.email), user=user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (payload.email.lower(),)).fetchone()
    if row is None or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    user = UserResponse(id=row["id"], email=row["email"], display_name=row["display_name"], avatar_data=row["avatar_data"] or "")
    return AuthResponse(access_token=create_access_token(user.id, user.email), user=user)


@router.get("/me", response_model=UserResponse)
def me(user: dict = Depends(current_user)) -> UserResponse:
    return UserResponse(**user)


@router.patch("/me", response_model=UserResponse)
def update_profile(payload: ProfileUpdateRequest, user: dict = Depends(current_user)) -> UserResponse:
    with db() as conn:
        conn.execute(
            "UPDATE users SET display_name = ?, avatar_data = ? WHERE id = ?",
            (payload.display_name, payload.avatar_data, user["id"]),
        )
        row = conn.execute(
            "SELECT id, email, display_name, avatar_data FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()
    return UserResponse(**dict(row))


@router.post("/change-password", status_code=204)
def change_password(payload: ChangePasswordRequest, user: dict = Depends(current_user)) -> None:
    with db() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        if row is None or not verify_password(payload.current_password, row["password_hash"]):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="当前密码错误")
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(payload.new_password), user["id"]))
