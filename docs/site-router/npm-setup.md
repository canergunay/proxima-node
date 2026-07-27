# Reverse proxy setup (NPM) — on site

The proxy itself is installed by the Proxima installer. Nothing below needs a
terminal: it is all done in a browser, and it can only be done **after** the
site's internet line is live and the router is forwarding ports 80 and 443.

That order is not a preference. Certificates are issued by a service that
connects back to this address over port 80 from the internet. On a bench, with
no line and no forwarding, the request cannot succeed no matter what is typed.

**Time:** about 20 minutes.

---

## Before you start

| | |
|---|---|
| The site's internet line | Live |
| The router | Built, ports 80 and 443 forwarded to the Proxima box |
| DNS records | The four names below pointing at the site's public address |
| A browser | On any device on the site network |

Check the names resolve before going further. From any machine:

```
nslookup svr-p.fs-bc.net
```

It must answer with the site's public address. If it does not, stop — every
certificate request below will fail and the failure message will not tell you
that DNS is the reason.

---

## 1. Open the proxy admin page

In a browser on the site network:

```
http://192.168.78.121:81
```

First login, which is the same on every fresh install:

| | |
|---|---|
| Email | `admin@example.com` |
| Password | `changeme` |

It immediately asks you to set a real name, email and password. Do that now and
put the new password in the password manager. There is no recovery: losing it
means reinstalling the proxy and re-issuing every certificate.

---

## 2. Add the four services

For each row in the table below: **Hosts → Proxy Hosts → Add Proxy Host**.

On the **Details** tab:

| Field | Value |
|---|---|
| Domain Names | the name from the table (press Enter after typing it) |
| Scheme | `http` |
| Forward Hostname / IP | the address from the table |
| Forward Port | the port from the table |
| Block Common Exploits | on |
| Websockets Support | on |

Then the **SSL** tab, before saving:

| Field | Value |
|---|---|
| SSL Certificate | *Request a new SSL Certificate* |
| Force SSL | on |
| HTTP/2 Support | on |
| I Agree to the Let's Encrypt Terms | tick |

Save. It takes 10–30 seconds while the certificate is issued.

### The four services

| Domain | Forward to | Port | What it is |
|---|---|---|---|
| `svr-p.fs-bc.net` | `192.168.78.121` | `5050` | Proxima panel |
| `svr.fs-bc.net` | `192.168.78.122` | `5000` | NAS web interface |
| `svr-d.fs-bc.net` | `192.168.78.121` | `7575` | dashboard |
| `svr-n.fs-bc.net` | `192.168.78.122` | `5000` | NAS, direct file access |

Add the Proxima panel first. If its certificate is issued, the whole chain —
DNS, forwarding, and the proxy — is working, and any later failure is that
one service rather than the setup.

---

## 3. When a certificate fails

The message shown is usually generic. In practice it is nearly always one of
these, in this order:

**The name does not resolve, or resolves elsewhere.** Check with `nslookup`
from outside the site, not from inside — a router's own DNS entries can make a
name look correct locally while the internet sees nothing.

**Port 80 is not reaching the box.** The certificate service connects *inward*
on port 80. Forwarding only 443 is a common and invisible mistake: the site
works, and certificates never issue.

**Something else already holds port 443.** A NAS web interface is the usual
culprit. The office site runs its proxy on 5443 for exactly this reason. If
that is the case here, tell Can before changing anything — the port is
referenced in the router configuration too.

---

## 4. What must not be added

**The VPN is not proxied and gets no name.** Not here, not in DNS, not
anywhere. It is reached on the site's bare IP address, on its own ports, and
that is deliberate: a DNS record would tell anyone examining the domain that a
VPN exists at this site and where it is.

**File sharing does not pass through the proxy.** It is not an HTTP service.
`svr-n.fs-bc.net` above is the NAS *web* interface; file access happens
directly to the NAS by its own address.

---

## 5. Check it worked

From outside the site — a phone on mobile data is the easiest way:

```
https://svr-p.fs-bc.net
```

The Proxima login page, with a valid certificate and no browser warning.

A warning about the certificate means it was not issued and the proxy fell
back to its self-signed one. Go back to step 3.
