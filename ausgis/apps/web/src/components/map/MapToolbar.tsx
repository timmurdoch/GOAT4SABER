"use client";
import { useState } from "react";
import {
  Box, IconButton, Tooltip, Menu, MenuItem, ListItemText, Divider, Typography,
} from "@mui/material";
import MapIcon from "@mui/icons-material/Map";
import AnalyticsIcon from "@mui/icons-material/Analytics";
import LayersIcon from "@mui/icons-material/Layers";
import HomeIcon from "@mui/icons-material/Home";
import { useRouter } from "next/navigation";

interface Props {
  onBasemapChange: (basemap: string) => void;
  onAnalysisOpen: () => void;
  currentBasemap: string;
}

const BASEMAP_OPTIONS = [
  { id: "osm", label: "Street (OSM)" },
  { id: "carto-light", label: "Light" },
  { id: "carto-dark", label: "Dark" },
];

export default function MapToolbar({ onBasemapChange, onAnalysisOpen, currentBasemap }: Props) {
  const router = useRouter();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  return (
    <Box
      sx={{
        position: "absolute",
        top: 16,
        left: "50%",
        transform: "translateX(-50%)",
        bgcolor: "background.paper",
        borderRadius: 2,
        boxShadow: 3,
        display: "flex",
        gap: 0.5,
        p: 0.5,
        zIndex: 10,
      }}
    >
      <Tooltip title="Dashboard">
        <IconButton size="small" onClick={() => router.push("/dashboard")}>
          <HomeIcon fontSize="small" />
        </IconButton>
      </Tooltip>

      <Divider orientation="vertical" flexItem />

      <Tooltip title="Change basemap">
        <IconButton size="small" onClick={(e) => setAnchorEl(e.currentTarget)}>
          <MapIcon fontSize="small" />
        </IconButton>
      </Tooltip>

      <Tooltip title="Analysis tools">
        <IconButton size="small" onClick={onAnalysisOpen}>
          <AnalyticsIcon fontSize="small" />
        </IconButton>
      </Tooltip>

      <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={() => setAnchorEl(null)}>
        <Typography variant="caption" sx={{ px: 2, py: 1, display: "block", color: "text.secondary" }}>
          Basemap
        </Typography>
        {BASEMAP_OPTIONS.map((b) => (
          <MenuItem
            key={b.id}
            selected={b.id === currentBasemap}
            onClick={() => { onBasemapChange(b.id); setAnchorEl(null); }}
          >
            <ListItemText>{b.label}</ListItemText>
          </MenuItem>
        ))}
      </Menu>
    </Box>
  );
}
