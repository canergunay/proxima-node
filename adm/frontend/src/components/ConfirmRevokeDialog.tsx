import {
  Alert, Button, Dialog, DialogActions, DialogContent, DialogTitle, Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";

interface Props {
  username: string;
  serverName: string;
  onCancel: () => void;
  onConfirm: () => void;
}

/**
 * Revoking is destructive: the remote account is deleted together with its
 * peers, because a WireGuard peer keeps working on its own keys once its
 * owner is gone. Say so plainly rather than hiding it behind "are you sure".
 */
export default function ConfirmRevokeDialog({ username, serverName, onCancel, onConfirm }: Props) {
  const { t } = useTranslation();

  return (
    <Dialog open onClose={onCancel} maxWidth="xs" fullWidth>
      <DialogTitle>{t("vpnUsers.revokeTitle")}</DialogTitle>
      <DialogContent>
        <Typography sx={{ mb: 2 }}>
          {t("vpnUsers.revokeBody", { username, server: serverName })}
        </Typography>
        <Alert severity="warning">{t("vpnUsers.revokeWarning")}</Alert>
        <Typography variant="caption" sx={{ display: "block", mt: 2, color: "text.secondary" }}>
          {t("vpnUsers.revokeAlternative")}
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel}>{t("common.cancel")}</Button>
        <Button color="error" variant="contained" onClick={onConfirm}>
          {t("vpnUsers.revokeConfirm")}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
