"""A site that was installed by hand has to be adoptable.

write_hosts_yml() skips any server without an ssh_host and calls it "registered
by hand, not provisioned by ADM". That was fine while every site came from the
provisioning flow, which is the only thing that ever set an ssh_host — and that
flow also runs the installer, opens a call-home tunnel and claims the instance,
none of which an already-running site needs or wants.

SHV is that site: installed and deployed by hand, with its own admins, keys and
seventeen groups. It reaches ERG over a tunnel that already exists, and it must
be possible to say so and have Ansible pick it up.

These guard the contract the adopt path rests on. The Flask layer that now lets
those fields be set is not exercised here.
"""

import pytest

from core import inventory_writer as iw


@pytest.fixture
def written(monkeypatch, tmp_path):
    """Capture hosts.yml instead of writing into the repository."""
    target = tmp_path / "hosts.yml"
    monkeypatch.setattr(iw, "HOSTS_YML", str(target))
    monkeypatch.setattr(iw, "INVENTORY_DIR", str(tmp_path))
    monkeypatch.setattr(iw, "_live_tunnels", lambda: {})

    import yaml

    def _read():
        return yaml.safe_load(target.read_text(encoding="utf-8"))

    return _read


def _site(name, **over):
    row = {
        "name": name,
        "ssh_host": "192.168.77.121",
        "ssh_port": 22,
        "ssh_user": "can",
        "server_code": name.upper(),
        "url": "http://example",
        "callhome_ip": None,
        "callhome_pubkey": None,
    }
    row.update(over)
    return row


# ── what lands in proxima_sites ──────────────────────────────────────────────

def test_a_site_with_an_ssh_host_is_offered_to_ansible(written):
    iw.write_hosts_yml([], [_site("shv")])
    hosts = written()["all"]["children"]["proxima_sites"]["hosts"]
    assert "shv" in hosts
    assert hosts["shv"]["ansible_host"] == "192.168.77.121"
    assert hosts["shv"]["server_code"] == "SHV"


def test_a_site_without_an_ssh_host_is_skipped(written):
    """This is the line the adopt path exists to get past."""
    iw.write_hosts_yml([], [_site("registered-only", ssh_host=None)])
    children = written()["all"]["children"]
    assert "proxima_sites" not in children or "registered-only" not in (
        children["proxima_sites"].get("hosts") or {})


def test_root_is_assumed_become_is_not_set(written):
    iw.write_hosts_yml([], [_site("shv", ssh_user="root")])
    entry = written()["all"]["children"]["proxima_sites"]["hosts"]["shv"]
    assert entry["ansible_user"] == "root"
    assert "ansible_become" not in entry


def test_a_non_root_user_is_given_become(written):
    iw.write_hosts_yml([], [_site("shv", ssh_user="can")])
    entry = written()["all"]["children"]["proxima_sites"]["hosts"]["shv"]
    assert entry["ansible_user"] == "can"
    assert entry["ansible_become"] is True


def test_an_unusual_port_is_written(written):
    iw.write_hosts_yml([], [_site("shv", ssh_port=2222)])
    entry = written()["all"]["children"]["proxima_sites"]["hosts"]["shv"]
    assert entry["ansible_port"] == 2222


def test_port_twenty_two_is_not_written(written):
    """Ansible's default; writing it adds noise to every diff for nothing."""
    iw.write_hosts_yml([], [_site("shv", ssh_port=22)])
    assert "ansible_port" not in (
        written()["all"]["children"]["proxima_sites"]["hosts"]["shv"])


# ── which address is chosen ──────────────────────────────────────────────────

def test_an_address_is_used_when_no_tunnel_has_answered(written):
    """SHV has no callhome address. Its existing tunnel to ERG is the box's own
    wg0, not one ADM registered, so ansible_host has to fall back to the address
    that is reachable — which is how `skip_callhome=true` stays safe."""
    iw.write_hosts_yml([], [_site("shv")])
    entry = written()["all"]["children"]["proxima_sites"]["hosts"]["shv"]
    assert entry["ansible_host"] == "192.168.77.121"


def test_a_tunnel_is_preferred_once_it_carries_traffic(written, monkeypatch):
    # handshakes() returns SECONDS SINCE each peer was last heard from, not a
    # timestamp — the age is what TUNNEL_FRESH_SECONDS is compared against.
    monkeypatch.setattr(iw, "_live_tunnels", lambda: {"pubkey-a": 10})
    iw.write_hosts_yml([], [_site("shv", callhome_ip="10.12.12.11",
                                  callhome_pubkey="pubkey-a")])
    entry = written()["all"]["children"]["proxima_sites"]["hosts"]["shv"]
    assert entry["ansible_host"] == "10.12.12.11"
    assert entry["mgmt_tunnel_host"] == "10.12.12.11"
    assert entry["public_host"] == "192.168.77.121"


def test_an_allocated_but_dead_tunnel_is_not_trusted(written, monkeypatch):
    """An address on the register means a key was issued, not that anything is
    listening. Pointing Ansible at it is how a provision fails against a box
    whose own address was reachable the whole time."""
    monkeypatch.setattr(iw, "_live_tunnels",
                        lambda: {"pubkey-a": iw.TUNNEL_FRESH_SECONDS + 60})
    iw.write_hosts_yml([], [_site("shv", callhome_ip="10.12.12.11",
                                  callhome_pubkey="pubkey-a")])
    entry = written()["all"]["children"]["proxima_sites"]["hosts"]["shv"]
    assert entry["ansible_host"] == "192.168.77.121"
    assert entry["mgmt_tunnel_host"] == "10.12.12.11"


def test_exit_nodes_are_untouched_by_a_site_being_added(written):
    exit_node = {
        "name": "erg-pl", "ip": "10.12.12.100", "server_type": "vpn_exit",
        "status": "active", "ssh_port": 22, "location": "PL", "provider": "BlueVPS",
        "callhome_ip": None, "callhome_pubkey": None,
    }
    iw.write_hosts_yml([exit_node], [_site("shv")])
    children = written()["all"]["children"]
    assert "erg-pl" in children["vpn_exit"]["hosts"]
    assert "shv" in children["proxima_sites"]["hosts"]


def test_a_decommissioned_node_is_left_out(written):
    dead = {
        "name": "erg-old", "ip": "10.12.12.99", "server_type": "vpn_exit",
        "status": "decommissioned", "ssh_port": 22,
        "callhome_ip": None, "callhome_pubkey": None,
    }
    iw.write_hosts_yml([dead], [])
    children = written()["all"]["children"]
    assert "vpn_exit" not in children or "erg-old" not in children["vpn_exit"]["hosts"]