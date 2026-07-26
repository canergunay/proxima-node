import { useMemo, useState } from "react";
import {
  Alert, Box, Button, Checkbox, Chip, Dialog, DialogActions, DialogContent,
  DialogTitle, Divider, FormControlLabel, IconButton, Stack, TextField,
  Tooltip, Typography,
} from "@mui/material";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import LockResetIcon from "@mui/icons-material/LockReset";
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

export default function VpnUserDialog({ user, servers, onClose, onSaved }: Props) {
  const { t } = useTranslation();
  const isNew = user === null;

  const [username, setUsername] = useState(user?.username ?? "");
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  const [note, setNote] = useState(user?.note ?? "");
  const [enabled, setEnabled] = useState(user?.enabled ?? true);
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
  /** Set once, after creation or a reset — the only time we ever see it. */
  const [issued, setIssued] = useState<{ password: string } | null>(null);
  const [copied, setCopied] = useState(false);

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
      return `${s.display_name}\n  ${t("vpnUsers.pkgAddress")}: ${addr}\n  ${t("vpnUsers.pkgUsername")}: ${username}\n  ${t("vpnUsers.pkgPassword")}: ${issued.password}`;
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
          enabled,
          servers: grantedServers.map((s) => ({ vpn_server_id: s.id, ...accessBody(s.id) })),
        });
        if (!data.ok) { setError(data.error); setSaving(false); return; }
        // Keep the dialog open: this is the only moment the password exists.
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

      // Grants: add or update the ones ticked, revoke is deliberately not done
      // here — it destroys peers, so it goes through the matrix confirmation.
      for (const s of servers) {
        const d = drafts[s.id];
        if (!d.granted) continue;
        await api.put(`/vpn-users/${user!.id}/access/${s.id}`, accessBody(s.id));
      }
      onSaved();
    } catch {
      setError(t("vpnUsers.requestFailed"));
    }
    setSaving(false);
  };

  const resetPassword = async () => {
    setError("");
    setSaving(true);
    try {
      const { data } = await api.post(`/vpn-users/${user!.id}/password`, {});
      if (data.ok) setIssued({ password: data.data.password });
      else setError(data.error);
    } catch {
      setError(t("vpnUsers.requestFailed"));
    }
    setSaving(false);
  };

  return (
    <Dialog open onClose={issued ? onSaved : onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{isNew ? t("vpnUsers.addUser") : username}</DialogTitle>
      <DialogContent>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        {issued ? (
          <Box>
            <Alert severity="warning" sx={{ mb: 2 }}>{t("vpnUsers.passwordOnce")}</Alert>
            <TextField
              multiline
              fullWidth
              value={onboarding}
              slotProps={{ input: { readOnly: true, sx: { fontFamily: "monospace", fontSize: 13 } } }}
            />
            <Button
              sx={{ mt: 1 }}
              startIcon={<ContentCopyIcon />}
              onClick={copyPackage}
              variant="contained"
            >
              {copied ? t("detail.copied") : t("vpnUsers.copyPackage")}
            </Button>
          </Box>
        ) : (
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("vpnUsers.username")}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={!isNew}
              helperText={isNew ? t("vpnUsers.usernameHelp") : t("vpnUsers.usernameLocked")}
              fullWidth
            />
            <TextField
              label={t("vpnUsers.fullName")}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              fullWidth
            />
            <TextField
              label={t("vpnUsers.note")}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              fullWidth
            />
            <FormControlLabel
              control={<Checkbox checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />}
              label={t("vpnUsers.accountEnabled")}
            />

            <Divider />
            <Typography variant="subtitle2">{t("vpnUsers.serverAccess")}</Typography>

            {servers.map((s) => {
              const d = drafts[s.id];
              const existing = user?.servers.find((x) => x.vpn_server_id === s.id);
              return (
                <Box key={s.id} sx={{ pl: 1, borderLeft: 2, borderColor: "divider" }}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
                    <FormControlLabel
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
                    {existing && (
                      <Typography variant="caption" color="text.secondary">
                        {t("vpnUsers.revokeFromMatrix")}
                      </Typography>
                    )}
                  </Box>
                  {d.granted && (
                    <Stack direction="row" spacing={2} sx={{ pl: 4, pb: 1 }}>
                      <TextField
                        size="small"
                        label={t("vpnUsers.maxPeers")}
                        value={d.max_peers}
                        onChange={(e) => setDraft(s.id, { max_peers: e.target.value.replace(/\D/g, "") })}
                        placeholder={t("vpnUsers.unlimited")}
                        sx={{ width: 130 }}
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
                    </Stack>
                  )}
                </Box>
              );
            })}
          </Stack>
        )}
      </DialogContent>
      <DialogActions>
        {!isNew && !issued && (
          <Tooltip title={t("vpnUsers.resetPasswordHint")}>
            <Button startIcon={<LockResetIcon />} onClick={resetPassword} disabled={saving}>
              {t("vpnUsers.resetPassword")}
            </Button>
          </Tooltip>
        )}
        <Box sx={{ flexGrow: 1 }} />
        {issued ? (
          <Button variant="contained" onClick={onSaved}>{t("common.close")}</Button>
        ) : (
          <>
            <Button onClick={onClose}>{t("common.cancel")}</Button>
            <Button variant="contained" onClick={save} disabled={saving || !username.trim()}>
              {t("common.save")}
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  );
}
