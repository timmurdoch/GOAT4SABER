"""ABS boundary and census data endpoints."""
from typing import Literal

from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import text

from app.core.dependencies import DB, CurrentUser

router = APIRouter(prefix="/abs", tags=["abs"])

BOUNDARY_TABLES = {
    "sa1": "abs_sa1_2021",
    "sa2": "abs_sa2_2021",
    "sa3": "abs_sa3_2021",
    "sa4": "abs_sa4_2021",
    "lga": "abs_lga_2023",
    "state": "abs_state_2021",
}

STATES = {"NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT"}


@router.get("/boundaries")
async def get_boundaries(
    level: Literal["sa1", "sa2", "sa3", "sa4", "lga", "state"],
    state: str | None = Query(None, description="State abbreviation e.g. VIC"),
    bbox: str | None = Query(None, description="minx,miny,maxx,maxy in WGS84"),
    current_user: CurrentUser = None,
    db: DB = None,
):
    table = BOUNDARY_TABLES.get(level)
    if not table:
        raise HTTPException(status_code=400, detail=f"Invalid level. Use: {list(BOUNDARY_TABLES.keys())}")

    where_clauses = ["1=1"]
    params: dict = {}

    if state:
        state_upper = state.upper()
        if state_upper not in STATES:
            raise HTTPException(status_code=400, detail=f"Invalid state. Use: {STATES}")
        where_clauses.append("state_abbrev = :state")
        params["state"] = state_upper

    if bbox:
        try:
            minx, miny, maxx, maxy = map(float, bbox.split(","))
        except ValueError:
            raise HTTPException(status_code=400, detail="bbox must be 'minx,miny,maxx,maxy'")
        where_clauses.append("ST_Intersects(geometry, ST_MakeEnvelope(:minx, :miny, :maxx, :maxy, 4326))")
        params.update({"minx": minx, "miny": miny, "maxx": maxx, "maxy": maxy})

    where = " AND ".join(where_clauses)
    result = await db.execute(
        text(f"""
            SELECT
                ST_AsGeoJSON(geometry)::json AS geometry,
                *
            FROM {table}
            WHERE {where}
            LIMIT 5000
        """),
        params,
    )
    rows = result.mappings().all()
    features = [
        {
            "type": "Feature",
            "geometry": r["geometry"],
            "properties": {k: v for k, v in r.items() if k != "geometry"},
        }
        for r in rows
    ]
    return {"type": "FeatureCollection", "features": features}


@router.get("/seifa")
async def get_seifa(
    sa2_code: str | None = None,
    lga_code: str | None = None,
    current_user: CurrentUser = None,
    db: DB = None,
):
    if not sa2_code and not lga_code:
        raise HTTPException(status_code=400, detail="Provide sa2_code or lga_code")

    where = "sa2_code_2021 = :code" if sa2_code else "lga_code_2023 = :code"
    code = sa2_code or lga_code

    result = await db.execute(
        text(f"SELECT * FROM abs_seifa_2021 WHERE {where}"),
        {"code": code},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="No SEIFA data found for this area")
    return dict(row)
