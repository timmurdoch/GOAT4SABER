"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { Box, Paper, TextField, Button, Typography, Alert, Link as MuiLink, CircularProgress } from "@mui/material";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import NextLink from "next/link";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

const schema = z.object({
  full_name: z.string().min(2),
  email: z.string().email(),
  password: z.string().min(8, "Password must be at least 8 characters"),
});
type FormData = z.infer<typeof schema>;

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [error, setError] = useState("");
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    try {
      setError("");
      await authApi.register(data.email, data.full_name, data.password);
      const loginRes = await authApi.login(data.email, data.password);
      const meRes = await authApi.me();
      setAuth(meRes.data, loginRes.data.access_token, loginRes.data.refresh_token);
      router.push("/dashboard");
    } catch (e: any) {
      setError(e?.response?.data?.detail || "Registration failed");
    }
  };

  return (
    <Box sx={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", bgcolor: "background.default" }}>
      <Paper sx={{ p: 4, width: "100%", maxWidth: 420 }}>
        <Typography variant="h5" fontWeight={700} mb={1}>Create your account</Typography>
        <Typography variant="body2" color="text.secondary" mb={3}>AusGIS — Australian WebGIS Platform</Typography>

        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <form onSubmit={handleSubmit(onSubmit)}>
          <TextField label="Full name" fullWidth sx={{ mb: 2 }} {...register("full_name")} error={!!errors.full_name} helperText={errors.full_name?.message} />
          <TextField label="Email" type="email" fullWidth sx={{ mb: 2 }} {...register("email")} error={!!errors.email} helperText={errors.email?.message} />
          <TextField label="Password" type="password" fullWidth sx={{ mb: 3 }} {...register("password")} error={!!errors.password} helperText={errors.password?.message} />
          <Button type="submit" variant="contained" fullWidth size="large" disabled={isSubmitting}>
            {isSubmitting ? <CircularProgress size={24} /> : "Create account"}
          </Button>
        </form>

        <Typography variant="body2" mt={2} textAlign="center">
          Already have an account?{" "}
          <MuiLink component={NextLink} href="/auth/login">Sign in</MuiLink>
        </Typography>
      </Paper>
    </Box>
  );
}
