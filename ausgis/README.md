# AusGIS — Australian WebGIS Analysis Platform

A self-hosted, Docker-deployable WebGIS platform for spatial analysis in Australia. Inspired by GOAT (Geo Open Accessibility Tool), built ground-up for Australian data standards and coordinate systems.

## Quick Start

```bash
cp .env.example .env
docker compose up -d
```

Services will be available at:
| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/api/docs |
| Tile server | http://localhost:8100 |
| MinIO console | http://localhost:9001 |

## Architecture

```
ausgis/
├── apps/
│   ├── api/        # FastAPI backend (port 8000)
│   ├── geoapi/     # MVT tile server + WMS/WFS (port 8100)
│   └── web/        # Next.js 14 frontend (port 3000)
├── packages/
│   └── shared-types/  # Shared TypeScript types
├── db/
│   └── init/       # PostGIS schema + bootstrap scripts
└── nginx/          # Reverse proxy config
```

## Tech Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.0, Pydantic v2
- **Database:** PostgreSQL 15 + PostGIS 3.4 + pgRouting
- **Queue:** Celery + Redis
- **Storage:** MinIO (S3-compatible)
- **Frontend:** Next.js 14, MapLibre GL JS, MUI, Zustand
- **Auth:** JWT (no Keycloak)

## Australian Data Bootstrap

Load base datasets after first `docker compose up`:

```bash
# Load ABS boundaries and optionally OSM + G-NAF
docker compose exec db /docker-entrypoint-initdb.d/bootstrap.sh

# With OSM road network (~1GB download):
LOAD_OSM=1 docker compose exec db /docker-entrypoint-initdb.d/bootstrap.sh

# With G-NAF addresses (requires manual download, ~3GB):
# 1. Download from https://data.gov.au/dataset/ds-dga-19432f89-dc3a-4ef3-b943-5326ef1dbecc
# 2. Extract PSV files to /tmp/ausgis-bootstrap/gnaf/
LOAD_GNAF=1 docker compose exec db /docker-entrypoint-initdb.d/bootstrap.sh
```

## API Endpoints

See interactive docs at `http://localhost:8000/api/docs`

Key endpoints:
- `POST /api/v1/auth/login` — JWT login
- `POST /api/v1/auth/register` — Create account
- `GET /api/v1/projects` — List projects
- `POST /api/v1/layers/upload` — Upload GeoJSON/SHP/GPKG/CSV
- `POST /api/v1/analysis/isochrone` — Walk/cycle/drive catchments
- `POST /api/v1/analysis/buffer` — Buffer analysis
- `POST /api/v1/analysis/point-in-polygon` — Aggregate points in polygons
- `POST /api/v1/analysis/spatial-join` — Spatial join
- `GET /api/v1/geocode/search` — G-NAF address search
- `GET /api/v1/abs/boundaries` — ABS SA1/SA2/SA3/SA4/LGA boundaries
- `GET /tiles/{layer_id}/{z}/{x}/{y}.mvt` — MapLibre MVT tiles

## Coordinate Systems

- Default storage: **GDA2020 / WGS84 (EPSG:4326)**
- Map rendering: **Web Mercator (EPSG:3857)**
- Australia extent: `[113, -44, 154, -10]`

## Development

```bash
# Run with hot reload
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Run API migrations
docker compose exec api alembic upgrade head

# Access database
docker compose exec db psql -U ausgis -d ausgis
```

## Environment Variables

See `.env.example` for all configuration options.
