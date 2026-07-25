export const DOC_TOPICS = [
  { slug: "introduction", label: "Introduction" },
  { slug: "architecture", label: "Architecture" },
  { slug: "installation", label: "Installation & Setup" },
  { slug: "dns-mode", label: "DNS Mode Deep Dive" },
  { slug: "domains", label: "Domain Management" },
  { slug: "keys-tunnels", label: "Key & Tunnel Management" },
  { slug: "self-hosted-outline", label: "Self-Hosted Outline Server" },
  { slug: "self-hosted-awg", label: "Self-Hosted AWG Server" },
  { slug: "health-failover", label: "Health & Failover" },
  { slug: "user-management", label: "User Management" },
  { slug: "proximavpn", label: "ProximaVPN" },
  { slug: "proxy-gateway", label: "Proxy Gateway" },
  { slug: "ui-guide", label: "UI Guide" },
  { slug: "api-reference", label: "API Reference" },
  { slug: "deployment", label: "Deployment & Operations" },
  { slug: "deployment-checklist", label: "Deployment Checklists" },
  { slug: "troubleshooting", label: "Troubleshooting" },
  { slug: "security", label: "Security" },
] as const;

export type DocSlug = (typeof DOC_TOPICS)[number]["slug"];
