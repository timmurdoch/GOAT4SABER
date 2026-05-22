#!/usr/bin/env bash
# AusGIS data bootstrap — downloads and loads Australian base datasets.
# Run once after docker compose up: docker compose exec db /docker-entrypoint-initdb.d/bootstrap.sh
# Requires: wget, ogr2ogr (GDAL), osm2pgsql, unzip

set -euo pipefail

DB_HOST="${POSTGRES_HOST:-localhost}"
DB_NAME="${POSTGRES_DB:-ausgis}"
DB_USER="${POSTGRES_USER:-ausgis}"
DB_PASS="${POSTGRES_PASSWORD:-changeme}"
PGCONN="postgresql://$DB_USER:$DB_PASS@$DB_HOST:5432/$DB_NAME"

DATA_DIR="/tmp/ausgis-bootstrap"
mkdir -p "$DATA_DIR"

echo "=== AusGIS Bootstrap ==="
echo "Database: $PGCONN"
echo ""

# ── 1. ABS ASGS 2021 Boundaries ───────────────────────────────────────────────
echo "[1/3] Downloading ABS ASGS 2021 boundaries..."

ABS_BASE="https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3/jul2021-jun2026/access-and-downloads/digital-boundary-files"

declare -A ABS_FILES=(
    ["SA1_2021_AUST_SHP_GDA2020.zip"]="abs_sa1_2021"
    ["SA2_2021_AUST_SHP_GDA2020.zip"]="abs_sa2_2021"
    ["SA3_2021_AUST_SHP_GDA2020.zip"]="abs_sa3_2021"
    ["SA4_2021_AUST_SHP_GDA2020.zip"]="abs_sa4_2021"
    ["LGA_2023_AUST_SHP_GDA2020.zip"]="abs_lga_2023"
    ["STE_2021_AUST_SHP_GDA2020.zip"]="abs_state_2021"
)

for zip_file in "${!ABS_FILES[@]}"; do
    table="${ABS_FILES[$zip_file]}"
    dest="$DATA_DIR/$zip_file"
    if [ ! -f "$dest" ]; then
        echo "  Downloading $zip_file..."
        wget -q -O "$dest" "$ABS_BASE/$zip_file" || {
            echo "  WARNING: Could not download $zip_file — skipping"
            continue
        }
    fi
    echo "  Loading $zip_file → $table..."
    tmpdir=$(mktemp -d)
    unzip -q "$dest" -d "$tmpdir"
    shp=$(find "$tmpdir" -name "*.shp" | head -1)
    if [ -n "$shp" ]; then
        ogr2ogr -f "PostgreSQL" "PG:$PGCONN" "$shp" \
            -nln "$table" \
            -t_srs EPSG:4326 \
            -overwrite \
            -lco GEOMETRY_NAME=geometry \
            -lco FID=gid \
            -progress
    fi
    rm -rf "$tmpdir"
done

echo "[1/3] ABS boundaries loaded."

# ── 2. G-NAF Address Database ─────────────────────────────────────────────────
echo "[2/3] G-NAF address loading..."
echo "  NOTE: G-NAF is ~3GB. Download manually from:"
echo "  https://data.gov.au/dataset/ds-dga-19432f89-dc3a-4ef3-b943-5326ef1dbecc"
echo "  Place the extracted PSV files in $DATA_DIR/gnaf/ and re-run with LOAD_GNAF=1"

if [ "${LOAD_GNAF:-0}" = "1" ] && [ -d "$DATA_DIR/gnaf" ]; then
    echo "  Loading G-NAF addresses from $DATA_DIR/gnaf ..."
    psql "$PGCONN" <<'SQL'
COPY gnaf_addresses (
    address_detail_pid, full_address, building_name,
    flat_type, flat_number, level_type, level_number,
    number_first, number_last, street_name, street_type_code,
    locality_name, state, postcode, confidence,
    geometry
)
FROM PROGRAM 'cat /tmp/ausgis-bootstrap/gnaf/ADDRESS_DETAIL_*.psv | python3 /tmp/ausgis-bootstrap/gnaf_transform.py'
WITH (FORMAT CSV, DELIMITER '|', HEADER TRUE);
SQL
    echo "  Building G-NAF indexes..."
    psql "$PGCONN" -c "REINDEX TABLE gnaf_addresses;"
fi

echo "[2/3] G-NAF step complete."

# ── 3. OSM Australia Road Network ─────────────────────────────────────────────
echo "[3/3] OSM road network..."
echo "  NOTE: OSM Australia extract is ~1GB. Set LOAD_OSM=1 to enable automatic download."

if [ "${LOAD_OSM:-0}" = "1" ]; then
    OSM_URL="https://download.geofabrik.de/australia-oceania/australia-latest.osm.pbf"
    OSM_FILE="$DATA_DIR/australia-latest.osm.pbf"
    if [ ! -f "$OSM_FILE" ]; then
        echo "  Downloading OSM Australia (~1GB)..."
        wget -q --show-progress -O "$OSM_FILE" "$OSM_URL"
    fi
    echo "  Processing with osm2pgsql..."
    osm2pgsql \
        --database "$PGCONN" \
        --slim \
        --hstore \
        --tag-transform-script /tmp/ausgis-bootstrap/osm2pgsql-roads.lua \
        "$OSM_FILE"
    echo "  Building pgRouting topology..."
    psql "$PGCONN" -c "SELECT pgr_createTopology('osm_roads_aus', 0.00001, 'geometry', 'id');"
fi

echo "[3/3] OSM step complete."
echo ""
echo "=== Bootstrap complete ==="
echo "To load optional datasets, set environment variables and re-run:"
echo "  LOAD_GNAF=1 LOAD_OSM=1 $0"
