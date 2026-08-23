from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .database import db
from .security import decode_access_token


bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    try:
        token = decode_access_token(credentials.credentials)
        user_id = int(token["sub"])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期，请重新登录")
    with db() as conn:
        row = conn.execute("SELECT id, email, display_name, avatar_data FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return dict(row)


def active_provider_for(user_id: int) -> dict:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM providers WHERE user_id = ? AND active = 1 ORDER BY updated_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=428, detail="请先配置并启用一个 AI Provider")
    return dict(row)
