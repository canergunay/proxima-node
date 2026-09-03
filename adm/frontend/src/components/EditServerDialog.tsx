import { useEffect, useState } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, TextField, Box, Alert,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import api from "../api/client";
import type { Server, VpnServer } from "../api/types";

/**
 * Rename and re-address a server that is already registered.
 *
 * Both PUT endpoints have always accepted these fields; nothing in the UI
 * reached them, so a server kept whatever name it was given at registration.
 * SHV still read "OFC Office Server" months after the site was renamed.
 */

type Kind = "exit" | "vpn";

interface Props {
  open: boolean;
  kind: Kind;
  server: Server | VpnServer | null;
  onClose: () => void;
  onSaved: () => void;
}

/** Which fields each kind exposes, in the order they are shown. */
const FIELDS: Record<Kind, { key: string; labelKey: string; required?: boolean }[]> = {
  exit: [
    { key: "display_name", labelKey: "editServer.displayName", required: true },
    { key: "name", labelKey: "editServer.name", required: true },
    { key: "ip", labelKey: "editServer.ip" },
    { key: "public_ip", labelKey: "editServer.publicIp" },
    { key: "location", labelKey: "editServer.location" },
    { key: "provider", labelKey: "editServer.provider" },
  ],
  vpn: [
    { key: "display_name", labelKey: "editServer.displayName", required: true },
    { key: "name", labelKey: "editServer.name", required: true },
    { key: "server_code", labelKey: "editServer.serverCode" },
    { key: "url", labelKey: "editServer.url" },
    { key: "public_url", labelKey: "editServer.publicUrl" },
    { key: "vpn_endpoint", labelKey: "editServer.vpnEndpoint" },
  ],
};

export default function EditServerDialog({ open, kind, server, onClose, onSaved }: Props) {
  const { t } = useTranslation();
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fields = FIELDS[kind];

  // Reload whenever a different server is opened, so the form never shows the
  // previous one's values.
  useEffect(() => {
    if (!server) return;
    const next: Record<string, string> = {};
    for (const f of fields) {
      const raw = (server as unknown as Record<string, unknown>)[f.key];
      next[f.key] = typeof raw === "string" ? raw : raw == null ? "" : String(raw);
    }
    setValues(next);
    setError("");
  }, [server, kind]);

  if (!server) return null;

  const handleSave = async () => {
    const missing = fields.find((f) => f.required && !values[f.key]?.trim());
    if (missing) {
      setError(t("editServer.requiredFields"));
      return;
    }

    // Send only what changed. The endpoints reject an empty update, which is
    // the right answer to "save without editing anything".
    const body: Record<string, string> = {};
    for (const f of fields) {
      const before = (server as unknown as Record<string, unknown>)[f.key];
      const beforeStr = typeof before === "string" ? before : before == null ? "" : String(before);
      const now = (values[f.key] ?? "").trim();
      if (now !== beforeStr) body[f.key] = now;
    }
    if (Object.keys(body).length === 0) {
      onClose();
      return;
    }

    setLoading(true);
    setError("");
    try {
      const path = kind === "exit" ? `/servers/${server.id}` : `/vpn-servers/${server.id}`;
      const { data } = await api.put(path, body);
      if (data.ok) {
        onSaved();
      } else {
        setError(data.error || t("editServer.saveFailed"));
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("editServer.saveFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{t("editServer.title")}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
          {error && <Alert severity="error">{error}</Alert>}
          {fields.map((f) => (
            <TextField
              key={f.key}
              label={t(f.labelKey)}
              value={values[f.key] ?? ""}
              onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
              required={f.required}
              size="small"
              fullWidth
            />
          ))}
          <Alert severity="info" sx={{ mt: 0.5 }}>
            {t("editServer.nameNote")}
          </Alert>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={loading}>{t("common.cancel")}</Button>
        <Button onClick={handleSave} variant="contained" disabled={loading}>
          {t("common.save")}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
