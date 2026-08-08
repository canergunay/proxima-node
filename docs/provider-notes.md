# VPS Provider Notes

Recommendations and observations from running Proxima exit servers.

## Currently Used

| Provider | Server | Location | Plan | Price | Notes |
|----------|--------|----------|------|-------|-------|
| BlueVPS | ERG-PL | Warsaw, PL | NVMe-bKVM 1024 | $6/mo | Good latency (31ms), stable |
| Hetzner | ERG-DE | Germany | — | — | Good but IPs sometimes throttled in RU |
| vps.com.tr | ERG-TR (FAST) | Istanbul, TR | EXTRA X (4C/4GB/60GB) | 249.90 TL + KDV = 299.88 TL/mo | **KVM, and the panel reports `Bandwidth: Unlimited`.** Bought 2026-08-09. AS213657, a Turkish AS registered to the operator — see "What the TR nodes measured" |
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

## vps.com.tr — what the site said before we bought (2026-08-04)

Kept because the gap between what a provider publishes and what it delivers is
the useful part of this record.

| Plan | Price | Notes |
|------|-------|-------|
| EXTRA (2C/4GB/50GB) | 209.90 TL/mo + 20 % KDV = 251.88 TL | Out of stock when checked |
| EXTRA X (4C/4GB/60GB) | 249.90 TL/mo + 20 % KDV = 299.88 TL | The one bought. Debian 12 offered, 1 Gbit port, 1 IPv4 |

Both are heavily oversized for an exit node (1 GB RAM / 10 GB disk is enough).
Findings at the time:

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

**Verdict 2026-08-04: do not buy — overturned 2026-08-09, bought and in
service.** The verdict rested on two claims, and both were wrong.

The first was mine. İnetmar was described here as advertising unmetered
traffic in writing; it does not. Its hero line reads *"limitsiz 100 Mbit/s
**hat**"* — the *line* is unmetered, not the volume — and its package table
states **2 TB/month**. That distinction is exactly the one Turkish hosting
marketing blurs, and it was repeated here from a search summary without being
checked against the page.

The second was the assumption that vps.com.tr's silence meant something bad.
The customer panel answers both open questions plainly: **Proxmox with virtio
boot order (a full KVM guest, not a container)** and **`Bandwidth Usage:
0 MB / Unlimited`**. A one-second preflight probe confirmed `virt: kvm` and
`/dev/net/tun` present before anything was installed.

So the honest summary is that the page was uninformative, not that the product
was poor. "Ask, do not infer" survives as the lesson; "unstated means bad"
does not.

The ~200 Mbit complaint on Şikayetvar remains untested — nothing so far has
needed sustained throughput.

## What the TR nodes measured (2026-08-09)

Both nodes geolocate to Turkey in two independent databases, and both are
flagged as datacenter ranges:

| | ERG-TR (FAST) | ERG-TR (HOSTKEY) |
|---|---|---|
| country (ipinfo, ip-api) | TR | TR |
| ISP / AS | HZD Teknoloji, **AS213657** | Hostkey B.V., AS57043 |
| `hosting` flag | true | true |

The AS registration differs and may matter: the new node's is a Turkish
company on a Turkish AS, the older one's a Dutch B.V.

**A controlled test found one platform that genuinely geo-gates.** TOD
(todtv.com.tr) returns 403 from Germany and 200 from Turkey, and the new node
passes it. TRT/tabii, Exxen, PuhuTV and five bank homepages return 200 from
both countries, so those tell us nothing — their gating, if any, happens at
playback or login rather than on the landing page.

Playback and banking-app login were verified by hand on 2026-08-09 and work.
Neither is testable from a shell: geo-gating for video happens in the player
and its licence request, and a bank decides at login on IP reputation and
device binding. `hosting: true` means the datacenter-blocking platforms
(Netflix and similar) will still refuse — TOD passing shows it checks
geography but not hosting.

## Turkish exit — what it is and is not for

- **Good for:** reaching Turkish services — banking apps, e-Devlet, TR-geofenced
  content, Turkish streaming platforms (BluTV, Exxen, TOD, beIN, TRT, Puhu).
- **Not a bypass location.** Traffic leaving a TR datacentre is subject to
  BTK/5651 blocking and provider log retention. Never present it as one.
- **Datacenter-IP detection is the main functional risk.** Global platforms
  (Netflix, Disney+, Amazon) block hosting ASNs; Turkish local platforms are
  far more permissive. Some banks refuse datacenter ranges outright — this is a
  property of the specific IP, not of "Turkey". Test per platform and per bank.
- **GeoIP must agree — checked 2026-08-09, both do.** ipinfo.io and ip-api.com
  place `82.26.94.37` and `185.229.12.109` in TR. Worth rechecking after any IP
  change: a database can report the registrant rather than the presence, which
  was the specific worry with HOSTKEY, a Dutch B.V. selling a TR region.
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
