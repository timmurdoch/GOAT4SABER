from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.dependencies import DB, CurrentUser
from app.models.analysis import AnalysisJob, AnalysisType, JobStatus
from app.schemas.analysis import (
    IsochroneRequest, BufferRequest, PointInPolygonRequest,
    SpatialJoinRequest, AnalysisJobResponse,
)
from app.workers.analysis_tasks import run_isochrone, run_buffer, run_point_in_polygon, run_spatial_join

router = APIRouter(prefix="/analysis", tags=["analysis"])


async def _create_and_dispatch(db: DB, project_id: str, user_id: str, job_type: AnalysisType, config: dict, task_fn) -> AnalysisJob:
    job = AnalysisJob(
        project_id=project_id,
        created_by=user_id,
        type=job_type,
        status=JobStatus.pending,
        config=config,
    )
    db.add(job)
    await db.flush()

    celery_result = task_fn.delay(job.id)
    job.celery_task_id = celery_result.id
    return job


@router.post("/isochrone", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_isochrone(payload: IsochroneRequest, current_user: CurrentUser, db: DB):
    job = await _create_and_dispatch(
        db, payload.project_id, current_user.id,
        AnalysisType.isochrone,
        payload.model_dump(),
        run_isochrone,
    )
    return job


@router.post("/buffer", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_buffer(payload: BufferRequest, current_user: CurrentUser, db: DB):
    job = await _create_and_dispatch(
        db, payload.project_id, current_user.id,
        AnalysisType.buffer,
        payload.model_dump(),
        run_buffer,
    )
    return job


@router.post("/point-in-polygon", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_pip(payload: PointInPolygonRequest, current_user: CurrentUser, db: DB):
    job = await _create_and_dispatch(
        db, payload.project_id, current_user.id,
        AnalysisType.point_in_polygon,
        payload.model_dump(),
        run_point_in_polygon,
    )
    return job


@router.post("/spatial-join", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_spatial_join(payload: SpatialJoinRequest, current_user: CurrentUser, db: DB):
    job = await _create_and_dispatch(
        db, payload.project_id, current_user.id,
        AnalysisType.spatial_join,
        payload.model_dump(),
        run_spatial_join,
    )
    return job


@router.get("/jobs/{job_id}", response_model=AnalysisJobResponse)
async def get_job(job_id: str, current_user: CurrentUser, db: DB):
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
