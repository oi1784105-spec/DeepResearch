import re

from pydantic import BaseModel, Field, field_validator


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise ValueError("请输入有效邮箱")
    return value


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=40)

    _normalize_email = field_validator("email")(normalize_email)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)

    _normalize_email = field_validator("email")(normalize_email)


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: str
    avatar_data: str = ""


class ProfileUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=40)
    avatar_data: str = Field(default="", max_length=3_000_000)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("昵称不能为空")
        return value

    @field_validator("avatar_data")
    @classmethod
    def validate_avatar(cls, value: str) -> str:
        if not value:
            return value
        if not value.startswith(("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,", "data:image/gif;base64,")):
            raise ValueError("头像仅支持 PNG、JPEG、WEBP 或 GIF 图片")
        return value


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    user: UserResponse
