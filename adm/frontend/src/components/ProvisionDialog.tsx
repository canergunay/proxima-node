import { useCallback, useEffect, useState } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, TextField, FormControl, InputLabel, Select, MenuItem,
  FormControlLabel, Checkbox, Alert, Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import api from "../api/client";
import type { Operation } from "../api/types";
import OutputViewer from "./OutputViewer";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export default function ProvisionDialog({ open, onClose, onCreated }: Props) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [ip, setIp] = useState("");
  const [rootPassword, setRootPassword] = useState("");
  const [serverType, setServerType] = useState<string>("vpn_exit");
  const [location, setLocation] = useState("");
  const [provider, setProvider] = useState("");
  const [installAdguard, setInstallAdguard] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [operationId, setOperationId] = useState<number | null>(null);
  const [operation, setOperation] = useState<Operation | null>(null);

  // Poll operation status
  useEffect(() => {
    if (!operationId) return;
    const interval = setInterval(async () => {
      try {
        const { data } = await api.get(`/operations/${operationId}`);
        if (data.ok) {
          setOperation(data.data);
          if (data.data.status !== "running") {
            clearInterval(interval);
          }
        }
      } catch { /* ignore */ }
    }, 2000);
    return () => clearInterval(interval);
  }, [operationId]);

  const resetForm = useCallback(() => {
    setName("");
    setDisplayName("");
    setIp("");
    setRootPassword("");
    setServerType("vpn_exit");
    setLocation("");
    setProvider("");
    setInstallAdguard(false);
    setError("");
    setOperationId(null);
    setOperation(null);
  }, []);

  const handleClose = () => {
    if (operation && operation.status !== "running") {
      onCreated();
    }
    resetForm();
    onClose();
  };

  const handleRegister = async (provision: boolean) => {
    setError("");
    setLoading(true);
    try {
      // Step 1: Register server
      const { data } = await api.post("/servers", {
        name, display_name: displayName, ip, server_type: serverType,
        location, provider, root_password: rootPassword,
        install_adguard: installAdguard,
      });
      if (!data.ok) {
        setError(data.error);
        setLoading(false);
        return;
      }

      if (!provision) {
        onCreated();
        resetForm();
        onClose();
        return;
      }

      // Step 2: Start provisioning
      const serverId = data.data.id;
      const { data: provData } = await api.post("/provision", { server_id: serverId });
      if (provData.ok) {
        setOperationId(provData.data.operation_id);
      } else {
        setError(provData.error);
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string } } })
        ?.response?.data?.error;
      setError(msg || t("common.error"));
    } finally {
      setLoading(false);
    }
  };

  const isProvisionView = operationId !== null;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>{t("provision.title")}</DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        {!isProvisionView ? (
          <>
            <TextField
              fullWidth label={t("provision.name")}
              placeholder={t("provision.namePlaceholder")}
              value={name} onChange={(e) => setName(e.target.value)}
              margin="normal" size="small" required
            />
            <TextField
              fullWidth label={t("provision.displayName")}
              value={displayName} onChange={(e) => setDisplayName(e.target.value)}
              margin="normal" size="small"
            />
            <TextField
              fullWidth label={t("provision.ip")}
              value={ip} onChange={(e) => setIp(e.target.value)}
              margin="normal" size="small" required
            />
            <TextField
              fullWidth label={t("provision.rootPassword")}
              type="password" value={rootPassword}
              onChange={(e) => setRootPassword(e.target.value)}
              margin="normal" size="small"
              helperText={t("provision.rootPasswordHelp")}
            />
            <FormControl fullWidth margin="normal" size="small">
              <InputLabel>{t("provision.serverType")}</InputLabel>
              <Select
                value={serverType} label={t("provision.serverType")}
                onChange={(e) => setServerType(e.target.value)}
              >
                <MenuItem value="vpn_exit">{t("server.vpnExit")}</MenuItem>
                <MenuItem value="dpi_bypass">{t("server.dpiBypass")}</MenuItem>
              </Select>
            </FormControl>
            <TextField
              fullWidth label={t("provision.location")}
              placeholder={t("provision.locationPlaceholder")}
              value={location} onChange={(e) => setLocation(e.target.value)}
              margin="normal" size="small"
            />
            <TextField
              fullWidth label={t("provision.provider")}
              placeholder={t("provision.providerPlaceholder")}
              value={provider} onChange={(e) => setProvider(e.target.value)}
              margin="normal" size="small"
            />
            {serverType === "vpn_exit" && (
              <FormControlLabel
                control={
                  <Checkbox
                    checked={installAdguard}
                    onChange={(e) => setInstallAdguard(e.target.checked)}
                  />
                }
                label={t("provision.adguard")}
                sx={{ mt: 1 }}
              />
            )}
          </>
        ) : (
          operation && <OutputViewer output={operation.output || ""} status={operation.status} />
        )}
      </DialogContent>
      <DialogActions>
        {!isProvisionView ? (
          <>
            <Button onClick={handleClose}>{t("provision.cancel")}</Button>
            <Button
              onClick={() => handleRegister(false)}
              disabled={loading || !name || !ip}
            >
              {t("provision.register")}
            </Button>
            <Button
              variant="contained"
              onClick={() => handleRegister(true)}
              disabled={loading || !name || !ip || !rootPassword}
            >
              {t("provision.registerAndProvision")}
            </Button>
          </>
        ) : (
          <Button onClick={handleClose}>
            {operation?.status === "running" ? t("common.close") : t("common.close")}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
