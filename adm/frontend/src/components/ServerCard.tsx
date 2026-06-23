import {
  Card, CardActionArea, CardContent, Typography, Box, Chip, LinearProgress,
} from "@mui/material";
import CircleIcon from "@mui/icons-material/Circle";
import { useTranslation } from "react-i18next";
import type { Server } from "../api/types";

interface Props {
  server: Server;
  onClick: () => void;
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  if (d > 0) return `${d}d ${h}h`;
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

const statusColors: Record<string, string> = {
  active: "#4caf50",
  new: "#9e9e9e",
  provisioning: "#ff9800",
  error: "#f44336",
  decommissioned: "#616161",
};

export default function ServerCard({ server, onClick }: Props) {
  const { t } = useTranslation();
  const status = server.agent_status;
  const isOnline = server.online;

  return (
    <Card variant="outlined">
      <CardActionArea onClick={onClick}>
        <CardContent>
          <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 1 }}>
            <Box>
              <Typography variant="subtitle1" fontWeight={700}>
                {server.display_name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {server.ip}
              </Typography>
            </Box>
            <Box sx={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 0.5 }}>
              <Chip
                icon={<CircleIcon sx={{ fontSize: 10, color: isOnline ? "#4caf50" : undefined }} />}
                label={isOnline ? t("server.online") : t("server.offline")}
                size="small"
                variant="outlined"
                color={isOnline ? "success" : "default"}
              />
              <Chip
                label={server.server_type === "vpn_exit" ? t("server.vpnExit") : t("server.dpiBypass")}
                size="small"
                variant="outlined"
              />
            </Box>
          </Box>

          <Box sx={{ display: "flex", gap: 1, mb: 1 }}>
            {server.location && (
              <Chip label={server.location} size="small" />
            )}
            <Chip
              label={t(`server.${server.status}`)}
              size="small"
              sx={{ bgcolor: statusColors[server.status] + "33", color: statusColors[server.status] }}
            />
          </Box>

          {status && (
            <Box sx={{ mt: 1.5 }}>
              {status.public_ip && (
                <Typography variant="caption" color="text.secondary" display="block">
                  {t("server.publicIp")}: {status.public_ip}
                </Typography>
              )}
              {status.uptime > 0 && (
                <Typography variant="caption" color="text.secondary" display="block">
                  {t("server.uptime")}: {formatUptime(status.uptime)}
                </Typography>
              )}
              <Box sx={{ mt: 1, display: "flex", gap: 2 }}>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    {t("server.disk")} {status.disk?.used_pct?.toFixed(0) ?? "—"}%
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={status.disk?.used_pct ?? 0}
                    color={(status.disk?.used_pct ?? 0) > 90 ? "error" : "primary"}
                    sx={{ height: 4, borderRadius: 2 }}
                  />
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    {t("server.memory")} {status.memory?.used_pct?.toFixed(0) ?? "—"}%
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={status.memory?.used_pct ?? 0}
                    color={(status.memory?.used_pct ?? 0) > 90 ? "error" : "primary"}
                    sx={{ height: 4, borderRadius: 2 }}
                  />
                </Box>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    {t("server.cpu")} {status.cpu?.used_pct?.toFixed(0) ?? "—"}%
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={status.cpu?.used_pct ?? 0}
                    color={(status.cpu?.used_pct ?? 0) > 80 ? "error" : "primary"}
                    sx={{ height: 4, borderRadius: 2 }}
                  />
                </Box>
              </Box>
            </Box>
          )}

          {server.error && (
            <Typography variant="caption" color="error" sx={{ mt: 1, display: "block" }}>
              {server.error}
            </Typography>
          )}
        </CardContent>
      </CardActionArea>
    </Card>
  );
}
