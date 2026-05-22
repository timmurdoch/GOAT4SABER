"""G-NAF geocoding endpoint — searches address table loaded from data.gov.au."""
import io
import csv
from typing import Annotated

from fastapi import APIRouter, Query, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from app.core.dependencies import DB, CurrentUser

router = APIRouter(prefix="/geocode", tags=["geocode"])


@router.get("/search")
async def search(
    q: Annotated[str, Query(min_length=3)],
    limit: int = 10,
    current_user: CurrentUser = None,
    db: DB = None,
):
    result = await db.execute(
        text("""
            SELECT
                address_detail_pid,
                full_address,
                ST_X(geometry) AS longitude,
                ST_Y(geometry) AS latitude,
                state,
                postcode
            FROM gnaf_addresses
            WHERE to_tsvector('english', full_address) @@ plainto_tsquery('english', :q)
               OR full_address ILIKE :like_q
            ORDER BY ts_rank(to_tsvector('english', full_address), plainto_tsquery('english', :q)) DESC
            LIMIT :limit
        """),
        {"q": q, "like_q": f"%{q}%", "limit": limit},
    )
    rows = result.mappings().all()
    return {
        "query": q,
        "results": [
            {
                "pid": r["address_detail_pid"],
                "address": r["full_address"],
                "longitude": float(r["longitude"]) if r["longitude"] else None,
                "latitude": float(r["latitude"]) if r["latitude"] else None,
                "state": r["state"],
                "postcode": r["postcode"],
            }
            for r in rows
        ],
    }


@router.post("/batch")
async def batch_geocode(
    current_user: CurrentUser,
    db: DB,
    file: Annotated[UploadFile, File()],
):
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    rows = list(reader)

    address_col = next((c for c in (reader.fieldnames or []) if "address" in c.lower()), None)
    if not address_col:
        raise HTTPException(status_code=400, detail="CSV must have an 'address' column")

    features = []
    for row in rows:
        addr = row.get(address_col, "")
        result = await db.execute(
            text("""
                SELECT full_address, ST_X(geometry) AS lon, ST_Y(geometry) AS lat
                FROM gnaf_addresses
                WHERE full_address ILIKE :q
                LIMIT 1
            """),
            {"q": f"%{addr}%"},
        )
        match = result.mappings().first()
        if match:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(match["lon"]), float(match["lat"])]},
                "properties": {**row, "matched_address": match["full_address"], "geocoded": True},
            })
        else:
            features.append({
                "type": "Feature",
                "geometry": None,
                "properties": {**row, "geocoded": False},
            })

    return {"type": "FeatureCollection", "features": features, "total": len(rows), "matched": sum(1 for f in features if f["properties"]["geocoded"])}
