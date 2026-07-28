import { memo, useCallback, useEffect, useMemo, useState } from "react";
import {
  Box, Typography, Chip, CircularProgress, Alert,
  Accordion, AccordionSummary, AccordionDetails,
  TextField, Button, Switch, FormControlLabel,
  Table, TableHead, TableRow, TableCell, TableBody, TableContainer,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useTranslation } from "react-i18next";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer, CartesianGrid,
} from "recharts";
import api from "../api/client";
import type { MetricPoint, VpnMetricPoint, AlertConfig, AlertEntry } from "../api/types";

const COLORS = ["#8884d8", "#82ca9d", "#ffc658", "#ff7300", "#00C49F", "#FF8042"];

type TimeRange = "24h" | "7d" | "30d";
const RANGE_HOURS: Record<TimeRange, number> = { "24h": 24, "7d": 168, "30d": 720 };

type Metric = "disk" | "memory" | "cpu";
type ChartRow = { time: number } & Record<string, number | null>;
type Series = { id: string; name: string; color: string };

/** Peak of the bucket a point summarises, kept beside its average. */
const peakKey = (seriesId: string) => `${seriesId}:max`;

/**
 * One row per timestamp, one column per server — the shape recharts wants.
 * Points arrive sorted by timestamp, and a Map preserves that order.
 */
function buildChartData<T extends { timestamp: number }>(
  points: T[],
  idField: keyof T,
  metric: Metric,
): ChartRow[] {
  const rows = new Map<number, ChartRow>();
  for (const p of points) {
    let row = rows.get(p.timestamp);
    if (!row) {
      row = { time: p.timestamp };
      rows.set(p.timestamp, row);
    }
    const sid = String(p[idField]);
    row[sid] = (p as Record<string, unknown>)[`${metric}_pct`] as number | null;
    const peak = (p as Record<string, unknown>)[`${metric}_max`];
    if (typeof peak === "number") row[peakKey(sid)] = peak;
  }
  return [...rows.values()];
}

function buildAll<T extends { timestamp: number }>(points: T[], idField: keyof T) {
  return {
    disk: buildChartData(points, idField, "disk"),
    memory: buildChartData(points, idField, "memory"),
    cpu: buildChartData(points, idField, "cpu"),
  };
}

type MetricChartProps = {
  title: string;
  data: ChartRow[];
  series: Series[];
  formatAxis: (ts: unknown) => string;
  formatLabel: (ts: unknown) => string;
  peakLabel: string;
};

/**
 * Memoised: without this every keystroke in the alert settings below
 * re-renders all six charts.
 */
const MetricChart = memo(function MetricChart({
  title, data, series, formatAxis, formatLabel, peakLabel,
}: MetricChartProps) {
  return (
    <Box sx={{ flex: 1, minWidth: { xs: "100%", sm: 300 }, minHeight: 260 }}>
      <Typography variant="subtitle2" sx={{ mb: 1 }}>{title}</Typography>
      <ResponsiveContainer width="100%" height={240} debounce={120}>
        <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#444" vertical={false} />
          <XAxis
            dataKey="time"
            tickFormatter={formatAxis}
            fontSize={11}
            stroke="#888"
            minTickGap={44}
            tickMargin={6}
          />
          <YAxis domain={[0, 100]} unit="%" fontSize={11} stroke="#888" width={40} />
          <Tooltip
            labelFormatter={formatLabel}
            isAnimationActive={false}
            contentStyle={{ backgroundColor: "#1e1e1e", border: "1px solid #555" }}
            formatter={(value, name, item) => {
              const row = item?.payload as ChartRow | undefined;
              const peak = row?.[peakKey(String(item?.dataKey))];
              const avg = typeof value === "number" ? value.toFixed(1) : String(value ?? "");
              const shown =
                typeof peak === "number" && typeof value === "number" && peak > value
                  ? `${avg}% (${peakLabel} ${peak}%)`
                  : `${avg}%`;
              return [shown, name];
            }}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {series.map((s) => (
            <Line
              key={s.id}
              dataKey={s.id}
              name={s.name}
              stroke={s.color}
              dot={false}
              activeDot={{ r: 3 }}
              strokeWidth={1.8}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </Box>
  );
});

export default function MonitoringTab() {
  const { t } = useTranslation();
  const [range, setRange] = useState<TimeRange>("24h");
  const [metrics, setMetrics] = useState<MetricPoint[]>([]);
  const [servers, setServers] = useState<Record<string, { name: string; display_name: string }>>({});
  const [metricsLoading, setMetricsLoading] = useState(true);

  const [vpnMetrics, setVpnMetrics] = useState<VpnMetricPoint[]>([]);
  const [vpnServers, setVpnServers] = useState<Record<string, { name: string; display_name: string }>>({});
  const [vpnMetricsLoading, setVpnMetricsLoading] = useState(true);

  const [alertConfig, setAlertConfig] = useState<AlertConfig | null>(null);
  const [configForm, setConfigForm] = useState<Partial<AlertConfig>>({});
  const [configSaving, setConfigSaving] = useState(false);
  const [configMsg, setConfigMsg] = useState("");
  const [testMsg, setTestMsg] = useState("");
  const [testSuccess, setTestSuccess] = useState(false);

  const [alerts, setAlerts] = useState<AlertEntry[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(false);

  const fetchMetrics = useCallback(async () => {
    setMetricsLoading(true);
    try {
      const { data } = await api.get(`/monitoring/metrics?hours=${RANGE_HOURS[range]}`);
      if (data.ok) {
        setMetrics(data.data.metrics || []);
        setServers(data.data.servers || {});
      }
    } catch { /* */ }
    setMetricsLoading(false);
  }, [range]);

  const fetchVpnMetrics = useCallback(async () => {
    setVpnMetricsLoading(true);
    try {
      const { data } = await api.get(`/monitoring/vpn-metrics?hours=${RANGE_HOURS[range]}`);
      if (data.ok) {
        setVpnMetrics(data.data.metrics || []);
        setVpnServers(data.data.servers || {});
      }
    } catch { /* */ }
    setVpnMetricsLoading(false);
  }, [range]);

  const fetchConfig = useCallback(async () => {
    try {
      const { data } = await api.get("/monitoring/config");
      if (data.ok) {
        setAlertConfig(data.data);
        setConfigForm(data.data);
      }
    } catch { /* */ }
  }, []);

  const fetchAlerts = useCallback(async () => {
    setAlertsLoading(true);
    try {
      const { data } = await api.get("/monitoring/alerts?limit=20");
      if (data.ok) setAlerts(data.data || []);
    } catch { /* */ }
    setAlertsLoading(false);
  }, []);

  useEffect(() => {
    fetchMetrics();
    fetchVpnMetrics();
    fetchConfig();
    fetchAlerts();
  }, [fetchMetrics, fetchVpnMetrics, fetchConfig, fetchAlerts]);

  const exitSeries = useMemo<Series[]>(
    () => Object.keys(servers).map((id, i) => ({
      id,
      name: servers[id]?.display_name || id,
      color: COLORS[i % COLORS.length],
    })),
    [servers],
  );
  const vpnSeries = useMemo<Series[]>(
    () => Object.keys(vpnServers).map((id, i) => ({
      id,
      name: vpnServers[id]?.display_name || id,
      color: COLORS[i % COLORS.length],
    })),
    [vpnServers],
  );

  const exitData = useMemo(() => buildAll(metrics, "server_id"), [metrics]);
  const vpnData = useMemo(() => buildAll(vpnMetrics, "vpn_server_id"), [vpnMetrics]);

  // The axis carries only what changes across the visible span; the full
  // date and time stay in the tooltip.
  const formatAxis = useCallback((ts: unknown) => {
    if (typeof ts !== "number") return String(ts);
    const d = new Date(ts * 1000);
    if (range === "24h") return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  }, [range]);

  const formatLabel = useCallback((ts: unknown) => {
    if (typeof ts !== "number") return String(ts);
    const d = new Date(ts * 1000);
    return d.toLocaleDateString([], { month: "short", day: "numeric" }) + " " +
      d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }, []);

  const peakLabel = t("monitoring.peak");

  const handleSaveConfig = async () => {
    setConfigSaving(true);
    setConfigMsg("");
    try {
      const body: Record<string, unknown> = {};
      if (configForm.enabled !== undefined) body.enabled = !!configForm.enabled;
      if (configForm.telegram_bot_token !== undefined &&
          configForm.telegram_bot_token !== alertConfig?.telegram_bot_token) {
        body.telegram_bot_token = configForm.telegram_bot_token;
      }
      if (configForm.telegram_chat_id !== undefined) body.telegram_chat_id = configForm.telegram_chat_id;
      if (configForm.disk_threshold !== undefined) body.disk_threshold = configForm.disk_threshold;
      if (configForm.memory_threshold !== undefined) body.memory_threshold = configForm.memory_threshold;
      if (configForm.cpu_threshold !== undefined) body.cpu_threshold = configForm.cpu_threshold;
      if (configForm.offline_minutes !== undefined) body.offline_minutes = configForm.offline_minutes;

      const { data } = await api.put("/monitoring/config", body);
      if (data.ok) {
        setConfigMsg(t("monitoring.configSaved"));
        fetchConfig();
        setTimeout(() => setConfigMsg(""), 3000);
      }
    } catch { /* */ }
    setConfigSaving(false);
  };

  const handleTestAlert = async () => {
    setTestMsg("");
    try {
      const { data } = await api.post("/monitoring/test-alert");
      setTestSuccess(!!data.ok);
      setTestMsg(data.ok ? t("monitoring.testAlertSent") : (data.error || t("monitoring.testAlertFailed")));
    } catch {
      setTestSuccess(false);
      setTestMsg(t("monitoring.testAlertFailed"));
    }
    setTimeout(() => setTestMsg(""), 5000);
  };

  return (
    <Box>
      {/* Time range selector */}
      <Box sx={{ display: "flex", gap: 1, mb: 3 }}>
        {(["24h", "7d", "30d"] as TimeRange[]).map((r) => (
          <Chip
            key={r}
            label={t(`monitoring.${r === "24h" ? "last24h" : r === "7d" ? "last7d" : "last30d"}`)}
            onClick={() => setRange(r)}
            color={range === r ? "primary" : "default"}
            variant={range === r ? "filled" : "outlined"}
          />
        ))}
      </Box>

      {/* Exit Server Charts */}
      <Typography variant="h6" sx={{ mb: 2 }}>{t("monitoring.exitServers")}</Typography>
      {metricsLoading ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
          <CircularProgress />
        </Box>
      ) : metrics.length === 0 ? (
        <Alert severity="info" sx={{ mb: 3 }}>{t("monitoring.noData")}</Alert>
      ) : (
        <Box sx={{ display: "flex", gap: 2, mb: 3, flexWrap: "wrap" }}>
          {[
            { label: t("monitoring.diskUsage"), data: exitData.disk },
            { label: t("monitoring.memoryUsage"), data: exitData.memory },
            { label: t("monitoring.cpuUsage"), data: exitData.cpu },
          ].map((chart) => (
            <MetricChart
              key={chart.label}
              title={chart.label}
              data={chart.data}
              series={exitSeries}
              formatAxis={formatAxis}
              formatLabel={formatLabel}
              peakLabel={peakLabel}
            />
          ))}
        </Box>
      )}

      {/* VPN Server Charts */}
      <Typography variant="h6" sx={{ mb: 2, mt: 2 }}>{t("monitoring.vpnServers")}</Typography>
      {vpnMetricsLoading ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
          <CircularProgress />
        </Box>
      ) : vpnMetrics.length === 0 ? (
        <Alert severity="info" sx={{ mb: 3 }}>{t("monitoring.noVpnData")}</Alert>
      ) : (
        <Box sx={{ display: "flex", gap: 2, mb: 3, flexWrap: "wrap" }}>
          {[
            { label: t("monitoring.diskUsage"), data: vpnData.disk },
            { label: t("monitoring.memoryUsage"), data: vpnData.memory },
            { label: t("monitoring.cpuUsage"), data: vpnData.cpu },
          ].map((chart) => (
            <MetricChart
              key={chart.label}
              title={chart.label}
              data={chart.data}
              series={vpnSeries}
              formatAxis={formatAxis}
              formatLabel={formatLabel}
              peakLabel={peakLabel}
            />
          ))}
        </Box>
      )}

      {/* Alert Settings */}
      <Accordion sx={{ mb: 3 }}>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="subtitle2">{t("monitoring.alertSettings")}</Typography>
        </AccordionSummary>
        <AccordionDetails>
          {alertConfig && (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 2, maxWidth: 500 }}>
              <FormControlLabel
                control={
                  <Switch
                    checked={!!configForm.enabled}
                    onChange={(e) => setConfigForm({ ...configForm, enabled: e.target.checked ? 1 : 0 })}
                  />
                }
                label={t("monitoring.alertsEnabled")}
              />
              <TextField
                label={t("monitoring.telegramBotToken")}
                size="small"
                type="password"
                value={configForm.telegram_bot_token || ""}
                onChange={(e) => setConfigForm({ ...configForm, telegram_bot_token: e.target.value })}
              />
              <TextField
                label={t("monitoring.telegramChatId")}
                size="small"
                value={configForm.telegram_chat_id || ""}
                onChange={(e) => setConfigForm({ ...configForm, telegram_chat_id: e.target.value })}
              />
              <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap" }}>
                <TextField
                  label={t("monitoring.diskThreshold")}
                  size="small"
                  type="number"
                  value={configForm.disk_threshold ?? 90}
                  onChange={(e) => setConfigForm({ ...configForm, disk_threshold: parseFloat(e.target.value) })}
                  slotProps={{ htmlInput: { min: 1, max: 100 } }}
                  sx={{ width: 130 }}
                />
                <TextField
                  label={t("monitoring.memoryThreshold")}
                  size="small"
                  type="number"
                  value={configForm.memory_threshold ?? 90}
                  onChange={(e) => setConfigForm({ ...configForm, memory_threshold: parseFloat(e.target.value) })}
                  slotProps={{ htmlInput: { min: 1, max: 100 } }}
                  sx={{ width: 130 }}
                />
                <TextField
                  label={t("monitoring.cpuThreshold")}
                  size="small"
                  type="number"
                  value={configForm.cpu_threshold ?? 80}
                  onChange={(e) => setConfigForm({ ...configForm, cpu_threshold: parseFloat(e.target.value) })}
                  slotProps={{ htmlInput: { min: 1, max: 100 } }}
                  sx={{ width: 130 }}
                />
                <TextField
                  label={t("monitoring.offlineMinutes")}
                  size="small"
                  type="number"
                  value={configForm.offline_minutes ?? 5}
                  onChange={(e) => setConfigForm({ ...configForm, offline_minutes: parseInt(e.target.value) })}
                  slotProps={{ htmlInput: { min: 1, max: 60 } }}
                  sx={{ width: 130 }}
                />
              </Box>
              <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
                <Button variant="contained" size="small" onClick={handleSaveConfig} disabled={configSaving}>
                  {t("monitoring.saveConfig")}
                </Button>
                <Button variant="outlined" size="small" onClick={handleTestAlert}>
                  {t("monitoring.testAlert")}
                </Button>
                {configMsg && (
                  <Typography variant="caption" color="success.main">{configMsg}</Typography>
                )}
                {testMsg && (
                  <Typography variant="caption" color={testSuccess ? "success.main" : "error"}>
                    {testMsg}
                  </Typography>
                )}
              </Box>
            </Box>
          )}
        </AccordionDetails>
      </Accordion>

      {/* Alert History */}
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="subtitle2">{t("monitoring.alertHistory")}</Typography>
        </AccordionSummary>
        <AccordionDetails>
          {alertsLoading ? (
            <CircularProgress size={20} />
          ) : alerts.length === 0 ? (
            <Typography variant="body2" color="text.secondary">{t("monitoring.noAlerts")}</Typography>
          ) : (
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ whiteSpace: "nowrap" }}>{t("monitoring.alertTime")}</TableCell>
                    <TableCell sx={{ whiteSpace: "nowrap" }}>{t("monitoring.alertServer")}</TableCell>
                    <TableCell>{t("monitoring.alertType")}</TableCell>
                    <TableCell>{t("monitoring.alertMessage")}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {alerts.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>
                        <Typography variant="caption">
                          {new Date(a.sent_at * 1000).toLocaleString()}
                        </Typography>
                      </TableCell>
                      <TableCell sx={{ whiteSpace: "nowrap" }}>{a.server_name || "—"}</TableCell>
                      <TableCell>
                        <Chip
                          label={a.alert_type}
                          size="small"
                          color={
                            a.alert_type.endsWith("_recovered")
                              ? "success"
                              : a.alert_type === "offline"
                                ? "error"
                                : "warning"
                          }
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" sx={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis" }}>
                          {a.message}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </AccordionDetails>
      </Accordion>
    </Box>
  );
}
