"use client";
import dynamic from "next/dynamic";
import { Box, CircularProgress } from "@mui/material";

const ProjectMap = dynamic(() => import("@/components/map/ProjectMap"), {
  ssr: false,
  loading: () => (
    <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100vh" }}>
      <CircularProgress />
    </Box>
  ),
});

export default function ProjectPage({ params }: { params: { id: string } }) {
  return <ProjectMap projectId={params.id} />;
}
