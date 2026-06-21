import { useCallback, useEffect, useState } from "react";
import {
  Box, Button, Grid2 as Grid, Typography, CircularProgress, Tabs, Tab,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useTranslation } from "react-i18next";
import api from "../api/client";
import type { Server, VpnServer } from "../api/types";
import ServerCard from "../components/ServerCard";
import ProvisionDialog from "../components/ProvisionDialog";
import ServerDetailDialog from "../components/ServerDetailDialog";
import VpnServerCard from "../components/VpnServerCard";
import AddVpnServerDialog from "../components/AddVpnServerDialog";
import VpnServerDetailDialog from "../components/VpnServerDetailDialog";
import MonitoringTab from "../components/MonitoringTab";

export default function Dashboard() {
  const { t } = useTranslation();
  const [tab, setTab] = useState(() => {
    const saved = localStorage.getItem("adm_dashboard_tab");
    return saved ? parseInt(saved) : 0;
  });

  // Exit servers state
  const [servers, setServers] = useState<Server[]>([]);
  const [serversLoading, setServersLoading] = useState(true);
  const [provisionOpen, setProvisionOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // VPN servers state
  const [vpnServers, setVpnServers] = useState<VpnServer[]>([]);
  const [vpnLoading, setVpnLoading] = useState(true);
  const [addVpnOpen, setAddVpnOpen] = useState(false);
  const [selectedVpn, setSelectedVpn] = useState<VpnServer | null>(null);

  const fetchServers = useCallback(async () => {
    try {
      const { data } = await api.get("/servers");
      if (data.ok) setServers(data.data);
    } catch { /* handled by interceptor */ }
    setServersLoading(false);
  }, []);

  const fetchVpnServers = useCallback(async () => {
    try {
      const { data } = await api.get("/vpn-servers");
      if (data.ok) setVpnServers(data.data);
    } catch { /* handled by interceptor */ }
    setVpnLoading(false);
  }, []);

  // Fetch exit servers on mount + polling
  useEffect(() => {
    fetchServers();
    const interval = setInterval(fetchServers, 30000);
    return () => clearInterval(interval);
  }, [fetchServers]);

  // Fetch VPN servers when tab 1 is active
  useEffect(() => {
    if (tab === 1) {
      fetchVpnServers();
      const interval = setInterval(fetchVpnServers, 30000);
      return () => clearInterval(interval);
    }
  }, [tab, fetchVpnServers]);

  const handleTabChange = (_: unknown, newValue: number) => {
    setTab(newValue);
    localStorage.setItem("adm_dashboard_tab", String(newValue));
  };

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
        <Typography variant="h5" fontWeight={700}>
          {t("dashboard.title")}
        </Typography>
        <Box sx={{ display: "flex", gap: 1 }}>
          {tab !== 2 && (
            <Button
              startIcon={<RefreshIcon />}
              onClick={() => {
                if (tab === 0) { setServersLoading(true); fetchServers(); }
                else { setVpnLoading(true); fetchVpnServers(); }
              }}
              variant="outlined"
              size="small"
            >
              {t("dashboard.refresh")}
            </Button>
          )}
          {tab === 0 && (
            <Button
              startIcon={<AddIcon />}
              onClick={() => setProvisionOpen(true)}
              variant="contained"
              size="small"
            >
              {t("dashboard.addServer")}
            </Button>
          )}
          {tab === 1 && (
            <Button
              startIcon={<AddIcon />}
              onClick={() => setAddVpnOpen(true)}
              variant="contained"
              size="small"
            >
              {t("dashboard.addVpnServer")}
            </Button>
          )}
        </Box>
      </Box>

      <Tabs
        value={tab}
        onChange={handleTabChange}
        sx={{ mb: 2, borderBottom: 1, borderColor: "divider" }}
      >
        <Tab label={t("dashboard.tabExitServers")} />
        <Tab label={t("dashboard.tabVpnServers")} />
        <Tab label={t("dashboard.tabMonitoring")} />
      </Tabs>

      {/* ── Tab 0: Exit Servers ──────────────────── */}
      {tab === 0 && (
        <>
          {serversLoading && servers.length === 0 ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
              <CircularProgress />
            </Box>
          ) : servers.length === 0 ? (
            <Typography color="text.secondary" sx={{ py: 8, textAlign: "center" }}>
              {t("dashboard.noServers")}
            </Typography>
          ) : (
            <Grid container spacing={2}>
              {servers.map((server) => (
                <Grid key={server.id} size={{ xs: 12, sm: 6, md: 4 }}>
                  <ServerCard server={server} onClick={() => setSelectedId(server.id)} />
                </Grid>
              ))}
            </Grid>
          )}

          <ProvisionDialog
            open={provisionOpen}
            onClose={() => setProvisionOpen(false)}
            onCreated={() => { setProvisionOpen(false); fetchServers(); }}
          />

          {selectedId && (
            <ServerDetailDialog
              serverId={selectedId}
              open={true}
              onClose={() => setSelectedId(null)}
              onRefresh={fetchServers}
            />
          )}
        </>
      )}

      {/* ── Tab 1: VPN Servers ───────────────────── */}
      {tab === 1 && (
        <>
          {vpnLoading && vpnServers.length === 0 ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 8 }}>
              <CircularProgress />
            </Box>
          ) : vpnServers.length === 0 ? (
            <Typography color="text.secondary" sx={{ py: 8, textAlign: "center" }}>
              {t("dashboard.noVpnServers")}
            </Typography>
          ) : (
            <Grid container spacing={2}>
              {vpnServers.map((server) => (
                <Grid key={server.id} size={{ xs: 12, sm: 6, md: 4 }}>
                  <VpnServerCard
                    server={server}
                    onClick={() => setSelectedVpn(server)}
                    onEdit={() => setSelectedVpn(server)}
                    onDelete={async () => {
                      if (!confirm(t("vpnDetail.confirmDelete", { name: server.display_name }))) return;
                      try {
                        await api.delete(`/vpn-servers/${server.id}`);
                        fetchVpnServers();
                      } catch { /* handled by interceptor */ }
                    }}
                  />
                </Grid>
              ))}
            </Grid>
          )}

          <AddVpnServerDialog
            open={addVpnOpen}
            onClose={() => setAddVpnOpen(false)}
            onCreated={() => { setAddVpnOpen(false); fetchVpnServers(); }}
          />

          {selectedVpn && (
            <VpnServerDetailDialog
              vpnServer={selectedVpn}
              open={true}
              onClose={() => setSelectedVpn(null)}
              onRefresh={fetchVpnServers}
              onDeleted={() => { setSelectedVpn(null); fetchVpnServers(); }}
            />
          )}
        </>
      )}

      {/* ── Tab 2: Monitoring ──────────────────────── */}
      {tab === 2 && <MonitoringTab />}
    </Box>
  );
}
