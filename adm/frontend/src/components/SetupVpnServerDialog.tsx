import { useEffect, useState } from "react";
import {
  Alert, Box, Button, Dialog, DialogActions, DialogContent, DialogTitle,
  Grid2 as Grid, Stack, TextField, Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import api from "../api/client";
import OutputViewer from "./OutputViewer";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}

export default function SetupVpnServerDialog({ open, onClose, onCreated }: Props) {
  const { t } = useTranslation();

  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [serverCode, setServerCode] = useState("");
  const [sshHost, setSshHost] = useState("");
  const [sshPort, setSshPort] = useState("22");
  const [sshUser, setSshUser] = useState("root");
  const [sshPassword, setSshPassword] = useState("");

  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const [operationId, setOperationId] = useState<number | null>(null);
  const [output, setOutput] = useState("");
  const [status, setStatus] = useState("running");

  // Follow the run. The install takes minutes — building images, compiling
  // the AmneziaWG module — so the log is the only honest progress indicator.
  useEffect(() => {
    if (!operationId) return;
    const interval = setInterval(async () => {
      try {
        const { data } = await api.get(`/operations/${operationId}`);
        if (data.ok) {
          setOutput(data.data.output || "");
          setStatus(data.data.status);
          if (data.data.status !== "running") clearInterval(interval);
        }
      } catch { /* handled by interceptor */ }
    }, 2000);
    return () => clearInterval(interval);
  }, [operationId]);

  const reset = () => {
    setName(""); setDisplayName(""); setServerCode("");
    setSshHost(""); setSshPort("22"); setSshUser("root"); setSshPassword("");
    setError(""); setOperationId(null); setOutput(""); setStatus("running");
  };

  const start = async () => {
    setError("");
    setStarting(true);
    try {
      const { data } = await api.post("/vpn-servers/provision", {
        name: name.trim().toLowerCase(),
        display_name: displayName.trim(),
        server_code: serverCode.trim().toUpperCase(),
        ssh_host: sshHost.trim(),
        ssh_port: Number(sshPort) || 22,
        ssh_user: sshUser.trim(),
        ssh_password: sshPassword,
      });
      if (!data.ok) { setError(data.error); setStarting(false); return; }
      setOperationId(data.data.operation_id);
    } catch {
      setError(t("vpnUsers.requestFailed"));
    }
    setStarting(false);
  };

  // No password required: a box already carrying ADM's key is the normal case
  // for a reinstall or a kit prepared before it ships.
  const canStart = name.trim().length > 0 && sshHost.trim().length > 0;

  const running = operationId !== null;
  const finished = running && status !== "running";

  return (
    <Dialog
      open={open}
      onClose={running && !finished ? undefined : () => { reset(); onClose(); }}
      maxWidth="md"
      fullWidth
    >
      <DialogTitle>{t("setupVpn.title")}</DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        {running ? (
          <Box>
            {status === "running" && (
              <Alert severity="info" sx={{ mb: 2 }}>{t("setupVpn.running")}</Alert>
            )}
            {status === "done" && (
              <Alert severity="success" sx={{ mb: 2 }}>{t("setupVpn.done")}</Alert>
            )}
            {status === "failed" && (
              <Alert severity="error" sx={{ mb: 2 }}>{t("setupVpn.failed")}</Alert>
            )}
            <OutputViewer output={output} status={status} />
          </Box>
        ) : (
          <Stack spacing={3} sx={{ mt: 1 }}>
            <Alert severity="info">{t("setupVpn.explainer")}</Alert>

            <Box>
              <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
                {t("setupVpn.identity")}
              </Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <TextField
                    label={t("addVpn.name")} value={name} fullWidth
                    onChange={(e) => setName(e.target.value)}
                    helperText={t("setupVpn.nameHelp")}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <TextField
                    label={t("addVpn.displayName")} value={displayName} fullWidth
                    onChange={(e) => setDisplayName(e.target.value)}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 4 }}>
                  <TextField
                    label={t("setupVpn.serverCode")} value={serverCode} fullWidth
                    onChange={(e) => setServerCode(e.target.value.slice(0, 5))}
                    helperText={t("setupVpn.serverCodeHelp")}
                  />
                </Grid>
              </Grid>
            </Box>

            <Box>
              <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
                {t("setupVpn.access")}
              </Typography>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <TextField
                    label={t("setupVpn.sshHost")} value={sshHost} fullWidth
                    onChange={(e) => setSshHost(e.target.value)}
                    helperText={t("setupVpn.sshHostHelp")}
                  />
                </Grid>
                <Grid size={{ xs: 6, sm: 2 }}>
                  <TextField
                    label={t("setupVpn.sshPort")} value={sshPort} fullWidth
                    onChange={(e) => setSshPort(e.target.value.replace(/\D/g, ""))}
                  />
                </Grid>
                <Grid size={{ xs: 6, sm: 4 }}>
                  <TextField
                    label={t("setupVpn.sshUser")} value={sshUser} fullWidth
                    onChange={(e) => setSshUser(e.target.value)}
                    helperText={t("setupVpn.sshUserHelp")}
                  />
                </Grid>
                <Grid size={12}>
                  <TextField
                    label={t("setupVpn.sshPassword")} value={sshPassword}
                    type="password" fullWidth
                    onChange={(e) => setSshPassword(e.target.value)}
                    helperText={t("setupVpn.sshPasswordHelp")}
                  />
                </Grid>
              </Grid>
            </Box>

            <Alert severity="success" icon={false}>
              {t("setupVpn.panelAdminNote")}
            </Alert>
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        {running ? (
          <Button
            variant="contained"
            disabled={!finished}
            onClick={() => { reset(); onCreated(); }}
          >
            {finished ? t("common.close") : t("setupVpn.pleaseWait")}
          </Button>
        ) : (
          <>
            <Button onClick={() => { reset(); onClose(); }}>{t("common.cancel")}</Button>
            <Button variant="contained" onClick={start} disabled={starting || !canStart}>
              {t("setupVpn.start")}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
}
