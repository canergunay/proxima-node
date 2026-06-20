export interface Server {
  id: number;
  name: string;
  display_name: string;
  ip: string;
  server_type: "vpn_exit" | "dpi_bypass";
  location: string;
  provider: string;
  status: string;
  agent_port: number;
  online: boolean;
  agent_status: AgentStatus | null;
  error: string | null;
}

export interface AgentStatus {
  hostname: string;
  uptime: number;
  server_type: string;
  public_ip: string;
  disk: { free_gb: number; total_gb: number; used_gb: number; used_pct: number };
  memory: { available_mb: number; total_mb: number; used_pct: number };
  services: Record<string, boolean>;
  docker_containers?: ContainerInfo[];
  version?: string;
}

export interface ContainerInfo {
  name: string;
  status: string;
  running: boolean;
}

export interface ServerDetail extends Server {
  ss_password: string | null;
  agent_api_key: string | null;
  ssconf_token: string | null;
  speedtest_api_key: string | null;
  ss_port: number;
  ss_cipher: string;
  node_id: string | null;
  install_adguard: number;
  created_at: number;
  updated_at: number;
  operations: Operation[];
}

export interface Operation {
  id: number;
  server_id: number | null;
  op_type: string;
  status: string;
  playbook: string | null;
  output?: string;
  error: string | null;
  started_at: number;
  completed_at: number | null;
}

export interface AuthMe {
  auth_configured: boolean;
  username?: string;
}

export interface VlessKeyData {
  uri: string;
  server: string;
  port: number;
  vless_uuid: string;
  public_key: string;
  short_id: string;
  server_name: string;
  flow: string;
  fingerprint: string;
}

// ── VPN Servers (Proxima instances) ─────────────────────────────────────

export interface VpnServer {
  id: number;
  name: string;
  display_name: string;
  url: string;
  has_token: boolean;
  online: boolean;
  proxima_status: ProximaStatus | null;
  error: string | null;
}

export interface ProximaStatus {
  server_ip: string;
  mode: string;
  deployment: string;
  dns_mode: { active: boolean; containers: Record<string, string> };
  slots: Record<string, ProximaSlotSummary>;
  bypass_active: boolean;
  bypass_slots: string[];
}

export interface ProximaSlotSummary {
  label: string;
  type: string;
  active: string | null;
  pool: string[];
  health: {
    last_ip_ok: boolean | null;
    last_ip: string | null;
    failover_count: number;
    bypass_active: boolean;
  };
}

export interface ProximaSlot {
  id: string;
  label: string;
  type: string;
  enabled: boolean;
  port: number;
  socks_port: number;
  direct: boolean;
  active: string | null;
  pool: string[];
  dpi_args?: string | null;
  via_slot?: string | null;
  health: {
    last_ip_check: string | null;
    last_ip_ok: boolean | null;
    last_ip: string | null;
    last_domain_check: string | null;
    last_domain_ok: boolean | null;
    domain_ok_count: number | null;
    domain_total_count: number | null;
    failover_count: number;
    key_stats: Record<string, unknown>;
  };
}

export interface ProximaTunnel {
  name: string;
  type: "awg" | "outline" | "xray";
  endpoint: string;
  method?: string | null;
  ssconf_url?: string;
  location?: string;
  tag?: string;
  prefix?: string;
  server?: string;
  port?: number;
  vless_uuid?: string;
  public_key?: string;
  short_id?: string;
  server_name?: string;
  flow?: string;
  fingerprint?: string;
}

export interface PreflightConflict {
  type: "port" | "service" | "container";
  port?: number;
  name?: string;
  detail: string;
  severity: "warning" | "info";
}

export interface PreflightData {
  os: string;
  arch: string;
  python: string;
  disk_free_gb: number;
  memory_mb: number;
  occupied_ports: { port: number; process: string }[];
  active_services: { name: string; state: string }[];
  docker_containers: { name: string; image: string; status: string }[];
  conflicts: PreflightConflict[];
  ssh_ok: boolean;
}
