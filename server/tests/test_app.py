import base64
import json

import pytest

import server
from helpers import PASSWORD, FakeDetector, FakeExtractor, image_data_url, login, scan, signed_in, signup

# ---------- Accounts ----------


def test_passwords_are_hashed_on_disk(client, tmp_path):
    signup(client)
    stored = (tmp_path / "accounts.json").read_text()
    assert PASSWORD not in stored
    record = json.loads(stored)["user@example.com"]
    assert record["password_hash"].startswith(("scrypt:", "pbkdf2:"))


def test_accounts_survive_restart(make_client):
    signup(make_client())
    assert login(make_client()).status_code == 200


def test_email_is_case_insensitive(client):
    signup(client, "User@Example.com")
    assert login(client, "user@example.com").status_code == 200


def test_duplicate_signup_is_rejected(client):
    signup(client)
    assert signup(client).status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": PASSWORD},
        {"email": "a@b.com", "password": "short"},
        {"email": "a@b.com", "password": "x" * 200},
        {"email": ["a@b.com"], "password": PASSWORD},
        {"email": "a@b.com", "password": 12345678},
    ],
)
def test_signup_rejects_invalid_input(client, payload):
    assert client.post("/signup_authorization", json=payload).status_code == 400


def test_wrong_password_and_unknown_email_get_the_same_answer(client):
    signup(client)
    wrong = login(client, password="wrong-password")
    unknown = login(client, email="nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.get_json() == unknown.get_json()


def test_login_locks_out_after_repeated_failures(client):
    signup(client)
    for _ in range(server.MAX_LOGIN_FAILURES):
        assert login(client, password="wrong-password").status_code == 401
    assert login(client).status_code == 429  # even the right password is blocked during lockout


def test_non_json_bodies_are_rejected(client):
    response = client.post("/login_authorization", data="email=a@b.com&password=x")
    assert response.status_code == 400


def test_logout_ends_the_session(client):
    signed_in(client)
    client.post("/logout", json={})
    assert client.get("/extract").status_code == 401


# ---------- Access control ----------


@pytest.mark.parametrize(
    "method, path",
    [
        ("post", "/predict"),
        ("post", "/confirm"),
        ("get", "/extract"),
        ("put", "/update_card"),
        ("delete", "/remove_card"),
        ("post", "/save_final"),
        ("get", "/final_results"),
    ],
)
def test_api_requires_login(client, method, path):
    response = getattr(client, method)(path, json={"id": 0, "details": {}})
    assert response.status_code == 401


def test_protected_pages_redirect_to_login(client):
    for page in ("index.html", "upload.html", "edit.html", "results.html"):
        body = client.get(f"/{page}").get_data(as_text=True)
        assert 'id="login-form"' in body  # the login page was served instead


def test_static_paths_cannot_escape_client_folder(client):
    assert client.get("/../server/server.py").status_code == 404
    assert client.get("/%2e%2e/server/server.py").status_code == 404


def test_users_only_see_their_own_contacts(make_client):
    alice = signed_in(make_client(), "alice@example.com")
    scan(alice)
    alice.post("/save_final", json={})

    bob = signed_in(make_client(), "bob@example.com")
    assert bob.get("/final_results").get_json() == []
    assert len(alice.get("/final_results").get_json()) == 1


# ---------- Scanning ----------


def test_full_scan_review_and_save_flow(client):
    signed_in(client)
    crops = scan(client).get_json()["crops"]
    assert len(crops) == 2

    cards = client.get("/extract").get_json()
    assert cards[0]["details"]["email"] == "jane@acme.com"

    update = client.put("/update_card", json={"id": 0, "details": {"name": "John", "email": "john@acme.com"}})
    assert update.status_code == 200
    assert client.delete("/remove_card", json={"id": 1}).status_code == 200

    saved = client.post("/save_final", json={}).get_json()
    assert saved == {"success": True, "saved": 1}
    results = client.get("/final_results").get_json()
    assert results[0]["details"]["name"] == "John"


def test_saving_twice_does_not_duplicate(client):
    signed_in(client)
    scan(client)
    client.post("/save_final", json={})
    client.post("/save_final", json={})
    assert len(client.get("/final_results").get_json()) == 1  # both fake cards have identical details


@pytest.mark.parametrize(
    "image",
    [
        "not a data url",
        "data:text/html;base64,PHNjcmlwdD4=",
        "data:image/jpeg;base64,!!!notbase64!!!",
        "data:image/jpeg;base64," + base64.b64encode(b"definitely not an image").decode(),
        12345,
    ],
)
def test_predict_rejects_bad_images(client, image):
    signed_in(client)
    assert client.post("/predict", json={"image": image}).status_code == 400


def test_predict_accepts_png(client):
    signed_in(client)
    assert client.post("/predict", json={"image": image_data_url("PNG")}).status_code == 200


def test_oversized_upload_is_rejected(client):
    signed_in(client)
    huge = "data:image/jpeg;base64," + "A" * (server.MAX_UPLOAD_BYTES + 10)
    assert client.post("/predict", json={"image": huge}).status_code == 413


def test_confirm_without_scan_is_rejected(client):
    signed_in(client)
    assert client.post("/confirm", json={}).status_code == 400


def test_out_of_bounds_and_empty_boxes_are_clamped_or_skipped(make_client):
    detector = FakeDetector(boxes=[[-50, -50, 100, 100], [900, 900, 5000, 5000], [10, 10, 10, 10]])
    client = signed_in(make_client(detector=detector))
    crops = scan(client).get_json()["crops"]
    assert len(crops) == 2  # the zero-area box is skipped


def test_extraction_failure_keeps_the_card_for_manual_entry(make_client):
    client = signed_in(make_client(extractor=FakeExtractor(fail=True)))
    scan(client)
    cards = client.get("/extract").get_json()
    assert len(cards) == 2
    assert all(value is None for value in cards[0]["details"].values())


# ---------- Untrusted AI output ----------


def test_model_output_is_limited_to_expected_fields(make_client):
    hostile = {
        "name": "<img src=x onerror=alert(1)>",
        "email": "x" * 5000,
        "phone_number": {"nested": "object"},
        "company_name": "Acme\x00\x1bCorp",
        "is_admin": True,
    }
    client = signed_in(make_client(extractor=FakeExtractor(result=hostile)))
    scan(client)
    details = client.get("/extract").get_json()[0]["details"]
    assert set(details) == set(server.CARD_FIELDS)
    assert len(details["email"]) == server.MAX_FIELD_LENGTH
    assert details["phone_number"] is None
    assert "\x00" not in details["company_name"]


@pytest.mark.parametrize(
    "body, status",
    [
        ({"id": "0", "details": {}}, 400),
        ({"id": True, "details": {}}, 400),
        ({"id": 0, "details": "not an object"}, 400),
        ({"id": 99, "details": {}}, 404),
    ],
)
def test_update_card_validates_input(client, body, status):
    signed_in(client)
    scan(client)
    assert client.put("/update_card", json=body).status_code == status


def test_remove_unknown_card_is_404(client):
    signed_in(client)
    scan(client)
    assert client.delete("/remove_card", json={"id": 42}).status_code == 404


def test_parse_model_response_handles_fenced_and_bad_json():
    assert server.parse_model_response('```json\n{"name": "A"}\n```') == {"name": "A"}
    assert server.parse_model_response("not json") == {}
    assert server.parse_model_response("[1, 2]") == {}


# ---------- Hardening ----------


def test_security_headers_are_set(client):
    headers = client.get("/").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "SAMEORIGIN"
    assert "default-src 'self'" in headers["Content-Security-Policy"]


def test_session_cookie_is_httponly_and_samesite(client):
    signup(client)
    cookie = login(client).headers["Set-Cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_session_cannot_be_forged_with_another_key(make_client, monkeypatch):
    client = signed_in(make_client())
    monkeypatch.setenv("BCR_SECRET_KEY", "attacker-key")
    forged = make_client()
    forged.set_cookie("session", client.get_cookie("session").value)
    assert forged.get("/extract").status_code == 401


# ---------- Crop quality ----------


class SizeRecordingExtractor(FakeExtractor):
    """Records the size of each crop the AI is given."""

    def __init__(self):
        super().__init__()
        self.sizes = []

    def extract(self, jpeg_b64):
        from io import BytesIO

        from PIL import Image

        self.sizes.append(Image.open(BytesIO(base64.b64decode(jpeg_b64))).size)
        return super().extract(jpeg_b64)


def test_scale_box_maps_and_widens():
    assert server.scale_box([100, 100, 200, 300], (1000, 1000), (2000, 500)) == [200, 50, 400, 150]
    assert server.scale_box([100, 100, 200, 200], (1000, 1000), (1000, 1000), margin=0.1) == [90, 90, 210, 210]


def test_crops_come_from_the_full_resolution_photo_with_a_margin(make_client):
    # Box covers the middle quarter of the 1024x1024 model image.
    extractor = SizeRecordingExtractor()
    client = signed_in(make_client(detector=FakeDetector(boxes=[[256, 256, 768, 768]]), extractor=extractor))
    client.post("/predict", json={"image": image_data_url(size=(2000, 1500))})
    client.post("/confirm", json={})
    # On the 2000x1500 photo the box is 1000x750; the 15% margin each side makes it 1.3x
    # (give or take a pixel of rounding).
    (width, height), = extractor.sizes
    assert abs(width - 1300) <= 1 and abs(height - 975) <= 1


def test_crop_margin_is_clamped_to_the_photo(make_client):
    extractor = SizeRecordingExtractor()
    client = signed_in(make_client(detector=FakeDetector(boxes=[[0, 0, 1024, 1024]]), extractor=extractor))
    client.post("/predict", json={"image": image_data_url(size=(800, 600))})
    client.post("/confirm", json={})
    assert extractor.sizes == [(800, 600)]


def test_very_large_photos_are_shrunk_before_cropping(make_client):
    extractor = SizeRecordingExtractor()
    client = signed_in(make_client(detector=FakeDetector(boxes=[[0, 0, 1024, 1024]]), extractor=extractor))
    client.post("/predict", json={"image": image_data_url(size=(4000, 3000))})
    client.post("/confirm", json={})
    assert max(extractor.sizes[0]) == server.MAX_CROP_SOURCE_SIDE


def test_prompt_tells_the_model_not_to_guess():
    prompt = server.EXTRACTION_PROMPT.lower()
    assert "never guess" in prompt and "unreadable" in prompt
