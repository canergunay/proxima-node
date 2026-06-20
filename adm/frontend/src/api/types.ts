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
  disk_usage_percent: number;
  memory_usage_percent: number;
  services: Record<string, boolean>;
  docker_containers?: ContainerInfo[];
  version: string;
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
