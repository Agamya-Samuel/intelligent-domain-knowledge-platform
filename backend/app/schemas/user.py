"""User Pydantic schemas — request/response models for the User model."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserCreateRequest(BaseModel):
    """Schema for creating a new user record."""

    id: str
    email: str
    name: str
    image_url: str | None = None

    model_config = ConfigDict(extra="forbid")


class UserResponse(BaseModel):
    """Schema for returning user data in API responses."""

    id: str
    email: str
    name: str
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
