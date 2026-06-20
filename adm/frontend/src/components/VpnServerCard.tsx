import {
  Card, CardActionArea, CardContent, Typography, Box, Chip,
} from "@mui/material";
import CircleIcon from "@mui/icons-material/Circle";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import { useTranslation } from "react-i18next";
import type { VpnServer } from "../api/types";

interface Props {
  server: VpnServer;
  onClick: () => void;
}

export default function VpnServerCard({ server, onClick }: Props) {
  const { t } = useTranslation();
  const status = server.proxima_status;
  const isOnline = server.online;

  // Count healthy slots — only slots that have been health-checked
  let healthyCount = 0;
  let totalSlots = 0;
  if (status?.slots) {
    for (const slot of Object.values(status.slots)) {
      // Skip unchecked slots (Direct, disabled, no active key)
      if (slot.health?.last_ip_ok === null || slot.health?.last_ip_ok === undefined) continue;
      totalSlots++;
      if (slot.health.last_ip_ok === true) healthyCount++;
    }
  }

  return (
    <Card variant="outlined">
      <CardActionArea onClick={onClick}>
        <CardContent>
          <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 1 }}>
            <Box>
              <Typography variant="subtitle1" fontWeight={700}>
                {server.display_name}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: "0.75rem" }}>
                {server.url}
              </Typography>
            </Box>
            <Chip
              icon={<CircleIcon sx={{ fontSize: 10, color: isOnline ? "#4caf50" : undefined }} />}
              label={isOnline ? t("vpnServer.online") : t("vpnServer.offline")}
              size="small"
              variant="outlined"
              color={isOnline ? "success" : "default"}
            />
          </Box>

          {status && (
            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mb: 1 }}>
              {totalSlots > 0 && (
                <Chip
                  label={t("vpnServer.slotsHealthy", { healthy: healthyCount, total: totalSlots })}
                  size="small"
                  color={healthyCount === totalSlots ? "success" : healthyCount > 0 ? "warning" : "error"}
                  variant="outlined"
                />
              )}
              <Chip
                label={`${t("vpnServer.dnsMode")}: ${status.dns_mode?.active ? t("vpnServer.dnsActive") : t("vpnServer.dnsInactive")}`}
                size="small"
                variant="outlined"
                color={status.dns_mode?.active ? "success" : "default"}
              />
              {status.bypass_active && (
                <Chip
                  icon={<WarningAmberIcon sx={{ fontSize: 14 }} />}
                  label={t("vpnServer.bypassActive")}
                  size="small"
                  color="warning"
                />
              )}
            </Box>
          )}

          {status && (
            <Box sx={{ mt: 0.5 }}>
              <Typography variant="caption" color="text.secondary" display="block">
                {t("vpnServer.serverIp")}: {status.server_ip}
              </Typography>
              {status.deployment && (
                <Typography variant="caption" color="text.secondary" display="block">
                  {t("vpnServer.deployment")}: {status.deployment}
                </Typography>
              )}
            </Box>
          )}

          {!server.has_token && (
            <Typography variant="caption" color="warning.main" sx={{ mt: 1, display: "block" }}>
              {t("vpnServer.noToken")}
            </Typography>
          )}

          {server.error && server.has_token && (
            <Typography variant="caption" color="error" sx={{ mt: 1, display: "block" }}>
              {server.error}
            </Typography>
          )}
        </CardContent>
      </CardActionArea>
    </Card>
  );
}
