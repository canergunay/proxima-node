import { useMemo, useState } from "react";
import {
  Alert, Box, Button, Checkbox, Chip, Dialog, DialogActions, DialogContent,
  DialogTitle, Divider, FormControlLabel, Grid2 as Grid, IconButton, Paper,
  Stack, TextField, Typography,
} from "@mui/material";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import { useTranslation } from "react-i18next";
import api from "../api/client";
import type { VpnServer, VpnUser, VpnUserAccess } from "../api/types";

interface Props {
  user: VpnUser | null;          // null = create
  servers: VpnServer[];
  onClose: () => void;
  onSaved: () => void;
}

/** Per-server limits the admin can edit from the detail view. */
interface Draft {
  granted: boolean;
  lan_access: boolean;
  max_peers: string;
}

const MIN_PASSWORD = 8;

export default function VpnUserDialog({ user, servers, onClose, onSaved }: Props) {
  const { t } = useTranslation();
  const isNew = user === null;

  const [username, setUsername] = useState(user?.username ?? "");
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [note, setNote] = useState(user?.note ?? "");
  const [enabled, setEnabled] = useState(user?.enabled ?? true);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [drafts, setDrafts] = useState<Record<number, Draft>>(() => {
    const out: Record<number, Draft> = {};
    for (const s of servers) {
      const a: VpnUserAccess | undefined = user?.servers.find((x) => x.vpn_server_id === s.id);
      out[s.id] = {
        granted: Boolean(a),
        lan_access: a?.lan_access ?? true,
        max_peers: a?.max_peers != null ? String(a.max_peers) : "",
      };
    }
    return out;
  });

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  /** Set once the password was accepted, so the onboarding block can be built. */
  const [issued, setIssued] = useState<{ password: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const tooShort = password.length > 0 && password.length < MIN_PASSWORD;

  const setDraft = (id: number, patch: Partial<Draft>) =>
    setDrafts((d) => ({ ...d, [id]: { ...d[id], ...patch } }));

  const grantedServers = useMemo(
    () => servers.filter((s) => drafts[s.id]?.granted),
    [servers, drafts],
  );

  /** The single block an admin hands over. One section per authorized site. */
  const onboarding = useMemo(() => {
    if (!issued) return "";
    const lines = grantedServers.map((s) => {
      const addr = s.public_url || s.url;
      return [
        s.display_name,
        `  ${t("vpnUsers.pkgAddress")}: ${addr}`,
        `  ${t("vpnUsers.pkgUsername")}: ${username}`,
        `  ${t("vpnUsers.pkgPassword")}: ${issued.password}`,
      ].join("\n");
    });
    return `${t("vpnUsers.pkgHeader")}\n\n${lines.join("\n\n")}`;
  }, [issued, grantedServers, username, t]);

  const copyPackage = async () => {
    await navigator.clipboard.writeText(onboarding);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const accessBody = (id: number) => {
    const d = drafts[id];
    return {
      lan_access: d.lan_access,
      max_peers: d.max_peers.trim() === "" ? null : Number(d.max_peers),
    };
  };

  const save = async () => {
    setError("");
    setSaving(true);
    try {
      if (isNew) {
        const { data } = await api.post("/vpn-users", {
          username: username.trim().toLowerCase(),
          full_name: fullName.trim(),
          note: note.trim(),
          password: password.trim(),
          enabled,
          servers: grantedServers.map((s) => ({ vpn_server_id: s.id, ...accessBody(s.id) })),
        });
        if (!data.ok) { setError(data.error); setSaving(false); return; }
        // Stay open and show the block to hand over.
        setIssued({ password: data.data.password });
        setSaving(false);
        return;
      }

      const { data } = await api.put(`/vpn-users/${user!.id}`, {
        full_name: fullName.trim(),
        note: note.trim(),
        enabled,
      });
      if (!data.ok) { setError(data.error); setSaving(false); return; }

      if (password.trim()) {
        const res = await api.post(`/vpn-users/${user!.id}/password`, {
          password: password.trim(),
        });
        if (!res.data.ok) { setError(res.data.error); setSaving(false); return; }
      }

      // Grants: add or update the ones ticked. Revoking is deliberately not
      // done here — it destroys peers, so it goes through the matrix
      // confirmation instead.
      for (const s of servers) {
        if (!drafts[s.id].granted) continue;
        await api.put(`/vpn-users/${user!.id}/access/${s.id}`, accessBody(s.id));
      }

      if (password.trim()) {
        setIssued({ password: password.trim() });
        setSaving(false);
        return;
      }
      onSaved();
    } catch {
      setError(t("vpnUsers.requestFailed"));
    }
    setSaving(false);
  };

  const canSave =
    username.trim().length > 0 &&
    !tooShort &&
    (!isNew || password.length >= MIN_PASSWORD);

  return (
    <Dialog open onClose={issued ? onSaved : onClose} maxWidth="md" fullWidth>
      <DialogTitle>{isNew ? t("vpnUsers.addUser") : username}</DialogTitle>
      <DialogContent dividers>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        {issued ? (
          <Box>
            <Alert severity="info" sx={{ mb: 2 }}>{t("vpnUsers.packageHint")}</Alert>
            <TextField
              multiline
              fullWidth
              value={onboarding}
              slotProps={{
                input: { readOnly: true, sx: { fontFamily: "monospace", fontSize: 13 } },
              }}
            />
            <Button
              sx={{ mt: 2 }}
              startIcon={<ContentCopyIcon />}
              onClick={copyPackage}
              variant="contained"
            >
              {copied ? t("detail.copied") : t("vpnUsers.copyPackage")}
            </Button>
          </Box>
        ) : (
          <Stack spacing={3} sx={{ mt: 1 }}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  label={t("vpnUsers.username")}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  disabled={!isNew}
                  helperText={isNew ? t("vpnUsers.usernameHelp") : t("vpnUsers.usernameLocked")}
                  fullWidth
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  label={t("vpnUsers.fullName")}
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  fullWidth
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  label={isNew ? t("vpnUsers.password") : t("vpnUsers.newPassword")}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  type={showPassword ? "text" : "password"}
                  error={tooShort}
                  helperText={
                    tooShort
                      ? t("vpnUsers.passwordTooShort", { min: MIN_PASSWORD })
                      : isNew
                        ? t("vpnUsers.passwordHelp", { min: MIN_PASSWORD })
                        : t("vpnUsers.newPasswordHelp")
                  }
                  fullWidth
                  slotProps={{
                    input: {
                      endAdornment: (
                        <IconButton size="small" onClick={() => setShowPassword((v) => !v)}>
                          {showPassword ? <VisibilityOffIcon fontSize="small" /> : <VisibilityIcon fontSize="small" />}
                        </IconButton>
                      ),
                    },
                  }}
                />
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <TextField
                  label={t("vpnUsers.note")}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  fullWidth
                />
              </Grid>
              <Grid size={12}>
                <FormControlLabel
                  control={<Checkbox checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />}
                  label={t("vpnUsers.accountEnabled")}
                />
              </Grid>
            </Grid>

            <Divider />

            <Box>
              <Typography variant="subtitle2" sx={{ mb: 1.5 }}>
                {t("vpnUsers.serverAccess")}
              </Typography>
              <Grid container spacing={2}>
                {servers.map((s) => {
                  const d = drafts[s.id];
                  const existing = user?.servers.find((x) => x.vpn_server_id === s.id);
                  return (
                    <Grid key={s.id} size={{ xs: 12, md: 6 }}>
                      <Paper
                        variant="outlined"
                        sx={{ p: 1.5, opacity: d.granted ? 1 : 0.6, height: "100%" }}
                      >
                        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                          <FormControlLabel
                            sx={{ flexGrow: 1, mr: 0 }}
                            control={
                              <Checkbox
                                checked={d.granted}
                                disabled={Boolean(existing)}
                                onChange={(e) => setDraft(s.id, { granted: e.target.checked })}
                              />
                            }
                            label={s.display_name}
                          />
                          {existing && existing.sync_status !== "synced" && (
                            <Chip size="small" color="warning" label={existing.sync_status} />
                          )}
                        </Box>

                        {d.granted ? (
                          <Stack spacing={1} sx={{ pl: 4, pt: 0.5 }}>
                            <TextField
                              size="small"
                              label={t("vpnUsers.maxPeers")}
                              value={d.max_peers}
                              onChange={(e) => setDraft(s.id, { max_peers: e.target.value.replace(/\D/g, "") })}
                              placeholder={t("vpnUsers.unlimited")}
                              sx={{ width: 160 }}
                            />
                            <FormControlLabel
                              control={
                                <Checkbox
                                  checked={d.lan_access}
                                  onChange={(e) => setDraft(s.id, { lan_access: e.target.checked })}
                                />
                              }
                              label={t("vpnUsers.lanAccess")}
                            />
                            {existing && (
                              <Typography variant="caption" color="text.secondary">
                                {t("vpnUsers.revokeFromMatrix")}
                              </Typography>
                            )}
                          </Stack>
                        ) : (
                          <Typography variant="caption" color="text.secondary" sx={{ pl: 4 }}>
                            {t("vpnUsers.notAuthorized")}
                          </Typography>
                        )}
                      </Paper>
                    </Grid>
                  );
                })}
              </Grid>
            </Box>
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        {issued ? (
          <Button variant="contained" onClick={onSaved}>{t("common.close")}</Button>
        ) : (
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="contained" onClick={save} disabled={saving || !canSave}>
              {t("common.save")}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
}
