# RJ Auto Metadata
# Copyright (C) 2025 Riiicil
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

# src/api/blackbox_api.py
from __future__ import annotations

import base64
import json
import os
import threading
import time
from typing import Dict, Iterable, List, Optional, Tuple, Union

import requests

from src.api.prompts import select_prompt
from src.utils.logging import log_message

API_ENDPOINT = "https://api.blackbox.ai/chat/completions"
API_TIMEOUT = 60
API_MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 8

FORCE_STOP_FLAG = False

BLACKBOX_MODELS: List[str] = [
    # Curated vision-capable models (keep list short to avoid UI overload)
    "blackboxai/google/gemini-2.5-pro",
    "blackboxai/google/gemini-2.5-flash",
]
DEFAULT_MODEL = "blackboxai/google/gemini-2.5-pro"

_ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
_API_KEY_LOCK = threading.Lock()
_API_KEY_INDEX = 0


def select_api_key(api_keys: Iterable[str]) -> Optional[str]:
    keys = list(api_keys) if not isinstance(api_keys, list) else api_keys
    if not keys:
        return None
    global _API_KEY_INDEX
    with _API_KEY_LOCK:
        key = keys[_API_KEY_INDEX % len(keys)]
        _API_KEY_INDEX = (_API_KEY_INDEX + 1) % len(keys)
        return key


def is_stop_requested() -> bool:
    return FORCE_STOP_FLAG


def set_force_stop() -> None:
    global FORCE_STOP_FLAG
    FORCE_STOP_FLAG = True
    log_message("Force stop flag activated for Blackbox provider.", "warning")


def reset_force_stop() -> None:
    global FORCE_STOP_FLAG
    FORCE_STOP_FLAG = False


def check_stop_event(stop_event, message: Optional[str] = None) -> bool:
    if is_stop_requested():
        if message:
            log_message(message)
        return True
    if stop_event is None:
        return False
    try:
        is_set = stop_event.is_set()
        if is_set and message:
            log_message(message)
        return is_set
    except Exception as exc:
        log_message(f"Failed to inspect stop_event: {exc}")
    return False


def _encode_image(path: str) -> Tuple[str, str]:
    _, ext = os.path.splitext(path)
    mime_type = "image/jpeg"
    if ext.lower() == ".png":
        mime_type = "image/png"
    elif ext.lower() == ".webp":
        mime_type = "image/webp"
    elif ext.lower() in {".heic", ".heif"}:
        mime_type = "image/heic"
    with open(path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("utf-8")
    return encoded, mime_type


def _validate_images(images: Iterable[str]) -> Tuple[bool, Optional[str]]:
    for image in images:
        _, ext = os.path.splitext(image)
        if ext.lower() not in _ALLOWED_EXTENSIONS:
            return False, f"File type {ext} not supported for Blackbox: {os.path.basename(image)}"
        if not os.path.exists(image):
            return False, f"Image not found for Blackbox request: {image}"
    return True, None


def _build_payload(
    images: List[str],
    prompt_text: str,
    model: str,
    keyword_count: Union[str, int],
) -> dict:
    try:
        keyword_limit = int(keyword_count)
        if keyword_limit <= 0:
            keyword_limit = 49
        keyword_limit = min(keyword_limit, 60)
    except Exception:
        keyword_limit = 49

    system_instruction = (
        "You generate stock photography metadata. Respond strictly with JSON that "
        "includes the keys 'title', 'description', 'keywords', 'adobe_stock_category', "
        "and 'shutterstock_category'. Do not include extra commentary."
    )

    user_content: List[dict] = []
    if prompt_text:
        user_content.append(
            {
                "type": "text",
                "text": (
                    f"{prompt_text}\n"
                    f"Return up to {keyword_limit} single-word keywords; keep them relevant and mostly unique."
                ),
            }
        )

    for image_path in images:
        encoded, mime_type = _encode_image(image_path)
        data_url = f"data:{mime_type};base64,{encoded}"
        user_content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": data_url,
                },
            }
        )

    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.7,
        "max_tokens": 900,
        "stream": False,
    }


def _extract_metadata_from_json(raw_json: dict) -> dict:
    keywords = raw_json.get("keywords") or []
    raw_keywords: List[str] = []
    if isinstance(keywords, list):
        raw_keywords = [str(item).strip() for item in keywords if str(item).strip()]
        tags = list(raw_keywords)
    elif isinstance(keywords, str):
        raw_keywords = [part.strip() for part in keywords.split(",") if part.strip()]
        tags = list(raw_keywords)
    else:
        tags = []

    tags = list(dict.fromkeys(tags))[:60]

    return {
        "title": raw_json.get("title", ""),
        "description": raw_json.get("description", ""),
        "tags": tags,
        "as_category": raw_json.get("adobe_stock_category", ""),
        "ss_category": raw_json.get("shutterstock_category", ""),
    }


def _parse_blackbox_response(response_data: dict) -> Optional[dict]:
    choices = response_data.get("choices") or []
    for choice in choices:
        message = choice.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            continue
        content = content.strip()
        if not content:
            continue

        try:
            raw_json = json.loads(content)
            if isinstance(raw_json, dict):
                return _extract_metadata_from_json(raw_json)
        except Exception:
            pass

        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                raw_json = json.loads(content[start : end + 1])
                if isinstance(raw_json, dict):
                    return _extract_metadata_from_json(raw_json)
            except Exception:
                continue

    return None


def get_blackbox_metadata(
    image_path: Union[str, List[str]],
    api_key: str,
    stop_event,
    use_png_prompt: bool = False,
    use_video_prompt: bool = False,
    selected_model_input: Optional[str] = None,
    keyword_count: Union[str, int] = "49",
    priority: str = "Detailed",
    is_vector_conversion: bool = False,
):
    images: List[str] = image_path if isinstance(image_path, list) else [image_path]

    is_valid, error_message = _validate_images(images)
    if not is_valid:
        log_message(error_message or "Invalid image for Blackbox request", "warning")
        return {"error": error_message or "unsupported_image_format"}

    if check_stop_event(stop_event, "Blackbox request cancelled before submission"):
        return "stopped"

    model_to_use = (selected_model_input or DEFAULT_MODEL).strip()
    if model_to_use not in BLACKBOX_MODELS:
        log_message(
            f"Unknown Blackbox model '{model_to_use}', falling back to {DEFAULT_MODEL}",
            "warning",
        )
        model_to_use = DEFAULT_MODEL

    # Reuse OpenAI prompt variant to keep expected JSON schema consistent
    prompt_text = select_prompt(
        priority,
        use_png_prompt=use_png_prompt,
        use_video_prompt=use_video_prompt,
        provider="openai",
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    attempt = 0
    while attempt < API_MAX_RETRIES:
        if check_stop_event(stop_event, "Blackbox request cancelled during retries"):
            return "stopped"

        payload = _build_payload(images, prompt_text, model_to_use, keyword_count)

        try:
            log_message(
                f"Sending metadata request to Blackbox model {model_to_use} (key ...{api_key[-5:]})",
                "info",
            )
            response = requests.post(
                API_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=API_TIMEOUT,
            )
        except requests.RequestException as exc:
            if check_stop_event(stop_event):
                return "stopped"
            log_message(f"Blackbox request failed: {exc}", "error")
            attempt += 1
            if attempt >= API_MAX_RETRIES:
                return {"error": str(exc)}
            time.sleep(RETRY_DELAY_SECONDS * attempt)
            continue

        if response.status_code == 200:
            try:
                response_data = response.json()
            except Exception as exc:
                log_message(f"Failed to decode Blackbox response JSON: {exc}", "error")
                return {"error": "invalid_json"}

            metadata = _parse_blackbox_response(response_data)
            if metadata:
                log_message("Metadata successfully extracted from Blackbox response", "success")
                return metadata

            log_message(
                "Blackbox response did not include usable metadata. If this persists, try another model.",
                "warning",
            )
            return {"error": "empty_response"}

        if response.status_code in {401, 403}:
            log_message("Blackbox authentication error - check API key", "error")
            return {"error": f"Authentication failed ({response.status_code})"}

        if response.status_code == 429:
            if check_stop_event(stop_event):
                return "stopped"
            log_message("Blackbox rate limit hit, backing off before retry", "warning")
            attempt += 1
            time.sleep(RETRY_DELAY_SECONDS * attempt)
            continue

        if 500 <= response.status_code < 600:
            if check_stop_event(stop_event):
                return "stopped"
            log_message(f"Blackbox server error {response.status_code}, retrying", "warning")
            attempt += 1
            time.sleep(RETRY_DELAY_SECONDS * attempt)
            continue

        error_text = ""
        try:
            error_payload = response.json()
            if isinstance(error_payload, dict):
                error_text = json.dumps(error_payload)[:200]
        except Exception:
            error_text = (response.text or "")[:200]

        log_message(
            f"Blackbox request failed (HTTP {response.status_code}): {error_text}",
            "error",
        )
        return {"error": error_text or f"http_{response.status_code}"}

    return {"error": "blackbox_max_retries"}


def check_api_keys_status(api_keys: Iterable[str], model: Optional[str] = None) -> dict:
    results: Dict[str, Tuple[int, str]] = {}
    test_model = (model or DEFAULT_MODEL).strip()

    payload = {
        "model": test_model,
        "messages": [{"role": "user", "content": "ping"}],
        "temperature": 0,
        "max_tokens": 8,
        "stream": False,
    }

    for key in api_keys:
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(
                API_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=20,
            )
            if response.status_code == 200:
                results[key] = (200, "OK")
            else:
                results[key] = (response.status_code, (response.text or "")[:120] or "error")
        except Exception as exc:
            results[key] = (-1, str(exc)[:120])

    return results
