"""Phone support: HTTPS phone mode and pages that work on small screens."""

import re
import stat
from pathlib import Path

import flask
import pytest

import server

CLIENT_DIR = Path(__file__).resolve().parents[2] / "client"
PAGES = sorted(CLIENT_DIR.glob("*.html"))


def test_certificate_covers_the_requested_hosts(tmp_path):
    cert, key = server.ensure_certificate(tmp_path, {"localhost", "127.0.0.1", "192.168.1.50", "mac.local"})
    assert server.certificate_hosts(cert) == {"localhost", "127.0.0.1", "192.168.1.50", "mac.local"}
    assert key.exists()


def test_private_key_is_only_readable_by_the_owner(tmp_path):
    _, key = server.ensure_certificate(tmp_path, {"localhost"})
    assert stat.S_IMODE(key.stat().st_mode) == 0o600


def test_certificate_is_reused_so_the_phone_accepts_it_once(tmp_path):
    cert, _ = server.ensure_certificate(tmp_path, {"localhost", "192.168.1.50"})
    first = cert.read_bytes()
    server.ensure_certificate(tmp_path, {"localhost", "192.168.1.50"})
    assert cert.read_bytes() == first


def test_certificate_is_remade_when_the_ip_changes(tmp_path):
    cert, _ = server.ensure_certificate(tmp_path, {"localhost", "192.168.1.50"})
    first = cert.read_bytes()
    server.ensure_certificate(tmp_path, {"localhost", "10.0.0.7"})
    assert cert.read_bytes() != first
    assert "10.0.0.7" in server.certificate_hosts(cert)


def test_broken_certificate_file_is_replaced(tmp_path):
    (tmp_path / "cert.pem").write_text("not a certificate")
    (tmp_path / "key.pem").write_text("not a key")
    cert, _ = server.ensure_certificate(tmp_path, {"localhost"})
    assert server.certificate_hosts(cert) == {"localhost"}


@pytest.fixture
def captured_run(tmp_path, monkeypatch):
    monkeypatch.setenv("BCR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(server, "BASE_DIR", tmp_path)
    monkeypatch.setattr(server, "local_network_ip", lambda: "192.168.1.50")
    calls = {}

    def fake_run(app, **kwargs):
        calls["app"], calls["kwargs"] = app, kwargs

    monkeypatch.setattr(flask.Flask, "run", fake_run)
    return calls


def test_phone_mode_serves_https_on_the_network_with_secure_cookies(captured_run, tmp_path, capsys):
    server.main(["--phone"])
    kwargs = captured_run["kwargs"]
    assert kwargs["host"] == "0.0.0.0"
    assert kwargs["ssl_context"] == (str(tmp_path / "certs" / "cert.pem"), str(tmp_path / "certs" / "key.pem"))
    assert captured_run["app"].config["SESSION_COOKIE_SECURE"] is True
    assert "https://192.168.1.50:5500" in capsys.readouterr().out
    assert "192.168.1.50" in server.certificate_hosts(tmp_path / "certs" / "cert.pem")


def test_normal_mode_stays_on_this_computer_only(captured_run):
    server.main([])
    assert captured_run["kwargs"]["host"] == "127.0.0.1"
    assert "ssl_context" not in captured_run["kwargs"]


def test_certificates_are_git_ignored():
    gitignore = (CLIENT_DIR.parent / ".gitignore").read_text().splitlines()
    assert "server/certs/" in gitignore


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_pages_are_sized_for_phones(page):
    html = page.read_text()
    assert re.search(r'<meta name="viewport" content="width=device-width', html)
    assert 'href="app.css"' in html


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_pages_have_no_inline_styles(page):
    # The CSP blocks inline styles, so any left behind would silently not apply.
    html = page.read_text()
    assert "<style" not in html and " style=" not in html


def test_no_frames_or_fixed_desktop_widths():
    css = (CLIENT_DIR / "app.css").read_text()
    # A fixed width over 360px would overflow a phone screen (max-width is fine).
    fixed = [int(n) for n in re.findall(r"(?<![-\w])width:\s*(\d+)px", css)]
    assert all(n <= 360 for n in fixed), fixed
    for page in PAGES:
        assert "<frame" not in page.read_text().lower()


def test_scan_page_offers_a_photo_picker_that_works_without_https():
    html = (CLIENT_DIR / "upload.html").read_text()
    assert re.search(r'<input type="file"[^>]*accept="image/\*"', html)


def test_csp_blocks_inline_styles_too(client):
    csp = client.get("/").headers["Content-Security-Policy"]
    style_src = re.search(r"style-src ([^;]+)", csp).group(1)
    assert "'unsafe-inline'" not in style_src
    assert "object-src 'none'" in csp
