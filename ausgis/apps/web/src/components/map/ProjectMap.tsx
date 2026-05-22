"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Box } from "@mui/material";
import LayerPanel from "@/components/panels/LayerPanel";
import AnalysisPanel from "@/components/panels/AnalysisPanel";
import MapToolbar from "@/components/map/MapToolbar";
import { useMapStore, BASEMAPS } from "@/stores/map";
import { layersApi } from "@/lib/api";

const GEOAPI_URL = process.env.NEXT_PUBLIC_GEOAPI_URL || "http://localhost:8100";

export default function ProjectMap({ projectId }: { projectId: string }) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const { layers, viewState, basemap, toggleLayerVisibility, updateLayer } = useMapStore();
  const [analysisOpen, setAnalysisOpen] = useState(false);

  // Init map
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: BASEMAPS[basemap] || BASEMAPS.osm,
      center: [viewState.longitude, viewState.latitude],
      zoom: viewState.zoom,
      pitch: viewState.pitch,
      bearing: viewState.bearing,
    });

    map.current.addControl(new maplibregl.NavigationControl(), "top-right");
    map.current.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
    map.current.addControl(new maplibregl.GeolocateControl({ trackUserLocation: true }), "top-right");

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []);

  // Sync layers to map sources/layers
  useEffect(() => {
    const m = map.current;
    if (!m || !m.isStyleLoaded()) return;

    layers.forEach((layer) => {
      const sourceId = `layer-${layer.id}`;
      const layerId = `layer-${layer.id}-render`;

      if (!m.getSource(sourceId) && layer.table_name) {
        m.addSource(sourceId, {
          type: "vector",
          tiles: [`${GEOAPI_URL}/tiles/${layer.id}/{z}/{x}/{y}.mvt`],
          minzoom: 0,
          maxzoom: 22,
        });

        const paintProps = layer.style || {};
        const layerType = (layer.style as any)?.type || _defaultLayerType(layer.geom_type);

        m.addLayer({
          id: layerId,
          type: layerType as any,
          source: sourceId,
          "source-layer": layer.id,
          paint: (paintProps as any).paint || _defaultPaint(layer.geom_type),
          layout: { visibility: layer.visible ? "visible" : "none" },
        });
      } else if (m.getLayer(layerId)) {
        m.setLayoutProperty(layerId, "visibility", layer.visible ? "visible" : "none");
      }
    });
  }, [layers]);

  const handleBasemapChange = useCallback((newBasemap: string) => {
    useMapStore.getState().setBasemap(newBasemap);
    map.current?.setStyle(BASEMAPS[newBasemap] || BASEMAPS.osm);
  }, []);

  return (
    <Box sx={{ display: "flex", height: "100vh", overflow: "hidden", position: "relative" }}>
      {/* Left: Layer panel */}
      <LayerPanel projectId={projectId} map={map} />

      {/* Centre: Map */}
      <Box ref={mapContainer} sx={{ flex: 1, height: "100%" }} />

      {/* Map toolbar */}
      <MapToolbar
        onBasemapChange={handleBasemapChange}
        onAnalysisOpen={() => setAnalysisOpen(true)}
        currentBasemap={basemap}
      />

      {/* Right: Analysis panel */}
      {analysisOpen && (
        <AnalysisPanel projectId={projectId} onClose={() => setAnalysisOpen(false)} />
      )}
    </Box>
  );
}

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
