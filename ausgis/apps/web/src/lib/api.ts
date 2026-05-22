import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      const refreshToken = localStorage.getItem("refresh_token");
      if (refreshToken) {
        try {
          const res = await axios.post(`${API_URL}/api/v1/auth/refresh`, { refresh_token: refreshToken });
          localStorage.setItem("access_token", res.data.access_token);
          localStorage.setItem("refresh_token", res.data.refresh_token);
          error.config.headers.Authorization = `Bearer ${res.data.access_token}`;
          return axios(error.config);
        } catch {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.location.href = "/auth/login";
        }
      }
    }
    return Promise.reject(error);
  }
);

export const authApi = {
  login: (email: string, password: string) =>
    api.post("/auth/login", { email, password }),
  register: (email: string, full_name: string, password: string) =>
    api.post("/auth/register", { email, full_name, password }),
  me: () => api.get("/auth/me"),
};

export const projectsApi = {
  list: () => api.get("/projects"),
  create: (name: string, description?: string) =>
    api.post("/projects", { name, description }),
  get: (id: string) => api.get(`/projects/${id}`),
};

export const layersApi = {
  upload: (formData: FormData) =>
    api.post("/layers/upload", formData, { headers: { "Content-Type": "multipart/form-data" } }),
  get: (id: string) => api.get(`/layers/${id}`),
  delete: (id: string) => api.delete(`/layers/${id}`),
  updateStyle: (id: string, style: Record<string, unknown>) =>
    api.patch(`/layers/${id}/style`, { style }),
  export: (id: string, format: string) =>
    api.get(`/layers/${id}/export`, { params: { format }, responseType: "blob" }),
};

export const analysisApi = {
  // Basic
  isochrone: (payload: Record<string, unknown>) => api.post("/analysis/isochrone", payload),
  buffer: (payload: Record<string, unknown>) => api.post("/analysis/buffer", payload),
  pointInPolygon: (payload: Record<string, unknown>) => api.post("/analysis/point-in-polygon", payload),
  spatialJoin: (payload: Record<string, unknown>) => api.post("/analysis/spatial-join", payload),
  // Network
  shortestPath: (payload: Record<string, unknown>) => api.post("/analysis/shortest-path", payload),
  odMatrix: (payload: Record<string, unknown>) => api.post("/analysis/od-matrix", payload),
  catchmentPopulation: (payload: Record<string, unknown>) => api.post("/analysis/catchment-population", payload),
  // Overlay / geometry
  clip: (payload: Record<string, unknown>) => api.post("/analysis/clip", payload),
  overlay: (payload: Record<string, unknown>) => api.post("/analysis/overlay", payload),
  dissolve: (payload: Record<string, unknown>) => api.post("/analysis/dissolve", payload),
  centroid: (payload: Record<string, unknown>) => api.post("/analysis/centroid", payload),
  convexHull: (payload: Record<string, unknown>) => api.post("/analysis/convex-hull", payload),
  voronoi: (payload: Record<string, unknown>) => api.post("/analysis/voronoi", payload),
  // Point analysis
  kernelDensity: (payload: Record<string, unknown>) => api.post("/analysis/kernel-density", payload),
  cluster: (payload: Record<string, unknown>) => api.post("/analysis/cluster", payload),
  hexbin: (payload: Record<string, unknown>) => api.post("/analysis/hexbin", payload),
  // Jobs
  getJob: (jobId: string) => api.get(`/analysis/jobs/${jobId}`),
  listJobs: (projectId: string) => api.get(`/analysis/jobs`, { params: { project_id: projectId } }),
};

export const geocodeApi = {
  search: (q: string) => api.get("/geocode/search", { params: { q } }),
};

export const absApi = {
  boundaries: (level: string, state?: string, bbox?: string) =>
    api.get("/abs/boundaries", { params: { level, state, bbox } }),
  seifa: (sa2Code?: string, lgaCode?: string) =>
    api.get("/abs/seifa", { params: { sa2_code: sa2Code, lga_code: lgaCode } }),
};
