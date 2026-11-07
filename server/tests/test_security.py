"""Security tests: each one tries an attack and checks that it fails."""

import base64
import csv
import io
import re
import struct
import zlib
from pathlib import Path

import pytest
from itsdangerous import TimestampSigner
from PIL import Image

import server
from helpers import PASSWORD, FakeDetector, FakeExtractor, image_data_url, login, scan, signed_in, signup

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENT_DIR = REPO_ROOT / "client"

PUBLIC_ROUTES = {"/", "/<path:path>", "/signup_authorization", "/login_authorization", "/logout"}

XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    '"><svg onload=alert(1)>',
    "javascript:alert(1)",
    "</textarea><script>alert(document.cookie)</script>",
    "{{7*7}}${7*7}",
]


def app_and_client(make_client, **kwargs):
    client = make_client(**kwargs)
    return client.application, client


def session_cookie(client):
    return client.get_cookie("session").value


def cookie_signed_with(secret, data, tmp_path):
    """Build a session cookie the way Flask does, but with any key."""
    app = server.create_app(
        {"TESTING": True, "DATA_DIR": str(tmp_path / "other"), "SECRET_KEY": secret},
        detector=FakeDetector(),
        extractor=FakeExtractor(),
    )
    return app.session_interface.get_signing_serializer(app).dumps(data)


def protected_endpoints(app):
    """Every (method, path) the app exposes, minus the routes meant to be public."""
    endpoints = []
    for rule in app.url_map.iter_rules():
        if rule.rule in PUBLIC_ROUTES or rule.endpoint == "static":
            continue
        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            endpoints.append((method, rule.rule))
    return endpoints


def call(client, method, path):
    kwargs = {} if method == "GET" else {"json": {"id": 0, "details": {}, "image": image_data_url()}}
    return client.open(path, method=method, **kwargs)


def png_header_only(width, height):
    """A tiny PNG file that claims to be width x height pixels."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"")) + chunk(b"IEND", b"")


def data_url(raw, mime="image/png"):
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def encoded_image(fmt, size=(64, 64)):
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, fmt)
    return buffer.getvalue()


# ---------- Missing or invalid authentication, on every endpoint ----------


def test_endpoint_discovery_is_not_empty(client):
    found = {path for _, path in protected_endpoints(client.application)}
    # If this fails, the route list changed; the tests below rely on it.
    assert {"/predict", "/confirm", "/extract", "/update_card", "/remove_card",
            "/save_final", "/final_results", "/export/contacts.csv", "/export/contacts.vcf"} <= found


def test_every_endpoint_rejects_requests_without_a_session(client):
    for method, path in protected_endpoints(client.application):
        assert call(client, method, path).status_code == 401, (method, path)


@pytest.mark.parametrize(
    "cookie",
    ["", "garbage", "eyJ1c2VyIjoiYUBiLmNvbSJ9", "eyJ1c2VyIjoiYUBiLmNvbSJ9.AAAAAA.BBBBBBBBBBBBBBBBBBBBBBBBBBB", "." * 50],
)
def test_every_endpoint_rejects_malformed_session_cookies(client, cookie):
    client.set_cookie("session", cookie)
    for method, path in protected_endpoints(client.application):
        assert call(client, method, path).status_code == 401, (method, path)


def test_every_endpoint_rejects_a_cookie_signed_with_another_key(make_client, tmp_path):
    victim = signed_in(make_client(), "victim@example.com")
    assert victim.get("/extract").status_code == 200
    attacker = make_client()
    attacker.set_cookie("session", cookie_signed_with("attacker-key", {"user": "victim@example.com", "v": 0}, tmp_path))
    for method, path in protected_endpoints(attacker.application):
        assert call(attacker, method, path).status_code == 401, (method, path)


def test_every_endpoint_rejects_a_replayed_cookie_after_logout(make_client):
    user = signed_in(make_client())
    stolen = session_cookie(user)
    assert user.post("/logout", json={}).status_code == 200

    attacker = make_client()
    attacker.set_cookie("session", stolen)
    for method, path in protected_endpoints(attacker.application):
        assert call(attacker, method, path).status_code == 401, (method, path)


def test_logging_in_again_after_logout_works(client):
    signed_in(client)
    client.post("/logout", json={})
    assert login(client).status_code == 200
    assert client.get("/extract").status_code == 200


def test_protected_pages_need_a_valid_session(make_client, tmp_path):
    forged = make_client()
    forged.set_cookie("session", cookie_signed_with("attacker-key", {"user": "a@b.com", "v": 0}, tmp_path))
    for page in sorted(p.name for p in CLIENT_DIR.glob("*.html")):
        if page in server.PUBLIC_PAGES:
            continue
        for client in (make_client(), forged):
            body = client.get(f"/{page}").get_data(as_text=True)
            assert 'id="login-form"' in body, page


@pytest.mark.parametrize("path", ["/Upload.HTML", "/EDIT.html", "/results.Html", "/index.htm"])
def test_page_login_check_cannot_be_skipped_with_letter_case(client, path):
    response = client.get(path)
    # On a case-sensitive disk the file doesn't exist (404); otherwise the login page is served.
    assert response.status_code == 404 or 'id="login-form"' in response.get_data(as_text=True)


def test_logout_without_a_session_is_harmless(client):
    assert client.post("/logout", json={}).status_code == 200


# ---------- Session tampering ----------


def test_editing_the_cookie_payload_breaks_the_signature(make_client):
    client = signed_in(make_client(), "alice@example.com")
    payload, rest = session_cookie(client).split(".", 1)
    data = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
    forged_payload = base64.urlsafe_b64encode(data.replace(b"alice", b"admin")).decode().rstrip("=")
    signup(client, "admin@example.com")

    client.set_cookie("session", forged_payload + "." + rest)
    assert client.get("/extract").status_code == 401


def test_cookie_for_an_account_that_does_not_exist_is_rejected(make_client, tmp_path):
    client = make_client()
    client.set_cookie("session", cookie_signed_with("test-secret", {"user": "ghost@example.com", "v": 0}, tmp_path))
    assert client.get("/extract").status_code == 401


def test_cookie_with_an_old_session_version_is_rejected(make_client, tmp_path):
    client = signed_in(make_client())
    client.post("/logout", json={})  # bumps the version to 1
    replay = make_client()
    replay.set_cookie("session", cookie_signed_with("test-secret", {"user": "user@example.com", "v": 0}, tmp_path))
    assert replay.get("/extract").status_code == 401


def test_expired_session_cookie_is_rejected(make_client, tmp_path, monkeypatch):
    signed_in(make_client())
    hours = make_client().application.permanent_session_lifetime.total_seconds()
    real_timestamp = TimestampSigner.get_timestamp
    monkeypatch.setattr(TimestampSigner, "get_timestamp", lambda self: real_timestamp(self) - int(hours) - 60)
    old_cookie = cookie_signed_with("test-secret", {"user": "user@example.com", "v": 0}, tmp_path)
    monkeypatch.setattr(TimestampSigner, "get_timestamp", real_timestamp)

    client = make_client()
    client.set_cookie("session", old_cookie)
    assert client.get("/extract").status_code == 401


def test_session_cookie_has_an_expiry(client):
    signup(client)
    cookie = login(client).headers["Set-Cookie"]
    assert "Expires=" in cookie


def test_login_replaces_any_planted_session_data(client):
    signup(client)
    with client.session_transaction() as planted:
        planted["user"] = "attacker@example.com"
        planted["is_admin"] = True
    login(client)
    with client.session_transaction() as current:
        assert current["user"] == "user@example.com"
        assert "is_admin" not in current


def test_session_cookie_does_not_contain_the_password(client):
    signup(client)
    login(client)
    payload = session_cookie(client).split(".")[0]
    decoded = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
    assert PASSWORD.encode() not in decoded


# ---------- Brute force and lockout ----------


def test_lockout_also_blocks_unknown_emails(client):
    # Otherwise a 429 vs 401 difference would reveal which emails have accounts.
    for _ in range(server.MAX_LOGIN_FAILURES):
        assert login(client, "nobody@example.com", "wrong-password").status_code == 401
    assert login(client, "nobody@example.com", "wrong-password").status_code == 429


def test_lockout_is_per_account(client):
    signup(client, "alice@example.com")
    signup(client, "bob@example.com")
    for _ in range(server.MAX_LOGIN_FAILURES):
        login(client, "alice@example.com", "wrong-password")
    assert login(client, "alice@example.com").status_code == 429
    assert login(client, "bob@example.com").status_code == 200


def test_lockout_cannot_be_dodged_with_case_or_spaces(client):
    signup(client)
    for variant in ["User@Example.com", " user@example.com", "USER@EXAMPLE.COM", "user@example.com ", "uSeR@example.com"]:
        login(client, variant, "wrong-password")
    assert login(client).status_code == 429


def test_lockout_expires(client, monkeypatch):
    signup(client)
    now = [1000.0]
    monkeypatch.setattr(server.time, "monotonic", lambda: now[0])
    for _ in range(server.MAX_LOGIN_FAILURES):
        login(client, password="wrong-password")
    assert login(client).status_code == 429
    now[0] += server.LOCKOUT_SECONDS - 1
    assert login(client).status_code == 429
    now[0] += 2
    assert login(client).status_code == 200


def test_successful_login_resets_the_failure_count(client):
    signup(client)
    for _ in range(server.MAX_LOGIN_FAILURES - 1):
        login(client, password="wrong-password")
    assert login(client).status_code == 200
    for _ in range(server.MAX_LOGIN_FAILURES - 1):
        assert login(client, password="wrong-password").status_code == 401


def test_too_many_auth_attempts_from_one_address_are_throttled(client):
    # Password spraying: one password tried against many different emails.
    statuses = [login(client, f"user{i}@example.com", "Summer2026!").status_code for i in range(server.AUTH_RATE_LIMIT + 5)]
    assert statuses[: server.AUTH_RATE_LIMIT] == [401] * server.AUTH_RATE_LIMIT
    assert set(statuses[server.AUTH_RATE_LIMIT:]) == {429}


def test_address_throttle_also_covers_signup(client):
    statuses = [signup(client, f"new{i}@example.com").status_code for i in range(server.AUTH_RATE_LIMIT + 1)]
    assert statuses[-1] == 429


def test_address_throttle_is_per_address_and_resets(client, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(server.time, "monotonic", lambda: now[0])
    for i in range(server.AUTH_RATE_LIMIT):
        login(client, f"u{i}@example.com", "x" * 10)
    assert login(client, "a@example.com", "x" * 10).status_code == 429

    other = client.post("/login_authorization", json={"email": "a@example.com", "password": "x" * 10},
                        environ_base={"REMOTE_ADDR": "10.0.0.2"})
    assert other.status_code == 401

    now[0] += server.AUTH_RATE_WINDOW
    assert login(client, "a@example.com", "x" * 10).status_code == 401


# ---------- Path traversal ----------


@pytest.mark.parametrize(
    "path",
    [
        "/../server/server.py",
        "/%2e%2e/server/server.py",
        "/%2e%2e%2fserver%2fserver.py",
        "/..%2fserver/server.py",
        "/%252e%252e/server/server.py",
        "/..%5cserver%5cserver.py",
        "/....//server/server.py",
        "/js/../../server/server.py",
        "/js/%2e%2e/%2e%2e/server/server.py",
        "/../.env",
        "/%2e%2e/.env",
        "/../server/data/accounts.json",
        "/data/accounts.json",
        "/server.py",
        "//etc/passwd",
        "/%2fetc%2fpasswd",
        "/login.html%00.png",
    ],
)
def test_static_files_cannot_escape_the_client_folder(make_client, path):
    client = signed_in(make_client())  # logged in, so only the path check stands in the way
    response = client.get(path)
    body = response.get_data(as_text=True)
    assert response.status_code in (400, 404), path
    assert "create_app" not in body and "password_hash" not in body and "root:" not in body


def test_dotenv_file_is_git_ignored():
    ignored = {line.strip() for line in (REPO_ROOT / ".gitignore").read_text().splitlines()}
    assert ".env" in ignored


# ---------- Oversized and malformed uploads ----------


def test_huge_dimension_image_is_rejected_before_decoding(client):
    signed_in(client)
    bomb = data_url(png_header_only(100_000, 100_000))  # a few bytes claiming 10 billion pixels
    response = client.post("/predict", json={"image": bomb})
    assert response.status_code == 400


@pytest.mark.filterwarnings("ignore::PIL.Image.DecompressionBombWarning")
def test_image_just_over_the_pixel_limit_is_rejected(client):
    # Pillow only warns (not errors) between 1x and 2x its limit, so the app checks itself.
    signed_in(client)
    image = Image.new("L", (6000, 5000))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    assert client.post("/predict", json={"image": data_url(buffer.getvalue())}).status_code == 400


@pytest.mark.parametrize("fmt", ["BMP", "GIF", "TIFF", "ICO", "PPM"])
def test_formats_other_than_jpeg_png_webp_are_rejected_even_if_mislabelled(client, fmt):
    signed_in(client)
    assert client.post("/predict", json={"image": data_url(encoded_image(fmt), "image/png")}).status_code == 400


def test_webp_is_accepted(client):
    signed_in(client)
    assert client.post("/predict", json={"image": data_url(encoded_image("WEBP"), "image/webp")}).status_code == 200


def test_truncated_jpeg_is_rejected(client):
    signed_in(client)
    raw = encoded_image("JPEG", (400, 300))
    assert client.post("/predict", json={"image": data_url(raw[: len(raw) // 3], "image/jpeg")}).status_code == 400


@pytest.mark.parametrize("image", [None, "", [], {}, True, "data:image/png;base64,", "data:image/svg+xml;base64,PHN2Zz4="])
def test_missing_or_wrong_type_image_is_rejected(client, image):
    signed_in(client)
    assert client.post("/predict", json={"image": image}).status_code == 400


def test_predict_without_an_image_field_is_rejected(client):
    signed_in(client)
    assert client.post("/predict", json={}).status_code == 400


@pytest.mark.parametrize("body", ["[]", '"text"', "42", "null", "{not json", '{"image": '])
def test_non_object_or_broken_json_is_rejected(client, body):
    signed_in(client)
    response = client.post("/predict", data=body, content_type="application/json")
    assert response.status_code == 400


def test_multipart_file_upload_is_rejected(client):
    signed_in(client)
    response = client.post(
        "/predict",
        data={"image": (io.BytesIO(encoded_image("JPEG")), "card.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


def test_oversized_json_is_rejected_on_every_endpoint(client):
    signed_in(client)
    huge = "x" * (server.MAX_UPLOAD_BYTES + 10)
    for method, path in [("POST", "/signup_authorization"), ("POST", "/login_authorization"),
                         ("PUT", "/update_card"), ("POST", "/predict")]:
        response = client.open(path, method=method, data='{"a":"' + huge + '"}', content_type="application/json")
        assert response.status_code == 413, path


def test_number_of_cards_per_scan_is_capped(make_client):
    many_boxes = [[i * 10, 0, i * 10 + 8, 8] for i in range(50)]
    extractor = FakeExtractor()
    client = signed_in(make_client(detector=FakeDetector(boxes=many_boxes), extractor=extractor))
    assert client.post("/predict", json={"image": image_data_url()}).get_json()["count"] == server.MAX_CARDS_PER_SCAN
    client.post("/confirm", json={})
    assert extractor.calls == server.MAX_CARDS_PER_SCAN


def test_one_scan_can_only_be_confirmed_once(make_client):
    extractor = FakeExtractor()
    client = signed_in(make_client(extractor=extractor))
    scan(client)
    calls = extractor.calls
    assert client.post("/confirm", json={}).status_code == 400
    assert extractor.calls == calls  # no extra paid model calls


# ---------- Cross-site request forgery ----------


@pytest.mark.parametrize(
    "method, path",
    [("POST", "/predict"), ("POST", "/confirm"), ("PUT", "/update_card"), ("DELETE", "/remove_card"),
     ("POST", "/save_final"), ("POST", "/logout"), ("POST", "/login_authorization"), ("POST", "/signup_authorization")],
)
@pytest.mark.parametrize("content_type", ["application/x-www-form-urlencoded", "text/plain", "multipart/form-data"])
def test_state_changes_require_json(make_client, method, path, content_type):
    # These are the content types a cross-site HTML form (or a no-preflight fetch) can send.
    client = signed_in(make_client())
    scan(client)
    body = 'id=0&details={}' if "form" in content_type else '{"id": 0}'
    response = client.open(path, method=method, data=body, content_type=content_type)
    assert response.status_code == 400
    assert client.get("/extract").status_code == 200  # still logged in, nothing changed
    assert len(client.get("/extract").get_json()) == 2
    assert client.get("/final_results").get_json() == []


# ---------- XSS payloads in card fields ----------


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_xss_in_model_output_comes_back_as_inert_json(make_client, payload):
    hostile = {"name": payload, "company_name": payload, "phone_number": payload, "email": payload}
    client = signed_in(make_client(extractor=FakeExtractor(result=hostile)))
    scan(client)
    response = client.get("/extract")
    assert response.mimetype == "application/json"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.get_json()[0]["details"]["name"] == payload  # stored as data, shown with textContent


@pytest.mark.parametrize("payload", XSS_PAYLOADS)
def test_xss_in_user_edits_is_stored_as_text(client, payload):
    signed_in(client)
    scan(client)
    client.put("/update_card", json={"id": 0, "details": {field: payload for field in server.CARD_FIELDS}})
    client.post("/save_final", json={})
    response = client.get("/final_results")
    assert response.mimetype == "application/json"
    assert response.get_json()[0]["details"]["company_name"] == payload


def test_csp_blocks_inline_and_eval_scripts(client):
    csp = client.get("/").headers["Content-Security-Policy"]
    script_src = re.search(r"script-src ([^;]+)", csp).group(1)
    assert "'unsafe-inline'" not in script_src
    assert "'unsafe-eval'" not in script_src
    assert "object-src" in csp or "default-src 'self'" in csp


def test_frontend_never_inserts_html_or_runs_strings_as_code():
    risky = re.compile(r"\.innerHTML|\.outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function\(|setTimeout\(\s*['\"]")
    for path in list(CLIENT_DIR.rglob("*.js")) + list(CLIENT_DIR.glob("*.html")):
        assert not risky.search(path.read_text()), path


def test_pages_have_no_inline_scripts_or_event_handlers():
    # The CSP blocks inline scripts, so any left behind would silently break the page.
    for page in CLIENT_DIR.glob("*.html"):
        html = page.read_text()
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), page
        assert not re.search(r"\son[a-z]+\s*=", html, re.IGNORECASE), page


@pytest.mark.parametrize("payload", ["=HYPERLINK(\"http://evil\",\"x\")", "+cmd|' /C calc'!A0", "-1+SUM(A1:A9)", "@SUM(1+1)", "\t=1+1"])
def test_csv_export_neutralises_spreadsheet_formulas(make_client, payload):
    client = signed_in(make_client(extractor=FakeExtractor(result={"name": payload, "company_name": "Acme"})))
    scan(client)
    client.post("/save_final", json={})
    text = client.get("/export/contacts.csv").get_data(as_text=True).lstrip("﻿")
    row = list(csv.reader(io.StringIO(text)))[1]
    assert not row[0].startswith(server.FORMULA_PREFIXES)


def test_csv_export_keeps_plain_phone_numbers_unchanged():
    assert server.safe_csv_cell("+61 400 000 000") == "+61 400 000 000"
    assert server.safe_csv_cell("(02) 9999-0000") == "(02) 9999-0000"
    assert server.safe_csv_cell("+SUM(A1)") == "'+SUM(A1)"


def test_vcard_export_cannot_be_given_extra_properties():
    entry = {"details": {"name": "Eve\r\nURL:http://evil\r\nEND:VCARD", "company_name": "A;B,C\\D",
                         "phone_number": None, "email": None}}
    lines = server.contacts_to_vcard([entry]).split("\r\n")
    assert not any(line.startswith("URL:") for line in lines)
    assert lines.count("END:VCARD") == 1
    assert "ORG:A\\;B\\,C\\\\D" in lines


def test_exports_are_downloads_not_pages(client):
    signed_in(client)
    for path, mimetype in [("/export/contacts.csv", "text/csv"), ("/export/contacts.vcf", "text/vcard")]:
        response = client.get(path)
        assert response.mimetype == mimetype
        assert response.headers["Content-Disposition"].startswith("attachment")
        assert response.headers["Cache-Control"] == "no-store"


# ---------- Cross-user access ----------


@pytest.fixture
def alice_and_bob(make_client):
    alice = signed_in(make_client(), "alice@example.com")
    scan(alice)
    bob = signed_in(make_client(), "bob@example.com")
    return alice, bob


def test_users_cannot_see_each_others_pending_cards(alice_and_bob):
    alice, bob = alice_and_bob
    assert bob.get("/extract").get_json() == []
    assert len(alice.get("/extract").get_json()) == 2


def test_users_cannot_edit_or_delete_each_others_cards(alice_and_bob):
    alice, bob = alice_and_bob
    assert bob.put("/update_card", json={"id": 0, "details": {"name": "Hacked"}}).status_code == 404
    assert bob.delete("/remove_card", json={"id": 0}).status_code == 404
    cards = alice.get("/extract").get_json()
    assert len(cards) == 2 and cards[0]["details"]["name"] == "Jane Doe"


def test_users_cannot_confirm_or_save_each_others_scans(alice_and_bob):
    alice, bob = alice_and_bob
    assert bob.post("/confirm", json={}).status_code == 400
    bob.post("/save_final", json={})
    assert bob.get("/final_results").get_json() == []
    assert alice.get("/final_results").get_json() == []


def test_exports_only_include_your_own_contacts(alice_and_bob):
    alice, bob = alice_and_bob
    alice.post("/save_final", json={})
    assert "Jane Doe" in alice.get("/export/contacts.csv").get_data(as_text=True)
    assert "Jane Doe" in alice.get("/export/contacts.vcf").get_data(as_text=True)
    assert "Jane Doe" not in bob.get("/export/contacts.csv").get_data(as_text=True)
    assert bob.get("/export/contacts.vcf").get_data(as_text=True) == ""


def test_one_user_logging_out_does_not_affect_another(alice_and_bob):
    alice, bob = alice_and_bob
    bob.post("/logout", json={})
    assert alice.get("/extract").status_code == 200


def test_cannot_sign_up_as_an_existing_user_with_a_different_case(alice_and_bob):
    _, bob = alice_and_bob
    assert signup(bob, " ALICE@example.com ").status_code == 409


def test_wrong_http_methods_are_refused(client):
    signed_in(client)
    # A GET falls through to the static file handler, which finds no such file.
    assert client.get("/signup_authorization").status_code in (404, 405)
    assert client.get("/save_final").status_code in (404, 405)
    assert client.post("/final_results", json={}).status_code == 405
    assert client.delete("/export/contacts.csv", json={}).status_code == 405
