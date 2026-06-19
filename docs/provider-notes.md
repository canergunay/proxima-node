# VPS Provider Notes

Recommendations and observations from running Proxima exit servers.

## Currently Used

| Provider | Server | Location | Plan | Price | Notes |
|----------|--------|----------|------|-------|-------|
| BlueVPS | ERG-PL | Warsaw, PL | NVMe-bKVM 1024 | $6/mo | Good latency (31ms), stable |
| Hetzner | ERG-DE | Germany | — | — | Good but IPs sometimes throttled in RU |
| Unknown | ERG-TR | Turkey | — | — | — |
| Unknown | ERG-FI | Finland | — | — | — |

## Selection Criteria

When choosing a VPS for a Proxima exit node:

1. **Clean IP** — Not on blocklists. Test with RIPE/Spamhaus before purchasing.
2. **Debian 12** — Primary supported OS. Ubuntu 22+ also works.
3. **KVM/QEMU** — Required for WireGuard kernel module (AWG). OpenVZ won't work.
4. **Location** — Low latency to your Proxima instance. Avoid countries that cooperate with your target country's censorship authority.
5. **Price** — $4-8/mo is typical. 1 GB RAM and 10 GB disk is sufficient.
6. **TUN/TAP** — Must allow /dev/net/tun for VPN containers.

## Providers to Avoid

| Provider | Reason |
|----------|--------|
| Aeza | Cooperates with RKN (Russian internet regulator) |
| Any OpenVZ provider | No WireGuard kernel module support |
