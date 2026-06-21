import { useCallback, useEffect, useState } from "react";
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, Typography, Box, Chip, TextField, Alert,
  CircularProgress, Accordion, AccordionSummary, AccordionDetails,
  Table, TableHead, TableRow, TableCell, TableBody,
  IconButton, Tooltip, Select, MenuItem, FormControl, InputLabel,
  Tabs, Tab,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import CircleIcon from "@mui/icons-material/Circle";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import DeleteIcon from "@mui/icons-material/Delete";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useTranslation } from "react-i18next";
import api from "../api/client";
import type { VpnServer, ProximaSlot, ProximaTunnel } from "../api/types";

interface Props {
  vpnServer: VpnServer;
  open: boolean;
  onClose: () => void;
  onRefresh: () => void;
  onDeleted: () => void;
}

function CopyButton({ text }: { text: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  return (
    <Tooltip title={copied ? t("detail.copied") : "Copy"}>
      <IconButton
        size="small"
        onClick={(e) => {
          e.stopPropagation();
          navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }}
      >
        <ContentCopyIcon fontSize="small" />
      </IconButton>
    </Tooltip>
  );
}

export default function VpnServerDetailDialog({ vpnServer, open, onClose, onRefresh, onDeleted }: Props) {
  const { t } = useTranslation();
  const [tab, setTab] = useState(0);
  const [slots, setSlots] = useState<ProximaSlot[]>([]);
  const [tunnels, setTunnels] = useState<ProximaTunnel[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [tunnelsLoading, setTunnelsLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [tokenInput, setTokenInput] = useState("");
  const [tokenMsg, setTokenMsg] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  // Add tunnel state
  const [addTunnelOpen, setAddTunnelOpen] = useState(false);
  const [tunnelType, setTunnelType] = useState<"outline" | "xray">("outline");
  const [tunnelForm, setTunnelForm] = useState<Record<string, string>>({});
  const [tunnelError, setTunnelError] = useState("");

  const serverId = vpnServer.id;
  const isOnline = vpnServer.online;

  const fetchSlots = useCallback(async () => {
    if (!isOnline) return;
    setSlotsLoading(true);
    try {
      const { data } = await api.get(`/vpn-servers/${serverId}/proxima/slots`);
      if (data.ok) setSlots(data.data || []);
    } catch { /* */ }
    setSlotsLoading(false);
  }, [serverId, isOnline]);

  const fetchTunnels = useCallback(async () => {
    if (!isOnline) return;
    setTunnelsLoading(true);
    try {
      const { data } = await api.get(`/vpn-servers/${serverId}/proxima/tunnels`);
      if (data.ok) setTunnels(data.data || []);
    } catch { /* */ }
    setTunnelsLoading(false);
  }, [serverId, isOnline]);

  useEffect(() => {
    if (open && isOnline) {
      fetchSlots();
      fetchTunnels();
    }
  }, [open, isOnline, fetchSlots, fetchTunnels]);

  const handleUpdateToken = async () => {
    if (!tokenInput.trim()) return;
    setActionLoading(true);
    try {
      const { data } = await api.put(`/vpn-servers/${serverId}`, { api_token: tokenInput.trim() });
      if (data.ok) {
        setTokenMsg(t("vpnDetail.tokenUpdated"));
        setTokenInput("");
        setTimeout(() => setTokenMsg(""), 3000);
        onRefresh();
      }
    } catch { /* */ }
    setActionLoading(false);
  };

  const handleDelete = async () => {
    setActionLoading(true);
    try {
      const { data } = await api.delete(`/vpn-servers/${serverId}`);
      if (data.ok) {
        onDeleted();
      }
    } catch { /* */ }
    setActionLoading(false);
  };

  const handleSlotAction = async (slotId: string, action: string, body?: Record<string, unknown>) => {
    setActionLoading(true);
    try {
      if (action === "activate") {
        await api.post(`/vpn-servers/${serverId}/proxima/slots/${slotId}/activate`, body || {});
      } else if (action === "restart") {
        await api.post(`/vpn-servers/${serverId}/proxima/slots/${slotId}/restart`);
      } else if (action === "check-ip") {
        await api.post(`/vpn-servers/${serverId}/proxima/slots/${slotId}/check-ip`);
      }
      // Refresh slots after action
      setTimeout(fetchSlots, 2000);
    } catch { /* */ }
    setActionLoading(false);
  };

  const handleAddTunnel = async () => {
    setTunnelError("");
    setActionLoading(true);
    try {
      const body: Record<string, unknown> = { type: tunnelType };
      if (tunnelType === "outline") {
        if (!tunnelForm.ssconf_url) {
          setTunnelError("ssconf URL is required");
          setActionLoading(false);
          return;
        }
        body.ssconf_url = tunnelForm.ssconf_url;
        if (tunnelForm.tag) body.tag = tunnelForm.tag;
        if (tunnelForm.location) body.location = tunnelForm.location;
      } else {
        const required = ["server", "port", "vless_uuid", "public_key", "short_id", "server_name"];
        for (const f of required) {
          if (!tunnelForm[f]) {
            setTunnelError(`${f} is required`);
            setActionLoading(false);
            return;
          }
        }
        body.server = tunnelForm.server;
        body.port = parseInt(tunnelForm.port);
        body.vless_uuid = tunnelForm.vless_uuid;
        body.public_key = tunnelForm.public_key;
        body.short_id = tunnelForm.short_id;
        body.server_name = tunnelForm.server_name;
        body.flow = tunnelForm.flow || "xtls-rprx-vision";
        body.fingerprint = tunnelForm.fingerprint || "chrome";
        if (tunnelForm.tag) body.tag = tunnelForm.tag;
      }

      const { data } = await api.post(`/vpn-servers/${serverId}/proxima/tunnels`, body);
      if (data.ok) {
        setAddTunnelOpen(false);
        setTunnelForm({});
        fetchTunnels();
      } else {
        setTunnelError(data.error || "Failed to add tunnel");
      }
    } catch (err: unknown) {
      setTunnelError(err instanceof Error ? err.message : "Failed");
    }
    setActionLoading(false);
  };

  const handleDeleteTunnel = async (tunnelName: string) => {
    if (!confirm(t("vpnDetail.confirmDeleteTunnel"))) return;
    setActionLoading(true);
    try {
      await api.delete(`/vpn-servers/${serverId}/proxima/tunnels/${tunnelName}`);
      fetchTunnels();
    } catch { /* */ }
    setActionLoading(false);
  };

  const status = vpnServer.proxima_status;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        {vpnServer.display_name}
        <Chip
          icon={<CircleIcon sx={{ fontSize: 10, color: isOnline ? "#4caf50" : undefined }} />}
          label={isOnline ? t("vpnServer.online") : t("vpnServer.offline")}
          size="small"
          variant="outlined"
          color={isOnline ? "success" : "default"}
          sx={{ ml: "auto" }}
        />
      </DialogTitle>

      <DialogContent dividers>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2, borderBottom: 1, borderColor: "divider" }}>
          <Tab label={t("vpnDetail.status")} />
          <Tab label={t("vpnDetail.slots")} disabled={!isOnline} />
          <Tab label={t("vpnDetail.tunnels")} disabled={!isOnline} />
        </Tabs>

        {/* ── Tab 0: Status ─────────────────────────── */}
        {tab === 0 && (
          <Box>
            {status && (
              <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5, mb: 2 }}>
                <Box sx={{ display: "flex", gap: 4 }}>
                  <Box>
                    <Typography variant="caption" color="text.secondary">{t("vpnDetail.serverIp")}</Typography>
                    <Typography variant="body2">{status.server_ip}</Typography>
                  </Box>
                  {status.deployment && (
                    <Box>
                      <Typography variant="caption" color="text.secondary">{t("vpnDetail.deployment")}</Typography>
                      <Typography variant="body2">{status.deployment}</Typography>
                    </Box>
                  )}
                  <Box>
                    <Typography variant="caption" color="text.secondary">{t("vpnServer.dnsMode")}</Typography>
                    <Typography variant="body2">
                      {status.dns_mode?.active ? t("vpnServer.dnsActive") : t("vpnServer.dnsInactive")}
                    </Typography>
                  </Box>
                </Box>

                {status.dns_mode?.containers && (
                  <Box>
                    <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5, display: "block" }}>
                      {t("vpnDetail.dnsContainers")}
                    </Typography>
                    <Box sx={{ display: "flex", gap: 1 }}>
                      {Object.entries(status.dns_mode.containers).map(([name, st]) => (
                        <Chip
                          key={name}
                          label={`${name}: ${st}`}
                          size="small"
                          color={st === "running" ? "success" : "error"}
                          variant="outlined"
                        />
                      ))}
                    </Box>
                  </Box>
                )}

                {status.bypass_active && (
                  <Alert severity="warning" variant="outlined">
                    {t("vpnServer.bypassActive")}
                    {status.bypass_slots?.length > 0 && `: ${status.bypass_slots.join(", ")}`}
                  </Alert>
                )}
              </Box>
            )}

            {!isOnline && vpnServer.error && (
              <Alert severity="error" variant="outlined" sx={{ mb: 2 }}>
                {vpnServer.error}
              </Alert>
            )}

            {/* Token management */}
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="subtitle2">{t("vpnDetail.tokenSection")}</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Box sx={{ display: "flex", gap: 1, alignItems: "flex-start" }}>
                  <TextField
                    size="small"
                    fullWidth
                    multiline
                    rows={2}
                    placeholder={t("vpnDetail.tokenPlaceholder")}
                    value={tokenInput}
                    onChange={(e) => setTokenInput(e.target.value)}
                  />
                  <Button
                    variant="contained"
                    size="small"
                    onClick={handleUpdateToken}
                    disabled={actionLoading || !tokenInput.trim()}
                    sx={{ whiteSpace: "nowrap" }}
                  >
                    {t("vpnDetail.updateToken")}
                  </Button>
                </Box>
                {tokenMsg && (
                  <Typography variant="caption" color="success.main" sx={{ mt: 1, display: "block" }}>
                    {tokenMsg}
                  </Typography>
                )}
                <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>
                  URL: {vpnServer.url}
                </Typography>
              </AccordionDetails>
            </Accordion>
          </Box>
        )}

        {/* ── Tab 1: Slots ──────────────────────────── */}
        {tab === 1 && (
          <Box>
            {slotsLoading ? (
              <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
                <CircularProgress size={24} />
              </Box>
            ) : slots.length === 0 ? (
              <Typography color="text.secondary" sx={{ py: 2, textAlign: "center" }}>
                No slots
              </Typography>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Slot</TableCell>
                    <TableCell>{t("vpnDetail.slotType")}</TableCell>
                    <TableCell>{t("vpnDetail.slotActive")}</TableCell>
                    <TableCell>{t("vpnDetail.slotIp")}</TableCell>
                    <TableCell>{t("vpnDetail.slotHealth")}</TableCell>
                    <TableCell align="right">Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {[...slots].sort((a, b) => {
                    const aNum = parseInt(a.id.replace(/\D/g, ""), 10);
                    const bNum = parseInt(b.id.replace(/\D/g, ""), 10);
                    if (!isNaN(aNum) && !isNaN(bNum)) return aNum - bNum;
                    return a.id.localeCompare(b.id);
                  }).map((slot) => (
                    <SlotRow
                      key={slot.id}
                      slot={slot}
                      onAction={handleSlotAction}
                      actionLoading={actionLoading}
                    />
                  ))}
                </TableBody>
              </Table>
            )}
            <Box sx={{ mt: 1, display: "flex", justifyContent: "flex-end" }}>
              <Button size="small" startIcon={<RefreshIcon />} onClick={fetchSlots} disabled={slotsLoading}>
                {t("dashboard.refresh")}
              </Button>
            </Box>
          </Box>
        )}

        {/* ── Tab 2: Tunnels ─────────────────────────── */}
        {tab === 2 && (
          <Box>
            {tunnelsLoading ? (
              <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
                <CircularProgress size={24} />
              </Box>
            ) : tunnels.length === 0 ? (
              <Typography color="text.secondary" sx={{ py: 2, textAlign: "center" }}>
                {t("vpnDetail.noTunnels")}
              </Typography>
            ) : (
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Name</TableCell>
                    <TableCell>{t("vpnDetail.tunnelType")}</TableCell>
                    <TableCell>{t("vpnDetail.tunnelEndpoint")}</TableCell>
                    <TableCell>{t("vpnDetail.tunnelTag")}</TableCell>
                    <TableCell align="right"></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {tunnels.map((tunnel) => (
                    <TableRow key={tunnel.name}>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                          {tunnel.name}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip label={tunnel.type} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                          {tunnel.endpoint}
                        </Typography>
                      </TableCell>
                      <TableCell>{tunnel.tag || "—"}</TableCell>
                      <TableCell align="right">
                        {tunnel.ssconf_url && <CopyButton text={tunnel.ssconf_url} />}
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => handleDeleteTunnel(tunnel.name)}
                          disabled={actionLoading}
                        >
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}

            <Box sx={{ mt: 2, display: "flex", gap: 1, justifyContent: "flex-end" }}>
              <Button size="small" startIcon={<RefreshIcon />} onClick={fetchTunnels} disabled={tunnelsLoading}>
                {t("dashboard.refresh")}
              </Button>
              <Button size="small" variant="contained" onClick={() => { setAddTunnelOpen(true); setTunnelForm({}); setTunnelError(""); }}>
                {t("vpnDetail.addTunnel")}
              </Button>
            </Box>

            {/* Add tunnel form */}
            {addTunnelOpen && (
              <Box sx={{ mt: 2, p: 2, border: 1, borderColor: "divider", borderRadius: 1 }}>
                <FormControl size="small" sx={{ mb: 2, minWidth: 150 }}>
                  <InputLabel>{t("vpnDetail.tunnelType")}</InputLabel>
                  <Select
                    value={tunnelType}
                    label={t("vpnDetail.tunnelType")}
                    onChange={(e) => {
                      setTunnelType(e.target.value as "outline" | "xray");
                      setTunnelForm({});
                    }}
                  >
                    <MenuItem value="outline">Outline (SS)</MenuItem>
                    <MenuItem value="xray">Xray (VLESS)</MenuItem>
                  </Select>
                </FormControl>

                <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
                  {tunnelType === "outline" ? (
                    <>
                      <TextField
                        label={t("vpnDetail.ssconfUrl")}
                        size="small"
                        fullWidth
                        required
                        value={tunnelForm.ssconf_url || ""}
                        onChange={(e) => setTunnelForm({ ...tunnelForm, ssconf_url: e.target.value })}
                        placeholder="ssconf://host:port/token"
                      />
                      <Box sx={{ display: "flex", gap: 1 }}>
                        <TextField
                          label={t("vpnDetail.tunnelTag")}
                          size="small"
                          value={tunnelForm.tag || ""}
                          onChange={(e) => setTunnelForm({ ...tunnelForm, tag: e.target.value })}
                          placeholder="e.g. erg-tr"
                        />
                        <TextField
                          label={t("vpnDetail.tunnelLocation")}
                          size="small"
                          value={tunnelForm.location || ""}
                          onChange={(e) => setTunnelForm({ ...tunnelForm, location: e.target.value })}
                          placeholder="TR, DE..."
                        />
                      </Box>
                    </>
                  ) : (
                    <>
                      <Box sx={{ display: "flex", gap: 1 }}>
                        <TextField
                          label="Server"
                          size="small"
                          fullWidth
                          required
                          value={tunnelForm.server || ""}
                          onChange={(e) => setTunnelForm({ ...tunnelForm, server: e.target.value })}
                        />
                        <TextField
                          label="Port"
                          size="small"
                          sx={{ width: 100 }}
                          required
                          value={tunnelForm.port || ""}
                          onChange={(e) => setTunnelForm({ ...tunnelForm, port: e.target.value })}
                          placeholder="8443"
                        />
                      </Box>
                      <TextField
                        label="UUID"
                        size="small"
                        fullWidth
                        required
                        value={tunnelForm.vless_uuid || ""}
                        onChange={(e) => setTunnelForm({ ...tunnelForm, vless_uuid: e.target.value })}
                      />
                      <Box sx={{ display: "flex", gap: 1 }}>
                        <TextField
                          label="Public Key"
                          size="small"
                          fullWidth
                          required
                          value={tunnelForm.public_key || ""}
                          onChange={(e) => setTunnelForm({ ...tunnelForm, public_key: e.target.value })}
                        />
                        <TextField
                          label="Short ID"
                          size="small"
                          sx={{ width: 150 }}
                          required
                          value={tunnelForm.short_id || ""}
                          onChange={(e) => setTunnelForm({ ...tunnelForm, short_id: e.target.value })}
                        />
                      </Box>
                      <Box sx={{ display: "flex", gap: 1 }}>
                        <TextField
                          label="SNI (Server Name)"
                          size="small"
                          fullWidth
                          required
                          value={tunnelForm.server_name || ""}
                          onChange={(e) => setTunnelForm({ ...tunnelForm, server_name: e.target.value })}
                          placeholder="www.google.com"
                        />
                        <TextField
                          label={t("vpnDetail.tunnelTag")}
                          size="small"
                          value={tunnelForm.tag || ""}
                          onChange={(e) => setTunnelForm({ ...tunnelForm, tag: e.target.value })}
                          placeholder="erg-tr"
                        />
                      </Box>
                    </>
                  )}

                  {tunnelError && (
                    <Typography variant="body2" color="error">{tunnelError}</Typography>
                  )}

                  <Box sx={{ display: "flex", gap: 1, justifyContent: "flex-end" }}>
                    <Button size="small" onClick={() => setAddTunnelOpen(false)}>
                      {t("common.cancel")}
                    </Button>
                    <Button size="small" variant="contained" onClick={handleAddTunnel} disabled={actionLoading}>
                      {t("vpnDetail.addTunnel")}
                    </Button>
                  </Box>
                </Box>
              </Box>
            )}
          </Box>
        )}
      </DialogContent>

      <DialogActions>
        {deleteConfirm ? (
          <>
            <Typography variant="body2" color="error" sx={{ mr: "auto", ml: 1 }}>
              {t("vpnDetail.confirmDelete")}
            </Typography>
            <Button onClick={() => setDeleteConfirm(false)} size="small">
              {t("common.cancel")}
            </Button>
            <Button color="error" variant="contained" size="small" onClick={handleDelete} disabled={actionLoading}>
              {t("common.confirm")}
            </Button>
          </>
        ) : (
          <>
            <Button color="error" size="small" onClick={() => setDeleteConfirm(true)}>
              {t("vpnDetail.deleteServer")}
            </Button>
            <Box sx={{ flex: 1 }} />
            <Button onClick={onClose}>
              {t("common.close")}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
}

// ── Slot Row Component ─────────────────────────────────────────────────

interface SlotRowProps {
  slot: ProximaSlot;
  onAction: (slotId: string, action: string, body?: Record<string, unknown>) => void;
  actionLoading: boolean;
}

function SlotRow({ slot, onAction, actionLoading }: SlotRowProps) {
  const { t } = useTranslation();
  const [activateKey, setActivateKey] = useState("");

  const healthColor = slot.health.last_ip_ok === true
    ? "success"
    : slot.health.last_ip_ok === false
      ? "error"
      : "default";

  const healthLabel = slot.health.last_ip_ok === true
    ? t("vpnDetail.healthy")
    : slot.health.last_ip_ok === false
      ? t("vpnDetail.unhealthy")
      : t("vpnDetail.unknown");

  return (
    <TableRow>
      <TableCell>
        <Typography variant="body2" fontWeight={600}>{slot.active || slot.label || slot.id}</Typography>
      </TableCell>
      <TableCell>
        {slot.type ? (
          <Chip label={slot.type} size="small" variant="outlined" />
        ) : (
          <Chip label="direct" size="small" variant="outlined" color="default" />
        )}
      </TableCell>
      <TableCell>
        <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: "0.75rem" }}>
          {slot.active || t("vpnDetail.noActiveKey")}
        </Typography>
      </TableCell>
      <TableCell>
        <Typography variant="body2" sx={{ fontFamily: "monospace", fontSize: "0.75rem" }}>
          {slot.health.last_ip || "—"}
        </Typography>
      </TableCell>
      <TableCell>
        <Chip label={healthLabel} size="small" color={healthColor as "success" | "error" | "default"} variant="outlined" />
      </TableCell>
      <TableCell align="right">
        <Box sx={{ display: "flex", gap: 0.5, alignItems: "center", justifyContent: "flex-end" }}>
          {slot.pool.length > 1 && (
            <>
              <Select
                size="small"
                value={activateKey}
                onChange={(e) => setActivateKey(e.target.value)}
                displayEmpty
                sx={{ fontSize: "0.75rem", minWidth: 100, height: 30 }}
              >
                <MenuItem value="" disabled>Key...</MenuItem>
                {slot.pool.filter(k => k !== slot.active).map(k => (
                  <MenuItem key={k} value={k} sx={{ fontSize: "0.75rem" }}>{k}</MenuItem>
                ))}
              </Select>
              <Button
                size="small"
                variant="outlined"
                onClick={() => { if (activateKey) onAction(slot.id, "activate", { key_name: activateKey }); }}
                disabled={actionLoading || !activateKey}
                sx={{ minWidth: 0, px: 1, fontSize: "0.7rem" }}
              >
                {t("vpnDetail.activate")}
              </Button>
            </>
          )}
          <Tooltip title={t("vpnDetail.checkIp")}>
            <IconButton size="small" onClick={() => onAction(slot.id, "check-ip")} disabled={actionLoading}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </TableCell>
    </TableRow>
  );
}
