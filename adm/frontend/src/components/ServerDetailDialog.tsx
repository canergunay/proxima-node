import { useCallback, useEffect, useState } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, Typography, Box, Chip, Divider, IconButton,
  Tooltip, Alert, CircularProgress, List, ListItem, ListItemText,
  TextField, Accordion, AccordionSummary, AccordionDetails,
} from "@mui/material";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import RefreshIcon from "@mui/icons-material/Refresh";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import VpnKeyIcon from "@mui/icons-material/VpnKey";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import WarningIcon from "@mui/icons-material/Warning";
import ErrorIcon from "@mui/icons-material/Error";
import InfoIcon from "@mui/icons-material/Info";
import { useTranslation } from "react-i18next";
import api from "../api/client";
import type { ServerDetail, Operation, PreflightData, VlessKeyData } from "../api/types";
import OutputViewer from "./OutputViewer";

interface Props {
  serverId: number;
  open: boolean;
  onClose: () => void;
  onRefresh: () => void;
}

interface SsKeyData {
  uri: string;
  ssconf_url: string;
  server: string;
  port: number;
  method: string;
  password: string;
}

function CopyField({ label, value, mono }: { label: string; value: string | null; mono?: boolean }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);

  if (!value) return null;

  const handleCopy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
      <Typography variant="body2" color="text.secondary" sx={{ minWidth: 100, flexShrink: 0 }}>
        {label}
      </Typography>
      <Typography
        variant="body2"
        fontFamily={mono !== false ? "monospace" : undefined}
        sx={{
          flex: 1,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          fontSize: mono !== false ? "0.8rem" : undefined,
        }}
      >
        {value}
      </Typography>
      <Tooltip title={copied ? t("detail.copied") : "Copy"}>
        <IconButton size="small" onClick={handleCopy}>
          <ContentCopyIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  );
}

export default function ServerDetailDialog({ serverId, open, onClose, onRefresh }: Props) {
  const { t } = useTranslation();
  const [server, setServer] = useState<ServerDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [operationId, setOperationId] = useState<number | null>(null);
  const [operation, setOperation] = useState<Operation | null>(null);
  const [rootPassword, setRootPassword] = useState("");
  const [ssKey, setSsKey] = useState<SsKeyData | null>(null);
  const [ssKeyLoading, setSsKeyLoading] = useState(false);
  const [ssKeyError, setSsKeyError] = useState(false);
  const [vlessKey, setVlessKey] = useState<VlessKeyData | null>(null);
  const [vlessKeyLoading, setVlessKeyLoading] = useState(false);
  const [vlessKeyError, setVlessKeyError] = useState(false);
  const [preflight, setPreflight] = useState<PreflightData | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [preflightError, setPreflightError] = useState("");

  const fetchDetail = useCallback(async () => {
    try {
      const { data } = await api.get(`/servers/${serverId}`);
      if (data.ok) setServer(data.data);
    } catch { /* ignore */ }
    setLoading(false);
  }, [serverId]);

  useEffect(() => {
    if (open) {
      setLoading(true);
      setSsKey(null);
      setSsKeyError(false);
      setVlessKey(null);
      setVlessKeyError(false);
      fetchDetail();
    }
  }, [open, fetchDetail]);

  // Fetch SS key when server is active
  useEffect(() => {
    if (!server || server.status !== "active") return;
    setSsKeyLoading(true);
    api.get(`/servers/${serverId}/ss-key`)
      .then(({ data }) => {
        if (data.ok) setSsKey(data.data);
        else setSsKeyError(true);
      })
      .catch(() => setSsKeyError(true))
      .finally(() => setSsKeyLoading(false));
  }, [server?.status, serverId]);

  // Fetch VLESS key when server is active + vpn_exit
  useEffect(() => {
    if (!server || server.status !== "active" || server.server_type !== "vpn_exit") return;
    setVlessKeyLoading(true);
    api.get(`/servers/${serverId}/vless-key`)
      .then(({ data }) => {
        if (data.ok) setVlessKey(data.data);
        else setVlessKeyError(true);
      })
      .catch(() => setVlessKeyError(true))
      .finally(() => setVlessKeyLoading(false));
  }, [server?.status, server?.server_type, serverId]);

  // Poll operation
  useEffect(() => {
    if (!operationId) return;
    const interval = setInterval(async () => {
      try {
        const { data } = await api.get(`/operations/${operationId}`);
        if (data.ok) {
          setOperation(data.data);
          if (data.data.status !== "running") {
            clearInterval(interval);
            fetchDetail();
            onRefresh();
          }
        }
      } catch { /* ignore */ }
    }, 2000);
    return () => clearInterval(interval);
  }, [operationId, fetchDetail, onRefresh]);

  const runPreflight = async () => {
    if (!server) return;
    setPreflightError("");
    setPreflightLoading(true);
    setPreflight(null);
    try {
      const body = rootPassword ? { root_password: rootPassword } : {};
      const { data } = await api.post(`/servers/${serverId}/preflight`, body);
      if (data.ok) {
        setPreflight(data.data);
      } else {
        setPreflightError(data.error);
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string } } })
        ?.response?.data?.error;
      setPreflightError(msg || t("common.error"));
    } finally {
      setPreflightLoading(false);
    }
  };

  const startProvision = async () => {
    if (!server) return;
    setError("");
    setActionLoading(true);
    setPreflight(null);
    setPreflightError("");
    try {
      const body = { server_id: serverId, ...(rootPassword ? { root_password: rootPassword } : {}) };
      const { data } = await api.post("/provision", body);
      if (data.ok) {
        setOperationId(data.data.operation_id);
      } else {
        setError(data.error);
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string } } })
        ?.response?.data?.error;
      setError(msg || t("common.error"));
    } finally {
      setActionLoading(false);
    }
  };

  const handleAction = async (action: string) => {
    if (!server) return;
    setError("");
    setActionLoading(true);

    if (action === "decommission" && !confirm(t("detail.confirmDecommission"))) {
      setActionLoading(false);
      return;
    }
    if (action === "rotate" && !confirm(t("detail.confirmRotate"))) {
      setActionLoading(false);
      return;
    }

    try {
      let endpoint = "";
      if (action === "decommission") endpoint = `/provision/${serverId}/decommission`;
      else if (action === "rotate") endpoint = `/provision/${serverId}/rotate`;
      else if (action === "update-agent") endpoint = `/provision/${serverId}/update-agent`;
      else if (action === "install-agent") endpoint = `/provision/${serverId}/install-agent`;
      else if (action === "install-xray-reality") endpoint = `/provision/${serverId}/install-xray-reality`;
      else if (action === "restart") {
        await api.post(`/servers/${serverId}/restart`, {});
        fetchDetail();
        setActionLoading(false);
        return;
      }

      const { data } = await api.post(endpoint, {});
      if (data.ok) {
        setOperationId(data.data.operation_id);
      } else {
        setError(data.error);
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { error?: string } } })
        ?.response?.data?.error;
      setError(msg || t("common.error"));
    } finally {
      setActionLoading(false);
    }
  };

  const handleClose = () => {
    setOperationId(null);
    setOperation(null);
    setError("");
    setPreflight(null);
    setPreflightError("");
    onClose();
  };

  if (loading) {
    return (
      <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
        <DialogContent sx={{ display: "flex", justifyContent: "center", py: 4 }}>
          <CircularProgress />
        </DialogContent>
      </Dialog>
    );
  }

  if (!server) return null;

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>
        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          {server.display_name}
          <Chip label={server.status} size="small" />
          <Box sx={{ flex: 1 }} />
          <IconButton onClick={fetchDetail} size="small">
            <RefreshIcon />
          </IconButton>
        </Box>
      </DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        {/* Operation output */}
        {operation && (
          <Box sx={{ mb: 3 }}>
            <OutputViewer output={operation.output || ""} status={operation.status} />
          </Box>
        )}

        {/* Root password for new/error servers */}
        {(server.status === "new" || server.status === "error") && (
          <Box sx={{ mb: 3 }}>
            <TextField
              label={t("provision.rootPassword")}
              type="password"
              value={rootPassword}
              onChange={(e) => setRootPassword(e.target.value)}
              fullWidth
              size="small"
              helperText={t("provision.rootPasswordHelp")}
            />
          </Box>
        )}

        {/* Preflight results */}
        {preflightLoading && (
          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 3, p: 2, bgcolor: "action.hover", borderRadius: 1 }}>
            <CircularProgress size={20} />
            <Typography variant="body2">{t("preflight.checking")}</Typography>
          </Box>
        )}

        {preflightError && (
          <Alert severity="error" sx={{ mb: 3 }}
            action={
              <Button color="inherit" size="small" onClick={runPreflight}>
                {t("preflight.retry")}
              </Button>
            }
          >
            {t("preflight.failed")}: {preflightError}
          </Alert>
        )}

        {preflight && (
          <Box sx={{ mb: 3, p: 2, bgcolor: "action.hover", borderRadius: 1 }}>
            <Typography variant="subtitle2" sx={{ mb: 1.5 }}>{t("preflight.title")}</Typography>

            {/* System info */}
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
              <CheckCircleIcon fontSize="small" color="success" />
              <Typography variant="body2">{t("preflight.sshOk")}</Typography>
            </Box>
            <Box sx={{ pl: 3.5, mb: 1 }}>
              <Typography variant="caption" color="text.secondary">
                {t("preflight.os")}: {preflight.os} ({preflight.arch})
                {preflight.python ? ` | ${t("preflight.python")}: ${preflight.python}` : ""}
                {` | ${t("preflight.disk")}: ${preflight.disk_free_gb} GB`}
                {` | ${t("preflight.memory")}: ${preflight.memory_mb} MB`}
              </Typography>
            </Box>

            {/* Conflicts */}
            {preflight.conflicts.length === 0 ? (
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <CheckCircleIcon fontSize="small" color="success" />
                <Typography variant="body2" color="success.main">{t("preflight.noConflicts")}</Typography>
              </Box>
            ) : (
              <>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
                  <WarningIcon fontSize="small" color="warning" />
                  <Typography variant="body2" color="warning.main">
                    {t("preflight.conflicts")} ({preflight.conflicts.length})
                  </Typography>
                </Box>
                <List dense disablePadding sx={{ pl: 3.5 }}>
                  {preflight.conflicts.map((c, i) => (
                    <ListItem key={i} disablePadding sx={{ py: 0.15 }}>
                      <ListItemText
                        primary={
                          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                            {c.severity === "warning" ? (
                              <ErrorIcon sx={{ fontSize: 14, color: "warning.main" }} />
                            ) : (
                              <InfoIcon sx={{ fontSize: 14, color: "info.main" }} />
                            )}
                            <Typography variant="body2">
                              {c.type === "port"
                                ? `${t("preflight.portInUse", { port: c.port })} — ${c.detail}`
                                : c.type === "service"
                                  ? `${t("preflight.serviceActive")}: ${c.name} (${c.detail})`
                                  : `${t("preflight.containerRunning")}: ${c.name} (${c.detail})`
                              }
                            </Typography>
                          </Box>
                        }
                        primaryTypographyProps={{ component: "div" }}
                      />
                    </ListItem>
                  ))}
                </List>
              </>
            )}
          </Box>
        )}

        {/* Connection Keys — shown for active servers */}
        {server.status === "active" && (
          <Box sx={{ mb: 3 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1.5 }}>
              <VpnKeyIcon fontSize="small" color="primary" />
              <Typography variant="subtitle2">{t("detail.connectionKeys")}</Typography>
            </Box>

            {ssKeyLoading && (
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, py: 1 }}>
                <CircularProgress size={16} />
                <Typography variant="body2" color="text.secondary">
                  {t("detail.fetchingKeys")}
                </Typography>
              </Box>
            )}

            {ssKeyError && !ssKey && (
              <Alert severity="warning" variant="outlined" sx={{ mb: 1 }}>
                {t("detail.keysUnavailable")}
              </Alert>
            )}

            {ssKey && (
              <Box sx={{ bgcolor: "action.hover", borderRadius: 1, p: 1.5, mb: 1 }}>
                <CopyField label={t("detail.ssUri")} value={ssKey.uri} />
                {server.ssconf_token && (
                  <CopyField
                    label={t("detail.ssconfProxyUrl")}
                    value={`ssconf://${window.location.host}/api/servers/${serverId}/ssconf/${server.ssconf_token}`}
                  />
                )}
                {ssKey.ssconf_url && (
                  <CopyField label={t("detail.ssconfDirectUrl")} value={ssKey.ssconf_url} />
                )}
              </Box>
            )}

            {/* VLESS keys — vpn_exit only */}
            {server.server_type === "vpn_exit" && vlessKeyLoading && (
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, py: 1 }}>
                <CircularProgress size={16} />
                <Typography variant="body2" color="text.secondary">
                  {t("detail.fetchingVlessKeys")}
                </Typography>
              </Box>
            )}

            {server.server_type === "vpn_exit" && vlessKeyError && !vlessKey && (
              <Alert severity="info" variant="outlined" sx={{ mb: 1 }}>
                {t("detail.vlessNotInstalled")}
              </Alert>
            )}

            {vlessKey && (
              <Box sx={{ bgcolor: "action.hover", borderRadius: 1, p: 1.5, mb: 1 }}>
                <CopyField label={t("detail.vlessUri")} value={vlessKey.uri} />
              </Box>
            )}

            {/* Raw credentials in collapsible section */}
            <Accordion disableGutters elevation={0} sx={{ bgcolor: "transparent", "&:before": { display: "none" } }}>
              <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ px: 0, minHeight: 36 }}>
                <Typography variant="body2" color="text.secondary">
                  {t("detail.rawCredentials")}
                </Typography>
              </AccordionSummary>
              <AccordionDetails sx={{ px: 0, pt: 0 }}>
                <CopyField label={t("detail.ssPassword")} value={server.ss_password} />
                <CopyField label={t("detail.agentApiKey")} value={server.agent_api_key} />
                <CopyField label={t("detail.ssconfToken")} value={server.ssconf_token} />
                <CopyField label={t("detail.speedtestKey")} value={server.speedtest_api_key} />
              </AccordionDetails>
            </Accordion>
          </Box>
        )}

        {/* Raw credentials for non-active non-new statuses (provisioning, error) */}
        {server.status !== "new" && server.status !== "active" && (
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle2" gutterBottom>{t("detail.credentials")}</Typography>
            <CopyField label={t("detail.ssPassword")} value={server.ss_password} />
            <CopyField label={t("detail.agentApiKey")} value={server.agent_api_key} />
            <CopyField label={t("detail.ssconfToken")} value={server.ssconf_token} />
            <CopyField label={t("detail.speedtestKey")} value={server.speedtest_api_key} />
          </Box>
        )}

        <Divider sx={{ my: 2 }} />

        {/* Server info */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="body2" color="text.secondary">
            IP: {server.ip} | Type: {server.server_type} | Location: {server.location || "-"} | Provider: {server.provider || "-"}
          </Typography>
          {server.node_id && (
            <Typography variant="body2" color="text.secondary">
              Node ID: {server.node_id}
            </Typography>
          )}
        </Box>

        {/* Operations history */}
        {server.operations && server.operations.length > 0 && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" gutterBottom>{t("detail.operations")}</Typography>
            <List dense disablePadding>
              {server.operations.map((op) => (
                <ListItem key={op.id} disablePadding sx={{ py: 0.25 }}>
                  <ListItemText
                    primary={`${op.op_type} — ${op.status}`}
                    secondary={new Date(op.started_at * 1000).toLocaleString()}
                    primaryTypographyProps={{ variant: "body2" }}
                    secondaryTypographyProps={{ variant: "caption" }}
                  />
                  {op.error && (
                    <Typography variant="caption" color="error">{op.error}</Typography>
                  )}
                </ListItem>
              ))}
            </List>
          </>
        )}
      </DialogContent>
      <DialogActions>
        {(server.status === "new" || server.status === "error") && !preflight && (
          <Button
            variant="contained"
            onClick={runPreflight}
            disabled={actionLoading || preflightLoading || !rootPassword}
          >
            {t("detail.provision")}
          </Button>
        )}
        {(server.status === "new" || server.status === "error") && preflight && (
          <>
            <Button
              variant="contained"
              color={preflight.conflicts.length > 0 ? "warning" : "primary"}
              onClick={startProvision}
              disabled={actionLoading}
            >
              {preflight.conflicts.length > 0 ? t("preflight.continueAnyway") : t("detail.provision")}
            </Button>
            <Button onClick={runPreflight} disabled={preflightLoading}>
              {t("preflight.retry")}
            </Button>
          </>
        )}
        {server.status === "active" && !server.online && (
          <Button variant="contained" onClick={() => handleAction("install-agent")} disabled={actionLoading}>
            {t("detail.installAgent")}
          </Button>
        )}
        {server.status === "active" && server.server_type === "vpn_exit" && !vlessKey && !vlessKeyLoading && (
          <Button variant="outlined" onClick={() => handleAction("install-xray-reality")} disabled={actionLoading}>
            {t("detail.installXrayReality")}
          </Button>
        )}
        {server.status === "active" && (
          <>
            <Button onClick={() => handleAction("restart")} disabled={actionLoading}>
              {t("detail.restart")}
            </Button>
            <Button onClick={() => handleAction("update-agent")} disabled={actionLoading}>
              {t("detail.updateAgent")}
            </Button>
            <Button onClick={() => handleAction("rotate")} disabled={actionLoading} color="warning">
              {t("detail.rotate")}
            </Button>
            <Button onClick={() => handleAction("decommission")} disabled={actionLoading} color="error">
              {t("detail.decommission")}
            </Button>
          </>
        )}
        <Button onClick={handleClose}>{t("common.close")}</Button>
      </DialogActions>
    </Dialog>
  );
}
