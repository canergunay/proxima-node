import { useCallback, useEffect, useState } from "react";
import {
  Alert, Box, Button, Checkbox, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, FormControlLabel, IconButton, MenuItem, Paper,
  Select, Snackbar, Stack, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, TextField, Tooltip, Typography,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import { useTranslation } from "react-i18next";
import api from "../api/client";
import type { Admin, AdminRole, VpnServer } from "../api/types";

interface Props {
  onBack: () => void;
}

const MIN_PASSWORD = 8;

export default function Admins({ onBack }: Props) {
  const { t } = useTranslation();
  const [admins, setAdmins] = useState<Admin[]>([]);
  const [servers, setServers] = useState<VpnServer[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Admin | null | "new">(null);
  const [deleting, setDeleting] = useState<Admin | null>(null);
  const [snack, setSnack] = useState<{ msg: string; error?: boolean } | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [a, s] = await Promise.all([api.get("/admins"), api.get("/vpn-servers")]);
      if (a.data.ok) setAdmins(a.data.data);
      if (s.data.ok) setServers(s.data.data);
    } catch { /* handled by interceptor */ }
    setLoading(false);
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const remove = async () => {
    if (!deleting) return;
    try {
      const { data } = await api.delete(`/admins/${deleting.id}`);
      if (!data.ok) setSnack({ msg: data.error, error: true });
    } catch {
      setSnack({ msg: t("vpnUsers.requestFailed"), error: true });
    }
    setDeleting(null);
    fetchAll();
  };

  const serverName = (id: number) =>
    servers.find((s) => s.id === id)?.display_name ?? `#${id}`;

  if (loading) {
    return <Box sx={{ display: "flex", justifyContent: "center", p: 4 }}><CircularProgress size={28} /></Box>;
  }

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
        <IconButton onClick={onBack}><ArrowBackIcon /></IconButton>
        <Typography variant="h5" fontWeight={700} sx={{ flexGrow: 1 }}>
          {t("admins.title")}
        </Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setEditing("new")}>
          {t("admins.addAdmin")}
        </Button>
      </Box>

      <Alert severity="info" sx={{ mb: 2 }}>{t("admins.roleExplainer")}</Alert>

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{t("admins.username")}</TableCell>
              <TableCell>{t("admins.role")}</TableCell>
              <TableCell>{t("admins.servers")}</TableCell>
              <TableCell>{t("vpnUsers.status")}</TableCell>
              <TableCell align="right">{t("common.actions")}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {admins.map((a) => (
              <TableRow key={a.id} hover>
                <TableCell>{a.username}</TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    color={a.role === "superadmin" ? "primary" : "default"}
                    label={t(a.role === "superadmin" ? "admins.superadmin" : "admins.scopedAdmin")}
                  />
                </TableCell>
                <TableCell>
                  {a.role === "superadmin"
                    ? <Typography variant="body2" color="text.secondary">{t("admins.allServers")}</Typography>
                    : a.scope.map((id) => (
                        <Chip key={id} size="small" variant="outlined" label={serverName(id)} sx={{ mr: 0.5 }} />
                      ))}
                </TableCell>
                <TableCell>
                  <Chip
                    size="small"
                    color={a.enabled ? "success" : "default"}
                    variant={a.enabled ? "filled" : "outlined"}
                    label={t(a.enabled ? "vpnUsers.filterEnabled" : "vpnUsers.filterDisabled")}
                  />
                </TableCell>
                <TableCell align="right">
                  <Tooltip title={t("common.save")}>
                    <IconButton size="small" onClick={() => setEditing(a)}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title={t("common.delete")}>
                    <IconButton size="small" color="error" onClick={() => setDeleting(a)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      {editing !== null && (
        <AdminDialog
          admin={editing === "new" ? null : editing}
          servers={servers}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); fetchAll(); }}
        />
      )}

      <Dialog open={!!deleting} onClose={() => setDeleting(null)} maxWidth="xs" fullWidth>
        <DialogTitle>{t("admins.deleteTitle")}</DialogTitle>
        <DialogContent>
          <Typography>{t("admins.deleteBody", { username: deleting?.username })}</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleting(null)}>{t("common.cancel")}</Button>
          <Button color="error" variant="contained" onClick={remove}>{t("common.delete")}</Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={Boolean(snack)}
        autoHideDuration={6000}
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

function AdminDialog({ admin, servers, onClose, onSaved }: {
  admin: Admin | null;
  servers: VpnServer[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const { t } = useTranslation();
  const isNew = admin === null;

  const [username, setUsername] = useState(admin?.username ?? "");
  const [role, setRole] = useState<AdminRole>(admin?.role ?? "admin");
  const [enabled, setEnabled] = useState(admin?.enabled ?? true);
  const [scope, setScope] = useState<number[]>(admin?.scope ?? []);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [issued, setIssued] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const tooShort = password.length > 0 && password.length < MIN_PASSWORD;
  const scopeMissing = role === "admin" && scope.length === 0;

  const toggleServer = (id: number) =>
    setScope((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const save = async () => {
    setError(""); setSaving(true);
    try {
      const body: Record<string, unknown> = { role, enabled, scope };
      if (password.trim()) body.password = password.trim();
      const { data } = isNew
        ? await api.post("/admins", { ...body, username: username.trim().toLowerCase() })
        : await api.put(`/admins/${admin!.id}`, body);
      if (!data.ok) { setError(data.error); setSaving(false); return; }
      if (data.data?.password) { setIssued(data.data.password); setSaving(false); return; }
      onSaved();
    } catch {
      setError(t("vpnUsers.requestFailed"));
    }
    setSaving(false);
  };

  return (
    <Dialog open onClose={issued ? onSaved : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{isNew ? t("admins.addAdmin") : username}</DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        {issued ? (
          <Box>
            <Alert severity="warning" sx={{ mb: 2 }}>{t("admins.passwordOnce")}</Alert>
            <TextField
              fullWidth
              value={`${username}\n${issued}`}
              multiline
              slotProps={{ input: { readOnly: true, sx: { fontFamily: "monospace" } } }}
            />
            <Button
              sx={{ mt: 2 }}
              variant="contained"
              startIcon={<ContentCopyIcon />}
              onClick={async () => {
                await navigator.clipboard.writeText(`${username}\n${issued}`);
                setCopied(true); setTimeout(() => setCopied(false), 2000);
              }}
            >
              {copied ? t("detail.copied") : t("vpnUsers.copyPackage")}
            </Button>
          </Box>
        ) : (
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("admins.username")}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={!isNew}
              fullWidth
            />
            <TextField
              label={isNew ? t("vpnUsers.password") : t("vpnUsers.newPassword")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              error={tooShort}
              helperText={tooShort
                ? t("vpnUsers.passwordTooShort", { min: MIN_PASSWORD })
                : isNew ? t("vpnUsers.passwordHelp", { min: MIN_PASSWORD })
                        : t("vpnUsers.newPasswordHelp")}
              fullWidth
            />
            <Select value={role} onChange={(e) => setRole(e.target.value as AdminRole)} fullWidth>
              <MenuItem value="superadmin">{t("admins.superadmin")}</MenuItem>
              <MenuItem value="admin">{t("admins.scopedAdmin")}</MenuItem>
            </Select>
            <Typography variant="caption" color="text.secondary">
              {t(role === "superadmin" ? "admins.superadminHelp" : "admins.scopedAdminHelp")}
            </Typography>

            {role === "admin" && (
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>{t("admins.servers")}</Typography>
                {servers.map((s) => (
                  <FormControlLabel
                    key={s.id}
                    control={
                      <Checkbox checked={scope.includes(s.id)} onChange={() => toggleServer(s.id)} />
                    }
                    label={s.display_name}
                  />
                ))}
                {scopeMissing && (
                  <Typography variant="caption" color="error" sx={{ display: "block" }}>
                    {t("admins.scopeRequired")}
                  </Typography>
                )}
              </Box>
            )}

            <FormControlLabel
              control={<Checkbox checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />}
              label={t("admins.accountEnabled")}
            />
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        {issued ? (
          <Button variant="contained" onClick={onSaved}>{t("common.close")}</Button>
        ) : (
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button
              variant="contained"
              onClick={save}
              disabled={saving || tooShort || scopeMissing
                || !username.trim() || (isNew && password.length < MIN_PASSWORD)}
            >
              {t("common.save")}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
}
