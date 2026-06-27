import { useCallback, useEffect, useState } from "react";
import {
  CssBaseline,
  ThemeProvider,
  createTheme,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Box,
  Menu,
  MenuItem,
  CircularProgress,
} from "@mui/material";
import SettingsIcon from "@mui/icons-material/Settings";
import LogoutIcon from "@mui/icons-material/Logout";
import { useTranslation } from "react-i18next";
import api from "./api/client";
import { getToken, setToken, clearToken } from "./auth";
import type { AuthMe } from "./api/types";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Settings from "./pages/Settings";

const darkTheme = createTheme({
  palette: { mode: "dark" },
});

type Page = "dashboard" | "settings";

export default function App() {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [authConfigured, setAuthConfigured] = useState(true);
  const [user, setUser] = useState<string | null>(null);
  const [page, setPage] = useState<Page>("dashboard");
  const [menuAnchor, setMenuAnchor] = useState<null | HTMLElement>(null);

  const checkAuth = useCallback(async () => {
    try {
      const { data } = await api.get<{ ok: boolean; data: AuthMe }>("/auth/me");
      if (!data.data.auth_configured) {
        setAuthConfigured(false);
        setUser(null);
      } else if (data.data.username) {
        setAuthConfigured(true);
        setUser(data.data.username);
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
    const handler = () => {
      clearToken();
      setUser(null);
    };
    window.addEventListener("adm:auth-expired", handler);
    return () => window.removeEventListener("adm:auth-expired", handler);
  }, [checkAuth]);

  const handleLogin = (token: string) => {
    setToken(token);
    setAuthConfigured(true);
    checkAuth();
  };

  const handleLogout = () => {
    clearToken();
    setUser(null);
    setPage("dashboard");
    setMenuAnchor(null);
  };

  if (loading) {
    return (
      <ThemeProvider theme={darkTheme}>
        <CssBaseline />
        <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh" }}>
          <CircularProgress size={32} />
        </Box>
      </ThemeProvider>
    );
  }

  if (!authConfigured || !getToken() || !user) {
    return (
      <ThemeProvider theme={darkTheme}>
        <CssBaseline />
        <Login
          isSetup={!authConfigured}
          onLogin={handleLogin}
        />
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <AppBar position="static" elevation={0} sx={{ bgcolor: "background.paper" }}>
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1, fontWeight: 700 }}>
            {t("app.title")}
          </Typography>
          <IconButton color="inherit" aria-label={t("common.settings")} onClick={(e) => setMenuAnchor(e.currentTarget)}>
            <SettingsIcon />
          </IconButton>
          <Menu
            anchorEl={menuAnchor}
            open={Boolean(menuAnchor)}
            onClose={() => setMenuAnchor(null)}
          >
            <MenuItem onClick={() => { setPage("settings"); setMenuAnchor(null); }}>
              <SettingsIcon fontSize="small" sx={{ mr: 1 }} />
              {t("common.settings")}
            </MenuItem>
            <MenuItem onClick={handleLogout}>
              <LogoutIcon fontSize="small" sx={{ mr: 1 }} />
              {t("common.logout")}
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>
      <Box component="main" sx={{ maxWidth: 1400, mx: "auto", p: 2 }}>
        {page === "dashboard" && <Dashboard />}
        {page === "settings" && <Settings onBack={() => setPage("dashboard")} />}
      </Box>
    </ThemeProvider>
  );
}
