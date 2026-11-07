"""Fakes and helpers shared by the test files (fixtures live in conftest.py)."""

import base64
from io import BytesIO

import numpy as np
from PIL import Image

PASSWORD = "correct-horse-1"


class FakeDetector:
    def __init__(self, boxes=None):
        self.boxes = boxes if boxes is not None else [[10, 10, 200, 120], [300, 300, 600, 500]]

    def detect(self, rgb):
        return self.boxes, rgb


class FakeExtractor:
    def __init__(self, result=None, fail=False):
        self.result = result or {"name": "Jane Doe", "company_name": "Acme", "phone_number": "0400 000 000", "email": "jane@acme.com"}
        self.fail = fail
        self.calls = 0

    def extract(self, jpeg_b64):
        self.calls += 1
        base64.b64decode(jpeg_b64, validate=True)  # crops must be real base64 JPEG
        if self.fail:
            raise RuntimeError("model unavailable")
        return dict(self.result)


def image_data_url(fmt="JPEG", size=(640, 480)):
    buffer = BytesIO()
    Image.fromarray(np.full((size[1], size[0], 3), 200, dtype=np.uint8)).save(buffer, format=fmt)
    mime = {"JPEG": "image/jpeg", "PNG": "image/png"}[fmt]
    return f"data:{mime};base64," + base64.b64encode(buffer.getvalue()).decode()


def signup(client, email="user@example.com", password=PASSWORD):
    return client.post("/signup_authorization", json={"email": email, "password": password})


def login(client, email="user@example.com", password=PASSWORD):
    return client.post("/login_authorization", json={"email": email, "password": password})


def signed_in(client, email="user@example.com"):
    assert signup(client, email).status_code == 201
    assert login(client, email).status_code == 200
    return client


def scan(client):
    assert client.post("/predict", json={"image": image_data_url()}).status_code == 200
    return client.post("/confirm", json={})
