import { useState } from "react";
import {
  Box, Button, Card, CardContent, TextField, Typography, Alert,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import api from "../api/client";

interface Props {
  isSetup: boolean;
  onLogin: (token: string) => void;
}

export default function Login({ isSetup, onLogin }: Props) {
  const { t } = useTranslation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const endpoint = isSetup ? "/auth/setup" : "/auth/login";
      const { data } = await api.post(endpoint, { username, password });
      if (data.ok) {
        onLogin(data.data.token);
      } else {
        setError(data.error || t("login.error"));
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string } } })
        ?.response?.data?.error;
      setError(msg || t("login.error"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        bgcolor: "background.default",
      }}
    >
      <Card sx={{ width: 400, maxWidth: "90vw" }}>
        <CardContent sx={{ p: 4 }}>
          <Typography variant="h5" gutterBottom fontWeight={700}>
            {isSetup ? t("setup.title") : t("login.title")}
          </Typography>
          {isSetup && (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              {t("setup.subtitle")}
            </Typography>
          )}
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <form onSubmit={handleSubmit}>
            <TextField
              fullWidth
              label={t("login.username")}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              margin="normal"
              autoFocus
              autoComplete="username"
            />
            <TextField
              fullWidth
              type="password"
              label={t("login.password")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              margin="normal"
              autoComplete={isSetup ? "new-password" : "current-password"}
            />
            <Button
              type="submit"
              variant="contained"
              fullWidth
              size="large"
              disabled={loading || !username || !password}
              sx={{ mt: 2 }}
            >
              {isSetup ? t("setup.submit") : t("login.submit")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </Box>
  );
}
