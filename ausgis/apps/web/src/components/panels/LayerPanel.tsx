"use client";
import { useRef, useState } from "react";
import {
  Box, Typography, IconButton, Tooltip, List, ListItem, ListItemText,
  ListItemIcon, Divider, CircularProgress, Chip, Alert, Snackbar,
} from "@mui/material";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import DeleteIcon from "@mui/icons-material/Delete";
import UploadIcon from "@mui/icons-material/Upload";
import LayersIcon from "@mui/icons-material/Layers";
import maplibregl from "maplibre-gl";
import { layersApi } from "@/lib/api";
import { useMapStore, MapLayer } from "@/stores/map";

interface Props {
  projectId: string;
  map: React.RefObject<maplibregl.Map | null>;
  loadingLayers?: boolean;
}

export default function LayerPanel({ projectId, map, loadingLayers = false }: Props) {
  const { layers, addLayer, removeLayer, toggleLayerVisibility } = useMapStore();
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("project_id", projectId);
      formData.append("name", file.name.replace(/\.[^.]+$/, ""));

      const res = await layersApi.upload(formData);
      const layer = res.data;

      // Add to Zustand store — ProjectMap's useEffect([layers]) handles map rendering
      addLayer({
        id: layer.id,
        name: layer.name,
        geom_type: layer.geom_type,
        visible: true,
        table_name: layer.table_name,
        style: {},
        source_type: layer.source_type,
      });
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "Upload failed — check file format and try again";
      setError(msg);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const handleDelete = async (layer: MapLayer) => {
    try {
      await layersApi.delete(layer.id);
    } catch {
      // If the API call fails (e.g. already deleted), still clean up locally
    }
    removeLayer(layer.id);
    const m = map.current;
    if (m) {
      const layerId = `layer-${layer.id}-render`;
      const sourceId = `layer-${layer.id}`;
      if (m.getLayer(layerId)) m.removeLayer(layerId);
      if (m.getSource(sourceId)) m.removeSource(sourceId);
    }
  };

  const handleToggleVisibility = (layer: MapLayer) => {
    toggleLayerVisibility(layer.id);
    const m = map.current;
    if (m) {
      const layerId = `layer-${layer.id}-render`;
      if (m.getLayer(layerId)) {
        // layer.visible is still the OLD value here — toggleLayerVisibility will flip it
        m.setLayoutProperty(layerId, "visibility", layer.visible ? "none" : "visible");
      }
    }
  };

  const geomIcon = (t: string | null) => {
    if (!t) return "·";
    if (t.includes("polygon")) return "⬡";
    if (t.includes("line")) return "╌";
    return "·";
  };

  return (
    <Box
      sx={{
        width: 280,
        height: "100%",
        bgcolor: "background.paper",
        borderRight: "1px solid",
        borderColor: "divider",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        zIndex: 10,
      }}
    >
      {/* Header */}
      <Box sx={{ px: 2, py: 1.5, borderBottom: "1px solid", borderColor: "divider", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <LayersIcon color="primary" fontSize="small" />
          <Typography variant="subtitle1" fontWeight={600}>Layers</Typography>
          {loadingLayers && <CircularProgress size={14} />}
        </Box>
        <Tooltip title="Upload layer (GeoJSON, SHP ZIP, GPKG, CSV, KML)">
          <span>
            <IconButton size="small" color="primary" onClick={() => fileInput.current?.click()} disabled={uploading}>
              {uploading ? <CircularProgress size={18} /> : <UploadIcon fontSize="small" />}
            </IconButton>
          </span>
        </Tooltip>
        <input
          ref={fileInput}
          type="file"
          hidden
          accept=".geojson,.json,.zip,.gpkg,.csv,.kml"
          onChange={handleFileUpload}
        />
      </Box>

      {/* Layer list */}
      <List dense sx={{ flex: 1, overflow: "auto", p: 0 }}>
        {!loadingLayers && layers.length === 0 && (
          <Box sx={{ p: 3, textAlign: "center" }}>
            <Typography variant="body2" color="text.secondary">No layers yet.</Typography>
            <Typography variant="caption" color="text.disabled">
              Click ↑ to upload a GeoJSON, Shapefile (ZIP), GPKG, or CSV.
            </Typography>
          </Box>
        )}

        {layers.map((layer) => (
          <Box key={layer.id}>
            <ListItem
              sx={{ py: 0.75, pr: 10 }}
              secondaryAction={
                <Box sx={{ display: "flex", gap: 0.5 }}>
                  <Tooltip title={layer.visible ? "Hide layer" : "Show layer"}>
                    <IconButton size="small" onClick={() => handleToggleVisibility(layer)}>
                      {layer.visible
                        ? <VisibilityIcon fontSize="small" />
                        : <VisibilityOffIcon fontSize="small" color="disabled" />}
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete layer">
                    <IconButton size="small" onClick={() => handleDelete(layer)}>
                      <DeleteIcon fontSize="small" color="error" />
                    </IconButton>
                  </Tooltip>
                </Box>
              }
            >
              <ListItemIcon sx={{ minWidth: 24, fontSize: 14, color: "text.secondary" }}>
                {geomIcon(layer.geom_type)}
              </ListItemIcon>
              <ListItemText
                primary={
                  <Typography variant="body2" fontWeight={500} noWrap title={layer.name}>
                    {layer.name}
                  </Typography>
                }
                secondary={
                  <Chip
                    label={layer.source_type}
                    size="small"
                    variant="outlined"
                    sx={{ fontSize: 9, height: 14, mt: 0.25 }}
                  />
                }
              />
            </ListItem>
            <Divider />
          </Box>
        ))}
      </List>

      {/* Error snackbar */}
      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={() => setError(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
      >
        <Alert severity="error" onClose={() => setError(null)} sx={{ width: "100%" }}>
          {error}
        </Alert>
      </Snackbar>
    </Box>
  );
}
