import { useState } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, TextField, Box,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import api from "../api/client";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export default function AddVpnServerDialog({ open, onClose, onCreated }: Props) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [url, setUrl] = useState("");
  const [apiToken, setApiToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    if (!name.trim() || !url.trim()) {
      setError("Name and URL are required");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const body: Record<string, string> = {
        name: name.trim().toLowerCase(),
        display_name: displayName.trim() || name.trim().toUpperCase(),
        url: url.trim(),
      };
      if (apiToken.trim()) {
        body.api_token = apiToken.trim();
      }

      const { data } = await api.post("/vpn-servers", body);
      if (data.ok) {
        // Reset form
        setName("");
        setDisplayName("");
        setUrl("");
        setApiToken("");
        onCreated();
      } else {
        setError(data.error || "Failed to create VPN server");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create VPN server";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{t("addVpn.title")}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          <TextField
            label={t("addVpn.name")}
            placeholder={t("addVpn.namePlaceholder")}
            value={name}
            onChange={(e) => setName(e.target.value)}
            size="small"
            fullWidth
            required
          />
          <TextField
            label={t("addVpn.displayName")}
            placeholder={t("addVpn.displayNamePlaceholder")}
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            size="small"
            fullWidth
          />
          <TextField
            label={t("addVpn.url")}
            placeholder={t("addVpn.urlPlaceholder")}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            size="small"
            fullWidth
            required
          />
          <TextField
            label={t("addVpn.apiToken")}
            value={apiToken}
            onChange={(e) => setApiToken(e.target.value)}
            size="small"
            fullWidth
            multiline
            rows={3}
            helperText={t("addVpn.apiTokenHelp")}
          />
          {error && (
            <Box sx={{ color: "error.main", fontSize: "0.875rem" }}>{error}</Box>
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={loading}>
          {t("common.cancel")}
        </Button>
        <Button
          variant="contained"
          onClick={handleSubmit}
          disabled={loading || !name.trim() || !url.trim()}
        >
          {t("addVpn.register")}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
