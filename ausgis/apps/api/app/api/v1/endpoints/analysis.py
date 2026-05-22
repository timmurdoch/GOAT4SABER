from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.dependencies import DB, CurrentUser
from app.models.analysis import AnalysisJob, JobStatus
from app.schemas.analysis import (
    # Basic
    IsochroneRequest, BufferRequest, PointInPolygonRequest, SpatialJoinRequest,
    # Network
    ShortestPathRequest, ODMatrixRequest, CatchmentPopulationRequest,
    # Overlay / geometry
    ClipRequest, OverlayRequest, DissolveRequest, CentroidRequest,
    ConvexHullRequest, VoronoiRequest,
    # Point
    KernelDensityRequest, ClusterRequest, HexbinRequest,
    # Response
    AnalysisJobResponse,
)
from app.workers.analysis_tasks import run_isochrone, run_buffer, run_point_in_polygon, run_spatial_join
from app.workers.network_tasks import run_shortest_path, run_od_matrix, run_catchment_population
from app.workers.vector_tasks import run_clip, run_overlay, run_dissolve, run_centroid, run_convex_hull, run_voronoi
from app.workers.point_tasks import run_kernel_density, run_cluster, run_hexbin

router = APIRouter(prefix="/analysis", tags=["analysis"])


async def _dispatch(db: DB, project_id: str, user_id: str, job_type: str, config: dict, task_fn) -> AnalysisJob:
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


# ── Basic ─────────────────────────────────────────────────────────────────────

@router.post("/isochrone", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_isochrone(payload: IsochroneRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "isochrone", payload.model_dump(), run_isochrone)


@router.post("/buffer", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_buffer(payload: BufferRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "buffer", payload.model_dump(), run_buffer)


@router.post("/point-in-polygon", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_pip(payload: PointInPolygonRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "point_in_polygon", payload.model_dump(), run_point_in_polygon)


@router.post("/spatial-join", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_spatial_join(payload: SpatialJoinRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "spatial_join", payload.model_dump(), run_spatial_join)


# ── Network ───────────────────────────────────────────────────────────────────

@router.post("/shortest-path", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_shortest_path(payload: ShortestPathRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "shortest_path", payload.model_dump(), run_shortest_path)


@router.post("/od-matrix", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_od_matrix(payload: ODMatrixRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "od_matrix", payload.model_dump(), run_od_matrix)


@router.post("/catchment-population", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_catchment_population(payload: CatchmentPopulationRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "catchment_population", payload.model_dump(), run_catchment_population)


# ── Overlay / geometry ────────────────────────────────────────────────────────

@router.post("/clip", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_clip(payload: ClipRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "clip", payload.model_dump(), run_clip)


@router.post("/overlay", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_overlay(payload: OverlayRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "overlay", payload.model_dump(), run_overlay)


@router.post("/dissolve", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_dissolve(payload: DissolveRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "dissolve", payload.model_dump(), run_dissolve)


@router.post("/centroid", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_centroid(payload: CentroidRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "centroid", payload.model_dump(), run_centroid)


@router.post("/convex-hull", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_convex_hull(payload: ConvexHullRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "convex_hull", payload.model_dump(), run_convex_hull)


@router.post("/voronoi", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_voronoi(payload: VoronoiRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "voronoi", payload.model_dump(), run_voronoi)


# ── Point analysis ────────────────────────────────────────────────────────────

@router.post("/kernel-density", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_kde(payload: KernelDensityRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "kernel_density", payload.model_dump(), run_kernel_density)


@router.post("/cluster", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_cluster(payload: ClusterRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "cluster", payload.model_dump(), run_cluster)


@router.post("/hexbin", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_hexbin(payload: HexbinRequest, current_user: CurrentUser, db: DB):
    return await _dispatch(db, payload.project_id, current_user.id, "hexbin", payload.model_dump(), run_hexbin)


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}", response_model=AnalysisJobResponse)
async def get_job(job_id: str, current_user: CurrentUser, db: DB):
    result = await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs", response_model=list[AnalysisJobResponse])
async def list_jobs(project_id: str, current_user: CurrentUser, db: DB):
    result = await db.execute(
        select(AnalysisJob)
        .where(AnalysisJob.project_id == project_id)
        .order_by(AnalysisJob.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()
