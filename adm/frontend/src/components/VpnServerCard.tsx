import {
  Card, CardActionArea, CardContent, Typography, Box, Chip, Tooltip,
  IconButton,
} from "@mui/material";
import CircleIcon from "@mui/icons-material/Circle";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import { useTranslation } from "react-i18next";
import type { VpnServer, ProximaSlotSummary, DomainCheckSummary } from "../api/types";

interface Props {
  server: VpnServer;
  onClick: () => void;
}

/** Sort slot entries by numeric slot ID */
function sortedSlots(slots: Record<string, ProximaSlotSummary>): [string, ProximaSlotSummary][] {
  return Object.entries(slots).sort(([a], [b]) => {
    const aNum = parseInt(a.replace(/\D/g, ""), 10);
    const bNum = parseInt(b.replace(/\D/g, ""), 10);
    if (!isNaN(aNum) && !isNaN(bNum)) return aNum - bNum;
    return a.localeCompare(b);
  });
}

function slotDotColor(ipOk: boolean | null | undefined): string {
  if (ipOk === true) return "#4caf50";
  if (ipOk === false) return "#f44336";
  return "#616161";
}

function domainDotColor(check: DomainCheckSummary): string {
  if (check.ok) return "#4caf50";
  if (check.http_status) return "#ff9800";
  return "#f44336";
}

/** Short domain label: web.whatsapp.com → whatsapp */
function shortDomain(domain: string): string {
  const parts = domain.replace(/^(www|web|api|m)\./, "").split(".");
  return parts[0] || domain;
}

export default function VpnServerCard({ server, onClick }: Props) {
  const { t } = useTranslation();
  const status = server.proxima_status;
  const isOnline = server.online;

  // Count healthy slots (only checked ones)
  let healthyCount = 0;
  let totalSlots = 0;
  if (status?.slots) {
    for (const slot of Object.values(status.slots)) {
      if (slot.health?.last_ip_ok === null || slot.health?.last_ip_ok === undefined) continue;
      totalSlots++;
      if (slot.health.last_ip_ok === true) healthyCount++;
    }
  }

  // Domain checks — sorted alphabetically for consistent display
  const domainEntries = server.domain_checks
    ? Object.entries(server.domain_checks).sort(([a], [b]) => a.localeCompare(b))
    : [];

  const linkUrl = server.public_url || server.url;

  return (
    <Card variant="outlined">
      <CardActionArea onClick={onClick}>
        <CardContent>
          <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 1 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Typography variant="subtitle1" fontWeight={700}>
                {server.display_name}
              </Typography>
              {linkUrl && (
                <Tooltip title={linkUrl} placement="top">
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      window.open(linkUrl, "_blank", "noopener");
                    }}
                    sx={{ p: 0.25 }}
                  >
                    <OpenInNewIcon sx={{ fontSize: 14, color: "text.secondary" }} />
                  </IconButton>
                </Tooltip>
              )}
            </Box>
            <Chip
              icon={<CircleIcon sx={{ fontSize: 10, color: isOnline ? "#4caf50" : undefined }} />}
              label={isOnline ? t("vpnServer.online") : t("vpnServer.offline")}
              size="small"
              variant="outlined"
              color={isOnline ? "success" : "default"}
            />
          </Box>

          {/* Domain health dots */}
          {domainEntries.length > 0 && (
            <Box sx={{ display: "flex", gap: 0.5, alignItems: "center", flexWrap: "wrap", mb: 1 }}>
              {domainEntries.map(([domain, check]) => (
                <Tooltip
                  key={domain}
                  title={`${domain}${check.http_status ? ` (${check.http_status})` : check.ok ? "" : " — ERR"}`}
                  placement="top"
                  arrow
                >
                  <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
                    <Box
                      sx={{
                        width: 10,
                        height: 10,
                        borderRadius: "50%",
                        bgcolor: domainDotColor(check),
                        border: "1px solid rgba(255,255,255,0.15)",
                        flexShrink: 0,
                      }}
                    />
                    <Typography
                      variant="caption"
                      sx={{
                        fontSize: "0.5rem",
                        color: "text.disabled",
                        lineHeight: 1,
                        mt: 0.15,
                        maxWidth: 28,
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {shortDomain(domain)}
                    </Typography>
                  </Box>
                </Tooltip>
              ))}
            </Box>
          )}

          {status && (
            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap", mb: 1, alignItems: "center" }}>
              {/* Slot health chip */}
              {totalSlots > 0 && (
                <Chip
                  label={t("vpnServer.slotsHealthy", { healthy: healthyCount, total: totalSlots })}
                  size="small"
                  color={healthyCount === totalSlots ? "success" : healthyCount > 0 ? "warning" : "error"}
                  variant="outlined"
                />
              )}
              {/* Slot dots (compact) */}
              {status.slots && Object.keys(status.slots).length > 0 && (
                <Box sx={{ display: "flex", gap: 0.3, alignItems: "center" }}>
                  {sortedSlots(status.slots).map(([id, slot]) => (
                    <Tooltip key={id} title={`${slot.label}${slot.health?.last_ip ? ` — ${slot.health.last_ip}` : ""}`} placement="top">
                      <Box
                        sx={{
                          width: 8,
                          height: 8,
                          borderRadius: "50%",
                          bgcolor: slotDotColor(slot.health?.last_ip_ok),
                          border: slot.health?.bypass_active ? "1.5px solid #ff9800" : "none",
                          flexShrink: 0,
                        }}
                      />
                    </Tooltip>
                  ))}
                </Box>
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
