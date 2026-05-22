-- ABS Statistical Area boundary tables (populated by bootstrap.sh)
CREATE TABLE IF NOT EXISTS abs_sa1_2021 (
    sa1_code_2021   VARCHAR(15) PRIMARY KEY,
    sa2_code_2021   VARCHAR(15),
    sa2_name_2021   VARCHAR(100),
    sa3_code_2021   VARCHAR(10),
    sa3_name_2021   VARCHAR(100),
    sa4_code_2021   VARCHAR(5),
    sa4_name_2021   VARCHAR(100),
    gcc_code_2021   VARCHAR(5),
    gcc_name_2021   VARCHAR(100),
    state_code_2021 VARCHAR(1),
    state_name_2021 VARCHAR(50),
    state_abbrev    VARCHAR(3),
    area_albers_sqkm NUMERIC(12,4),
    geometry        GEOMETRY(MultiPolygon, 4326)
);
CREATE INDEX IF NOT EXISTS idx_abs_sa1_geom ON abs_sa1_2021 USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_abs_sa1_sa2 ON abs_sa1_2021 (sa2_code_2021);

CREATE TABLE IF NOT EXISTS abs_sa2_2021 (
    sa2_code_2021   VARCHAR(15) PRIMARY KEY,
    sa2_name_2021   VARCHAR(100),
    sa3_code_2021   VARCHAR(10),
    sa3_name_2021   VARCHAR(100),
    sa4_code_2021   VARCHAR(5),
    sa4_name_2021   VARCHAR(100),
    gcc_code_2021   VARCHAR(5),
    gcc_name_2021   VARCHAR(100),
    state_code_2021 VARCHAR(1),
    state_name_2021 VARCHAR(50),
    state_abbrev    VARCHAR(3),
    area_albers_sqkm NUMERIC(12,4),
    geometry        GEOMETRY(MultiPolygon, 4326)
);
CREATE INDEX IF NOT EXISTS idx_abs_sa2_geom ON abs_sa2_2021 USING GIST (geometry);

CREATE TABLE IF NOT EXISTS abs_sa3_2021 (
    sa3_code_2021   VARCHAR(10) PRIMARY KEY,
    sa3_name_2021   VARCHAR(100),
    sa4_code_2021   VARCHAR(5),
    sa4_name_2021   VARCHAR(100),
    gcc_code_2021   VARCHAR(5),
    state_code_2021 VARCHAR(1),
    state_abbrev    VARCHAR(3),
    area_albers_sqkm NUMERIC(12,4),
    geometry        GEOMETRY(MultiPolygon, 4326)
);
CREATE INDEX IF NOT EXISTS idx_abs_sa3_geom ON abs_sa3_2021 USING GIST (geometry);

CREATE TABLE IF NOT EXISTS abs_sa4_2021 (
    sa4_code_2021   VARCHAR(5) PRIMARY KEY,
    sa4_name_2021   VARCHAR(100),
    gcc_code_2021   VARCHAR(5),
    state_code_2021 VARCHAR(1),
    state_abbrev    VARCHAR(3),
    area_albers_sqkm NUMERIC(12,4),
    geometry        GEOMETRY(MultiPolygon, 4326)
);
CREATE INDEX IF NOT EXISTS idx_abs_sa4_geom ON abs_sa4_2021 USING GIST (geometry);

CREATE TABLE IF NOT EXISTS abs_lga_2023 (
    lga_code_2023   VARCHAR(10) PRIMARY KEY,
    lga_name_2023   VARCHAR(100),
    state_code_2021 VARCHAR(1),
    state_abbrev    VARCHAR(3),
    area_albers_sqkm NUMERIC(12,4),
    geometry        GEOMETRY(MultiPolygon, 4326)
);
CREATE INDEX IF NOT EXISTS idx_abs_lga_geom ON abs_lga_2023 USING GIST (geometry);

CREATE TABLE IF NOT EXISTS abs_state_2021 (
    state_code_2021 VARCHAR(1) PRIMARY KEY,
    state_name_2021 VARCHAR(50),
    state_abbrev    VARCHAR(3),
    area_albers_sqkm NUMERIC(12,4),
    geometry        GEOMETRY(MultiPolygon, 4326)
);
CREATE INDEX IF NOT EXISTS idx_abs_state_geom ON abs_state_2021 USING GIST (geometry);

-- SEIFA 2021
CREATE TABLE IF NOT EXISTS abs_seifa_2021 (
    sa2_code_2021       VARCHAR(15) PRIMARY KEY,
    sa2_name_2021       VARCHAR(100),
    irsd_score          INTEGER,
    irsd_decile         SMALLINT,
    irsad_score         INTEGER,
    irsad_decile        SMALLINT,
    ier_score           INTEGER,
    ier_decile          SMALLINT,
    ieo_score           INTEGER,
    ieo_decile          SMALLINT,
    usual_resident_pop  INTEGER
);

-- G-NAF address table (populated by bootstrap.sh from data.gov.au)
CREATE TABLE IF NOT EXISTS gnaf_addresses (
    address_detail_pid  VARCHAR(15) PRIMARY KEY,
    full_address        TEXT NOT NULL,
    building_name       TEXT,
    flat_type           VARCHAR(20),
    flat_number         VARCHAR(20),
    level_type          VARCHAR(20),
    level_number        VARCHAR(20),
    number_first        VARCHAR(20),
    number_last         VARCHAR(20),
    street_name         VARCHAR(100),
    street_type_code    VARCHAR(20),
    locality_name       VARCHAR(100),
    state               VARCHAR(3),
    postcode            VARCHAR(4),
    confidence          SMALLINT,
    geometry            GEOMETRY(Point, 4326)
);
CREATE INDEX IF NOT EXISTS idx_gnaf_geom ON gnaf_addresses USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_gnaf_trgm ON gnaf_addresses USING GIN (full_address gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_gnaf_fts ON gnaf_addresses USING GIN (to_tsvector('english', full_address));

-- OSM road network for pgRouting (populated by osm2pgsql bootstrap)
CREATE TABLE IF NOT EXISTS osm_roads_aus (
    id          BIGSERIAL PRIMARY KEY,
    osm_id      BIGINT,
    name        TEXT,
    highway     VARCHAR(50),
    oneway      BOOLEAN DEFAULT FALSE,
    maxspeed    INTEGER,
    lanes       SMALLINT,
    source      BIGINT,
    target      BIGINT,
    cost        DOUBLE PRECISION,
    reverse_cost DOUBLE PRECISION,
    geometry    GEOMETRY(LineString, 4326)
);
CREATE INDEX IF NOT EXISTS idx_osm_roads_geom ON osm_roads_aus USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_osm_roads_source ON osm_roads_aus (source);
CREATE INDEX IF NOT EXISTS idx_osm_roads_target ON osm_roads_aus (target);
