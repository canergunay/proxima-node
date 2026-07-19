# Burocons Altyapı Standartları

> Bu doküman, şantiye (şantiye = site) altyapı kurulumlarının referans standardıdır.
> Claude Code (CC) bu dokümanı okuyarak çalışmalıdır. Buradaki kararlar
> tartışılmış ve kesinleşmiştir; değiştirilmesi gerekiyorsa önce sorulmalıdır.

---

## 1. Genel İlkeler

**Aşırı mühendislik yasak.** Her kurulum, derin teknik bilgisi olmayan bir
IT çalışanı tarafından devralınabilecek kadar basit olmalıdır. Karmaşıklık
bir maliyettir, çözüm değildir.

**Templatable olmalı.** Her şantiye kurulumu, standart bir şablondan
tekrarlanabilir olmalıdır. Tek seferlik, el yapımı çözümler kabul edilmez.

**Operatör Rusya'dadır.** Tüm kararlar Rusya'daki ağ, tedarik ve yaptırım
gerçekleriyle uyumlu olmalıdır.

---

## 2. Ağ ve Erişim Kısıtları (Rusya)

Bunlar deneyimle öğrenilmiş kısıtlardır, teorik değildir.

**Cloudflare orange-cloud (proxy) kullanılamaz.**
Mid-2025'ten beri Rus ISP'leri tarafından throttle ediliyor.
Rusya'ya bakan tüm DNS kayıtları **gray-cloud (DNS-only)** olmalıdır.

**Standart WireGuard ve OpenVPN DPI ile throttle ediliyor.**
Bu yüzden **AmneziaWG** tabanlı ProximaVPN kullanılıyor.

**VPN ve sing-box dağıtım endpoint'leri asla DNS'e girmez.**
Bare-IP zorunludur. Gerekçe throttle değil, **DPI tespit direncidir**:
bir DNS kaydı, `fs-bc.net` domainine bakan birine VPN altyapısının
varlığını ve konumunu ele verir. Bu bilinçli bir gizlilik kararıdır.

**SMB (port 445) NPM üzerinden geçmez.**
NPM yalnızca HTTP/HTTPS proxy'dir. SMB doğrudan NAS'a gider.
Protokolleri tek hostname altında karıştırmak sürdürülemez karmaşıklık yaratır.

---

## 3. İsimlendirme Standardı — `fs-bc.net`

Şablon: `<site>[-<rol>].fs-bc.net`

### SVR (Sviridova) — ilk tam standart uygulama

| Amaç | Adres | Katman |
|---|---|---|
| NAS web arayüzü | `svr.fs-bc.net` | NPM (HTTPS) |
| SMB erişimi | `svr-n.fs-bc.net` / `\\bc-svr` | Doğrudan NAS |
| Proxima admin paneli | `svr-p.fs-bc.net` | NPM (HTTPS) |
| Homarr dashboard | `svr-d.fs-bc.net` | NPM (HTTPS) |
| **VPN / sing-box profil** | **DNS'te YOK — bare-IP** | Doğrudan |

### SHV (Sukharevskaya) — yarım standartlaştırılmış (bilinçli teknik borç)

| Amaç | Adres | Not |
|---|---|---|
| NAS web arayüzü | `shv.fs-bc.net` | NPM üzerinden, modernize edildi |
| SMB erişimi | `buroconstruction.synology.me` / `\\Buro` | Eski isim korundu |
| VPN | bare-IP | Eski yapı korundu |

SHV'de SMB ve VPN eski isimleriyle bırakıldı; sebebi aktif kullanıcıların
masaüstü kısayollarını, DS file bağlantılarını ve yer imlerini bozmamaktır.
Bu bir başarısızlık değil, kabul edilmiş teknik borçtur.

### Kural

Yeni şantiyeler **tam standardı** uygular. `<site>` kodu üç harflidir
(SHV, SVR, ...). Rol ekleri: `-n` (SMB/network), `-p` (panel), `-d` (dashboard).
VPN için **rol eki tanımlanmamıştır ve tanımlanmayacaktır.**

### DNS kayıt yapısı

- Her şantiye için yalnızca `<site>.fs-bc.net` **A kaydı** tutulur
  (şantiye public IP'si; hedef her şantiyede statik IP'dir).
- Rol adresleri (`-p`, `-d`, `-n`) bu A kaydına **CNAME**'dir.
  IP değişirse tek kayıt güncellenir.
- Dinamik IP'li istisna durumlarda Proxima'nın DDNS modülü (Cloudflare)
  yalnızca A kaydını günceller; CNAME'ler otomatik takip eder.
- **Split DNS:** LAN içinden `<site>*.fs-bc.net` sorgularına Proxima dnsmasq
  lokal sunucu IP'sini (.121) döner. Hairpin NAT kullanılmaz. CGNAT'lı
  sahalarda panel erişiminin tek yolu budur.

---

## 4. Donanım Standardı

### Şantiye sunucusu (Linux/Docker host)

**Lenovo ThinkCentre M70q Gen 5 Tiny [12TESKR400]**
- Intel Core i5-14400T
- 16 GB DDR5 SO-DIMM (2 yuva, biri boş — yükseltilebilir)
- 512 GB NVMe M.2 PCIe (ikinci M.2 2280 yuvası boş)
- OS'suz gelir (Windows lisansı ödenmez)
- VESA montaj destekli, 7/24 çalışmaya uygun

Aynı model hem **Linux sunucu** hem **ofis masaüstü** rolünde kullanılır.
Tek donanım standardı = tek yedek parça mantığı, tek öğrenme eğrisi.

### Şantiye NAS

**Synology DS725+** + **3 × WD Red Plus WD40EFPX 4TB**
- RAID 1 (SHR-1), 3. disk cold spare
- **CMR zorunlu.** SMR (örn. WD40EFAX) RAID rebuild sürelerini
  kabul edilemez ölçüde uzatır. WD40EFPX standarttır.

### Ağ

**MikroTik RB4011** (RouterOS 7.x) — tüm şantiyelerde standart.
CAPsMAN ile yönetilen cAP ax erişim noktaları.

## 5. Debian Kurulum Standardı

Referans: SVR sunucusu, Debian 12 (Bookworm), netinst amd64.

### BIOS ayarları (kurulumdan önce)
- Secure Boot → **Disabled**
- After Power Loss → **Power On** (elektrik kesintisi sonrası otomatik açılış)
- Boot: F12 ile tek seferlik USB seçimi (kalıcı boot sırası değiştirilmez)

### Kurulum seçimleri
| Adım | Seçim |
|---|---|
| Dil | English (log/hata mesajları İngilizce olsun) |
| Konum | Russian Federation |
| Locale | en_US.UTF-8 |
| Timezone | Moscow |
| Hostname | `svr` (site kodu, küçük harf) |
| Domain | `fs-bc.net` |
| Root parolası | **Boş bırakılır** — root kilitlenir, ilk kullanıcı sudo alır |
| Kullanıcı | `can` |
| Bölümleme | Guided — use entire disk, all files in one partition |
| LVM / şifreleme | **Kullanılmaz** (şifreli disk otomatik açılışı engeller) |
| Mirror | Russian Federation → `mirror.yandex.ru` |
| popularity-contest | No |
| Paket seçimi | **Yalnızca** SSH server + standard system utilities |

**Masaüstü ortamı (GNOME vb.) kurulmaz.** Sunucuda gereksiz yer, RAM ve
saldırı yüzeyi demektir. Yönetim SSH üzerinden yapılır.

**web server (Apache) kurulmaz.** Reverse proxy görevini Docker içindeki
NPM üstlenir; Apache çakışma yaratır.

### Kurulum sonrası
- IP adresi **MikroTik'te DHCP static lease** ile MAC'e sabitlenir.
  Debian tarafında statik IP tanımlanmaz — IP planı merkezi kalır.
- SSH ile Windows üzerinden yönetilir; monitör/klavye kalıcı bağlı tutulmaz.

---

## 6. Servis Katmanı (Docker)

Referans stack (OFC sunucusundan devralınan standart):

- **Proxima / AmneziaWG** — VPN
- **Nginx Proxy Manager (NPM)** — HTTP/HTTPS reverse proxy, Let's Encrypt
- **Portainer** — container yönetimi
- **Homarr** — dashboard

### İzleme merkezidir — şantiyede lokal Healthchecks kurulmaz

Şantiyenin kendi izleme servisi kendi çöküşünü bildiremez. Bu yüzden:

- **Kısa vade:** şantiye sunucusu, ERG'deki merkezi Healthchecks'e
  cron ile dead-man ping atar (sıfır geliştirme gerektirir).
- **Orta vade:** ADM (adm.prxa.net), yönetim tüneli üzerinden şantiye
  sunucularını doğrudan izler (kutu 10.14.14.x'te her zaman erişilebilir,
  proxima-agent :5051). ADM entegrasyonu ayrı iş kalemidir, şantiye
  kurulumunu bloklamaz.

### Kritik kural: taşınabilirlik

Sunucular **hazırlık ortamında kurulup şantiyeye taşınır.** Bu nedenle:

- Docker compose ve NPM konfigürasyonlarında **sabit IP yazılmaz**
- Container adı veya hostname kullanılır
- Ortama bağlı değerler **parametrize edilir** (`.env` veya değişken dosyası)

Şantiyeye taşındığında yalnızca ağ parametreleri değişmeli, stack'e
dokunulmamalıdır.

---

## 7. Yedekleme Mimarisi

```
Şantiye NAS  --(gecelik Hyper Backup)-->  Merkez Buro NAS  -->  DS118
```

Kullanıcılar her zaman **canlı NAS'a** erişir; yedek katmanı kullanıcıya
açılmaz.

---

## 8. Bilinen Tuzaklar

**MikroTik raw chain.** Artık kalmış IPsec `notrack` kuralları connection
tracking'i tamamen bypass ederek masquerade'i engelleyebilir. VPN/NAT
arızalarında **raw chain mutlaka kontrol edilir.**

**Synology izin modeli.** Shared Folder seviyesi *tavandır*; File Station
ACL granüler kontroldür. Alt klasör sorununu çözmek için Shared Folder
seviyesinde izin düşürmek tüm alt ACL'leri ezer. **Tavana dokunulmaz.**

**Tarayıcı HSTS önbelleği.** Daha önce `:5001` gibi portlu erişim yapılmış
bir hostname, NPM düzgün çalışsa bile tarayıcıda bozuk yönlendirme
gösterebilir. Teşhiste temiz tarayıcı kullanılır.

---

## 9. IP ve Subnet Planı

### LAN şablonu — `192.168.<N>.0/24`

Site başına üçüncü oktet: OFC=77, SVR=78, yeni şantiyeler sırayla 79+.

| Adres | Kullanım |
|---|---|
| `.1` | MikroTik router |
| `.2 – .9` | Pool dışı rezerv (acil manuel IP ihtiyacı) |
| `.10 – .250` | DHCP pool (≈240 adres) |
| `.121` | Proxima sunucusu (static lease, pool içinde) |
| `.122` | Synology NAS (static lease, pool içinde) |

MikroTik'te static lease pool içinde tanımlanır — lease'li adres başka
cihaza dağıtılmaz. Yazıcı gibi sabit IP isteyen cihazlar geldikçe
**make-static** ile sabitlenir; Debian/cihaz tarafında statik IP yazılmaz.

### VPN subnet şablonu — `10.<N>.x.0/24`

Her lokasyon bir `10.<N>` bloğuna sahiptir; o lokasyonun **tüm** VPN
katmanları kendi bloğunda kalır. Çakışma yapısal olarak imkânsızlaşır.

Katman deseni: **wg1 (ProximaVPN) = `10.N.N`**, **wg2 (sing-box WG) = `10.N.(N+1)`**,
**wg0 (yedek, varsa) = `10.N.0`**.

Envanter (2026-07-19, `ip addr` + `wg show` ile doğrulandı):

| Lokasyon | Blok | wg1 (ProximaVPN) | wg2 (sing-box) | wg0 (yedek) |
|---|---|---|---|---|
| ERG | `10.14.x` | `10.14.14.0/24` | `10.14.15.0/24` | `10.13.13.0/24` *(legacy, blok dışı)* |
| OFC | `10.15.x` | `10.15.15.0/24` | `10.15.16.0/24` | `10.16.16.0/24` *(legacy, blok dışı — dokunulmaz)* |
| SVR | `10.17.x` | `10.17.17.0/24` | `10.17.18.0/24` (gerekirse) | `10.17.0.0/24` (gerekirse) |
| Yeni şantiye | `10.18.x`+ | `10.N.N.0/24` | `10.N.(N+1).0/24` | `10.N.0.0/24` |

**Rezerve bloklar (tahsis edilemez):**
- `10.10.x` — site-to-site interconnect: OFC MikroTik `bc-wireguard`
  (port 13231, host adresi `10.10.10.0` — nonstandart .0, çalışıyor,
  dokunulmaz) ↔ ERG `wg-bcshv` (`10.10.10.2`); kişisel erişim peer'ı
  `10.10.10.3`. OFC LAN 192.168.77.0/24'ü de taşır.
- `10.13.x` — ERG wg0 legacy yedek tüneli (aktif, ERG↔OFC; dokunulmaz)
- `10.16.x` — OFC wg0 legacy yedek tüneli (`10.16.16.0/24`) tarafından
  işgal edildiği için **atlanır** — hiçbir siteye tahsis edilmez.
  (Karar 2026-07-19: çalışan acil erişim tüneline dokunulmadı,
  SVR bloğu 10.17'ye kaydırıldı.)

Envanter durumu: **TAMAMLANDI** (2026-07-19). Linux tarafı `ip addr` +
`wg show`, MikroTik tarafı `/ip address print` + WG print ile doğrulandı.
Bilinmeyen subnet kalmamıştır.

**Kurallar:**
- Yeni subnet tahsisi bu tablo güncellenmeden yapılmaz.
- Mevcut subnet'ler yeniden numaralandırılmaz, yalnızca kaydedilir.
  Legacy bir subnet bir bloğu işgal ediyorsa **blok atlanır**
  (örnek: OFC wg0 → 10.16 atlandı, SVR = 10.17).
- MikroTik WG arayüzleri de bu tabloya dahildir (OFC MikroTik:
  `bc-wireguard`, port 13231 — interconnect bloğunda).

---

## 10. MikroTik Şantiye Standardı (RB4011)

Kit hazırlık ortamında yapılandırılır; sahada yalnızca WAN değişir.

### Temel yapılandırma
- Bridge + LAN `192.168.<N>.1/24`, DHCP server (pool `.10–.250`)
- DHCP option 6 (DNS) ve option 3 (gateway) → `.121` (Proxima)
- Static lease: sunucu MAC → `.121`, NAS MAC → `.122`
- DSTNAT `5555/UDP` → `.121` — **`in-interface=WAN` zorunlu**
  (bilinen tuzak: belirtilmezse LAN'dan çıkan VPN UDP trafiği hijack edilir)
- **Hairpin DNAT (zorunlu):** VPN profilleri bare-IP olduğu için (Bölüm 2)
  split DNS onları kurtaramaz — LAN içindeki bir telefon public IP'ye
  bağlanmaya çalışır. Kural: `src-address=LAN dst-address=<publicIP>
  dst-port=5555/udp → .121` + eşlik eden srcnat masquerade.
  (Referans desen: OFC "ProximaVPN hairpin DNAT" kuralı.)
  Web panelleri için hairpin gerekmez — split DNS halleder.

### Call-home yönetim tüneli (zorunlu)
Hem MikroTik hem Proxima sunucusu, ERG wg1'e **outbound peer** olarak
bağlanır (`PersistentKeepalive=25`). Saha CGNAT arkasında olsa bile iki
bağımsız uzaktan erişim kanalı korunur: kutu ölürse router'a, router
ölürse kutuya ulaşılır. Sunucu `10.14.14.x` adresi üzerinden SSH ve
ADM erişimine açıktır.

### Netwatch failsafe (zorunlu)
Netwatch `.121`'i izler: down → DHCP option 3/6 router'a (`.1`) döner,
up → geri. **Şantiyenin interneti Proxima'ya bağımlı değildir** —
sunucu çökerse yalnızca VPN yönlendirme durur, internet devam eder.

### WAN ve güvenlik
- WAN: varsayılan DHCP client. PPPoE/LTE gerekiyorsa sahada yapılandırılır —
  kitin **tek saha-bağımlı ayarı** budur.
- WAN'dan yönetim erişimi kapalı; WinBox yalnızca LAN + VPN üzerinden.
- Raw chain temiz tutulur (bkz. Bilinen Tuzaklar).
