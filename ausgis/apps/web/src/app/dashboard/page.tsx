"use client";
import { useEffect, useState } from "react";
import {
  Box, Typography, Button, Card, CardContent, CardActions,
  Grid, CircularProgress, Fab, Dialog, DialogTitle,
  DialogContent, TextField, DialogActions,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import MapIcon from "@mui/icons-material/Map";
import { useRouter } from "next/navigation";
import { projectsApi } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export default function DashboardPage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");

  useEffect(() => {
    projectsApi.list().then((r) => setProjects(r.data)).finally(() => setLoading(false));
  }, []);

  const handleCreate = async () => {
    const res = await projectsApi.create(newName, newDesc);
    setProjects((p) => [res.data, ...p]);
    setCreateOpen(false);
    setNewName("");
    setNewDesc("");
    router.push(`/projects/${res.data.id}`);
  };

  return (
    <Box sx={{ minHeight: "100vh", bgcolor: "background.default" }}>
      <Box sx={{ bgcolor: "primary.main", color: "white", px: 4, py: 2, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Typography variant="h6" fontWeight={700}>AusGIS</Typography>
        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          <Typography variant="body2">{user?.full_name}</Typography>
          <Button variant="outlined" size="small" color="inherit" onClick={() => { logout(); router.push("/auth/login"); }}>
            Sign out
          </Button>
        </Box>
      </Box>

      <Box sx={{ p: 4 }}>
        <Typography variant="h5" fontWeight={700} mb={3}>My Projects</Typography>

        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", mt: 8 }}>
            <CircularProgress />
          </Box>
        ) : projects.length === 0 ? (
          <Box sx={{ textAlign: "center", mt: 8 }}>
            <MapIcon sx={{ fontSize: 64, color: "text.disabled", mb: 2 }} />
            <Typography variant="h6" color="text.secondary">No projects yet</Typography>
            <Typography variant="body2" color="text.secondary" mb={3}>Create a project to start mapping</Typography>
            <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateOpen(true)}>
              Create Project
            </Button>
          </Box>
        ) : (
          <Grid container spacing={3}>
            {projects.map((p) => (
              <Grid item xs={12} sm={6} md={4} key={p.id}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" fontWeight={600}>{p.name}</Typography>
                    <Typography variant="body2" color="text.secondary">{p.description || "No description"}</Typography>
                    <Typography variant="caption" color="text.disabled" display="block" mt={1}>
                      {new Date(p.created_at).toLocaleDateString("en-AU")}
                    </Typography>
                  </CardContent>
                  <CardActions>
                    <Button size="small" startIcon={<MapIcon />} onClick={() => router.push(`/projects/${p.id}`)}>
                      Open Map
                    </Button>
                  </CardActions>
                </Card>
              </Grid>
            ))}
          </Grid>
        )}
      </Box>

      <Fab color="primary" sx={{ position: "fixed", bottom: 24, right: 24 }} onClick={() => setCreateOpen(true)}>
        <AddIcon />
      </Fab>

      <Dialog open={createOpen} onClose={() => setCreateOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>New Project</DialogTitle>
        <DialogContent>
          <TextField label="Project name" fullWidth sx={{ mt: 1, mb: 2 }} value={newName} onChange={(e) => setNewName(e.target.value)} />
          <TextField label="Description (optional)" fullWidth multiline rows={3} value={newDesc} onChange={(e) => setNewDesc(e.target.value)} />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleCreate} disabled={!newName.trim()}>Create</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
