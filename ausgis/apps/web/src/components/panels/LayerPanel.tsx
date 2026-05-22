"use client";
import { useRef, useState } from "react";
import {
  Box, Typography, IconButton, Tooltip, List, ListItem, ListItemText,
  ListItemIcon, Switch, Divider, Button, CircularProgress, Chip,
} from "@mui/material";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import DeleteIcon from "@mui/icons-material/Delete";
import UploadIcon from "@mui/icons-material/Upload";
import LayersIcon from "@mui/icons-material/Layers";
import { layersApi } from "@/lib/api";
import { useMapStore, MapLayer } from "@/stores/map";

interface Props {
  projectId: string;
  map: React.RefObject<maplibregl.Map | null>;
}

export default function LayerPanel({ projectId, map }: Props) {
  const { layers, addLayer, removeLayer, toggleLayerVisibility } = useMapStore();
  const fileInput = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("project_id", projectId);
      formData.append("name", file.name.replace(/\.[^.]+$/, ""));
      const res = await layersApi.upload(formData);
      const layer = res.data;
      addLayer({
        id: layer.id,
        name: layer.name,
        geom_type: layer.geom_type,
        visible: true,
        table_name: layer.table_name,
        style: layer.style || {},
        source_type: layer.source_type,
      });

      if (map.current && layer.table_name) {
        const m = map.current;
        const GEOAPI_URL = process.env.NEXT_PUBLIC_GEOAPI_URL || "http://localhost:8100";
        m.addSource(`layer-${layer.id}`, {
          type: "vector",
          tiles: [`${GEOAPI_URL}/tiles/${layer.id}/{z}/{x}/{y}.mvt`],
        });
        m.addLayer({
          id: `layer-${layer.id}-render`,
          type: layer.geom_type?.includes("polygon") ? "fill" : layer.geom_type?.includes("line") ? "line" : "circle",
          source: `layer-${layer.id}`,
          "source-layer": layer.id,
          paint: layer.geom_type?.includes("polygon")
            ? { "fill-color": "#3B82F6", "fill-opacity": 0.5 }
            : layer.geom_type?.includes("line")
            ? { "line-color": "#3B82F6", "line-width": 2 }
            : { "circle-radius": 5, "circle-color": "#3B82F6" },
        });
      }
    } catch (err) {
      console.error("Upload failed", err);
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  const handleDelete = async (layer: MapLayer) => {
    await layersApi.delete(layer.id);
    removeLayer(layer.id);
    if (map.current) {
      if (map.current.getLayer(`layer-${layer.id}-render`)) map.current.removeLayer(`layer-${layer.id}-render`);
      if (map.current.getSource(`layer-${layer.id}`)) map.current.removeSource(`layer-${layer.id}`);
    }
  };

  const geomIcon = (t: string | null) => {
    if (!t) return "•";
    if (t.includes("polygon")) return "⬡";
    if (t.includes("line")) return "—";
    return "•";
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
      <Box sx={{ p: 2, borderBottom: "1px solid", borderColor: "divider", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <LayersIcon color="primary" fontSize="small" />
          <Typography variant="subtitle1" fontWeight={600}>Layers</Typography>
        </Box>
        <Tooltip title="Upload layer (GeoJSON, SHP, GPKG, CSV)">
          <span>
            <IconButton size="small" color="primary" onClick={() => fileInput.current?.click()} disabled={uploading}>
              {uploading ? <CircularProgress size={18} /> : <UploadIcon fontSize="small" />}
            </IconButton>
          </span>
        </Tooltip>
        <input ref={fileInput} type="file" hidden accept=".geojson,.json,.zip,.gpkg,.csv,.kml" onChange={handleFileUpload} />
      </Box>

      <List dense sx={{ flex: 1, overflow: "auto", p: 0 }}>
        {layers.length === 0 && (
          <Box sx={{ p: 3, textAlign: "center" }}>
            <Typography variant="body2" color="text.secondary">No layers yet.</Typography>
            <Typography variant="caption" color="text.disabled">Upload a file to get started.</Typography>
          </Box>
        )}
        {layers.map((layer) => (
          <Box key={layer.id}>
            <ListItem
              sx={{ py: 1 }}
              secondaryAction={
                <Box sx={{ display: "flex", gap: 0.5 }}>
                  <Tooltip title={layer.visible ? "Hide" : "Show"}>
                    <IconButton size="small" onClick={() => {
                      toggleLayerVisibility(layer.id);
                      if (map.current?.getLayer(`layer-${layer.id}-render`)) {
                        map.current.setLayoutProperty(`layer-${layer.id}-render`, "visibility", layer.visible ? "none" : "visible");
                      }
                    }}>
                      {layer.visible ? <VisibilityIcon fontSize="small" /> : <VisibilityOffIcon fontSize="small" color="disabled" />}
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete">
                    <IconButton size="small" onClick={() => handleDelete(layer)}>
                      <DeleteIcon fontSize="small" color="error" />
                    </IconButton>
                  </Tooltip>
                </Box>
              }
            >
              <ListItemIcon sx={{ minWidth: 28, fontSize: 16 }}>{geomIcon(layer.geom_type)}</ListItemIcon>
              <ListItemText
                primary={<Typography variant="body2" fontWeight={500} noWrap>{layer.name}</Typography>}
                secondary={
                  <Chip label={layer.source_type} size="small" variant="outlined" sx={{ fontSize: 10, height: 16 }} />
                }
              />
            </ListItem>
            <Divider />
          </Box>
        ))}
      </List>
    </Box>
  );
}
