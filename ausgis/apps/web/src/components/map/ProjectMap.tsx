"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Box, CircularProgress } from "@mui/material";
import LayerPanel from "@/components/panels/LayerPanel";
import AnalysisPanel from "@/components/panels/AnalysisPanel";
import MapToolbar from "@/components/map/MapToolbar";
import { useMapStore, BASEMAPS, MapLayer } from "@/stores/map";
import { layersApi } from "@/lib/api";

const GEOAPI_URL = process.env.NEXT_PUBLIC_GEOAPI_URL || "http://localhost:8100";

function _defaultLayerType(geomType: string | null): string {
  if (!geomType) return "circle";
  if (geomType.includes("polygon")) return "fill";
  if (geomType.includes("line") || geomType.includes("string")) return "line";
  return "circle";
}

function _defaultPaint(geomType: string | null): Record<string, unknown> {
  if (!geomType) return { "circle-radius": 5, "circle-color": "#3B82F6" };
  if (geomType.includes("polygon")) return { "fill-color": "#3B82F6", "fill-opacity": 0.5 };
  if (geomType.includes("line") || geomType.includes("string")) return { "line-color": "#3B82F6", "line-width": 2 };
  return { "circle-radius": 5, "circle-color": "#3B82F6" };
}

function addLayerToMap(m: maplibregl.Map, layer: MapLayer) {
  if (!layer.table_name) return;
  const sourceId = `layer-${layer.id}`;
  const layerId = `layer-${layer.id}-render`;
  if (m.getSource(sourceId)) return; // already added

  m.addSource(sourceId, {
    type: "vector",
    tiles: [`${GEOAPI_URL}/tiles/${layer.id}/{z}/{x}/{y}.mvt`],
    minzoom: 0,
    maxzoom: 22,
  });

  const styleSpec = layer.style as any;
  const layerType = styleSpec?.type || _defaultLayerType(layer.geom_type);
  const paint = styleSpec?.paint || _defaultPaint(layer.geom_type);

  m.addLayer({
    id: layerId,
    type: layerType,
    source: sourceId,
    "source-layer": layer.id,
    paint,
    layout: { visibility: layer.visible ? "visible" : "none" },
  });
}

function syncAllLayers(m: maplibregl.Map, layers: MapLayer[]) {
  layers.forEach((layer) => {
    try {
      addLayerToMap(m, layer);
      // Sync visibility for already-added layers
      const layerId = `layer-${layer.id}-render`;
      if (m.getLayer(layerId)) {
        m.setLayoutProperty(layerId, "visibility", layer.visible ? "visible" : "none");
      }
    } catch (e) {
      // Individual layer errors shouldn't break the rest
      console.warn(`Failed to sync layer ${layer.id}:`, e);
    }
  });
}

export default function ProjectMap({ projectId }: { projectId: string }) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const styleReady = useRef(false);
  const { layers, viewState, basemap, addLayer, clearLayers } = useMapStore();
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [loadingLayers, setLoadingLayers] = useState(true);

  // Fetch existing project layers from API on mount
  useEffect(() => {
    clearLayers();
    setLoadingLayers(true);
    layersApi.list(projectId)
      .then((res) => {
        res.data.forEach((layer: any) => {
          addLayer({
            id: layer.id,
            name: layer.name,
            geom_type: layer.geom_type,
            visible: layer.visible ?? true,
            table_name: layer.table_name,
            style: {},
            source_type: layer.source_type,
          });
        });
      })
      .catch((err) => console.error("Failed to load project layers:", err))
      .finally(() => setLoadingLayers(false));

    // Clear layers when leaving this project
    return () => clearLayers();
  }, [projectId]);

  // Init map
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    const m = new maplibregl.Map({
      container: mapContainer.current,
      style: BASEMAPS[basemap] || BASEMAPS.osm,
      center: [viewState.longitude, viewState.latitude],
      zoom: viewState.zoom,
    });

    m.addControl(new maplibregl.NavigationControl(), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
    m.addControl(new maplibregl.GeolocateControl({ trackUserLocation: true }), "top-right");

    m.on("load", () => {
      styleReady.current = true;
      // Sync any layers that arrived before the style was ready
      syncAllLayers(m, useMapStore.getState().layers);
    });

    map.current = m;

    return () => {
      styleReady.current = false;
      m.remove();
      map.current = null;
    };
  }, []);

  // Sync store → map whenever layers change
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    if (styleReady.current) {
      syncAllLayers(m, layers);
    }
    // If style isn't ready yet, the 'load' handler above will pick it up
  }, [layers]);

  const handleBasemapChange = useCallback((newBasemap: string) => {
    const m = map.current;
    if (!m) return;
    useMapStore.getState().setBasemap(newBasemap);
    styleReady.current = false;
    m.setStyle(BASEMAPS[newBasemap] || BASEMAPS.osm);
    m.once("style.load", () => {
      styleReady.current = true;
      syncAllLayers(m, useMapStore.getState().layers);
    });
  }, []);

  return (
    <Box sx={{ display: "flex", height: "100vh", overflow: "hidden", position: "relative" }}>
      <LayerPanel projectId={projectId} map={map} loadingLayers={loadingLayers} />

      <Box ref={mapContainer} sx={{ flex: 1, height: "100%" }} />

      <MapToolbar
        onBasemapChange={handleBasemapChange}
        onAnalysisOpen={() => setAnalysisOpen(true)}
        currentBasemap={basemap}
      />

      {analysisOpen && (
        <AnalysisPanel projectId={projectId} onClose={() => setAnalysisOpen(false)} />
      )}
    </Box>
  );
}
