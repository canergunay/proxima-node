import { useCallback, useEffect, useState } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, Typography, Box, Chip, Divider, IconButton,
  Tooltip, Alert, CircularProgress, List, ListItem, ListItemText,
} from "@mui/material";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useTranslation } from "react-i18next";
import api from "../api/client";
import type { ServerDetail, Operation } from "../api/types";
import OutputViewer from "./OutputViewer";

interface Props {
  serverId: number;
  open: boolean;
  onClose: () => void;
  onRefresh: () => void;
}

function CopyField({ label, value }: { label: string; value: string | null }) {
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
      <Typography variant="body2" color="text.secondary" sx={{ minWidth: 120 }}>
        {label}
      </Typography>
      <Typography
        variant="body2"
        fontFamily="monospace"
        sx={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}
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
      fetchDetail();
    }
  }, [open, fetchDetail]);

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
      if (action === "provision") endpoint = "/provision";
      else if (action === "decommission") endpoint = `/provision/${serverId}/decommission`;
      else if (action === "rotate") endpoint = `/provision/${serverId}/rotate`;
      else if (action === "update-agent") endpoint = `/provision/${serverId}/update-agent`;
      else if (action === "restart") {
        await api.post(`/servers/${serverId}/restart`, {});
        fetchDetail();
        setActionLoading(false);
        return;
      }

      const body = action === "provision" ? { server_id: serverId } : {};
      const { data } = await api.post(endpoint, body);
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

  const ssconfUrl = server.ssconf_token
    ? `https://${server.ip}:8390/${server.ssconf_token}`
    : null;

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

        {/* Credentials */}
        {server.status !== "new" && (
          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle2" gutterBottom>{t("detail.credentials")}</Typography>
            <CopyField label={t("detail.ssPassword")} value={server.ss_password} />
            <CopyField label={t("detail.agentApiKey")} value={server.agent_api_key} />
            <CopyField label={t("detail.ssconfToken")} value={server.ssconf_token} />
            <CopyField label={t("detail.speedtestKey")} value={server.speedtest_api_key} />
            {ssconfUrl && <CopyField label={t("detail.ssconfUrl")} value={ssconfUrl} />}
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
        {server.status === "new" && (
          <Button
            variant="contained"
            onClick={() => handleAction("provision")}
            disabled={actionLoading}
          >
            {t("detail.provision")}
          </Button>
        )}
        {server.status === "error" && (
          <Button
            variant="contained"
            onClick={() => handleAction("provision")}
            disabled={actionLoading}
          >
            {t("detail.provision")}
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
