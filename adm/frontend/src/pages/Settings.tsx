import { useState } from "react";
import {
  Box, Button, Card, CardContent, TextField, Typography, Alert,
  FormControl, InputLabel, Select, MenuItem, IconButton,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import { useTranslation } from "react-i18next";
import api from "../api/client";

interface Props {
  onBack: () => void;
}

export default function Settings({ onBack }: Props) {
  const { t, i18n } = useTranslation();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setMessage("");

    if (newPassword !== confirmPassword) {
      setError(t("settings.passwordMismatch"));
      return;
    }

    setLoading(true);
    try {
      const { data } = await api.put("/auth/password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      if (data.ok) {
        setMessage(t("settings.passwordChanged"));
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
      } else {
        setError(data.error);
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string } } })
        ?.response?.data?.error;
      setError(msg || t("common.error"));
    } finally {
      setLoading(false);
    }
  };

  const handleLanguageChange = (lang: string) => {
    i18n.changeLanguage(lang);
    localStorage.setItem("adm_lang", lang);
  };

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 3 }}>
        <IconButton onClick={onBack}>
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h5" fontWeight={700}>
          {t("settings.title")}
        </Typography>
      </Box>

      <Card sx={{ maxWidth: 500, mb: 3 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {t("settings.language")}
          </Typography>
          <FormControl fullWidth size="small">
            <InputLabel>{t("settings.language")}</InputLabel>
            <Select
              value={i18n.language}
              label={t("settings.language")}
              onChange={(e) => handleLanguageChange(e.target.value)}
            >
              <MenuItem value="en">English</MenuItem>
              <MenuItem value="tr">Turkce</MenuItem>
              <MenuItem value="ru">Русский</MenuItem>
            </Select>
          </FormControl>
        </CardContent>
      </Card>

      <Card sx={{ maxWidth: 500 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {t("settings.changePassword")}
          </Typography>
          {message && <Alert severity="success" sx={{ mb: 2 }}>{message}</Alert>}
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <form onSubmit={handleChangePassword}>
            <TextField
              fullWidth
              type="password"
              label={t("settings.currentPassword")}
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              margin="normal"
              size="small"
            />
            <TextField
              fullWidth
              type="password"
              label={t("settings.newPassword")}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              margin="normal"
              size="small"
            />
            <TextField
              fullWidth
              type="password"
              label={t("settings.confirmPassword")}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              margin="normal"
              size="small"
            />
            <Button
              type="submit"
              variant="contained"
              disabled={loading || !currentPassword || !newPassword || !confirmPassword}
              sx={{ mt: 2 }}
            >
              {t("settings.save")}
            </Button>
          </form>
        </CardContent>
      </Card>
    </Box>
  );
}
