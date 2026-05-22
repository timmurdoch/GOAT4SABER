import { create } from "zustand";

export interface MapLayer {
  id: string;
  name: string;
  geom_type: string | null;
  visible: boolean;
  table_name: string | null;
  style: Record<string, unknown>;
  source_type: string;
}

interface MapState {
  layers: MapLayer[];
  selectedLayerId: string | null;
  basemap: string;
  viewState: {
    longitude: number;
    latitude: number;
    zoom: number;
    pitch: number;
    bearing: number;
  };
  addLayer: (layer: MapLayer) => void;
  removeLayer: (id: string) => void;
  updateLayer: (id: string, updates: Partial<MapLayer>) => void;
  toggleLayerVisibility: (id: string) => void;
  setSelectedLayer: (id: string | null) => void;
  setBasemap: (basemap: string) => void;
  setViewState: (vs: Partial<MapState["viewState"]>) => void;
  reorderLayers: (layers: MapLayer[]) => void;
  clearLayers: () => void;
}

export const useMapStore = create<MapState>()((set) => ({
  layers: [],
  selectedLayerId: null,
  basemap: "osm",
  viewState: {
    longitude: 133.7751,
    latitude: -25.2744,
    zoom: 4,
    pitch: 0,
    bearing: 0,
  },
  addLayer: (layer) =>
    set((s) => ({ layers: [layer, ...s.layers] })),
  removeLayer: (id) =>
    set((s) => ({ layers: s.layers.filter((l) => l.id !== id) })),
  updateLayer: (id, updates) =>
    set((s) => ({ layers: s.layers.map((l) => (l.id === id ? { ...l, ...updates } : l)) })),
  toggleLayerVisibility: (id) =>
    set((s) => ({
      layers: s.layers.map((l) => (l.id === id ? { ...l, visible: !l.visible } : l)),
    })),
  setSelectedLayer: (id) => set({ selectedLayerId: id }),
  setBasemap: (basemap) => set({ basemap }),
  setViewState: (vs) => set((s) => ({ viewState: { ...s.viewState, ...vs } })),
  reorderLayers: (layers) => set({ layers }),
  clearLayers: () => set({ layers: [], selectedLayerId: null }),
}));

export const BASEMAPS: Record<string, string> = {
  osm: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
  "carto-light": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  "carto-dark": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
  satellite: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
};
