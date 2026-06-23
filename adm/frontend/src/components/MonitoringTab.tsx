import { useCallback, useEffect, useState } from "react";
import {
  Box, Typography, Chip, CircularProgress, Alert,
  Accordion, AccordionSummary, AccordionDetails,
  TextField, Button, Switch, FormControlLabel,
  Table, TableHead, TableRow, TableCell, TableBody,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useTranslation } from "react-i18next";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer, CartesianGrid,
} from "recharts";
import api from "../api/client";
import type { MetricPoint, AlertConfig, AlertEntry } from "../api/types";

const COLORS = ["#8884d8", "#82ca9d", "#ffc658", "#ff7300", "#00C49F", "#FF8042"];

type TimeRange = "24h" | "7d" | "30d";
const RANGE_HOURS: Record<TimeRange, number> = { "24h": 24, "7d": 168, "30d": 720 };

export default function MonitoringTab() {
  const { t } = useTranslation();
  const [range, setRange] = useState<TimeRange>("24h");
  const [metrics, setMetrics] = useState<MetricPoint[]>([]);
  const [servers, setServers] = useState<Record<string, { name: string; display_name: string }>>({});
  const [metricsLoading, setMetricsLoading] = useState(true);

  const [alertConfig, setAlertConfig] = useState<AlertConfig | null>(null);
  const [configForm, setConfigForm] = useState<Partial<AlertConfig>>({});
  const [configSaving, setConfigSaving] = useState(false);
  const [configMsg, setConfigMsg] = useState("");
  const [testMsg, setTestMsg] = useState("");

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
    fetchConfig();
    fetchAlerts();
  }, [fetchMetrics, fetchConfig, fetchAlerts]);

  // Build chart data: group metrics by timestamp, one entry per timestamp
  const serverIds = Object.keys(servers);

  const buildChartData = (field: "disk_pct" | "memory_pct" | "cpu_pct") => {
    const grouped: Record<number, Record<string, number | null>> = {};
    for (const m of metrics) {
      const ts = m.timestamp;
      if (!grouped[ts]) grouped[ts] = {};
      grouped[ts][String(m.server_id)] = m[field];
    }
    return Object.entries(grouped)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([ts, vals]) => ({
        time: Number(ts),
        ...vals,
      }));
  };

  const diskData = buildChartData("disk_pct");
  const memoryData = buildChartData("memory_pct");
  const cpuData = buildChartData("cpu_pct");

  const formatTime = (ts: unknown) => {
    if (typeof ts !== "number") return String(ts);
    const d = new Date(ts * 1000);
    if (range === "24h") return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    return d.toLocaleDateString([], { month: "short", day: "numeric" }) + " " +
      d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

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
      setTestMsg(data.ok ? t("monitoring.testAlertSent") : (data.error || t("monitoring.testAlertFailed")));
    } catch {
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

      {/* Charts */}
      {metricsLoading ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
          <CircularProgress />
        </Box>
      ) : metrics.length === 0 ? (
        <Alert severity="info" sx={{ mb: 3 }}>{t("monitoring.noData")}</Alert>
      ) : (
        <Box sx={{ display: "flex", gap: 2, mb: 3, flexWrap: "wrap" }}>
          {/* Disk chart */}
          <Box sx={{ flex: 1, minWidth: 350, minHeight: 250 }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>{t("monitoring.diskUsage")}</Typography>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={diskData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                <XAxis dataKey="time" tickFormatter={formatTime} fontSize={11} stroke="#888" />
                <YAxis domain={[0, 100]} unit="%" fontSize={11} stroke="#888" />
                <Tooltip
                  labelFormatter={formatTime}
                  contentStyle={{ backgroundColor: "#1e1e1e", border: "1px solid #555" }}
                />
                <Legend />
                {serverIds.map((sid, i) => (
                  <Line
                    key={sid}
                    dataKey={sid}
                    name={servers[sid]?.display_name || sid}
                    stroke={COLORS[i % COLORS.length]}
                    dot={false}
                    strokeWidth={2}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </Box>

          {/* Memory chart */}
          <Box sx={{ flex: 1, minWidth: 350, minHeight: 250 }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>{t("monitoring.memoryUsage")}</Typography>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={memoryData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                <XAxis dataKey="time" tickFormatter={formatTime} fontSize={11} stroke="#888" />
                <YAxis domain={[0, 100]} unit="%" fontSize={11} stroke="#888" />
                <Tooltip
                  labelFormatter={formatTime}
                  contentStyle={{ backgroundColor: "#1e1e1e", border: "1px solid #555" }}
                />
                <Legend />
                {serverIds.map((sid, i) => (
                  <Line
                    key={sid}
                    dataKey={sid}
                    name={servers[sid]?.display_name || sid}
                    stroke={COLORS[i % COLORS.length]}
                    dot={false}
                    strokeWidth={2}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </Box>

          {/* CPU chart */}
          <Box sx={{ flex: 1, minWidth: 350, minHeight: 250 }}>
            <Typography variant="subtitle2" sx={{ mb: 1 }}>{t("monitoring.cpuUsage")}</Typography>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={cpuData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#444" />
                <XAxis dataKey="time" tickFormatter={formatTime} fontSize={11} stroke="#888" />
                <YAxis domain={[0, 100]} unit="%" fontSize={11} stroke="#888" />
                <Tooltip
                  labelFormatter={formatTime}
                  contentStyle={{ backgroundColor: "#1e1e1e", border: "1px solid #555" }}
                />
                <Legend />
                {serverIds.map((sid, i) => (
                  <Line
                    key={sid}
                    dataKey={sid}
                    name={servers[sid]?.display_name || sid}
                    stroke={COLORS[i % COLORS.length]}
                    dot={false}
                    strokeWidth={2}
                    connectNulls
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </Box>
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
              <Box sx={{ display: "flex", gap: 2 }}>
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
                  <Typography variant="caption" color={testMsg.includes("sent") || testMsg.includes("gönderildi") || testMsg.includes("отправлено") ? "success.main" : "error"}>
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
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t("monitoring.alertTime")}</TableCell>
                  <TableCell>{t("monitoring.alertServer")}</TableCell>
                  <TableCell>{t("monitoring.alertType")}</TableCell>
                  <TableCell>{t("monitoring.alertMessage")}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {alerts.map((a) => (
                  <TableRow key={a.id}>
                    <TableCell>
                      <Typography variant="caption">
                        {new Date(a.sent_at * 1000).toLocaleString()}
                      </Typography>
                    </TableCell>
                    <TableCell>{a.server_name || "—"}</TableCell>
                    <TableCell>
                      <Chip
                        label={a.alert_type}
                        size="small"
                        color={a.alert_type === "offline" ? "error" : "warning"}
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
          )}
        </AccordionDetails>
      </Accordion>
    </Box>
  );
}
