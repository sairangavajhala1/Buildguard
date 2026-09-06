"""Smallest.ai TTS integration for Buildguard phone alert notifications.

Generates spoken phone-alert audio for HITL (human-in-the-loop) resolutions
using the Smallest.ai Lightning API and optionally hands the audio to a
telephony webhook so the call can be placed to the subcontractor.
"""

import os
import time
from pathlib import Path

import requests

# Smallest.ai Lightning API
SMALLEST_TTS_URL = "https://waves-api.smallest.ai/api/v1/lightning/get_speech"
DEFAULT_VOICE_ID = "emily"  # or any voice available on the account


class VoiceDispatchError(Exception):
    """Raised when a voice alert cannot be generated or dispatched."""


def _api_key() -> str:
    key = os.getenv("SMALLEST_AI_API_KEY")
    if not key:
        raise VoiceDispatchError(
            "SMALLEST_AI_API_KEY is not set. Configure it to dispatch voice alerts."
        )
    return key


def _audio_dir() -> Path:
    return Path(os.getenv("BUILDGUARD_AUDIO_DIR", "output/audio"))


def _call_webhook_url() -> str | None:
    """Optional webhook that places the actual phone call using the generated
    audio (e.g. a Twilio / SIP gateway). When unset, the service generates the
    audio and reports it as ready for dispatch instead."""
    return os.getenv("BUILDGUARD_CALL_WEBHOOK_URL")


def generate_alert_audio(
    message: str,
    voice_id: str = DEFAULT_VOICE_ID,
    speed: float = 1.0,
    violation_id: str | None = None,
) -> Path:
    """Synthesize ``message`` with Smallest.ai TTS and store it as a WAV file.

    Returns the path of the generated audio file.
    """
    if not message or not message.strip():
        raise VoiceDispatchError("Cannot generate audio for an empty message.")

    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "text": message,
        "voice_id": voice_id,
        "speed": speed,
    }

    try:
        response = requests.post(SMALLEST_TTS_URL, json=payload, headers=headers, timeout=120)
    except requests.RequestException as exc:  # network / timeout
        raise VoiceDispatchError(f"Smallest.ai TTS request failed: {exc}") from exc

    if response.status_code != 200:
        raise VoiceDispatchError(
            f"Smallest.ai TTS returned HTTP {response.status_code}: "
            f"{response.text[:300]}"
        )

    out_dir = _audio_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "wav" if "audio" in response.headers.get("Content-Type", "audio/wav") else "wav"
    label = f"{violation_id}_" if violation_id else ""
    out_path = out_dir / f"alert_{label}{int(time.time())}.{suffix}"
    out_path.write_bytes(response.content)
    return out_path


def dispatch_voice_alert(
    phone_number: str,
    message: str,
    voice_id: str = DEFAULT_VOICE_ID,
    speed: float = 1.0,
    violation_id: str | None = None,
) -> dict:
    """Generate a phone alert for ``message`` and dispatch it to ``phone_number``.

    Steps:
      1. Synthesize ``message`` to audio via Smallest.ai TTS.
      2. If a ``BUILDGUARD_CALL_WEBHOOK_URL`` is configured, POST the audio and
         phone number to it so the call can be placed. Otherwise the audio is
         written locally and reported as ready for dispatch.

    Returns a dict with status, audio path and call disposition.
    """
    audio_path = generate_alert_audio(message, voice_id=voice_id, speed=speed,
                                      violation_id=violation_id)

    provider_status = "audio_generated"
    call_webhook_url = _call_webhook_url()
    if call_webhook_url:
        try:
            with audio_path.open("rb") as audio_file:
                response = requests.post(
                    call_webhook_url,
                    data={"phone_number": phone_number, "message": message},
                    files={"audio": (audio_path.name, audio_file, "audio/wav")},
                    timeout=60,
                )
        except requests.RequestException as exc:
            raise VoiceDispatchError(f"Call provider dispatch failed: {exc}") from exc
        if response.status_code >= 400:
            raise VoiceDispatchError(
                f"Call provider returned HTTP {response.status_code}: "
                f"{response.text[:300]}"
            )
        provider_status = "call_dispatched"

    return {
        "status": "dispatched",
        "provider_status": provider_status,
        "phone_number": phone_number,
        "audio_path": str(audio_path),
        "message": message,
    }