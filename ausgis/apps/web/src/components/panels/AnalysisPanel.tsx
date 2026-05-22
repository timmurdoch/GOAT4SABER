"use client";
import { useState, useCallback } from "react";
import {
  Box, Typography, IconButton, Accordion, AccordionSummary, AccordionDetails,
  TextField, Button, Select, MenuItem, FormControl, InputLabel, CircularProgress,
  Alert, Chip, Divider, Switch, FormControlLabel, Tooltip,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import RouteIcon from "@mui/icons-material/Route";
import LayersIcon from "@mui/icons-material/Layers";
import ScatterPlotIcon from "@mui/icons-material/ScatterPlot";
import SearchIcon from "@mui/icons-material/Search";
import { analysisApi, geocodeApi } from "@/lib/api";
import { useMapStore, MapLayer } from "@/stores/map";

interface Props {
  projectId: string;
  onClose: () => void;
}

type JobResult = { id: string; status: string; result_data?: Record<string, unknown>; result_layer_id?: string } | null;

// Shared polling helper
async function pollJob(
  jobId: string,
  onComplete: (job: { result_layer_id: string; result_data: Record<string, unknown> }) => void,
  onError: (msg: string) => void,
) {
  const interval = setInterval(async () => {
    try {
      const res = await analysisApi.getJob(jobId);
      const job = res.data;
      if (job.status === "completed") {
        clearInterval(interval);
        onComplete(job);
      } else if (job.status === "failed") {
        clearInterval(interval);
        onError(job.error_message || "Job failed");
      }
    } catch {
      clearInterval(interval);
      onError("Failed to poll job status");
    }
  }, 2000);
}

// Generic result display
function JobResultAlert({ result }: { result: JobResult }) {
  if (!result) return null;
  if (result.status === "error") return <Alert severity="error" sx={{ mt: 1 }}>{(result as any).message}</Alert>;
  if (result.status === "submitted") return <Alert severity="info" sx={{ mt: 1 }}>Running… checking every 2s</Alert>;
  if (result.status === "done") {
    const data = result.result_data;
    return (
      <Alert severity="success" sx={{ mt: 1 }}>
        Done — result added to layers
        {data && (
          <Box sx={{ mt: 0.5 }}>
            {Object.entries(data).map(([k, v]) => (
              <Chip key={k} label={`${k}: ${v}`} size="small" sx={{ mr: 0.5, mb: 0.5, fontSize: 10 }} />
            ))}
          </Box>
        )}
      </Alert>
    );
  }
  return null;
}

// Generic "dispatch + poll + add layer" hook
function useAnalysisTool(projectId: string) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<JobResult>(null);
  const addLayer = useMapStore((s) => s.addLayer);

  const run = useCallback(async (
    apiFn: () => Promise<{ data: { id: string } }>,
    layerMeta: { name: string; geom_type: string },
  ) => {
    setLoading(true);
    setResult({ id: "", status: "submitted" });
    try {
      const res = await apiFn();
      pollJob(
        res.data.id,
        (job) => {
          if (job.result_layer_id) {
            addLayer({
              id: job.result_layer_id,
              name: layerMeta.name,
              geom_type: layerMeta.geom_type,
              visible: true,
              table_name: job.result_layer_id,
              style: {},
              source_type: "analysis",
            });
          }
          setResult({ id: res.data.id, status: "done", result_data: job.result_data });
        },
        (msg) => setResult({ id: res.data.id, status: "error", message: msg } as any),
      );
    } catch (e: any) {
      setResult({ id: "", status: "error", message: e?.response?.data?.detail || e.message } as any);
    } finally {
      setLoading(false);
    }
  }, [addLayer, projectId]);

  return { loading, result, run };
}

// ── Layer selector ────────────────────────────────────────────────────────────
function LayerSelect({ label, value, onChange, layers }: { label: string; value: string; onChange: (v: string) => void; layers: MapLayer[] }) {
  return (
    <FormControl size="small" fullWidth>
      <InputLabel>{label}</InputLabel>
      <Select value={value} label={label} onChange={(e) => onChange(e.target.value)}>
        {layers.filter((l) => l.table_name).map((l) => (
          <MenuItem key={l.id} value={l.id}>{l.name}</MenuItem>
        ))}
      </Select>
    </FormControl>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// NETWORK TOOLS
// ═══════════════════════════════════════════════════════════════════════════════

function IsochroneForm({ projectId }: { projectId: string }) {
  const [lat, setLat] = useState("-37.814");
  const [lng, setLng] = useState("144.963");
  const [mode, setMode] = useState("walk");
  const [cutoffs, setCutoffs] = useState("5,10,15,20");
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">
        Walk/cycle/drive catchment rings from a single origin point.
      </Typography>
      <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1 }}>
        <TextField label="Latitude" value={lat} onChange={(e) => setLat(e.target.value)} size="small" />
        <TextField label="Longitude" value={lng} onChange={(e) => setLng(e.target.value)} size="small" />
      </Box>
      <FormControl size="small" fullWidth>
        <InputLabel>Mode</InputLabel>
        <Select value={mode} label="Mode" onChange={(e) => setMode(e.target.value)}>
          <MenuItem value="walk">Walk</MenuItem>
          <MenuItem value="cycle">Cycle</MenuItem>
          <MenuItem value="drive">Drive</MenuItem>
        </Select>
      </FormControl>
      <TextField label="Time cutoffs (min, comma-sep)" value={cutoffs} onChange={(e) => setCutoffs(e.target.value)} size="small" />
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.isochrone({ project_id: projectId, origin: { lat: parseFloat(lat), lng: parseFloat(lng) }, mode, time_cutoffs: cutoffs.split(",").map((c) => parseInt(c.trim())) }),
        { name: `Isochrone (${mode})`, geom_type: "polygon" },
      )} disabled={loading}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}

function ShortestPathForm({ projectId }: { projectId: string }) {
  const [oLat, setOLat] = useState("-37.814"); const [oLng, setOLng] = useState("144.963");
  const [dLat, setDLat] = useState("-37.820"); const [dLng, setDLng] = useState("144.970");
  const [mode, setMode] = useState("walk");
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">
        Route between two points. Uses pgRouting on OSM network; falls back to straight-line if OSM not loaded.
      </Typography>
      <Typography variant="caption" fontWeight={600}>Origin</Typography>
      <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1 }}>
        <TextField label="Lat" value={oLat} onChange={(e) => setOLat(e.target.value)} size="small" />
        <TextField label="Lng" value={oLng} onChange={(e) => setOLng(e.target.value)} size="small" />
      </Box>
      <Typography variant="caption" fontWeight={600}>Destination</Typography>
      <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1 }}>
        <TextField label="Lat" value={dLat} onChange={(e) => setDLat(e.target.value)} size="small" />
        <TextField label="Lng" value={dLng} onChange={(e) => setDLng(e.target.value)} size="small" />
      </Box>
      <FormControl size="small" fullWidth>
        <InputLabel>Mode</InputLabel>
        <Select value={mode} label="Mode" onChange={(e) => setMode(e.target.value)}>
          <MenuItem value="walk">Walk</MenuItem>
          <MenuItem value="cycle">Cycle</MenuItem>
          <MenuItem value="drive">Drive</MenuItem>
        </Select>
      </FormControl>
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.shortestPath({ project_id: projectId, origin: { lat: parseFloat(oLat), lng: parseFloat(oLng) }, destination: { lat: parseFloat(dLat), lng: parseFloat(dLng) }, mode }),
        { name: `Route (${mode})`, geom_type: "linestring" },
      )} disabled={loading}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}

function ODMatrixForm({ projectId, layers }: { projectId: string; layers: MapLayer[] }) {
  const [originsId, setOriginsId] = useState("");
  const [destsId, setDestsId] = useState("");
  const [mode, setMode] = useState("walk");
  const [maxPairs, setMaxPairs] = useState("500");
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">
        Distance/time matrix between all origin–destination pairs. Output: lines connecting each pair with distance and duration attributes.
      </Typography>
      <LayerSelect label="Origins layer" value={originsId} onChange={setOriginsId} layers={layers} />
      <LayerSelect label="Destinations layer" value={destsId} onChange={setDestsId} layers={layers} />
      <FormControl size="small" fullWidth>
        <InputLabel>Mode</InputLabel>
        <Select value={mode} label="Mode" onChange={(e) => setMode(e.target.value)}>
          <MenuItem value="walk">Walk</MenuItem>
          <MenuItem value="cycle">Cycle</MenuItem>
          <MenuItem value="drive">Drive</MenuItem>
        </Select>
      </FormControl>
      <TextField label="Max pairs" value={maxPairs} onChange={(e) => setMaxPairs(e.target.value)} size="small" type="number" />
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.odMatrix({ project_id: projectId, origins_layer_id: originsId, destinations_layer_id: destsId, mode, max_pairs: parseInt(maxPairs) }),
        { name: `OD Matrix (${mode})`, geom_type: "linestring" },
      )} disabled={loading || !originsId || !destsId}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}

function CatchmentPopForm({ projectId, layers }: { projectId: string; layers: MapLayer[] }) {
  const [catchmentId, setCatchmentId] = useState("");
  const [level, setLevel] = useState("sa2");
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">
        Intersect a catchment polygon with ABS census boundaries to estimate population within. Requires ABS data bootstrap.
      </Typography>
      <LayerSelect label="Catchment polygon layer" value={catchmentId} onChange={setCatchmentId} layers={layers} />
      <FormControl size="small" fullWidth>
        <InputLabel>Census level</InputLabel>
        <Select value={level} label="Census level" onChange={(e) => setLevel(e.target.value)}>
          {["sa1", "sa2", "sa3", "sa4", "lga"].map((l) => <MenuItem key={l} value={l}>{l.toUpperCase()}</MenuItem>)}
        </Select>
      </FormControl>
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.catchmentPopulation({ project_id: projectId, catchment_layer_id: catchmentId, census_level: level }),
        { name: `Catchment Population (${level.toUpperCase()})`, geom_type: "polygon" },
      )} disabled={loading || !catchmentId}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// OVERLAY & GEOMETRY TOOLS
// ═══════════════════════════════════════════════════════════════════════════════

function ClipForm({ projectId, layers }: { projectId: string; layers: MapLayer[] }) {
  const [inputId, setInputId] = useState("");
  const [clipId, setClipId] = useState("");
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">Clip a layer to the extent of a polygon mask.</Typography>
      <LayerSelect label="Input layer" value={inputId} onChange={setInputId} layers={layers} />
      <LayerSelect label="Clip mask (polygon)" value={clipId} onChange={setClipId} layers={layers} />
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.clip({ project_id: projectId, input_layer_id: inputId, clip_layer_id: clipId }),
        { name: "Clipped layer", geom_type: "polygon" },
      )} disabled={loading || !inputId || !clipId}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}

function OverlayForm({ projectId, layers }: { projectId: string; layers: MapLayer[] }) {
  const [aId, setAId] = useState("");
  const [bId, setBId] = useState("");
  const [op, setOp] = useState("intersection");
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">Boolean overlay: intersection, union, difference, or symmetric difference.</Typography>
      <LayerSelect label="Layer A" value={aId} onChange={setAId} layers={layers} />
      <LayerSelect label="Layer B" value={bId} onChange={setBId} layers={layers} />
      <FormControl size="small" fullWidth>
        <InputLabel>Operation</InputLabel>
        <Select value={op} label="Operation" onChange={(e) => setOp(e.target.value)}>
          <MenuItem value="intersection">Intersection</MenuItem>
          <MenuItem value="union">Union</MenuItem>
          <MenuItem value="difference">Difference (A − B)</MenuItem>
          <MenuItem value="symmetric_difference">Symmetric Difference</MenuItem>
        </Select>
      </FormControl>
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.overlay({ project_id: projectId, layer_a_id: aId, layer_b_id: bId, operation: op }),
        { name: `${op.replace("_", " ")} result`, geom_type: "polygon" },
      )} disabled={loading || !aId || !bId}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}

function DissolveForm({ projectId, layers }: { projectId: string; layers: MapLayer[] }) {
  const [layerId, setLayerId] = useState("");
  const [field, setField] = useState("");
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">Merge features, optionally grouped by an attribute. Leave field blank to dissolve all into one polygon.</Typography>
      <LayerSelect label="Layer" value={layerId} onChange={setLayerId} layers={layers} />
      <TextField label="Dissolve field (optional)" value={field} onChange={(e) => setField(e.target.value)} size="small" />
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.dissolve({ project_id: projectId, layer_id: layerId, dissolve_field: field || null }),
        { name: "Dissolved", geom_type: "polygon" },
      )} disabled={loading || !layerId}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}

function CentroidForm({ projectId, layers }: { projectId: string; layers: MapLayer[] }) {
  const [layerId, setLayerId] = useState("");
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">Extract the centroid point of each feature.</Typography>
      <LayerSelect label="Layer" value={layerId} onChange={setLayerId} layers={layers} />
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.centroid({ project_id: projectId, layer_id: layerId }),
        { name: "Centroids", geom_type: "point" },
      )} disabled={loading || !layerId}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}

function ConvexHullForm({ projectId, layers }: { projectId: string; layers: MapLayer[] }) {
  const [layerId, setLayerId] = useState("");
  const [perFeature, setPerFeature] = useState(false);
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">Minimum convex polygon containing all features, or one hull per feature.</Typography>
      <LayerSelect label="Layer" value={layerId} onChange={setLayerId} layers={layers} />
      <FormControlLabel control={<Switch size="small" checked={perFeature} onChange={(e) => setPerFeature(e.target.checked)} />} label={<Typography variant="caption">One hull per feature</Typography>} />
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.convexHull({ project_id: projectId, layer_id: layerId, per_feature: perFeature }),
        { name: "Convex Hull", geom_type: "polygon" },
      )} disabled={loading || !layerId}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}

function VoronoiForm({ projectId, layers }: { projectId: string; layers: MapLayer[] }) {
  const [layerId, setLayerId] = useState("");
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">Thiessen / Voronoi polygons — each region contains all points closer to its seed than any other.</Typography>
      <LayerSelect label="Point layer (seeds)" value={layerId} onChange={setLayerId} layers={layers} />
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.voronoi({ project_id: projectId, layer_id: layerId }),
        { name: "Voronoi Polygons", geom_type: "polygon" },
      )} disabled={loading || !layerId}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// POINT ANALYSIS TOOLS
// ═══════════════════════════════════════════════════════════════════════════════

function KDEForm({ projectId, layers }: { projectId: string; layers: MapLayer[] }) {
  const [layerId, setLayerId] = useState("");
  const [resolution, setResolution] = useState("60");
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">
        Gaussian KDE heatmap — returns density contour polygons at the 50th, 75th, 90th, 95th percentile.
      </Typography>
      <LayerSelect label="Point layer" value={layerId} onChange={setLayerId} layers={layers} />
      <TextField label="Grid resolution (cells/axis, max 200)" value={resolution} onChange={(e) => setResolution(e.target.value)} size="small" type="number" />
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.kernelDensity({ project_id: projectId, layer_id: layerId, grid_resolution: parseInt(resolution) }),
        { name: "KDE Density", geom_type: "polygon" },
      )} disabled={loading || !layerId}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}

function ClusterForm({ projectId, layers }: { projectId: string; layers: MapLayer[] }) {
  const [layerId, setLayerId] = useState("");
  const [eps, setEps] = useState("1.0");
  const [minSamples, setMinSamples] = useState("5");
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">
        DBSCAN density clustering. Points labelled with cluster_id (−1 = noise). Tune ε for your point density.
      </Typography>
      <LayerSelect label="Point layer" value={layerId} onChange={setLayerId} layers={layers} />
      <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1 }}>
        <TextField label="ε radius (km)" value={eps} onChange={(e) => setEps(e.target.value)} size="small" type="number" />
        <TextField label="Min points" value={minSamples} onChange={(e) => setMinSamples(e.target.value)} size="small" type="number" />
      </Box>
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.cluster({ project_id: projectId, layer_id: layerId, eps_km: parseFloat(eps), min_samples: parseInt(minSamples) }),
        { name: "DBSCAN Clusters", geom_type: "point" },
      )} disabled={loading || !layerId}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}

function HexbinForm({ projectId, layers }: { projectId: string; layers: MapLayer[] }) {
  const [layerId, setLayerId] = useState("");
  const [cellSize, setCellSize] = useState("2.0");
  const [aggregate, setAggregate] = useState("count");
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">
        Aggregate points into a hexagonal grid. Each hex carries the count or a numeric attribute aggregate.
      </Typography>
      <LayerSelect label="Point layer" value={layerId} onChange={setLayerId} layers={layers} />
      <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1 }}>
        <TextField label="Cell size (km)" value={cellSize} onChange={(e) => setCellSize(e.target.value)} size="small" type="number" />
        <FormControl size="small">
          <InputLabel>Aggregate</InputLabel>
          <Select value={aggregate} label="Aggregate" onChange={(e) => setAggregate(e.target.value)}>
            <MenuItem value="count">Count</MenuItem>
            <MenuItem value="sum">Sum</MenuItem>
            <MenuItem value="mean">Mean</MenuItem>
          </Select>
        </FormControl>
      </Box>
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.hexbin({ project_id: projectId, layer_id: layerId, cell_size_km: parseFloat(cellSize), aggregate }),
        { name: `Hexbin (${cellSize}km)`, geom_type: "polygon" },
      )} disabled={loading || !layerId}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}

function PipForm({ projectId, layers }: { projectId: string; layers: MapLayer[] }) {
  const [pointsId, setPointsId] = useState("");
  const [polygonsId, setPolygonsId] = useState("");
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">Count points within each polygon.</Typography>
      <LayerSelect label="Points layer" value={pointsId} onChange={setPointsId} layers={layers} />
      <LayerSelect label="Polygons layer" value={polygonsId} onChange={setPolygonsId} layers={layers} />
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.pointInPolygon({ project_id: projectId, points_layer_id: pointsId, polygons_layer_id: polygonsId }),
        { name: "Point-in-Polygon", geom_type: "polygon" },
      )} disabled={loading || !pointsId || !polygonsId}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}

function GeocodeSearchForm() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{ address: string; latitude: number; longitude: number }[]>([]);
  const [loading, setLoading] = useState(false);

  const handleSearch = async () => {
    setLoading(true);
    try {
      const res = await geocodeApi.search(query);
      setResults(res.data.results);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">G-NAF Australian address geocoder. Requires G-NAF bootstrap.</Typography>
      <Box sx={{ display: "flex", gap: 1 }}>
        <TextField size="small" label="Address" value={query} onChange={(e) => setQuery(e.target.value)} fullWidth onKeyDown={(e) => e.key === "Enter" && handleSearch()} />
        <Button variant="contained" size="small" onClick={handleSearch} disabled={loading || query.length < 3}>
          {loading ? <CircularProgress size={16} /> : <SearchIcon fontSize="small" />}
        </Button>
      </Box>
      {results.map((r, i) => (
        <Box key={i} sx={{ p: 1, bgcolor: "grey.50", borderRadius: 1 }}>
          <Typography variant="body2">{r.address}</Typography>
          <Typography variant="caption" color="text.secondary">{r.latitude?.toFixed(5)}, {r.longitude?.toFixed(5)}</Typography>
        </Box>
      ))}
    </Box>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ROOT PANEL
// ═══════════════════════════════════════════════════════════════════════════════

interface ToolItem { label: string; form: React.ReactNode }

function ToolGroup({ title, icon, tools }: { title: string; icon: React.ReactNode; tools: ToolItem[] }) {
  const [openTool, setOpenTool] = useState<string | null>(null);

  return (
    <Accordion disableGutters elevation={0} sx={{ border: "1px solid", borderColor: "divider", mb: 1 }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 2, py: 0.5 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          {icon}
          <Typography variant="subtitle2" fontWeight={600}>{title}</Typography>
        </Box>
      </AccordionSummary>
      <AccordionDetails sx={{ px: 1, py: 0 }}>
        {tools.map((tool) => (
          <Accordion
            key={tool.label}
            disableGutters elevation={0}
            expanded={openTool === tool.label}
            onChange={(_, e) => setOpenTool(e ? tool.label : null)}
            sx={{ "&:before": { display: "none" }, borderTop: "1px solid", borderColor: "divider" }}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon fontSize="small" />} sx={{ px: 2, py: 0.25, minHeight: 36 }}>
              <Typography variant="body2">{tool.label}</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ px: 2, pb: 2 }}>
              {tool.form}
            </AccordionDetails>
          </Accordion>
        ))}
      </AccordionDetails>
    </Accordion>
  );
}

export default function AnalysisPanel({ projectId, onClose }: Props) {
  const layers = useMapStore((s) => s.layers);

  const networkTools: ToolItem[] = [
    { label: "Isochrone", form: <IsochroneForm projectId={projectId} /> },
    { label: "Shortest Path", form: <ShortestPathForm projectId={projectId} /> },
    { label: "OD Matrix", form: <ODMatrixForm projectId={projectId} layers={layers} /> },
    { label: "Catchment Population", form: <CatchmentPopForm projectId={projectId} layers={layers} /> },
  ];

  const overlayTools: ToolItem[] = [
    { label: "Buffer", form: <_BufferForm projectId={projectId} layers={layers} /> },
    { label: "Clip", form: <ClipForm projectId={projectId} layers={layers} /> },
    { label: "Overlay (Union / Intersect / Diff)", form: <OverlayForm projectId={projectId} layers={layers} /> },
    { label: "Dissolve", form: <DissolveForm projectId={projectId} layers={layers} /> },
    { label: "Centroid", form: <CentroidForm projectId={projectId} layers={layers} /> },
    { label: "Convex Hull", form: <ConvexHullForm projectId={projectId} layers={layers} /> },
    { label: "Voronoi Polygons", form: <VoronoiForm projectId={projectId} layers={layers} /> },
    { label: "Spatial Join", form: <_SpatialJoinForm projectId={projectId} layers={layers} /> },
  ];

  const pointTools: ToolItem[] = [
    { label: "Kernel Density (KDE)", form: <KDEForm projectId={projectId} layers={layers} /> },
    { label: "DBSCAN Clusters", form: <ClusterForm projectId={projectId} layers={layers} /> },
    { label: "Hexbin Aggregation", form: <HexbinForm projectId={projectId} layers={layers} /> },
    { label: "Point-in-Polygon", form: <PipForm projectId={projectId} layers={layers} /> },
  ];

  return (
    <Box sx={{ width: 340, height: "100%", bgcolor: "background.paper", borderLeft: "1px solid", borderColor: "divider", display: "flex", flexDirection: "column", zIndex: 10 }}>
      <Box sx={{ p: 2, borderBottom: "1px solid", borderColor: "divider", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Typography variant="subtitle1" fontWeight={600}>Analysis Tools</Typography>
        <IconButton size="small" onClick={onClose}><CloseIcon fontSize="small" /></IconButton>
      </Box>

      <Box sx={{ flex: 1, overflow: "auto", p: 1 }}>
        <ToolGroup title="Network Analysis" icon={<RouteIcon color="primary" fontSize="small" />} tools={networkTools} />
        <ToolGroup title="Overlay & Geometry" icon={<LayersIcon color="secondary" fontSize="small" />} tools={overlayTools} />
        <ToolGroup title="Point Analysis" icon={<ScatterPlotIcon sx={{ color: "success.main" }} fontSize="small" />} tools={pointTools} />

        <Accordion disableGutters elevation={0} sx={{ border: "1px solid", borderColor: "divider", mb: 1 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 2, py: 0.5 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <SearchIcon fontSize="small" sx={{ color: "text.secondary" }} />
              <Typography variant="subtitle2" fontWeight={600}>Geocode</Typography>
            </Box>
          </AccordionSummary>
          <AccordionDetails sx={{ px: 2, pb: 2 }}>
            <GeocodeSearchForm />
          </AccordionDetails>
        </Accordion>
      </Box>
    </Box>
  );
}

// Inline buffer / spatial-join forms that reuse the shared hook
function _BufferForm({ projectId, layers }: { projectId: string; layers: MapLayer[] }) {
  const [layerId, setLayerId] = useState("");
  const [distance, setDistance] = useState("500");
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">Expand features outward by a fixed distance (metres).</Typography>
      <LayerSelect label="Source layer" value={layerId} onChange={setLayerId} layers={layers} />
      <TextField label="Distance (metres)" value={distance} onChange={(e) => setDistance(e.target.value)} size="small" type="number" />
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.buffer({ project_id: projectId, layer_id: layerId, distance_m: parseFloat(distance) }),
        { name: `Buffer ${distance}m`, geom_type: "polygon" },
      )} disabled={loading || !layerId}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}

function _SpatialJoinForm({ projectId, layers }: { projectId: string; layers: MapLayer[] }) {
  const [leftId, setLeftId] = useState("");
  const [rightId, setRightId] = useState("");
  const [predicate, setPredicate] = useState("intersects");
  const { loading, result, run } = useAnalysisTool(projectId);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      <Typography variant="caption" color="text.secondary">Join attributes from layer B onto matching features in layer A.</Typography>
      <LayerSelect label="Left layer (receives attrs)" value={leftId} onChange={setLeftId} layers={layers} />
      <LayerSelect label="Right layer (donates attrs)" value={rightId} onChange={setRightId} layers={layers} />
      <FormControl size="small" fullWidth>
        <InputLabel>Predicate</InputLabel>
        <Select value={predicate} label="Predicate" onChange={(e) => setPredicate(e.target.value)}>
          <MenuItem value="intersects">Intersects</MenuItem>
          <MenuItem value="within">Within</MenuItem>
          <MenuItem value="contains">Contains</MenuItem>
        </Select>
      </FormControl>
      <Button variant="contained" size="small" onClick={() => run(
        () => analysisApi.spatialJoin({ project_id: projectId, left_layer_id: leftId, right_layer_id: rightId, predicate }),
        { name: "Spatial Join", geom_type: "point" },
      )} disabled={loading || !leftId || !rightId}>{loading ? <CircularProgress size={16} /> : "Run"}</Button>
      <JobResultAlert result={result} />
    </Box>
  );
}
