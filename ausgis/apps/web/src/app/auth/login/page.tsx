"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Box, Paper, TextField, Button, Typography, Alert, Link as MuiLink, CircularProgress,
} from "@mui/material";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import NextLink from "next/link";
import axios from "axios";
import { useAuthStore } from "@/stores/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});
type FormData = z.infer<typeof schema>;

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [error, setError] = useState("");
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    try {
      setError("");
      // Step 1: login
      const loginRes = await axios.post(`${API_URL}/api/v1/auth/login`, {
        email: data.email,
        password: data.password,
      });
      const { access_token, refresh_token } = loginRes.data;

      // Step 2: fetch user with token passed directly in header
      const meRes = await axios.get(`${API_URL}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${access_token}` },
      });

      // Step 3: store everything
      setAuth(meRes.data, access_token, refresh_token);
      router.push("/dashboard");
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Invalid email or password";
      setError(msg);
    }
  };

  return (
    <Box sx={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", bgcolor: "background.default" }}>
      <Paper sx={{ p: 4, width: "100%", maxWidth: 420 }}>
        <Typography variant="h5" fontWeight={700} mb={1}>Sign in to AusGIS</Typography>
        <Typography variant="body2" color="text.secondary" mb={3}>Australian WebGIS Analysis Platform</Typography>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
        <form onSubmit={handleSubmit(onSubmit)}>
          <TextField
            label="Email" type="email" fullWidth sx={{ mb: 2 }}
            {...register("email")} error={!!errors.email} helperText={errors.email?.message}
          />
          <TextField
            label="Password" type="password" fullWidth sx={{ mb: 3 }}
            {...register("password")} error={!!errors.password} helperText={errors.password?.message}
          />
          <Button type="submit" variant="contained" fullWidth size="large" disabled={isSubmitting}>
            {isSubmitting ? <CircularProgress size={24} /> : "Sign in"}
          </Button>
        </form>
        <Typography variant="body2" mt={2} textAlign="center">
          No account?{" "}
          <MuiLink component={NextLink} href="/auth/register">Create one</MuiLink>
        </Typography>
      </Paper>
    </Box>
  );
}
