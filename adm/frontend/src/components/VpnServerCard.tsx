import {
  Card, CardActionArea, CardContent, Typography, Box, Chip, Tooltip,
  IconButton, LinearProgress,
} from "@mui/material";
import CircleIcon from "@mui/icons-material/Circle";
import LaunchIcon from "@mui/icons-material/Launch";
import EditIcon from "@mui/icons-material/Edit";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import { useTranslation } from "react-i18next";
import type { VpnServer, ProximaSlotSummary, ServiceStatus } from "../api/types";

// ── Brand SVG Icons (from ProximaVPN ServiceDots) ────────────────

const IconWhatsApp = () => (
  <svg viewBox="0 0 24 24" width="14" height="14">
    <path fill="currentColor" d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
  </svg>
);

const IconTelegram = () => (
  <svg viewBox="0 0 24 24" width="14" height="14">
    <path fill="currentColor" d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
  </svg>
);

const IconChatGPT = () => (
  <svg viewBox="0 0 24 24" width="14" height="14">
    <path fill="currentColor" d="M22.424 9.82a6.14 6.14 0 0 0-.522-4.91 6.17 6.17 0 0 0-6.6-2.9A6.15 6.15 0 0 0 10.635.3a6.23 6.23 0 0 0-3.177.129A6.15 6.15 0 0 0 4.62 2.78a6.15 6.15 0 0 0-2.345 1.018A6 6 0 0 0 .83 7.08a5.99 5.99 0 0 0 .754 7.097 6.14 6.14 0 0 0 .519 4.91 6.17 6.17 0 0 0 6.603 2.9 6.15 6.15 0 0 0 2.066 1.492c.789.347 1.642.525 2.505.519 2.67.003 5.037-1.698 5.852-4.206a6.15 6.15 0 0 0 2.345-1.02 6 6 0 0 0 1.71-1.879 5.99 5.99 0 0 0-.76-7.074m-9.145 12.61a4.575 4.575 0 0 1-2.918-1.042l.144-.081 4.845-2.757a.795.795 0 0 0 .398-.683v-6.735l2.05 1.167a.045.045 0 0 1 .036.053v5.583c-.005 2.48-2.042 4.488-5.555 4.494m-9.795-4.125a4.425 4.425 0 0 1-.54-3.015l.142.086 4.843 2.76a.795.795 0 0 0 .791 0l5.924-3.37v2.333a.075.075 0 0 1-.033.062L9.71 19.95c-2.182 1.24-4.967.503-6.226-1.646m-1.275-10.41A4.53 4.53 0 0 1 4.605 5.922v5.678a.765.765 0 0 0 .393.677l5.895 3.356-2.05 1.169a.075.075 0 0 1-.071 0L3.878 14.013a4.47 4.47 0 0 1-1.67-6.14zm16.824 3.856L13.11 8.381l2.043-1.164a.075.075 0 0 1 .072 0l4.897 2.79a4.5 4.5 0 0 1 1.76 1.81 4.44 4.44 0 0 1-.406 4.8 4.575 4.575 0 0 1-2.04 1.496V12.42a.78.78 0 0 0-.414-.668m2.04-3.022-.146-.086-3.839-2.783a.795.795 0 0 0-.795 0L9.374 9.23V6.897a.06.06 0 0 1 .028-.06L14.3 4.05a4.605 4.605 0 0 1 4.886.209c.71.487 1.264 1.167 1.599 1.954.334.789.434 1.655.286 2.496zM8.255 12.863l-2.05-1.17a.075.075 0 0 1-.039-.056V6.074c0-.855.249-1.69.714-2.41a4.545 4.545 0 0 1 1.913-1.658 4.62 4.62 0 0 1 4.85.615l-.143.081-4.845 2.757a.795.795 0 0 0-.398.683zm1.113-2.366L12 8.998l2.643 1.5v3l-2.633 1.5-2.643-1.5z"/>
  </svg>
);

const IconClaude = () => (
  <svg viewBox="0 0 24 24" width="14" height="14">
    <path fill="currentColor" d="m4.7144 15.9555 4.7174-2.6471.079-.2307-.079-.1275h-.2307l-.7893-.0486-2.6956-.0729-2.3375-.0971-2.2646-.1214-.5707-.1215-.5343-.7042.0546-.3522.4797-.3218.686.0608 1.5179.1032 2.2767.1578 1.6514.0972 2.4468.255h.3886l.0546-.1579-.1336-.0971-.1032-.0972L6.973 9.8356l-2.55-1.6879-1.3356-.9714-.7225-.4918-.3643-.4614-.1578-1.0078.6557-.7225.8803.0607.2246.0607.8925.686 1.9064 1.4754 2.4893 1.8336.3643.3035.1457-.1032.0182-.0728-.164-.2733-1.3539-2.4467-1.445-2.4893-.6435-1.032-.17-.6194c-.0607-.255-.1032-.4674-.1032-.7285L6.287.1335 6.6997 0l.9957.1336.419.3642.6192 1.4147 1.0018 2.2282 1.5543 3.0296.4553.8985.2429.8318.091.255h.1579v-.1457l.1275-1.706.2368-2.0947.2307-2.6957.0789-.7589.3764-.9107.7468-.4918.5828.2793.4797.686-.0668.4433-.2853 1.8517-.5586 2.9021-.3643 1.9429h.2125l.2429-.2429.9835-1.3053 1.6514-2.0643.7286-.8196.85-.9046.5464-.4311h1.0321l.759 1.1293-.34 1.1657-1.0625 1.3478-.8804 1.1414-1.2628 1.7-.7893 1.36.0729.1093.1882-.0183 2.8535-.607 1.5421-.2794 1.8396-.3157.8318.3886.091.3946-.3278.8075-1.967.4857-2.3072.4614-3.4364.8136-.0425.0304.0486.0607 1.5482.1457.6618.0364h1.621l3.0175.2247.7892.522.4736.6376-.079.4857-1.2142.6193-1.6393-.3886-3.825-.9107-1.3113-.3279h-.1822v.1093l1.0929 1.0686 2.0035 1.8092 2.5075 2.3314.1275.5768-.3218.4554-.34-.0486-2.2039-1.6575-.85-.7468-1.9246-1.621h-.1275v.17l.4432.6496 2.3436 3.5214.1214 1.0807-.17.3521-.6071.2125-.6679-.1214-1.3721-1.9246L14.38 17.959l-1.1414-1.9428-.1397.079-.674 7.2552-.3156.3703-.7286.2793-.6071-.4614-.3218-.7468.3218-1.4753.3886-1.9246.3157-1.53.2853-1.9004.17-.6314-.0121-.0425-.1397.0182-1.4328 1.9672-2.1796 2.9446-1.7243 1.8456-.4128.164-.7164-.3704.0667-.6618.4008-.5889 2.386-3.0357 1.4389-1.882.929-1.0868-.0062-.1579h-.0546l-6.3385 4.1164-1.1293.1457-.4857-.4554.0608-.7467.2307-.2429 1.9064-1.3114Z"/>
  </svg>
);

const IconGemini = () => (
  <svg viewBox="0 0 24 24" width="14" height="14">
    <path fill="currentColor" d="M11.04 19.32Q12 21.51 12 24q0-2.49.93-4.68.96-2.19 2.58-3.81t3.81-2.55Q21.51 12 24 12q-2.49 0-4.68-.93a12.3 12.3 0 0 1-3.81-2.58 12.3 12.3 0 0 1-2.58-3.81Q12 2.49 12 0q0 2.49-.96 4.68-.93 2.19-2.55 3.81a12.3 12.3 0 0 1-3.81 2.58Q2.49 12 0 12q2.49 0 4.68.96 2.19.93 3.81 2.55t2.55 3.81"/>
  </svg>
);

const IconYouTube = () => (
  <svg viewBox="0 0 24 24" width="14" height="14">
    <path fill="currentColor" d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
  </svg>
);

// ── Service definitions ──────────────────────────────────────────

interface ServiceDef {
  id: string;
  label: string;
  icon: React.FC;
  brandColor: string;
}

const SERVICES: ServiceDef[] = [
  { id: "whatsapp", label: "WhatsApp", icon: IconWhatsApp, brandColor: "#25D366" },
  { id: "telegram", label: "Telegram", icon: IconTelegram, brandColor: "#26A5E4" },
  { id: "chatgpt", label: "ChatGPT", icon: IconChatGPT, brandColor: "#10A37F" },
  { id: "claude", label: "Claude", icon: IconClaude, brandColor: "#D97757" },
  { id: "gemini", label: "Gemini", icon: IconGemini, brandColor: "#8E75B2" },
  { id: "youtube", label: "YouTube", icon: IconYouTube, brandColor: "#FF0000" },
];

// ── Card helpers ─────────────────────────────────────────────────

interface Props {
  server: VpnServer;
  onClick: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

function latencyColor(ms: number): string {
  if (ms < 500) return "#4caf50";
  if (ms <= 2000) return "#ff9800";
  return "#f44336";
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

export default function VpnServerCard({ server, onClick, onEdit, onDelete }: Props) {
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

  const linkUrl = server.public_url || server.url;
  const connectivity = server.connectivity;

  // Build a lookup map from connectivity array for O(1) access
  const connectivityMap = new Map<string, ServiceStatus>();
  if (connectivity) {
    for (const svc of connectivity) {
      connectivityMap.set(svc.id, svc);
    }
  }

  return (
    <Card variant="outlined">
      <CardActionArea onClick={onClick}>
        <CardContent>
          <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 1 }}>
            <Typography variant="subtitle1" fontWeight={700}>
              {server.display_name}
            </Typography>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.25 }}>
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
                    <LaunchIcon sx={{ fontSize: 16 }} />
                  </IconButton>
                </Tooltip>
              )}
              <Tooltip title={t("vpnServer.edit")} placement="top">
                <IconButton
                  size="small"
                  onClick={(e) => { e.stopPropagation(); onEdit(); }}
                  sx={{ p: 0.25 }}
                >
                  <EditIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Tooltip>
              <Tooltip title={t("vpnServer.delete")} placement="top">
                <IconButton
                  size="small"
                  onClick={(e) => { e.stopPropagation(); onDelete(); }}
                  sx={{ p: 0.25 }}
                >
                  <DeleteOutlineIcon sx={{ fontSize: 16, color: "error.main" }} />
                </IconButton>
              </Tooltip>
              <Chip
                icon={<CircleIcon sx={{ fontSize: 10, color: isOnline ? "#4caf50" : undefined }} />}
                label={isOnline ? t("vpnServer.online") : t("vpnServer.offline")}
                size="small"
                variant="outlined"
                color={isOnline ? "success" : "default"}
                sx={{ ml: 0.5 }}
              />
            </Box>
          </Box>

          {/* Service connectivity icons with latency */}
          {connectivityMap.size > 0 && (
            <Box sx={{ display: "flex", gap: 0.75, mb: 1 }}>
              {SERVICES.map((svc) => {
                const st = connectivityMap.get(svc.id);
                if (!st) return null;
                const Icon = svc.icon;
                const isAccessible = st.accessible;
                const borderColor = isAccessible ? "#4caf50" : "#f44336";
                const tooltipText = isAccessible
                  ? `${svc.label}: OK${st.latency_ms ? ` (${st.latency_ms}ms)` : ""}`
                  : `${svc.label}: ${st.error || "Blocked"}`;
                return (
                  <Tooltip key={svc.id} title={tooltipText} placement="top" arrow>
                    <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0.25 }}>
                      <Box
                        sx={{
                          width: 26,
                          height: 26,
                          borderRadius: "50%",
                          border: `2px solid ${borderColor}`,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          bgcolor: !isAccessible ? "#f44336" : "transparent",
                          color: !isAccessible ? "#fff" : svc.brandColor,
                        }}
                      >
                        <Icon />
                      </Box>
                      {st.latency_ms != null && (
                        <Typography
                          variant="caption"
                          sx={{
                            fontFamily: "monospace",
                            fontSize: "0.55rem",
                            fontWeight: 600,
                            color: latencyColor(st.latency_ms),
                            lineHeight: 1,
                          }}
                        >
                          {st.latency_ms}ms
                        </Typography>
                      )}
                    </Box>
                  </Tooltip>
                );
              })}
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
              {/* Slot dots (compact) — only show checked slots */}
              {status.slots && Object.keys(status.slots).length > 0 && (
                <Box sx={{ display: "flex", gap: 0.3, alignItems: "center" }}>
                  {sortedSlots(status.slots)
                    .filter(([, slot]) => slot.health?.last_ip_ok !== null && slot.health?.last_ip_ok !== undefined)
                    .map(([id, slot]) => (
                    <Tooltip key={id} title={`${slot.active || slot.label}${slot.health?.last_ip ? ` — ${slot.health.last_ip}` : ""}`} placement="top">
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

          {/* System metrics bars */}
          {status?.system && (
            <Box sx={{ display: "flex", gap: 2, mt: 1 }}>
              <Box sx={{ flex: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  {t("server.disk")} {status.system.disk?.used_pct?.toFixed(0) ?? "—"}%
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={status.system.disk?.used_pct ?? 0}
                  color={(status.system.disk?.used_pct ?? 0) > 90 ? "error" : "primary"}
                  sx={{ height: 4, borderRadius: 2 }}
                />
              </Box>
              <Box sx={{ flex: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  {t("server.memory")} {status.system.memory?.used_pct?.toFixed(0) ?? "—"}%
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={status.system.memory?.used_pct ?? 0}
                  color={(status.system.memory?.used_pct ?? 0) > 90 ? "error" : "primary"}
                  sx={{ height: 4, borderRadius: 2 }}
                />
              </Box>
              <Box sx={{ flex: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  {t("server.cpu")} {status.system.cpu?.used_pct?.toFixed(0) ?? "—"}%
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={status.system.cpu?.used_pct ?? 0}
                  color={(status.system.cpu?.used_pct ?? 0) > 80 ? "error" : "primary"}
                  sx={{ height: 4, borderRadius: 2 }}
                />
              </Box>
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
