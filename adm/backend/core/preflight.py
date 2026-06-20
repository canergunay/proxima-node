"""Pre-flight check — inspect target server before provisioning."""

import json
import logging
import subprocess

log = logging.getLogger("adm.preflight")

RECON_SCRIPT = r"""#!/bin/bash
set -e

# Collect system info
OS=$(cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'"' -f2 || echo "unknown")
ARCH=$(uname -m)
PYTHON=$(python3 --version 2>/dev/null | awk '{print $2}' || echo "")
DISK_FREE=$(df -BG / 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G' || echo "0")
MEM_TOTAL=$(free -m 2>/dev/null | awk '/Mem:/{print $2}' || echo "0")

# Check ports
PORTS_JSON="["
FIRST=1
for PORT in 8388 5051 8390 8999; do
    PROC=$(ss -tlnp 2>/dev/null | grep ":${PORT} " | head -1 | sed -n 's/.*users:(("\([^"]*\)",pid=\([0-9]*\).*/\1 (PID \2)/p' || echo "")
    if [ -n "$PROC" ]; then
        [ $FIRST -eq 0 ] && PORTS_JSON="${PORTS_JSON},"
        PORTS_JSON="${PORTS_JSON}{\"port\":${PORT},\"process\":\"${PROC}\"}"
        FIRST=0
    fi
done
PORTS_JSON="${PORTS_JSON}]"

# Check systemd services
SVCS_JSON="["
FIRST=1
for SVC in shadowsocks-libev-server@config outline-ss-server zapret-nfqws2 proxima-agent proxima-ssconf; do
    STATE=$(systemctl is-active "$SVC" 2>/dev/null || echo "inactive")
    if [ "$STATE" != "inactive" ]; then
        [ $FIRST -eq 0 ] && SVCS_JSON="${SVCS_JSON},"
        SVCS_JSON="${SVCS_JSON}{\"name\":\"${SVC}\",\"state\":\"${STATE}\"}"
        FIRST=0
    fi
done
SVCS_JSON="${SVCS_JSON}]"

# Check Docker containers
CONTAINERS_JSON="[]"
if command -v docker &>/dev/null; then
    CONTAINERS_JSON=$(docker ps --format '{"name":"{{.Names}}","image":"{{.Image}}","status":"{{.Status}}"}' 2>/dev/null | paste -sd',' | sed 's/^/[/;s/$/]/' || echo "[]")
    [ -z "$CONTAINERS_JSON" ] && CONTAINERS_JSON="[]"
fi

cat <<ENDJSON
{
  "os": "$OS",
  "arch": "$ARCH",
  "python": "$PYTHON",
  "disk_free_gb": $DISK_FREE,
  "memory_mb": $MEM_TOTAL,
  "occupied_ports": $PORTS_JSON,
  "active_services": $SVCS_JSON,
  "docker_containers": $CONTAINERS_JSON
}
ENDJSON
"""


def run_preflight(server_ip: str, root_password: str | None = None,
                  timeout: int = 30) -> dict:
    """Run pre-flight checks on a target server via SSH.

    Returns structured result dict with ok/error and data.
    """
    # Build SSH command
    ssh_opts = [
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=10",
        "-o", "BatchMode=no",
    ]

    if root_password:
        cmd = ["sshpass", "-p", root_password, "ssh"] + ssh_opts
    else:
        cmd = ["ssh"] + ssh_opts

    cmd.extend([f"root@{server_ip}", "bash -s"])

    log.info(f"[PREFLIGHT] Running checks on {server_ip}")

    try:
        result = subprocess.run(
            cmd,
            input=RECON_SCRIPT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "Permission denied" in stderr:
                return {"ok": False, "error": "SSH authentication failed — check password or SSH key"}
            if "Connection refused" in stderr:
                return {"ok": False, "error": "SSH connection refused — check IP and SSH service"}
            if "No route to host" in stderr or "Connection timed out" in stderr:
                return {"ok": False, "error": "Cannot reach server — check IP and network"}
            return {"ok": False, "error": f"SSH failed: {stderr[:200]}"}

        # Parse JSON output
        stdout = result.stdout.strip()
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return {"ok": False, "error": f"Failed to parse server response: {stdout[:200]}"}

        # Build conflicts list
        conflicts = []

        for port_info in data.get("occupied_ports", []):
            conflicts.append({
                "type": "port",
                "port": port_info["port"],
                "detail": port_info.get("process", "unknown"),
                "severity": "warning",
            })

        for svc_info in data.get("active_services", []):
            conflicts.append({
                "type": "service",
                "name": svc_info["name"],
                "detail": svc_info.get("state", "active"),
                "severity": "warning",
            })

        for container in data.get("docker_containers", []):
            conflicts.append({
                "type": "container",
                "name": container.get("name", "?"),
                "detail": container.get("image", "?"),
                "severity": "info",
            })

        data["conflicts"] = conflicts
        data["ssh_ok"] = True

        return {"ok": True, "data": data}

    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "SSH connection timed out"}
    except FileNotFoundError:
        return {"ok": False, "error": "sshpass not installed — required for password-based SSH"}
    except Exception as e:
        log.error(f"[PREFLIGHT] Error: {e}")
        return {"ok": False, "error": str(e)}
