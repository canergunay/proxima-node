import { useCallback, useEffect, useState } from "react";
import {
  Box, Button, Grid2 as Grid, Typography, CircularProgress,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useTranslation } from "react-i18next";
import api from "../api/client";
import type { Server } from "../api/types";
import ServerCard from "../components/ServerCard";
import ProvisionDialog from "../components/ProvisionDialog";
import ServerDetailDialog from "../components/ServerDetailDialog";

export default function Dashboard() {
  const { t } = useTranslation();
  const [servers, setServers] = useState<Server[]>([]);
  const [loading, setLoading] = useState(true);
  const [provisionOpen, setProvisionOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const fetchServers = useCallback(async () => {
    try {
      const { data } = await api.get("/servers");
      if (data.ok) setServers(data.data);
    } catch { /* handled by interceptor */ }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchServers();
    const interval = setInterval(fetchServers, 30000);
    return () => clearInterval(interval);
  }, [fetchServers]);

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 3 }}>
        <Typography variant="h5" fontWeight={700}>
          {t("dashboard.title")}
        </Typography>
        <Box sx={{ display: "flex", gap: 1 }}>
          <Button
            startIcon={<RefreshIcon />}
            onClick={() => { setLoading(true); fetchServers(); }}
            variant="outlined"
            size="small"
          >
            {t("dashboard.refresh")}
          </Button>
          <Button
            startIcon={<AddIcon />}
            onClick={() => setProvisionOpen(true)}
            variant="contained"
            size="small"
          >
            {t("dashboard.addServer")}
          </Button>
        </Box>
      </Box>

      {loading && servers.length === 0 ? (
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
    </Box>
  );
}
