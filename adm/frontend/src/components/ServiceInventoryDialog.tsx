import { useEffect, useState } from "react";
import {
  Alert, Box, Chip, CircularProgress, Dialog, DialogContent, DialogTitle,
  Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import api from "../api/client";

interface ServiceRow {
  name: string;
  port: number;
  proto: string;
  exposure: "public" | "lan" | "management" | "internal" | "local" | "unknown";
  detail: string;
  listening: boolean | null;
  process: string;
  expected: boolean;
}

interface Inventory {
  server_ip: string;
  deployment: string;
  vpn_endpoint: string;
  management_address: string;
  services: ServiceRow[];
  containers: { name: string; status: string; image: string }[];
  observed: boolean;
}

interface Props {
  open: boolean;
  serverId: number | null;
  serverName: string;
  onClose: () => void;
}

const EXPOSURE_COLOR: Record<string, "error" | "warning" | "info" | "default"> = {
  public: "error",       // reachable from the internet — the one to read first
  lan: "warning",
  management: "info",
  internal: "default",
  local: "default",
  unknown: "warning",
};

export default function ServiceInventoryDialog(
  { open, serverId, serverName, onClose }: Props,
) {
  const { t } = useTranslation();
  const [data, setData] = useState<Inventory | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !serverId) return;
    setLoading(true);
    setError("");
    setData(null);
    api.get(`/vpn-servers/${serverId}/services`)
      .then(({ data: res }) => {
        if (res.ok) setData(res.data);
        else setError(res.error);
      })
      .catch(() => setError(t("services.unreachable")))
      .finally(() => setLoading(false));
  }, [open, serverId, t]);

  const missing = data?.services.filter((s) => s.listening === false) ?? [];
  const unexpected = data?.services.filter((s) => !s.expected) ?? [];

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{t("services.title", { name: serverName })}</DialogTitle>
      <DialogContent dividers>
        {loading && (
          <Box sx={{ display: "flex", justifyContent: "center", p: 3 }}>
            <CircularProgress size={28} />
          </Box>
        )}

        {error && <Alert severity="error">{error}</Alert>}

        {data && (
          <>
            <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1, mb: 2 }}>
              <Chip size="small" variant="outlined"
                    label={t("services.lanAddress", { value: data.server_ip || "—" })} />
              <Chip size="small" variant="outlined"
                    label={t("services.managementAddress",
                             { value: data.management_address || "—" })} />
              <Chip size="small" variant="outlined"
                    label={t("services.vpnEndpoint", { value: data.vpn_endpoint || "—" })} />
            </Box>

            {/* Not observed is not the same as nothing running, and saying so
                matters more here than anywhere: an empty table would read as
                a bare machine. */}
            {!data.observed && (
              <Alert severity="warning" sx={{ mb: 2 }}>{t("services.notObserved")}</Alert>
            )}
            {missing.length > 0 && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {t("services.missing", {
                  list: missing.map((s) => `${s.name} (${s.port}/${s.proto})`).join(", "),
                })}
              </Alert>
            )}
            {unexpected.length > 0 && (
              <Alert severity="info" sx={{ mb: 2 }}>
                {t("services.unexpected", {
                  list: unexpected.map((s) => `${s.port}/${s.proto}`).join(", "),
                })}
              </Alert>
            )}

            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t("services.service")}</TableCell>
                  <TableCell>{t("services.port")}</TableCell>
                  <TableCell>{t("services.exposure")}</TableCell>
                  <TableCell>{t("services.state")}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.services.map((s) => (
                  <TableRow key={`${s.port}-${s.proto}`} hover>
                    <TableCell>
                      {s.name}
                      {s.detail && (
                        <Typography variant="caption" color="text.secondary"
                                    sx={{ display: "block" }}>
                          {s.detail}
                        </Typography>
                      )}
                    </TableCell>
                    <TableCell sx={{ whiteSpace: "nowrap" }}>
                      {s.port}/{s.proto}
                    </TableCell>
                    <TableCell>
                      <Chip size="small" label={t(`services.exposure_${s.exposure}`)}
                            color={EXPOSURE_COLOR[s.exposure] ?? "default"}
                            variant={s.exposure === "public" ? "filled" : "outlined"} />
                    </TableCell>
                    <TableCell>
                      {s.listening === null
                        ? "—"
                        : s.listening
                          ? <Chip size="small" color="success" variant="outlined"
                                  label={t("services.listening")} />
                          : <Chip size="small" color="error"
                                  label={t("services.notListening")} />}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {data.containers.length > 0 && (
              <Box sx={{ mt: 3 }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  {t("services.containers", { count: data.containers.length })}
                </Typography>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                  {data.containers.map((c) => (
                    <Chip key={c.name} size="small" label={c.name}
                          color={c.status === "running" ? "success" : "default"}
                          variant={c.status === "running" ? "outlined" : "filled"} />
                  ))}
                </Box>
              </Box>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
