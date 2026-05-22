// Shared TypeScript types between web client and any future TS services

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_superuser: boolean;
  api_key: string | null;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export type GeomType = "point" | "linestring" | "polygon" | "multipoint" | "multilinestring" | "multipolygon" | "raster";
export type SourceType = "upload" | "wms" | "wfs" | "analysis" | "abs";

export interface Layer {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  geom_type: GeomType | null;
  srid: number;
  source_type: SourceType;
  storage_path: string | null;
  table_name: string | null;
  feature_count: number | null;
  metadata_: Record<string, unknown>;
  visible: boolean;
  created_at: string;
}

export type AnalysisType = "isochrone" | "buffer" | "point_in_polygon" | "spatial_join" | "catchment";
export type JobStatus = "pending" | "running" | "completed" | "failed";

export interface AnalysisJob {
  id: string;
  project_id: string;
  type: AnalysisType;
  status: JobStatus;
  config: Record<string, unknown>;
  result_layer_id: string | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface GeocodeResult {
  pid: string;
  address: string;
  longitude: number | null;
  latitude: number | null;
  state: string;
  postcode: string;
}
