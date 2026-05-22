"use client";
import { useState } from "react";
import {
  Box, Typography, IconButton, Tabs, Tab, TextField, Button,
  Select, MenuItem, FormControl, InputLabel, CircularProgress,
  Alert, Chip, Divider,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { analysisApi, geocodeApi } from "@/lib/api";
import { useMapStore } from "@/stores/map";

interface Props {
  projectId: string;
  onClose: () => void;
}

export default function AnalysisPanel({ projectId, onClose }: Props) {
  const [tab, setTab] = useState(0);
  const layers = useMapStore((s) => s.layers);

  return (
    <Box
      sx={{
        width: 320,
        height: "100%",
        bgcolor: "background.paper",
        borderLeft: "1px solid",
        borderColor: "divider",
        display: "flex",
        flexDirection: "column",
        zIndex: 10,
      }}
    >
      <Box sx={{ p: 2, borderBottom: "1px solid", borderColor: "divider", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Typography variant="subtitle1" fontWeight={600}>Analysis Tools</Typography>
        <IconButton size="small" onClick={onClose}><CloseIcon fontSize="small" /></IconButton>
      </Box>

      <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto" sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Tab label="Isochrone" />
        <Tab label="Buffer" />
        <Tab label="Pip" />
        <Tab label="Geocode" />
      </Tabs>

      <Box sx={{ flex: 1, overflow: "auto", p: 2 }}>
        {tab === 0 && <IsochroneForm projectId={projectId} />}
        {tab === 1 && <BufferForm projectId={projectId} layers={layers} />}
        {tab === 2 && <PipForm projectId={projectId} layers={layers} />}
        {tab === 3 && <GeocodeForm />}
      </Box>
    </Box>
  );
}

function IsochroneForm({ projectId }: { projectId: string }) {
  const [lat, setLat] = useState("-37.814");
  const [lng, setLng] = useState("144.963");
  const [mode, setMode] = useState("walk");
  const [cutoffs, setCutoffs] = useState("5,10,15,20");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const addLayer = useMapStore((s) => s.addLayer);

  const handleRun = async () => {
    setLoading(true);
    setResult(null);
    try {
      const res = await analysisApi.isochrone({
        project_id: projectId,
        origin: { lat: parseFloat(lat), lng: parseFloat(lng) },
        mode,
        time_cutoffs: cutoffs.split(",").map((c) => parseInt(c.trim())),
      });
      setResult(`Job started: ${res.data.id}`);

      const pollInterval = setInterval(async () => {
        const jobRes = await analysisApi.getJob(res.data.id);
        if (jobRes.data.status === "completed" && jobRes.data.result_layer_id) {
          clearInterval(pollInterval);
          addLayer({
            id: jobRes.data.result_layer_id,
            name: `Isochrone (${mode})`,
            geom_type: "polygon",
            visible: true,
            table_name: jobRes.data.result_layer_id,
            style: { type: "fill", paint: { "fill-color": "#f59e0b", "fill-opacity": 0.4 } },
            source_type: "analysis",
          });
          setResult("Isochrone ready — check Layers panel");
        } else if (jobRes.data.status === "failed") {
          clearInterval(pollInterval);
          setResult(`Failed: ${jobRes.data.error_message}`);
        }
      }, 2000);
    } catch (e: any) {
      setResult(`Error: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Typography variant="body2" color="text.secondary">
        Generate walk/cycle/drive catchment areas from a point.
      </Typography>
      <TextField label="Latitude" value={lat} onChange={(e) => setLat(e.target.value)} size="small" fullWidth />
      <TextField label="Longitude" value={lng} onChange={(e) => setLng(e.target.value)} size="small" fullWidth />
      <FormControl size="small" fullWidth>
        <InputLabel>Mode</InputLabel>
        <Select value={mode} label="Mode" onChange={(e) => setMode(e.target.value)}>
          <MenuItem value="walk">Walk</MenuItem>
          <MenuItem value="cycle">Cycle</MenuItem>
          <MenuItem value="drive">Drive</MenuItem>
        </Select>
      </FormControl>
      <TextField label="Time cutoffs (minutes, comma-separated)" value={cutoffs} onChange={(e) => setCutoffs(e.target.value)} size="small" fullWidth />
      <Button variant="contained" onClick={handleRun} disabled={loading}>
        {loading ? <CircularProgress size={20} /> : "Run Isochrone"}
      </Button>
      {result && <Alert severity={result.startsWith("Error") || result.startsWith("Failed") ? "error" : "info"}>{result}</Alert>}
    </Box>
  );
}

function BufferForm({ projectId, layers }: { projectId: string; layers: any[] }) {
  const [layerId, setLayerId] = useState("");
  const [distance, setDistance] = useState("500");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const addLayer = useMapStore((s) => s.addLayer);

  const handleRun = async () => {
    setLoading(true);
    try {
      const res = await analysisApi.buffer({ project_id: projectId, layer_id: layerId, distance_m: parseFloat(distance) });
      const poll = setInterval(async () => {
        const job = await analysisApi.getJob(res.data.id);
        if (job.data.status === "completed") {
          clearInterval(poll);
          addLayer({ id: job.data.result_layer_id, name: `Buffer ${distance}m`, geom_type: "polygon", visible: true, table_name: job.data.result_layer_id, style: {}, source_type: "analysis" });
          setResult("Buffer ready");
        } else if (job.data.status === "failed") {
          clearInterval(poll);
          setResult(`Failed: ${job.data.error_message}`);
        }
      }, 2000);
    } catch (e: any) {
      setResult(`Error: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Typography variant="body2" color="text.secondary">Create a buffer around layer features.</Typography>
      <FormControl size="small" fullWidth>
        <InputLabel>Source layer</InputLabel>
        <Select value={layerId} label="Source layer" onChange={(e) => setLayerId(e.target.value)}>
          {layers.filter((l) => l.table_name).map((l) => <MenuItem key={l.id} value={l.id}>{l.name}</MenuItem>)}
        </Select>
      </FormControl>
      <TextField label="Buffer distance (metres)" value={distance} onChange={(e) => setDistance(e.target.value)} size="small" fullWidth />
      <Button variant="contained" onClick={handleRun} disabled={loading || !layerId}>
        {loading ? <CircularProgress size={20} /> : "Run Buffer"}
      </Button>
      {result && <Alert severity={result.startsWith("Error") || result.startsWith("Failed") ? "error" : "success"}>{result}</Alert>}
    </Box>
  );
}

function PipForm({ projectId, layers }: { projectId: string; layers: any[] }) {
  const [pointsId, setPointsId] = useState("");
  const [polygonsId, setPolygonsId] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const addLayer = useMapStore((s) => s.addLayer);

  const handleRun = async () => {
    setLoading(true);
    try {
      const res = await analysisApi.pointInPolygon({ project_id: projectId, points_layer_id: pointsId, polygons_layer_id: polygonsId });
      const poll = setInterval(async () => {
        const job = await analysisApi.getJob(res.data.id);
        if (job.data.status === "completed") {
          clearInterval(poll);
          addLayer({ id: job.data.result_layer_id, name: "Point-in-Polygon result", geom_type: "polygon", visible: true, table_name: job.data.result_layer_id, style: {}, source_type: "analysis" });
          setResult("Done — result added to layers");
        } else if (job.data.status === "failed") {
          clearInterval(poll);
          setResult(`Failed: ${job.data.error_message}`);
        }
      }, 2000);
    } catch (e: any) {
      setResult(`Error: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Typography variant="body2" color="text.secondary">Count points within polygons.</Typography>
      <FormControl size="small" fullWidth>
        <InputLabel>Points layer</InputLabel>
        <Select value={pointsId} label="Points layer" onChange={(e) => setPointsId(e.target.value)}>
          {layers.filter((l) => l.table_name).map((l) => <MenuItem key={l.id} value={l.id}>{l.name}</MenuItem>)}
        </Select>
      </FormControl>
      <FormControl size="small" fullWidth>
        <InputLabel>Polygons layer</InputLabel>
        <Select value={polygonsId} label="Polygons layer" onChange={(e) => setPolygonsId(e.target.value)}>
          {layers.filter((l) => l.table_name).map((l) => <MenuItem key={l.id} value={l.id}>{l.name}</MenuItem>)}
        </Select>
      </FormControl>
      <Button variant="contained" onClick={handleRun} disabled={loading || !pointsId || !polygonsId}>
        {loading ? <CircularProgress size={20} /> : "Run"}
      </Button>
      {result && <Alert severity={result.startsWith("Error") || result.startsWith("Failed") ? "error" : "success"}>{result}</Alert>}
    </Box>
  );
}

function GeocodeForm() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
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
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Typography variant="body2" color="text.secondary">Search Australian addresses (G-NAF).</Typography>
      <Box sx={{ display: "flex", gap: 1 }}>
        <TextField size="small" label="Address" value={query} onChange={(e) => setQuery(e.target.value)} fullWidth onKeyDown={(e) => e.key === "Enter" && handleSearch()} />
        <Button variant="contained" onClick={handleSearch} disabled={loading || query.length < 3}>
          {loading ? <CircularProgress size={18} /> : "Go"}
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
