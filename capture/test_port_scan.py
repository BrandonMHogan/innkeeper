"""Behavioral unit tests for port_scan._run_and_post_scan, exercising
payload-construction logic against a mocked nmap.PortScanner rather than
a real scan or real network call. Fixture-free, pure pytest + monkeypatch —
mirrors the backend's fixture-free pure-function test style."""

from unittest.mock import MagicMock

import httpx

from port_scan import API_URL, _run_and_post_scan


def test_run_and_post_scan_posts_only_open_ports(monkeypatch):
    scanner = MagicMock()
    scanner.all_hosts.return_value = ["10.0.0.5"]
    scanner.__getitem__.return_value = {
        "tcp": {
            22: {"state": "open"},
            23: {"state": "open"},
            9999: {"state": "closed"},
        }
    }

    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return MagicMock()

    monkeypatch.setattr(httpx, "post", fake_post)

    _run_and_post_scan(scanner, 7, "10.0.0.5")

    assert captured["url"] == f"{API_URL}/api/capture/scan"
    assert captured["json"] == {"device_id": 7, "open_ports": [22, 23]}


def test_run_and_post_scan_handles_unresponsive_host(monkeypatch):
    scanner = MagicMock()
    scanner.all_hosts.return_value = []  # target did not respond

    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append(json)
        return MagicMock()

    monkeypatch.setattr(httpx, "post", fake_post)

    _run_and_post_scan(scanner, 3, "10.0.0.9")

    assert len(calls) == 1
    assert calls[0] == {"device_id": 3, "open_ports": []}


def test_run_and_post_scan_swallows_post_exception(monkeypatch):
    scanner = MagicMock()
    scanner.all_hosts.return_value = ["10.0.0.5"]
    scanner.__getitem__.return_value = {"tcp": {22: {"state": "open"}}}

    def fake_post(url, json=None, timeout=None):
        raise httpx.ConnectError("network failure")

    monkeypatch.setattr(httpx, "post", fake_post)

    # Must return normally, not raise.
    _run_and_post_scan(scanner, 1, "10.0.0.5")
