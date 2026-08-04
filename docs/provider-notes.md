# VPS Provider Notes

Recommendations and observations from running Proxima exit servers.

## Currently Used

| Provider | Server | Location | Plan | Price | Notes |
|----------|--------|----------|------|-------|-------|
| BlueVPS | ERG-PL | Warsaw, PL | NVMe-bKVM 1024 | $6/mo | Good latency (31ms), stable |
| Hetzner | ERG-DE | Germany | — | — | Good but IPs sometimes throttled in RU |
| HOSTKEY | ERG-TR | Turkey | server ID 37582 | 830 ₽/mo | **Metered: 0.5 TB outbound included, then 720 ₽/TB.** Inbound unlimited, 1000 Mbps port. Active since 18.06.2026, auto-renew from balance |
| Unknown | ERG-FI | Finland | — | — | Aeza — see "Providers to Avoid"; kept because Aeza IPs are not blocked on Russian LTE |

## Metered vs unmetered

ERG-TR is the only **metered** node. For an exit server the billed direction is
the painful one: internet → server is inbound (free), server → client is
outbound (metered), so downloads and video streaming land squarely on the cap.
0.5 TB is roughly 220–330 h of 1080p, ~165 h of Netflix HD, or ~70 h of 4K.

`agent.py` collects cpu/disk/memory only and ADM alerts on cpu/disk/memory/
offline — **there is no traffic counter anywhere in the stack**, so an overage
surfaces as an invoice rather than an alert. Add traffic accounting before
routing bulk traffic through a metered node (master plan 20.A3/20.A4).

## Candidates (not purchased)

| Provider | Location | Plan | Price | Notes |
|----------|----------|------|-------|-------|
| vps.com.tr | Istanbul, TR | EXTRA (2C/4GB/50GB) | 209.90 TL/mo + 20 % KDV = 251.88 TL | Out of stock when checked 2026-08-04 |
| vps.com.tr | Istanbul, TR | EXTRA X (4C/4GB/60GB) | 249.90 TL/mo + 20 % KDV = 299.88 TL | Cheapest in-stock package. Debian 12 offered, 1 Gbit port, 1 IPv4 |

Both packages are heavily oversized for an exit node (1 GB RAM / 10 GB disk is
enough). Site researched 2026-08-04 — findings:

- **No traffic policy is published anywhere** — not on the package pages, not
  in `hizmet-sartlari.php`. They never use the words "limitsiz/sınırsız
  trafik". Hosts that genuinely sell unmetered TR transit put it in the page
  title (İdealHosting's product is titled *"TR Lokasyon Limitsiz Trafik Sanal
  Sunucular"*). Treat "unlimited" as unverified until they say so in writing.
- **Virtualization is not stated.** Their blog carries generic KVM-vs-OpenVZ
  explainers, but no page says their own VPS is KVM. This is the AWG hard
  blocker — ask before ordering.
- **VPN is implicitly tolerated**: they publish a *"VDS Sunucu ile Kendi
  VPN'inizi Kurun"* tutorial (OpenVPN, WireGuard named as an alternative) and
  sell a **"VPN Kullanıcısı"** cart add-on. But the ToS contains no explicit
  AUP — §3.7 just permits termination for violating unstated "ana hatlar".
- **They are a datacenter tenant, not the owner.** `kiralik-sunucu-altyapi.php`
  describes a third-party carrier-neutral facility (7 500 m² enclosed, seismic
  isolators, direct TT/Turkcell/Vodafone/TurkNet, 10/40/100/400 Gbps).
- **🚩 Şikayetvar** carries *"Vaat Edilen Hız Sağlanmadı"* — 1 Gbit advertised,
  ~200 Mbit measured — plus unexplained server shutdowns, power interruptions
  and unanswered tickets. (Second-hand: the site 403s direct fetch.) Verify
  sustained throughput over hours before trusting this box with bulk traffic.
- Legal entity: HZD Teknoloji ve İnovasyon San. ve Tic. Ltd. Şti., Istanbul.

**Verdict 2026-08-04: do not buy.** The only reason to prefer it was an
assumption that it is unmetered, and that claim appears nowhere in its
published material. Turkish hosts sell unmetered traffic at a capped port
speed instead — İnetmar advertises "limitsiz 100 Mbit/s", states KVM and a
Tier III ISO-27001 Türkiye datacenter, and starts at **$3.99/mo (~188 TL)**,
cheaper than vps.com.tr's 299.88 TL with all three terms in writing.

For an exit node that shape is strictly better: 1080p ≈ 8 Mbit and 4K ≈ 25
Mbit, so 100 Mbit carries ~4 concurrent 4K streams — while a 1 Gbit port
against a 0.5 TB cap runs out after ~70 h of 4K. **Unmetered at 100 Mbit beats
metered at 1 Gbit for this workload.** Other providers that put unmetered TR
traffic in writing: İdealHosting, Turhost, DeHost, hosting.com.tr, Sunucun.

## Turkish exit — what it is and is not for

- **Good for:** reaching Turkish services — banking apps, e-Devlet, TR-geofenced
  content, Turkish streaming platforms (BluTV, Exxen, TOD, beIN, TRT, Puhu).
- **Not a bypass location.** Traffic leaving a TR datacentre is subject to
  BTK/5651 blocking and provider log retention. Never present it as one.
- **Datacenter-IP detection is the main functional risk.** Global platforms
  (Netflix, Disney+, Amazon) block hosting ASNs; Turkish local platforms are
  far more permissive. Some banks refuse datacenter ranges outright — this is a
  property of the specific IP, not of "Turkey". Test per platform and per bank.
- **GeoIP must agree.** HOSTKEY is a Russian company running a TR region;
  GeoIP databases sometimes report the registrant rather than the presence.
  Verify `82.26.94.37` resolves to TR in MaxMind/IP2Location before relying on
  it for geo-restricted content.
- **Session stability matters more than uptime for banking.** An exit change
  mid-session (TR → DE) reads as account takeover: session kill, device
  re-verification, or a fraud lock. Prefer failing closed over failing over.

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
