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
CAPsMAN ile yönetilen **cAP ac (RBcAPGi-5acD2nD)** erişim noktaları.

> Bu madde 2026-07-27'de düzeltildi. Önceki hâli "cAP **ax**" diyordu; SVR için
> satın alınan donanım cAP **ac**'dir. Fark kozmetik değildir:
>
> - **Sürücü yığını:** cAP ac legacy `wireless` sürücüsünü kullanır, yani
>   `/caps-man`. Yeni `/interface wifi capsman` (wifi-qcom) yalnızca ax
>   donanımında çalışır. İki yığın birbirinin yerine geçmez; komutları ortak değil.
> - **Şifreleme:** legacy yığın **yalnızca WPA2-PSK**'dir. WPA3 yoktur.
>   (SHV'nin ax üniteleri `wpa2-psk,wpa3-psk` kullanıyor — yeni şantiyeler bu
>   seviyeye ancak ax donanımla çıkabilir.)
> - **Kural:** bir şantiyede **tek yığın** çalışır. SHV bugün ikisini birden
>   çalıştırıyor (14 legacy cap arayüzü + 4 yeni wifi arayüzü); bu, config'inin
>   en kafa karıştırıcı yanıdır ve tekrarlanmaz.
>
> Yeni alımlarda cAP ax tercih edilir (WPA3 + tek modern yığın). Elde cAP ac
> varsa kullanılır; karıştırılmaz — bir şantiye ya hep ac ya hep ax olur.

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
- **Orta vade:** ADM (adm.prxa.net), acil durum yönetim ağı üzerinden
  şantiye sunucularını doğrudan izler (kutu `10.13.13.10+` adresinde her
  zaman erişilebilir — Bölüm 11). ADM entegrasyonu ayrı iş kalemidir,
  şantiye kurulumunu bloklamaz.

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

**iptables legacy / nft bölünmesi.** Host `iptables-nft` kullanırken
`network_mode: host` çalışan bir container kendi imajındaki
`iptables-legacy` ile yazarsa, kurallar **kaybolmaz — görünmez olur**.
İki paralel kural seti oluşur; paket ikisinden de geçtiği için nft'deki
bir DROP, legacy'deki ACCEPT'i geçersiz kılar. Kural "eklenmiş" görünür
ama hiçbir işe yaramaz.

Teşhis: `iptables-legacy -S FORWARD` ile `iptables-nft -S FORWARD`
karşılaştırılır. Container'ın hangisini kullandığı
`docker exec <ad> readlink -f $(which iptables)` ile görülür.

Gerçek vaka (2026-07-27): ERG'de wg-easy container'ı `xtables-legacy-multi`
kullanıyordu. `wg0.conf` PostUp'ının yazdığı FORWARD ve MASQUERADE
kuralları legacy tabloya düşmüştü, host ise nft okuyordu. Sonuç: wg0
istemcileri bir aydır LAN'a erişemiyordu ve kimse fark etmemişti.
Kural yazan container'lara güvenilmez — **kurallar host'un yetkili
tablosuna, ufw üzerinden konur** (`ufw route allow ...` +
`/etc/ufw/before.rules` içindeki `*nat` bloğu). Böylece `ufw reload`
sonrasında da yaşarlar.

**Doğru yazılmış ve hiçbir şey yapmayan kural.** Bu ailenin kendi başlığı
olmayı hak edecek kadar örneği birikti. Ortak deseni şu: **yapılandırma
doğru, etki yok.** Hata yok, log yok, uyarı yok; `print` çıktısı kuralı
olması gerektiği gibi gösterir.

| Yazılan | Neden işlemedi |
|---|---|
| Script içinde `[find address=192.168.78.0/24]` | `/` komut yolu başlatır, değer kesilir, boş listeye `set` sessiz no-op — ama `:log` yine çalışır |
| Netwatch + `dont-require-permissions=no` | script hiç başlamaz; hata yok, log yok, `run-count` artmaz |
| Spoke'ta `src-address=10.10.10.2/32` | hub maskeliyordu, paket `10.10.10.0` olarak varıyordu — **düzeltildi**, Bölüm 12 |
| Hub'dan spoke'un *arkasındaki* cihaza erişim | aynı maskeleme; istek varıyor, cevap `10.10.10.0`'a adreslendiği için tünele geri dönemiyor, **hiçbir yerde drop sayacı artmıyor** |
| NAT'ta `place-before=[find out-interface=…]` | `find` boş döner, `place-before` boş değer alır, `add` "no such item" ile düşer — çapa olarak yorum kullanılır |
| SHV'de `Priority-Web` mangle | sonraki kural üzerine yazıyor; `passthrough` varsayılanı `yes` |
| `place-before=0,1,2,3,4` | her N o anki listeye göre çözülür, kurallar mevcutların arasına serpilir |
| `move [find …] destination=N` | sessiz no-op; `numbers=` ile de |
| Bir arayüzü silip yeniden yaratmak | ateş duvarı kuralları arayüze **isimle değil dahili ID ile** bağlanır; eski ID'ye bakan her kural `I` (invalid) olur, listede neredeyse normal görünür, tek işaret gözden kaçan bir `;;; no interface` satırıdır |
| Arayüzü silmek peer'ını **silmez** | peer hayatta kalır, sonraki `add` "entry with this name already exists" ile düşer, `/import` orada durur ve dosyanın geri kalanı hiç çalışmaz |
| Çapasız `remove [find comment~"..."]` | desen beklenenden fazlasına uyar. `~"management network"` ifadesi **`input: emergency management network`** kuralını da sildi ve sahanın acil erişimi kapandı. Bu, aynı hatanın **ikinci** tekrarı (ilki `~"interconnect"`). Kural: kaldırma desenleri daima `^` ile çapalanır ve silinecek liste **önce `print` ile görülür** |

**Doğrulama config okunarak değil, sayaçla yapılır:**
`/ip firewall filter print stats`, `/system script print` (`run-count`),
`/system scheduler print detail` (`last-started`),
`/ip route print` (`A` mı `I` mi).

Ve en pahalıya mal olan sonuç: **"elle denedim, çalıştı" hiçbir şey
ispatlamaz.** Yukarıdaki `[find]` ve izin hatalarının ikisi de terminalde
elle kusursuz çalışıyordu; yalnızca script bağlamında ölüydüler.

---

## 9. IP ve Subnet Planı

### LAN şablonu — `192.168.<N>.0/24`

Site başına üçüncü oktet: OFC=77, SVR=78, yeni şantiyeler sırayla 79+.

| Adres | Kullanım |
|---|---|
| `.1` | MikroTik router |
| `.2 – .9` | Pool dışı rezerv (acil manuel IP ihtiyacı) |
| `.10 – .30` | DHCP pool |
| `.31 – .39` | Erişim noktaları (cAP), sabit lease |
| `.121` | Proxima sunucusu (sabit lease) |
| `.122` | Synology NAS (sabit lease) |

**Havuz `.30`'da biter, `.250`'de değil.** Bu tablo 2026-07-19'da
`.10 – .250` yazıyordu ve havuz `.121` ile `.122`'yi kapsıyordu — yani bir
dizüstü, sahanın tamamının bağlı olduğu adresi kapabilirdi. Aşama
dosyalarında 2026-07-28'de düzeltildi, bu tablo **2026-07-30'da**. Havuzun
üstündeki her şey rezervedir.

MikroTik'te static lease pool içinde de tanımlanabilir — lease'li adres başka
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
| ERG | `10.14.x` | `10.14.14.0/24` | `10.14.15.0/24` | `10.13.13.0/24` *(yedek değil — acil durum yönetim ağı, Bölüm 11)* |
| OFC | `10.15.x` | `10.15.15.0/24` | `10.15.16.0/24` | `10.16.16.0/24` *(legacy, blok dışı — dokunulmaz)* |
| SVR | `10.17.x` | `10.17.17.0/24` | `10.17.18.0/24` (gerekirse) | `10.17.0.0/24` (gerekirse) |
| Yeni şantiye | `10.18.x`+ | `10.N.N.0/24` | `10.N.(N+1).0/24` | `10.N.0.0/24` |

**Rezerve bloklar (tahsis edilemez):**
- `10.10.x` — **şantiyeler arası interconnect** (hub-and-spoke, hub =
  SHV MikroTik `bc-wireguard`, port 13231). Bölüm 12. Adres defteri:

  | Adres | Kime |
  |---|---|
  | `10.10.10.1` | SHV — hub |
  | `10.10.10.2` | ERG `wg-bcshv` |
  | `10.10.10.3` | kişisel erişim peer'ı |
  | `10.10.10.10+` | **şantiye router'ları** (SVR `.10`) |

  **Hub 2026-07-30'da `.0`'dan `.1`'e taşındı.** Eski adres bir ağ
  adresiydi ve dört ayrı sessiz arızanın ortak sebebi oldu: spoke'ta
  `gateway=10.10.10.0` yazılan rotalar kabul edilip **Inactive** kalıyordu;
  hub o adrese maskelediği için spoke'ta kaynak-tabanlı kural hiç
  eşleşmiyordu; ve o adrese dönen cevaplar tünele geri geçemediği için
  şantiye router'ının arkasındaki hiçbir cihaza ulaşılamıyordu.

  Taşıma tek taraflıydı: ERG ve SVR'nin peer'ları zaten `10.10.10.0/24`
  aralığını taşıdığı için **hiçbirine dokunulmadı.** Önce `.1` eklendi,
  doğrulandı, sonra `.0` kaldırıldı. Rotalarda hâlâ `gateway=<wg-arayüzü>`
  kullanılır — WireGuard için zaten doğru deyim, ve artık `.1` ile
  `gateway=10.10.10.1` de çalışır.
- `10.13.x` — **acil durum yönetim ağı** (`10.13.13.0/24`). Bu blok
  2026-07-19 envanterinde "ERG wg0 legacy yedek tüneli (ERG↔OFC)" olarak
  kaydedilmişti; **kayıt yanlıştı**. 2026-07-27'de doğrulandı: ERG'de
  wg-easy container'ının sunduğu yönetim VPN'idir, peer'ları kişisel
  cihazlardır. ERG↔OFC bağlantısı `10.10.x` interconnect'idir.
  Kullanımı Bölüm 11'de tanımlıdır.
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
Sunucu ve MikroTik, ERG'in **acil durum yönetim ağına** (`10.13.13.0/24`,
Bölüm 11) outbound peer olarak bağlanır. Ayrıntı ve kurulum orada.

Bu bölümün önceki hâli tünelin ERG **wg1**'e bağlandığını söylüyordu;
yanlıştı. wg1 son kullanıcı VPN'idir — site sunucularını oraya koymak,
her kullanıcı peer'ının yönetim düzlemine erişebilmesi demektir.

### Netwatch failsafe (zorunlu)
Netwatch `.121`'i izler: down → DHCP option 3/6 router'a (`.1`) döner,
up → geri. **Şantiyenin interneti Proxima'ya bağımlı değildir** —
sunucu çökerse yalnızca VPN yönlendirme durur, internet devam eder.

### WAN ve güvenlik
- WAN: varsayılan DHCP client. PPPoE/LTE gerekiyorsa sahada yapılandırılır —
  kitin **tek saha-bağımlı ayarı** budur.
- WAN'dan yönetim erişimi kapalı; WinBox yalnızca LAN + VPN üzerinden.
- Raw chain temiz tutulur (bkz. Bilinen Tuzaklar).

---

## 11. Acil Durum Yönetim Ağı — `10.13.13.0/24`

Uzaktaki bir siteyi yönetmenin, o sitenin **inbound** yapılandırmasına
bağlı olmaması gerekir. Aksi hâlde döngü oluşur: port yönlendirmesini,
NPM'yi ya da VPN endpoint'ini değiştirmek, o değişikliği yapmak için
kullandığın erişimi tehdit eder.

Çözüm yönü tersine çevirmektir: **site dışarı arar.** Yönetim erişimi
hiçbir DSTNAT kuralına, hiçbir açık porta bağlı değildir. Sahada
yönlendirmeler yanlış yapılmış olsa bile siteye ulaşır, düzeltirsin.

ERG bu ağın buluşma noktasıdır (wg-easy, `vpn.ergunay.com:51820`).
Sen nerede olursan ol — ofis, ev, LTE — wg0'a bağlanınca tüm sitelere
ulaşırsın.

### Adres planı

| Aralık | Kime |
|---|---|
| `10.13.13.1` | ERG (wg-easy sunucusu) |
| `10.13.13.2–.9` | Yönetici cihazları (dizüstü, telefon) |
| `10.13.13.10+` | **Site sunucuları** (call-home) |

Mevcut: `.2` CE-Laptop, `.3` CE-IPhone, `.4` Kerem-Direct, `.10` SVR.

### Site tarafı — kurulum

Kutuda **düz WireGuard**, systemd ile. Docker **değil**: Docker geç
kalkabilir, Proxima işleri container'ları yeniden başlatır. Kurtarma
yolu kurtardığı şeye bağlı olamaz.

```ini
# /etc/wireguard/wg-erg.conf   (chmod 600)
[Interface]
PrivateKey = <site>
Address    = 10.13.13.<N>/24

[Peer]
PublicKey    = <ERG wg-easy public key>
PresharedKey = <site>
AllowedIPs   = 10.13.13.0/24
Endpoint     = vpn.ergunay.com:51820
PersistentKeepalive = 25
```

```bash
apt-get install -y wireguard-tools
systemctl enable --now wg-quick@wg-erg
```

**`AllowedIPs` yalnızca `10.13.13.0/24` olmalıdır.** ERG'in LAN'ları
(`192.168.2.0/24`, `192.168.1.0/24`) buraya **yazılmaz** — sitenin kendi
LAN'ı ile çakışırsa kutu kendi ağını kaybeder.

> ⚠️ wg-easy'nin `WG_ALLOWED_IPS` ayarı global şablondur ve ERG'in
> LAN'larını içerir. Site peer'ı wg-easy arayüzünden indirilirse **yanlış
> config çıkar**. Site config'i elle yazılır.

### ERG tarafı — peer ekleme

Peer'lar `/opt/erg/wireguard/wg-easy-data/wg0.json` içinde tutulur
(host'a mount'lu, kalıcı). Çalışan tünelleri düşürmemek için:

1. `wg0.json`'a client kaydı eklenir (kalıcılık),
2. `wg set wg0 peer <pub> preshared-key <dosya> allowed-ips 10.13.13.<N>/32`
   ile canlıya uygulanır — wg-easy **yeniden başlatılmaz**.

### ERG tarafı — yönlendirme (kritik)

Peer'ların birbirini görmesi için ERG'de yönlendirme gerekir. Kurallar
**ufw'ye** konur; container'ın PostUp'ına güvenilmez (bkz. Bölüm 8,
legacy/nft tuzağı):

```bash
ufw route allow in on wg0 out on wg0       # peer-to-peer → sitelere erişim
ufw route allow in on wg0 out on enp3s0    # yönetim ağı → ERG LAN
```

`/etc/ufw/before.rules` içine, `*filter`'dan **önce**:

```
*nat
:POSTROUTING ACCEPT [0:0]
-A POSTROUTING -s 10.13.13.0/24 -o enp3s0 -j MASQUERADE
COMMIT
```

Doğrulama: `ufw reload` sonrasında üç kural da yerinde olmalı. Proxima'nın
kendi zincirleri (`PROXIMA_LAN`, wg1 FORWARD kuralları) reload'dan
etkilenmez — 2026-07-27'de doğrulandı.

### Sürekli açık — neden

Tünel **her zaman açıktır**, "Proxima çökerse devreye girsin" değildir:

- Çöküşü tespit edecek şeyin çalışıyor olması gerekir; kutu bozukken en
  az güvenilecek şey odur.
- Hiç ayağa kalkmamış tünel, çalıştığı **bilinmeyen** tüneldir.
- Maliyeti yok: `PersistentKeepalive=25` ile saniyede ~4 bayt.
- Bedava sağlık sinyali: son handshake, kurtarma yolunun yaşadığını
  ihtiyaç duymadan **önce** gösterir.

### Doğrulama (2026-07-27, SVR ile)

| Sınav | Sonuç |
|---|---|
| Kurulum | handshake 15 sn içinde, ping 1.2 ms, SSH açık |
| Proxima tamamen durdurulunca (`docker compose down`) | tünel ayakta, erişim sürüyor |
| Sunucu yeniden başlatılınca | 30 sn'de kendiliğinden geri geldi |
| Yönetici cihazından siteye | wg0 peer-to-peer üzerinden ulaşıldı |

### Bilinen sınır

ERG tek buluşma noktasıdır; ERG'in interneti giderse aynı anda tüm
sitelerin yönetimi kesilir. Bilinçli kabul edildi (ADM zaten ERG'de).
Karar geri dönülebilir: ikinci bir hedef eklemek, site başına bir peer
eklemektir — yeniden tasarım değil.

Bu ağın üyeliği 2026-07-27'de genişletildi: MikroTik'ler de peer olabilir
ve SVR router'ı `10.13.13.11` olarak dahil edildi (aşama dosyası
`site-router/svr-03-wireguard.rsc`). Böylece "kutu ölürse router'a,
router ölürse kutuya" ilkesi geri geldi. Yeni bir şantiyede **her ikisi
de** peer yapılır; yalnızca biri yapılırsa o cihaz öldüğünde saha kör
kalır.

Not: Proxima kutularının call-home'u 2026-07-27'de `wg-adm`'e
(`10.12.12.0/24`, port 51822) taşındı — bu ağ artık insanlar ve
MikroTik'ler içindir. SVR kutusu `10.12.12.10`.

---

## 12. Şantiyeler Arası Interconnect — `10.10.10.0/24`

Amaç tek cümleyle: **şirket ağındaki bir kişi, hangi şantiyede olursa
olsun, VPN istemcisi açmadan diğer şantiyelerin NAS'larına ulaşabilmeli.**
Yetkilendirme ağın işi değil — Synology kimin neyi göreceğine kendi karar
verir. Router yalnızca hangi *makinelerin* erişilebilir olduğunu belirler:
NAS evet, yazıcı hayır.

### Topoloji: hub-and-spoke, hub = SHV

Siteler birbirine değil, **yalnızca hub'a** bağlanır. N. şantiyeyi
eklemek = hub'a bir peer + yeni router'da bir aşama dosyası. Mevcut
hiçbir cihaza dokunulmaz. İkili bağlarla (mesh) her yeni saha N-1 ayrı
düzenleme demek olurdu ve unutulan biri "yarısı çalışan, kimsenin
açıklayamadığı" bir ağ üretirdi.

**Hub neden SHV, neden ERG değil:** yedekleme akışı zaten
`Şantiye NAS → Merkez Buro NAS`, yani trafiğin ağırlık merkezi ofiste.
ERG bir ev hattıdır; her sahanın birbirine erişimi ev upload'ına ve ev
internetinin ayakta olmasına bağlanmamalı. **ERG yönetim hub'ı olarak
kalır** (Bölüm 11) ve interconnect üzerinden her yere ulaşır. İki düzlem
ayrıdır ve ayrı kalmalıdır: yönetim ağının tek işi "her şey bozulduğunda
ayakta olmak", veri yolu politikasıyla iç içe geçerse o özelliğini
kaybeder.

### Adresleme kuralı

Cihazlara **kendi yerel adreslerinden** erişilir — `192.168.77.10`,
`192.168.78.1`, `192.168.2.91`. Tünel adresleri günlük kullanımda
görünmez. Bölünme şudur: **`10.x` acil durum yolu, `192.168.x` günlük
yol.**

Spoke'ların hub peer'ında tek tek LAN değil **supernet** yazılır:

```
allowed-address = 10.10.10.0/24, 192.168.2.0/24, 192.168.64.0/18
```

`192.168.64.0/18` bloğu 192.168.64–127'yi kapsar, yani gelecekteki her
şantiye (79, 80, …) baştan izinlidir. Spoke'un kendi LAN'ı da bu /18'in
içindedir; zararsız, çünkü connected route daha spesifiktir ve yerel
trafik tünele girmez.

**Şantiye LAN'ları bu /18 içinden seçilir** (OFC 77, SVR 78, sıradaki
79…). Blok dışına çıkan bir LAN, supernet'in verdiği "tek cihaza dokun"
özelliğini bozar.

### Politika — hedefe göre, kullanıcıya göre değil

Kurallar **hedef sitenin kendi router'ında** durur; kaynakta değil. Ofis
için SHV, şantiye için o şantiyenin router'ı karar verir — kural ile
koruduğu şey aynı yerde kalır.

**Ofis (SHV, hub):**

| Kaynak | Erişim |
|---|---|
| `10.10.10.2-.3` (ERG kutusu, yönetici peer'ı) | tam ofis LAN'ı — deploy yolu |
| `192.168.2.0/24` (ERG LAN) | tam ofis LAN'ı |
| Şantiye LAN'ları | yalnızca NAS `192.168.77.10`, gerisi drop |
| Şantiye LAN'ları → ERG | yalnızca kutu `192.168.2.91`, ev LAN'ı drop |

**Şantiye router'ları:** şantiye *kullanıcılarından* gelen trafik **yalnızca
NAS'a** ulaşır. Router'ın kendisi input zinciriyle erişilebilir kalır —
kendisine giden paket forward'a hiç uğramaz.

### Yönetim düzlemi — `10.13.13.0/24` her sahanın her cihazına

Karar (2026-07-30): **yönetim ağında olmak yetkinin kendisidir.** O ağdaki
bir cihaz, her şantiyenin her cihazına, cihazın **kendi yerel adresiyle**
erişir — `192.168.78.1` router, `192.168.78.121` Linux sunucu,
`192.168.78.30` erişim noktası. Yönetici ayrı bir adres uzayı öğrenmez.
ERG kapsam dışıdır (Keenetic'in arkasında, ayrı iş).

**ERG, bu trafiği interconnect'e sokarken `10.10.10.2`'ye çevirir**
(`/etc/ufw/before.rules` içindeki `*nat` bloğunda kalıcı SNAT). Zorunlu,
çünkü saha `10.13.13.0/24`'e dönemez: şantiye router'ı o ağı **kendi
call-home tünelinden connected rota** olarak bilir ve hiçbir statik rota
onu yenemez; ERG de o peer'da yalnızca `10.13.13.11` kaynağını kabul eder.
Dönüş paketleri WireGuard tarafından, hiçbir yere log düşmeden düşerdi.

Bunun doğrudan sonucu: **saha router'ındaki yönetim kuralı `10.10.10.2`'yi
eşleştirir, `10.13.13.0/24`'ü değil.** İkincisi yazılırsa kural sonsuza
kadar sıfırda kalır. Bir saat boyunca öyle kaldı.

Bedeli: saha logları yöneticiyi tek tek değil `10.10.10.2` olarak görür.
Yönetim düzlemi küçük ve zaten tek bir güvenilen kaynak olarak tanımlı
olduğu için kabul edildi.

**Hub'ın örtülü maskelemesi kapatıldı — ve bu bir kolaylık değil, bir
arıza düzeltmesiydi.** SHV'de matcher'sız bir
`srcnat masquerade out-interface=bc-wireguard` kuralı vardı; tünelden çıkan
**her** paketi router'ın kendi `10.10.10.0` adresine çeviriyordu. İki sonucu
oldu, biri can sıkıcı biri ölümcül:

- Spoke'ta kaynak-tabanlı kural hiç eşleşmiyordu, çünkü kim gönderirse
  göndersin paket aynı adresten geliyordu. `src-address=10.10.10.2/32`
  kabul edilir, listelenir, sayacı sıfırda kalır.
- **`10.10.10.0`'a adreslenen bir cevap, spoke tarafından tünele geri
  iletilemiyordu.** Sonuç: bir şantiye router'ının *arkasındaki* hiçbir
  cihaza hub'dan ulaşılamıyordu. İstekler varıyor ve kabul ediliyor,
  cevaplar kayboluyor, hiçbir yerde drop sayacı artmıyor. Hub şantiyenin
  **router'ına** ulaşıyor, arkasındaki hiçbir şeye ulaşamıyor.

Bu, bu router'ın eski `.0` adresinin sessizce yol açtığı **dördüncü**
arızaydı. Kalıcı çözüm ona normal bir host adresi vermektir; şimdilik
uygulanan dar düzeltme, çalışan bir üretim adresine dokunmayan şu kuraldır
(`shv-hub-interconnect.rsc` içinde):

```
/ip firewall nat
add chain=srcnat action=accept dst-address=192.168.64.0/18 \
    out-interface=bc-wireguard   # blanket masquerade'in ÜSTÜNE
```

Şantiye aralığına kapsandığı için ofis→internet (`out ether5`) ve
ofis→ERG (`192.168.2.x`, /18 dışında) eskisi gibi maskelenmeye devam eder.

Sonuç olarak **kaynak adresleri artık tünelde korunuyor**: spoke'ta
kaynak-tabanlı kural yazılabilir, şantiye NAS'ının logları uzak cihazı
gerçek adresiyle görür ve "maskeleme yerine açık yönlendirme" ilkesi bu
tünelde de geçerlidir. Yalnızca **hedefi ofis LAN'ı olan** trafik hâlâ
maskelenir (NAT kuralı 0, `out bridge1`).

**Blanket kural yazılmaz.** İlk taslakta şantiye router'larında
`src=10.10.10.0/29 → tam LAN` vardı. Kaldırıldı: yönetim ağı bilinçli
olarak `10.13.13.0/24` ile sınırlanmışken, o kural aynı yere **ikinci ve
daha geniş** bir yol açıyordu — `.31–.39`'daki cAP'ler dâhil, ki onlar
"ERG'den erişilemez" diye kayıtlıydı. Biri tasarımla dar, diğeri kazayla
geniş iki örtüşen yol, ikisinden de kötüdür; çünkü denetlenmeyen hep
geniş olanıdır. Bir yeteneğe ihtiyaç varsa **tek hosta indirgenmiş tek
kural** olarak, yorumunda gerekçesiyle yazılır.

Aynı sebeple hub'daki kural `/29` değil `10.10.10.2/31` — yalnızca var
olan iki cihaz. Şantiye router'ları `.10+`'da ve bu aralığın dışında;
yöneticiyle saha kullanıcısını ayıran şey bu.

### Aşama dosyaları

- `site-router/shv-hub-interconnect.rsc` — hub politikası, yeniden
  çalıştırılabilir (kendi kurallarını silip yeniden kurar). Peer'lar
  içinde **değildir**: politika tazelemek bir sahanın tünelini
  düşürmemeli.
- `site-router/svr-06-interconnect.rsc` — spoke tarafı, şantiye başına.

**Spoke'un özel anahtarı dosyada açıkça set edilir**, RouterOS'un kendi
üretmesine bırakılmaz; anahtar ERG'de `/root/svr-mikrotik-keys.txt`
içinde durur ve dosyaya yer tutucu girer (aşama 3 ile aynı desen). Sebep:
router sıfırlanırsa dosyayı yeniden import etmek **aynı** anahtarı geri
getirir ve hub'a dokunulmaz. Aksi hâlde sıfırlama anahtarı sessizce
değiştirir — arayüz kalkar, hub peer'ı hâlâ listeler, el sıkışma hiç
olmaz ve bunu raporlayan hiçbir şey yoktur. Bu tam olarak bir kez yaşandı.

**Aşama sırası 1→2→3→4→(5)→6, istisnasız.** Hem aşama 2 hem aşama 6
`/ip service ssh|winbox address` listelerini **üzerine yazar**, eklemez.
Aşama 2'yi 6'dan sonra çalıştırmak interconnect'i o listelerden sessizce
düşürür ve router `10.10.10.x`'ten cevap vermeyi bırakır.

### Yakalanan tuzaklar (2026-07-28)

- **`gateway=10.10.10.0` sessizce ölü.** Bkz. Bölüm 9. Rotalar `Inactive`
  kalır, trafik başka bir yolu bulur ve her şey çalışıyor görünür.
  Bayraklara bakılmadan hiçbir şey doğrulanmış sayılmaz.
- **RouterOS kural sıralaması üç denemeden ikisinde sessizce çalışmıyor.**
  `place-before=0,1,2,3,4` kuralları mevcutların *arasına* serper (her N o
  anki listeye göre çözülür). `move [find …] destination=N` ve
  `move numbers=[find …] destination=N` hiçbir şey yapmaz. Çalışan tek
  yol: tek bir sabit çapaya karşı `add … place-before=[find comment="…"]`.
- **Çapa seçerken yorumda `/` olmamalı** — tırnaksız slash `find`
  ifadesini keser (netwatch failsafe'inde kayıtlı aynı tuzak).
- **Ping tek başına politikayı ispatlamaz.** Ofis zincirinde koşulsuz bir
  ICMP accept var; interconnect bloğu onun altında kalırsa engellenmesi
  gereken hedefler ping'e cevap verir ve kurallar tek tek doğru görünür.
  Doğrulama drop kuralının **paket sayacıyla** yapılır.

### Bilinen sınır — hub'ın çıplak `accept`'i (ölçüldü 2026-07-30)

Hub'ın `forward` zincirinde matcher'sız bir `action=accept` vardır ve
altındaki her kural, **kendi son drop'u dâhil**, ölüdür (o drop bugüne
kadar sıfır paket saydı). Interconnect kuralları bu yüzden zincirin
**en tepesine** konur; o güne kadar buraya kural *eklenir*, mevcut kural
kaldırılmaz.

Temizliğin riski "ne kesileceğini bilmemek"ti. Artık bilmiyor değiliz:
çıplak kuralın **üstüne**, meşru kategorileri sayan `accept` kuralları
konuldu (accept'in üstüne accept — hiçbir paketin kaderi değişmez, yalnızca
sayaçlar yerine oturur). Sonuç:

| Kural | ~50 sn'de paket |
|---|---|
| `established, related, untracked` | 76.648 |
| LAN → internet (`new`) | 2.144 |
| yayınlanan servisler (`new`) | 16 |
| ofis → interconnect (`new`) | 0 |
| **çıplak accept (artık)** | **2** |

Yani dört kategori trafiğin %99,99'unu kapsıyor ve çıplak kural neredeyse
boş. **Belirleyici kelime `untracked`:** ilk denemede yalnızca
`established,related` yazılmıştı ve artık 45 saniyede 143.855 pakette
kalmıştı. Bu kelime SVR'nin standart şablonunda zaten var; SHV elle
kurulduğu için eksikti. Raw chain boş, yani `notrack` kaynaklı değil.

Kalan artığı adlandırmak için çıplak kuralın üstüne bir `action=log`
kuralı eklendi. (Bir gece boyunca "doğrulanmamış" diye kayıtlıydı: 40
saniyede sayacı sıfır kalmıştı. Enstrüman sağlammış, **örnek kısaymış** —
6,5 saatte 7.050 paket yazdı. Aynı kapsam hatası, bu sefer ölçüm tarafında.)

### Çözüldü — 2026-07-30

Log 906 paketlik bir örnekte artığı ikiye ayırdı:

- **%99 `connection-state:invalid`** — LAN→internet, conntrack bağlantıyı
  kapattıktan sonra gelen TCP FIN/RST. Düşürülmesi zaten doğru olan trafik;
  saha şablonunda ikinci kural olarak var, bu router eski olduğu için yoktu.
- **%1 `new,dnat`, `bridge1→bridge1`** — **hairpin NAT**. Ofis içinden
  sitenin kendi public adresine vuran cihazlar. Küçük, meşru ve bir
  default-drop'un sessizce öldüreceği tam da bu. Denetimin var olma sebebi
  bu kuralı bulmaktı.

İkisi de kapsandıktan sonra çıplak kural **sıfır paket** almaya başladı
(50 sn arayla üç ölçüm: 6111 / 6111 / 6111 — donmuş; o 6111 de dosyanın
kuralları silip yeniden eklediği birkaç saniyenin artığıydı).

Ardından çıplak kural **devre dışı bırakıldı** (silinmedi — geri alması
`disabled=no`). Zincir ilk kez kendi son drop'uyla kapanıyor. Ofisten,
VPN kapalı telefonla doğrulandı: Wi-Fi'dan hairpin, LTE'den aynı servis,
sıradan gezinme — üçü de çalışıyor; son drop sıfır paket, logda tek satır
yok. **Silme işlemi bir hafta geçtikten sonra** yapılacak: eldeki kanıt bir
gece ve bir sabah, pazar 03:00 yedeğini kapsamıyor.

Kalıntı: `Allow Turkcell VoWiFi` kuralı (udp 500/4500, any→any) blokun
üstünde kalır, yani bir şantiye herhangi bir ofis makinesine o iki porttan
ulaşabilir. IKE trafiği; çıplak accept temizliğiyle birlikte kalkar.

---

## 13. Saha Sırları — ERG'de Nerede Durur

Aşama dosyaları git'te durur ve **hiçbir sır içermez**; yerlerinde yer
tutucu vardır. Değerler yalnızca ERG'de, `root`'a ait `0600` dosyalarda:

| Dosya | İçerik | Kullanıldığı yer |
|---|---|---|
| `/root/svr-mikrotik-keys.txt` | `wg-erg` PrivateKey + PresharedKey; `bc-shv` PrivateKey + PublicKey | Aşama 3 (yönetim tüneli), aşama 6 (interconnect) |
| `/root/svr-wifi-psk.txt` | Ofis Wi-Fi parolası | Aşama 4 (CAPsMAN) |

Bölünme kasıtlı: şablonlar her sahaya kopyalanır, sırlar kopyalanmaz. Bir
sır dosyaya gömülürse tüm sahalara dağılır ve git geçmişinden çıkarılamaz.

**Neden ERG'de.** Sıfırlama sonrası aşama 4'ü ya da 6'yı yeniden uygulamak
için değerin bir yerde durması gerekir; aksi hâlde her sıfırlama bir insanı
bekler. `bc-shv` anahtarının yazılı olmasının ayrı bir sebebi var: aynı
anahtar geri gelmezse hub sessizce el sıkışmayı bırakır (Bölüm 12).

**Dosyaya parola yazarken kabuk geçmişine düşürme.** `printf '%s' 'PAROLA' |
sudo tee …` biçimi parolayı `~/.bash_history`'ye ve argüman listesine
yazar — dosyanın kendisinden kötü bir yer, çünkü `0600` mantığıyla
korunmuyor. Doğrusu stdin'den okumak:

```bash
umask 077
sudo sh -c 'cat > /root/svr-wifi-psk.txt && chmod 600 /root/svr-wifi-psk.txt'
# parolayı yaz, Enter, sonra Ctrl-D
sudo wc -c /root/svr-wifi-psk.txt   # karakter sayısı + 1 olmalı
```

`cat` girdiyi harfi harfine alır; parolada tırnak, `$`, `!` olsa bile
bozulmaz — `printf '...'` biçiminin bozulacağı yer tam burasıdır.

### Bakım borcu: bu kopyalar bayatlayabilir

**Ofis Wi-Fi parolası değişirse `/root/svr-wifi-psk.txt` sessizce
bayatlar.** Aşama 4 eski parolayı kurar, belirtisi de "cAP'ler adopt oldu
ama telefonlar bağlanmıyor" olur — sebebi aramak zaman alır. Wi-Fi parolası
her değiştiğinde bu dosya da güncellenir. Aynı şey SSID standardı için de
geçerli: `Buro` / `Buro_5G` her sahada aynıdır ve **aynı ad aynı parolayı
zorunlu kılar**, o yüzden sahaya özel parola üretilmez.

---

## 14. Erişim Matrisi — kim nereden nereye

Ölçüm tarihi **2026-07-30**. Her satır ya cihazdan okundu ya trafikle sınandı;
hangisi olduğu işaretli. **Hafızadan yazılmış hiçbir satır yok** — bu bölümün
ilk hâli wg-easy peer isimlerini eski bir nottan almıştı ve silinmiş bir
kullanıcıyı listede gösteriyordu.

### Yönetim ağı — wg-easy, `10.13.13.0/24`

Üyelik **ölçüldü** (`wg show wg0` ve `wg0.json` birebir):

| Adres | Kim |
|---|---|
| `.2` | CE-Laptop |
| `.3` | CE-IPhone |
| `.11` | SVR-Mikrotik (router, kişi değil) |

Bugün itibarıyla **üyelik yetkinin kendisidir**: bu ağdaki bir cihaz her
sahanın her cihazına ulaşır. İkinci bir kapı yok — peer eklemek yetki
vermektir.

| Hedef | Erişim | Nasıl doğrulandı |
|---|---|---|
| ERG sunucusu + ERG LAN | tam | trafikle |
| Tüm ofis LAN'ı | tam | trafikle |
| Tüm SVR LAN'ı | tam | trafikle |
| SVR kutusu (`10.12.12.10`) | tam | trafikle |

Yol: ERG bu trafiği interconnect'e sokarken `10.10.10.2`'ye çevirir (Bölüm 12).

### Diğer aktörler

| Kaynak | Erişim | Doğrulama |
|---|---|---|
| ERG kutusu `10.10.10.2` | tüm ofis LAN'ı, tüm SVR LAN'ı | trafikle |
| Kişisel peer `10.10.10.3` | tüm ofis LAN'ı; **SVR LAN'ına erişemez** | kuraldan |
| Ofis LAN `192.168.77.x` | SVR sahasında yalnızca NAS `192.168.78.122` | kuraldan |
| Şantiye LAN `192.168.78.x` | ofiste yalnızca NAS `192.168.77.10`; ERG'de yalnızca kutu `192.168.2.91` | trafikle + drop sayacıyla |

**Ofis LAN'ından ERG'ye erişim düzgün bir sınır değil.** Ölçüldü: ERG kutusu
`.91` ✓, SVR kutusu `.96` ✓, Keenetic `.1` ✗. ufw'de `wg-bcshv → enp3s0` kuralı
yok, yani bu bir ateş duvarı sınırı değil. Muhtemel açıklama (**çıkarım,
ölçülmedi**): ofis trafiği ERG'ye `10.10.10.1` olarak varıyor ve yalnızca o
adrese dönüş rotasını bilen cihazlar cevap verebiliyor.

### İnternetten

| Saha | Açık |
|---|---|
| SHV | `2210/tcp` (input'ta, her yerden), `13231/udp`; DSTNAT → NAS `.10`: 5000, 5001, 22022, 1194, 5005, 5006, 21115-21119 · NVR `.3`: 8000 · Proxima `.121`: 5555 |
| SVR | 5555 (ProximaVPN), 80/443 (NPM), 5556 + 8443 (sing-box) |
| ERG | ufw'de 22, 80, 443, 53, 5050, 5555, 8443, 51820, 51821, 51822, 8086, 8090, 7878, 8989, 9696, 19999, 12345, 3478, 5349, 20000-20100, 49152-49252 — hepsi `Anywhere` |

**ERG'nin ufw listesi perimetre değildir.** "Keenetic bir portu yönlendirirse
kim girebilir"i anlatır. Gerçek perimetre Keenetic'tir ve yönlendirme tablosu
buradan görülemez — bu listeye bakıp "şu port açık" demek yanlıştır.

### Kapsanmayan

**ProximaVPN istemcilerinin (wg1/wg2) erişimi bu turda haritalanmadı.** O
erişimi MikroTik değil, sahanın Proxima kutusundaki kurallar belirler.

### Bilinen tutarsızlıklar

- `10.10.10.3` ofise tam, SVR'ye hiç erişiyor — ya yönetim ağına taşınmalı ya
  da saha kuralına eklenmeli.
- Şantiyeler ERG'de yalnızca kutuya ulaşabilirken ofis LAN'ı için böyle bir
  sınır yok. Bilinçli bir karar değil, eski bir kuraldan geliyor.
- SHV'nin input zincirinde default drop yok ve `2210/tcp` her yerden açık;
  SVR'de input kapalı. İki saha aynı standartta değil.
