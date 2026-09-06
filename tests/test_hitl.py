"""Tests for the Buildguard HITL override workflow (TTS fully mocked)."""

import os

import pytest
from fastapi.testclient import TestClient

from app import store
from app.main import app, build_resolution_message
from app.models import OverrideDecision, ViolationStatus
from app.voice_service import VoiceDispatchError, dispatch_voice_alert


@pytest.fixture(autouse=True)
def reset_store():
    store.reset()
    yield
    store.reset()


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("SMALLEST_AI_API_KEY", "test_key")
    monkeypatch.setenv("BUILDGUARD_AUDIO_DIR", str(tmp_path / "audio"))
    monkeypatch.delenv("BUILDGUARD_CALL_WEBHOOK_URL", raising=False)

    class FakeResponse:
        status_code = 200
        headers = {"Content-Type": "audio/wav"}

        @staticmethod
        def content():
            raise NotImplementedError

    def fake_post(url, *args, **kwargs):
        fake = FakeResponse()
        fake.content = b"RIFFfakewavdata"  # pretend audio payload
        return fake

    monkeypatch.setattr("app.voice_service.requests.post", fake_post)
    return TestClient(app)


def test_list_violations_returns_seeded_flagged(client):
    resp = client.get("/hitl/violations")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    assert all(v["status"] == "flagged" for v in body)


def test_list_violations_filtered_by_status(client):
    client.post(
        "/hitl/override",
        json={"violation_id": "V-1001", "decision": "approve"},
    )
    resp = client.get("/hitl/violations?status=approved")
    assert resp.status_code == 200
    body = resp.json()
    assert [v["id"] for v in body] == ["V-1001"]


def test_override_approve_dispatches_call(client, tmp_path):
    resp = client.post(
        "/hitl/override",
        json={
            "violation_id": "V-1001",
            "decision": "approve",
            "resolution_notes": "Anchors certified by third-party inspector.",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolved_status"] == "approved"
    assert body["call_status"] == "audio_generated"
    assert body["audio_path"].endswith(".wav")
    # Audio file actually written, and message mentions approval.
    assert (tmp_path / "audio").exists()
    assert len(list((tmp_path / "audio").glob("*.wav"))) == 1
    assert "approved" in body["message"].lower()
    # Store reflects the resolution.
    assert store.get_violation("V-1001").status == ViolationStatus.APPROVED


def test_override_reject_dispatches_call(client):
    resp = client.post(
        "/hitl/override",
        json={"violation_id": "V-1002", "decision": "reject"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolved_status"] == "rejected"
    assert "confirmed" in body["message"].lower()
    assert store.get_violation("V-1002").status == ViolationStatus.REJECTED


def test_override_unknown_violation_returns_404(client):
    resp = client.post(
        "/hitl/override",
        json={"violation_id": "V-9999", "decision": "approve"},
    )
    assert resp.status_code == 404


def test_override_already_resolved_returns_409(client):
    client.post(
        "/hitl/override",
        json={"violation_id": "V-1001", "decision": "approve"},
    )
    resp = client.post(
        "/hitl/override",
        json={"violation_id": "V-1001", "decision": "reject"},
    )
    assert resp.status_code == 409


def test_override_missing_api_key_returns_502(client, monkeypatch):
    monkeypatch.delenv("SMALLEST_AI_API_KEY", raising=False)
    resp = client.post(
        "/hitl/override",
        json={"violation_id": "V-1003", "decision": "approve"},
    )
    assert resp.status_code == 502
    assert "SMALLEST_AI_API_KEY" in resp.json()["detail"]
    # Violation must remain flagged when dispatch fails.
    assert store.get_violation("V-1003").status == ViolationStatus.FLAGGED


def test_override_call_provider_webhook_receives_audio(monkeypatch, tmp_path):
    monkeypatch.setenv("SMALLEST_AI_API_KEY", "test_key")
    monkeypatch.setenv("BUILDGUARD_AUDIO_DIR", str(tmp_path / "audio"))
    monkeypatch.setenv("BUILDGUARD_CALL_WEBHOOK_URL", "https://calls.example.com/inbound")

    captured = {}

    def fake_post(url, *args, **kwargs):
        captured["cells"] = kwargs
        if "text" in kwargs.get("json", {}):  # TTS call
            class FakeTts:
                status_code = 200
                headers = {"Content-Type": "audio/wav"}
                content = b"RIFFfakewavdata"
            return FakeTts()
        # Webhook call
        class FakeHook:
            status_code = 200
            text = "ok"
        return FakeHook()

    monkeypatch.setattr("app.voice_service.requests.post", fake_post)

    result = dispatch_voice_alert("+1555010010", "Resolution message", violation_id="V-1001")
    assert result["provider_status"] == "call_dispatched"
    assert captured["cells"]["data"]["phone_number"] == "+1555010010"
    assert "audio" in captured["cells"]["files"]


def test_dispatch_empty_message_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("SMALLEST_AI_API_KEY", "test_key")
    monkeypatch.setenv("BUILDGUARD_AUDIO_DIR", str(tmp_path / "audio"))
    with pytest.raises(VoiceDispatchError):
        dispatch_voice_alert("+1555010010", "   ", violation_id="V-1001")


def test_build_resolution_message_covers_both_decisions():
    violation = store.get_violation("V-1002")
    approve = build_resolution_message(violation, OverrideDecision.APPROVE, "")
    reject = build_resolution_message(violation, OverrideDecision.REJECT, "Fix by Friday")
    assert "approved" in approve.lower()
    assert "confirmed" in reject.lower()
    assert "Fix by Friday" in reject