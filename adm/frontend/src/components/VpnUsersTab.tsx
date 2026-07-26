import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Alert, Box, Button, Chip, CircularProgress, IconButton, MenuItem, Paper,
  Select, Snackbar, Table, TableBody, TableCell, TableContainer, TableHead,
  TableRow, TableSortLabel, TextField, Tooltip, Typography,
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

function cellOf(user: VpnUser, serverId: number): VpnUserAccess | undefined {
  return user.servers.find((s) => s.vpn_server_id === serverId);
}

/** Rank a cell so sorting reads top-to-bottom as "most access first". */
function cellRank(cell: VpnUserAccess | undefined): number {
  if (!cell) return 0;
  return cell.lan_access ? 2 : 1;
}

type SortKey = string; // "username" | "enabled" | `server:${id}`
type ServerFilter = "" | "granted" | "not" | "lan_on" | "lan_off" | "pending";

export default function VpnUsersTab() {
  const { t } = useTranslation();
  const [users, setUsers] = useState<VpnUser[]>([]);
  const [servers, setServers] = useState<VpnServer[]>([]);
  const [summary, setSummary] = useState<SyncSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [dialogUser, setDialogUser] = useState<VpnUser | null | "new">(null);
  const [revoking, setRevoking] = useState<{ user: VpnUser; server: VpnServer } | null>(null);
  const [snack, setSnack] = useState<{ msg: string; error?: boolean } | null>(null);

  // Column state
  const [sortKey, setSortKey] = useState<SortKey>("username");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [fUser, setFUser] = useState("");
  const [fEnabled, setFEnabled] = useState<"" | "on" | "off">("");
  const [fServer, setFServer] = useState<Record<number, ServerFilter>>({});

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

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("asc"); }
  };

  const visible = useMemo(() => {
    const q = fUser.trim().toLowerCase();

    const rows = users.filter((u) => {
      if (q && !u.username.toLowerCase().includes(q) && !u.full_name.toLowerCase().includes(q)) {
        return false;
      }
      if (fEnabled === "on" && !u.enabled) return false;
      if (fEnabled === "off" && u.enabled) return false;

      for (const s of servers) {
        const f = fServer[s.id];
        if (!f) continue;
        const cell = cellOf(u, s.id);
        if (f === "granted" && !cell) return false;
        if (f === "not" && cell) return false;
        if (f === "lan_on" && !(cell && cell.lan_access)) return false;
        if (f === "lan_off" && !(cell && !cell.lan_access)) return false;
        if (f === "pending" && !(cell && cell.sync_status !== "synced")) return false;
      }
      return true;
    });

    const dir = sortDir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      if (sortKey === "enabled") {
        return (Number(a.enabled) - Number(b.enabled)) * dir
          || a.username.localeCompare(b.username);
      }
      if (sortKey.startsWith("server:")) {
        const id = Number(sortKey.slice(7));
        return (cellRank(cellOf(a, id)) - cellRank(cellOf(b, id))) * dir
          || a.username.localeCompare(b.username);
      }
      return a.username.localeCompare(b.username) * dir;
    });
  }, [users, servers, fUser, fEnabled, fServer, sortKey, sortDir]);

  const reportSync = (sync?: { failed?: { target: string; error: string }[] }) => {
    const failed = sync?.failed ?? [];
    if (failed.length) {
      setSnack({
        msg: t("vpnUsers.syncFailed", {
          detail: failed.map((f) => `${f.target}: ${f.error}`).join(", "),
        }),
        error: true,
      });
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

  const waiting = (summary?.pending ?? 0) + (summary?.pending_delete ?? 0);
  const filtersOn = Boolean(fUser || fEnabled || Object.values(fServer).some(Boolean));
  const selectSx = { minWidth: 120, "& .MuiSelect-select": { py: 0.5, fontSize: 13 } };

  return (
    <Box>
      <Box sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap", mb: 2 }}>
        <Typography variant="body2" color="text.secondary">
          {filtersOn
            ? t("vpnUsers.countFiltered", { shown: visible.length, total: users.length })
            : t("vpnUsers.count", { count: users.length })}
        </Typography>
        {filtersOn && (
          <Button size="small" onClick={() => { setFUser(""); setFEnabled(""); setFServer({}); }}>
            {t("vpnUsers.clearFilters")}
          </Button>
        )}
        <Box sx={{ flexGrow: 1 }} />
        {waiting > 0 && (
          <Chip size="small" color="warning" label={t("vpnUsers.waiting", { count: waiting })} />
        )}
        {(summary?.error ?? 0) > 0 && (
          <Chip size="small" color="error" label={t("vpnUsers.failed", { count: summary!.error })} />
        )}
        <Tooltip title={t("vpnUsers.syncNow")}>
          <span>
            <IconButton onClick={syncAll} disabled={busy === "sync"}><SyncIcon /></IconButton>
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
                <TableCell sx={{ minWidth: 200 }}>
                  <TableSortLabel
                    active={sortKey === "username"}
                    direction={sortKey === "username" ? sortDir : "asc"}
                    onClick={() => toggleSort("username")}
                  >
                    {t("vpnUsers.user")}
                  </TableSortLabel>
                </TableCell>
                <TableCell sx={{ minWidth: 120 }}>
                  <TableSortLabel
                    active={sortKey === "enabled"}
                    direction={sortKey === "enabled" ? sortDir : "asc"}
                    onClick={() => toggleSort("enabled")}
                  >
                    {t("vpnUsers.status")}
                  </TableSortLabel>
                </TableCell>
                {servers.map((s) => (
                  <TableCell key={s.id} align="center" sx={{ minWidth: 150 }}>
                    <TableSortLabel
                      active={sortKey === `server:${s.id}`}
                      direction={sortKey === `server:${s.id}` ? sortDir : "asc"}
                      onClick={() => toggleSort(`server:${s.id}`)}
                    >
                      {s.display_name}
                    </TableSortLabel>
                  </TableCell>
                ))}
              </TableRow>

              {/* Filter row — one control per column, mirroring the header. */}
              <TableRow>
                <TableCell sx={{ py: 0.5 }}>
                  <TextField
                    size="small"
                    fullWidth
                    placeholder={t("vpnUsers.search")}
                    value={fUser}
                    onChange={(e) => setFUser(e.target.value)}
                    slotProps={{ input: { sx: { fontSize: 13 } } }}
                  />
                </TableCell>
                <TableCell sx={{ py: 0.5 }}>
                  <Select
                    size="small"
                    fullWidth
                    displayEmpty
                    value={fEnabled}
                    onChange={(e) => setFEnabled(e.target.value as typeof fEnabled)}
                    sx={selectSx}
                  >
                    <MenuItem value="">{t("vpnUsers.filterAllStatus")}</MenuItem>
                    <MenuItem value="on">{t("vpnUsers.filterEnabled")}</MenuItem>
                    <MenuItem value="off">{t("vpnUsers.filterDisabled")}</MenuItem>
                  </Select>
                </TableCell>
                {servers.map((s) => (
                  <TableCell key={s.id} align="center" sx={{ py: 0.5 }}>
                    <Select
                      size="small"
                      fullWidth
                      displayEmpty
                      value={fServer[s.id] ?? ""}
                      onChange={(e) =>
                        setFServer((f) => ({ ...f, [s.id]: e.target.value as ServerFilter }))
                      }
                      sx={selectSx}
                    >
                      <MenuItem value="">{t("vpnUsers.filterAll")}</MenuItem>
                      <MenuItem value="granted">{t("vpnUsers.filterGranted")}</MenuItem>
                      <MenuItem value="not">{t("vpnUsers.filterNotGranted")}</MenuItem>
                      <MenuItem value="lan_on">{t("vpnUsers.filterLanOn")}</MenuItem>
                      <MenuItem value="lan_off">{t("vpnUsers.filterLanOff")}</MenuItem>
                      <MenuItem value="pending">{t("vpnUsers.filterPending")}</MenuItem>
                    </Select>
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>

            <TableBody>
              {visible.map((u) => (
                <TableRow key={u.id} hover>
                  <TableCell>
                    <Box
                      component="button"
                      onClick={() => setDialogUser(u)}
                      sx={{
                        background: "none", border: 0, p: 0, cursor: "pointer",
                        color: "primary.main", textAlign: "left", font: "inherit",
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

                  <TableCell>
                    <Chip
                      size="small"
                      color={u.enabled ? "success" : "default"}
                      variant={u.enabled ? "filled" : "outlined"}
                      label={u.enabled ? t("vpnUsers.filterEnabled") : t("vpnUsers.filterDisabled")}
                    />
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
              {visible.length === 0 && (
                <TableRow>
                  <TableCell colSpan={servers.length + 2}>
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
