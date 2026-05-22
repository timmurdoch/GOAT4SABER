from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, or_

from app.core.dependencies import DB, CurrentUser
from app.models.project import Project, ProjectMember, ProjectRole
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse, MemberAdd, MemberResponse

router = APIRouter(prefix="/projects", tags=["projects"])


async def _require_project_access(project_id: str, user_id: str, db: DB, min_role: ProjectRole = ProjectRole.viewer) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.owner_id == user_id:
        return project

    member_result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
    )
    member = member_result.scalar_one_or_none()
    role_order = {ProjectRole.viewer: 0, ProjectRole.editor: 1, ProjectRole.admin: 2}
    if not member or role_order[member.role] < role_order[min_role]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    return project


@router.get("", response_model=list[ProjectResponse])
async def list_projects(current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(Project).where(
            or_(
                Project.owner_id == current_user.id,
                Project.id.in_(
                    select(ProjectMember.project_id).where(ProjectMember.user_id == current_user.id)
                ),
            )
        )
    )
    return result.scalars().all()


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, current_user: CurrentUser, db: DB):
    project = Project(
        name=payload.name,
        description=payload.description,
        owner_id=current_user.id,
    )
    db.add(project)
    await db.flush()
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, current_user: CurrentUser, db: DB):
    return await _require_project_access(project_id, current_user.id, db)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, payload: ProjectUpdate, current_user: CurrentUser, db: DB):
    project = await _require_project_access(project_id, current_user.id, db, ProjectRole.admin)
    if payload.name is not None:
        project.name = payload.name
    if payload.description is not None:
        project.description = payload.description
    db.add(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, current_user: CurrentUser, db: DB):
    project = await _require_project_access(project_id, current_user.id, db, ProjectRole.admin)
    if project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the owner can delete a project")
    await db.delete(project)


@router.post("/{project_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def add_member(project_id: str, payload: MemberAdd, current_user: CurrentUser, db: DB):
    await _require_project_access(project_id, current_user.id, db, ProjectRole.admin)

    user_result = await db.execute(select(User).where(User.email == payload.user_email))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    member = ProjectMember(project_id=project_id, user_id=user.id, role=payload.role)
    db.add(member)
    await db.flush()
    return member


@router.get("/{project_id}/members", response_model=list[MemberResponse])
async def list_members(project_id: str, current_user: CurrentUser, db: DB):
    await _require_project_access(project_id, current_user.id, db)
    result = await db.execute(select(ProjectMember).where(ProjectMember.project_id == project_id))
    return result.scalars().all()
