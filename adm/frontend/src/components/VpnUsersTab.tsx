import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Box, Button, Chip, CircularProgress, IconButton, Paper, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, TextField, Tooltip,
  Typography, Alert, Snackbar,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import RefreshIcon from "@mui/icons-material/Refresh";
import SyncIcon from "@mui/icons-material/Sync";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import RadioButtonUncheckedIcon from "@mui/icons-material/RadioButtonUnchecked";
import LanIcon from "@mui/icons-material/Lan";
import BlockIcon from "@mui/icons-material/Block";
import { useTranslation } from "react-i18next";
import api from "../api/client";
import type { SyncSummary, VpnServer, VpnUser, VpnUserAccess } from "../api/types";
import VpnUserDialog from "./VpnUserDialog";
import ConfirmRevokeDialog from "./ConfirmRevokeDialog";

/** Cell state derived from the access row (or its absence). */
function cellOf(user: VpnUser, serverId: number): VpnUserAccess | undefined {
  return user.servers.find((s) => s.vpn_server_id === serverId);
}

export default function VpnUsersTab() {
  const { t } = useTranslation();
  const [users, setUsers] = useState<VpnUser[]>([]);
  const [servers, setServers] = useState<VpnServer[]>([]);
  const [summary, setSummary] = useState<SyncSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [dialogUser, setDialogUser] = useState<VpnUser | null | "new">(null);
  const [revoking, setRevoking] = useState<{ user: VpnUser; server: VpnServer } | null>(null);
  const [snack, setSnack] = useState<{ msg: string; error?: boolean } | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [u, s, sum] = await Promise.all([
        api.get("/vpn-users"),
        api.get("/vpn-servers"),
        api.get("/vpn-users/sync/status"),
      ]);
      if (u.data.ok) setUsers(u.data.data);
      if (s.data.ok) setServers(s.data.data);
      if (sum.data.ok) setSummary(sum.data.data);
    } catch { /* handled by interceptor */ }
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return users;
    return users.filter(
      (u) => u.username.toLowerCase().includes(q) || u.full_name.toLowerCase().includes(q),
    );
  }, [users, search]);

  /** Report what the immediate push did, so a silent failure is impossible. */
  const reportSync = (sync?: { failed?: { target: string; error: string }[] }) => {
    const failed = sync?.failed ?? [];
    if (failed.length) {
      setSnack({ msg: t("vpnUsers.syncFailed", { detail: failed.map((f) => `${f.target}: ${f.error}`).join(", ") }), error: true });
    }
  };

  const grant = async (user: VpnUser, server: VpnServer, patch: Record<string, unknown>) => {
    const key = `${user.id}:${server.id}`;
    setBusy(key);
    try {
      const { data } = await api.put(`/vpn-users/${user.id}/access/${server.id}`, patch);
      if (data.ok) reportSync(data.data?.sync);
      else setSnack({ msg: data.error, error: true });
    } catch {
      setSnack({ msg: t("vpnUsers.requestFailed"), error: true });
    }
    setBusy(null);
    fetchAll();
  };

  const confirmRevoke = async () => {
    if (!revoking) return;
    const { user, server } = revoking;
    setRevoking(null);
    setBusy(`${user.id}:${server.id}`);
    try {
      const { data } = await api.delete(`/vpn-users/${user.id}/access/${server.id}`);
      if (data.ok) {
        reportSync(data.data?.sync);
        if (data.data?.pending_sync) setSnack({ msg: t("vpnUsers.revokeQueued") });
      } else setSnack({ msg: data.error, error: true });
    } catch {
      setSnack({ msg: t("vpnUsers.requestFailed"), error: true });
    }
    setBusy(null);
    fetchAll();
  };

  const syncAll = async () => {
    setBusy("sync");
    try {
      const { data } = await api.post("/vpn-users/sync", {});
      if (data.ok) {
        const failed = data.data.failed ?? [];
        setSnack(failed.length
          ? { msg: t("vpnUsers.syncFailed", { detail: `${failed.length}` }), error: true }
          : { msg: t("vpnUsers.syncDone") });
      }
    } catch {
      setSnack({ msg: t("vpnUsers.requestFailed"), error: true });
    }
    setBusy(null);
    fetchAll();
  };

  if (loading) {
    return <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}><CircularProgress size={28} /></Box>;
  }

  const waiting = (summary?.pending ?? 0) + (summary?.pending_delete ?? 0) + (summary?.error ?? 0);

  return (
    <Box>
      <Box sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap", mb: 2 }}>
        <TextField
          size="small"
          placeholder={t("vpnUsers.search")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          sx={{ minWidth: 220 }}
        />
        <Box sx={{ flexGrow: 1 }} />
        {waiting > 0 && (
          <Chip
            size="small"
            color={summary?.error ? "error" : "warning"}
            label={t("vpnUsers.waiting", { count: waiting })}
          />
        )}
        <Tooltip title={t("vpnUsers.syncNow")}>
          <span>
            <IconButton onClick={syncAll} disabled={busy === "sync"}>
              <SyncIcon />
            </IconButton>
          </span>
        </Tooltip>
        <Tooltip title={t("dashboard.refresh")}>
          <IconButton onClick={fetchAll}><RefreshIcon /></IconButton>
        </Tooltip>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setDialogUser("new")}>
          {t("vpnUsers.addUser")}
        </Button>
      </Box>

      {summary?.errors?.length ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {summary.errors.map((e) => `${e.username}@${e.server_name}: ${e.sync_error}`).join(" · ")}
        </Alert>
      ) : null}

      {servers.length === 0 ? (
        <Typography color="text.secondary">{t("dashboard.noVpnServers")}</Typography>
      ) : (
        <TableContainer component={Paper} sx={{ overflowX: "auto" }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ minWidth: 180 }}>{t("vpnUsers.user")}</TableCell>
                {servers.map((s) => (
                  <TableCell key={s.id} align="center" sx={{ minWidth: 110 }}>
                    {s.display_name}
                    <Typography variant="caption" sx={{ display: "block", color: "text.secondary" }}>
                      {t("vpnUsers.accessLan")}
                    </Typography>
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {filtered.map((u) => (
                <TableRow key={u.id} hover>
                  <TableCell>
                    <Box
                      component="button"
                      onClick={() => setDialogUser(u)}
                      sx={{
                        background: "none", border: 0, p: 0, cursor: "pointer",
                        color: u.enabled ? "primary.main" : "text.disabled",
                        textAlign: "left", font: "inherit",
                        textDecoration: u.enabled ? "none" : "line-through",
                      }}
                    >
                      {u.username}
                    </Box>
                    {u.full_name && (
                      <Typography variant="caption" sx={{ display: "block", color: "text.secondary" }}>
                        {u.full_name}
                      </Typography>
                    )}
                  </TableCell>

                  {servers.map((s) => {
                    const cell = cellOf(u, s.id);
                    const key = `${u.id}:${s.id}`;
                    const pending = cell && cell.sync_status !== "synced";
                    return (
                      <TableCell key={s.id} align="center" sx={{ whiteSpace: "nowrap" }}>
                        <Tooltip title={cell ? t("vpnUsers.revokeHint") : t("vpnUsers.grantHint")}>
                          <span>
                            <IconButton
                              size="small"
                              disabled={busy === key}
                              onClick={() => (cell ? setRevoking({ user: u, server: s }) : grant(u, s, {}))}
                            >
                              {cell
                                ? <CheckCircleIcon fontSize="small" color={pending ? "warning" : "success"} />
                                : <RadioButtonUncheckedIcon fontSize="small" sx={{ color: "action.disabled" }} />}
                            </IconButton>
                          </span>
                        </Tooltip>

                        <Tooltip title={!cell ? "" : cell.lan_access ? t("vpnUsers.lanOnHint") : t("vpnUsers.lanOffHint")}>
                          <span>
                            <IconButton
                              size="small"
                              disabled={!cell || busy === key}
                              onClick={() => cell && grant(u, s, { lan_access: !cell.lan_access })}
                            >
                              {cell?.lan_access
                                ? <LanIcon fontSize="small" color="primary" />
                                : <BlockIcon fontSize="small" sx={{ color: cell ? "error.main" : "action.disabledBackground" }} />}
                            </IconButton>
                          </span>
                        </Tooltip>
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
              {filtered.length === 0 && (
                <TableRow>
                  <TableCell colSpan={servers.length + 1}>
                    <Typography color="text.secondary" sx={{ py: 2, textAlign: "center" }}>
                      {t("vpnUsers.noUsers")}
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Typography variant="caption" sx={{ display: "block", mt: 1, color: "text.secondary" }}>
        {t("vpnUsers.legend")}
      </Typography>

      {dialogUser !== null && (
        <VpnUserDialog
          user={dialogUser === "new" ? null : dialogUser}
          servers={servers}
          onClose={() => setDialogUser(null)}
          onSaved={() => { setDialogUser(null); fetchAll(); }}
        />
      )}

      {revoking && (
        <ConfirmRevokeDialog
          username={revoking.user.username}
          serverName={revoking.server.display_name}
          onCancel={() => setRevoking(null)}
          onConfirm={confirmRevoke}
        />
      )}

      <Snackbar
        open={Boolean(snack)}
        autoHideDuration={snack?.error ? 8000 : 3000}
        onClose={() => setSnack(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert severity={snack?.error ? "error" : "success"} onClose={() => setSnack(null)}>
          {snack?.msg}
        </Alert>
      </Snackbar>
    </Box>
  );
}
