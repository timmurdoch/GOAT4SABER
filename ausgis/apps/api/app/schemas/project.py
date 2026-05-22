from datetime import datetime
from pydantic import BaseModel
from app.models.project import ProjectRole


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MemberAdd(BaseModel):
    user_email: str
    role: ProjectRole = ProjectRole.viewer


class MemberResponse(BaseModel):
    id: str
    user_id: str
    role: ProjectRole
    joined_at: datetime

    model_config = {"from_attributes": True}
