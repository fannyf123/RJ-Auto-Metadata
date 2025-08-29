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

# src/api/gemini_api.py
import os
import sys
import random
import requests
import base64
import json
import time
import re
import threading
from collections import defaultdict
from src.utils.logging import log_message

# SDK DISABLED - Using pure REST API only for quota efficiency
# try:
#     from google import genai
#     from google.genai import types
#     GENAI_SDK_AVAILABLE = True
# except ImportError:
GENAI_SDK_AVAILABLE = False
log_message("Google Generative AI SDK disabled - Using pure REST API for optimal quota usage.", "info")
from src.api.gemini_prompts import (
    PROMPT_TEXT, PROMPT_TEXT_PNG, PROMPT_TEXT_VIDEO,
    PROMPT_TEXT_BALANCED, PROMPT_TEXT_PNG_BALANCED, PROMPT_TEXT_VIDEO_BALANCED,
    PROMPT_TEXT_FAST, PROMPT_TEXT_PNG_FAST, PROMPT_TEXT_VIDEO_FAST
)

# SDK client functions removed - using pure REST API only

# Reordered models: 1.5 series first (better rate limits for free keys)
GEMINI_MODELS = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
    # "gemini-1.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",  
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite-preview-06-17",
    "gemini-2.5-pro"
]

# Thinking budget constants removed - pure REST API doesn't support thinking config

DEFAULT_MODEL = "gemini-1.5-flash"
FALLBACK_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash-8b",
    "gemini-1.5-flash"
]
MODEL_LAST_USED = defaultdict(float)
MODEL_LOCK = threading.Lock()
API_KEY_LAST_USED = defaultdict(float) 
API_KEY_LOCK = threading.Lock() 
API_KEY_MIN_INTERVAL = 3.0  # Increased from 2.0 to 3.0 for better rate limit management

# Extension-like API key blacklisting for rate limits
API_KEY_BLACKLIST = {}  # {api_key: expiry_timestamp}
RATE_LIMIT_BLACKLIST_DURATION = 60  # 60 seconds blacklist for rate-limited keys
SUCCESS_DELAY = 1.0  # Small delay after successful requests to avoid burst rate limits 

# DEBUG: Force failure for testing Auto Retry (set to True for testing)
DEBUG_FORCE_FAILURE = False  # ← SET TO FALSE FOR NORMAL USE
DEBUG_FAILURE_RATE = 0.3  # 30% of files will artificially fail

API_TIMEOUT = 60
API_MAX_RETRIES = 1  # Reduced from 3 to 1 for quota efficiency
API_RETRY_DELAY = 10

FORCE_STOP_FLAG = False

def blacklist_api_key(api_key, reason='rate limit'):
    """Blacklist an API key due to rate limiting"""
    expiry = time.time() + RATE_LIMIT_BLACKLIST_DURATION
    API_KEY_BLACKLIST[api_key] = expiry
    log_message(f"API key ...{api_key[-4:]} blacklisted for {RATE_LIMIT_BLACKLIST_DURATION}s due to {reason}", "warning")

def calculate_smart_delay(api_keys_list: list, user_delay: float) -> tuple[float, str]:
    """
    Calculate optimal delay based on API key blacklist status.
    
    Returns:
        tuple: (effective_delay, reason_message)
    """
    if not api_keys_list:
        return user_delay, "No API keys available"
    
    now = time.time()
    
    # Check if all keys are blacklisted
    blacklisted_keys = []
    available_keys = []
    earliest_expiry = float('inf')
    
    for key in api_keys_list:
        blacklist_expiry = API_KEY_BLACKLIST.get(key)
        if blacklist_expiry and now < blacklist_expiry:
            blacklisted_keys.append(key)
            earliest_expiry = min(earliest_expiry, blacklist_expiry)
        else:
            available_keys.append(key)
    
    # If there are available keys, use normal delay
    if available_keys:
        return user_delay, f"Using normal delay ({len(available_keys)}/{len(api_keys_list)} keys available)"
    
    # All keys are blacklisted - calculate smart delay
    if blacklisted_keys:
        remaining_blacklist_time = earliest_expiry - now
        if remaining_blacklist_time > user_delay:
            # Override user delay with blacklist time + buffer
            smart_delay = remaining_blacklist_time + 5  # 5s buffer
            reason = f"Smart delay override: All {len(api_keys_list)} API key(s) blacklisted. " \
                    f"User delay {user_delay}s → {smart_delay:.1f}s to wait for blacklist expiry"
            return smart_delay, reason
    
    # Fallback to user delay
    return user_delay, "Using user delay (blacklist expired or edge case)"

def select_smart_api_key(api_keys_list: list) -> str | None:
    if not api_keys_list:
        return None

    with API_KEY_LOCK:
        now = time.time()
        
        # Filter out blacklisted keys (rate-limited recently)
        available_keys = []
        for key in api_keys_list:
            blacklist_expiry = API_KEY_BLACKLIST.get(key)
            if blacklist_expiry and now < blacklist_expiry:
                log_message(f"API key ...{key[-4:]} still blacklisted for {int(blacklist_expiry - now)}s", "debug")
                continue
            # Remove expired blacklist entries
            elif blacklist_expiry and now >= blacklist_expiry:
                del API_KEY_BLACKLIST[key]
                log_message(f"API key ...{key[-4:]} removed from blacklist", "info")
            available_keys.append(key)
        
        if not available_keys:
            log_message("All API keys are blacklisted! Using least recently blacklisted key.", "warning")
            # If all keys are blacklisted, use the one that expires soonest
            earliest_expiry = float('inf')
            least_recent_key = None
            for key in api_keys_list:
                expiry = API_KEY_BLACKLIST.get(key, 0)
                if expiry < earliest_expiry:
                    earliest_expiry = expiry
                    least_recent_key = key
            return least_recent_key
        
        # Select oldest used key from available keys
        key_statuses = []
        for key in available_keys:
            last_used_time = API_KEY_LAST_USED.get(key, 0)
            key_statuses.append((last_used_time, key))

        key_statuses.sort(key=lambda x: x[0])
        selected_key = key_statuses[0][1]
        API_KEY_LAST_USED[selected_key] = now
        
        log_message(f"Selected API key ...{selected_key[-4:]} ({len(available_keys)}/{len(api_keys_list)} keys available)", "debug")
        return selected_key

def select_best_fallback_model(fallback_models_list: list, excluded_model_name: str | None = None) -> str | None:
    if not fallback_models_list:
        return None

    model_statuses = []
    for model_name in fallback_models_list:
        if model_name == excluded_model_name:
            log_message(f"Model fallback '{model_name}' skipped because it's the same as the failed new model.", "info")
            continue
        if model_name not in GEMINI_MODELS:
            log_message(f"Model fallback '{model_name}' not in GEMINI_MODELS list, skipped.", "warning")
            continue
        last_used_time = MODEL_LAST_USED.get(model_name, 0)
        model_statuses.append((last_used_time, model_name))

    if not model_statuses:
        return None

    model_statuses.sort(key=lambda x: x[0])
        
    return model_statuses[0][1]

def is_stop_requested():
    global FORCE_STOP_FLAG
    return FORCE_STOP_FLAG

def set_force_stop():
    global FORCE_STOP_FLAG
    FORCE_STOP_FLAG = True
    log_message("Force stop flag has been activated. All processes will stop immediately.", "warning")

def reset_force_stop():
    global FORCE_STOP_FLAG
    FORCE_STOP_FLAG = False

def check_stop_event(stop_event, message=None):
    if is_stop_requested():
        if message: log_message(message)
        return True
    if stop_event is not None:
        try:
            is_set = stop_event.is_set()
            if is_set and message: log_message(message)
            return is_set
        except Exception as e:
            log_message(f"Error checking stop_event: {e}")
            return False
    return False

def get_api_endpoint(model_name):
    return f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"

def select_next_model():
    with MODEL_LOCK:
        sorted_models = sorted(GEMINI_MODELS, key=lambda m: MODEL_LAST_USED.get(m, 0))
        
        selected_model = sorted_models[0]
        
        MODEL_LAST_USED[selected_model] = time.time()
        return selected_model

def wait_for_model_cooldown(model_name, stop_event=None):
    try:
        min_interval = 0.75
        last_used = MODEL_LAST_USED.get(model_name, 0)
        now = time.time()
        remaining = last_used + min_interval - now
        while remaining > 0:
            if check_stop_event(stop_event):
                return
            time.sleep(min(remaining, 0.05))
            now = time.time()
            remaining = last_used + min_interval - now
    except Exception:
        return

def wait_for_api_key_cooldown(api_key, stop_event=None):
    try:
        last_used = API_KEY_LAST_USED.get(api_key, 0)
        now = time.time()
        remaining = last_used + API_KEY_MIN_INTERVAL - now
        while remaining > 0:
            if check_stop_event(stop_event):
                return
            time.sleep(min(remaining, 0.05))
            now = time.time()
            remaining = last_used + API_KEY_MIN_INTERVAL - now
        API_KEY_LAST_USED[api_key] = time.time()
    except Exception:
        return

def _attempt_gemini_request(
    image_paths,
    current_api_key: str,
    model_to_use: str,
    stop_event,
    use_png_prompt: bool,
    use_video_prompt: bool,
    priority: str,
    image_basename: str,
    is_vector_conversion: bool = False
) -> tuple:

    if check_stop_event(stop_event, f"API request cancelled before model cooldown: {image_basename}"):
        return -2, None, "stopped", "Process stopped before model cooldown"

    wait_for_model_cooldown(model_to_use, stop_event)

    if check_stop_event(stop_event, f"API request cancelled after model cooldown: {image_basename}"):
        return -2, None, "stopped", "Process stopped after model cooldown"

    api_endpoint = get_api_endpoint(model_to_use)
    
    if isinstance(image_paths, str):
        image_paths = [image_paths]
        log_message(f"Sending {image_basename} to model {model_to_use} (API Key: ...{current_api_key[-5:]})", "info")
    else:
        log_message(f"Sending {len(image_paths)} frame(s) from {image_basename} to model {model_to_use} (API Key: ...{current_api_key[-5:]})", "info")

    final_is_vector_conversion = is_vector_conversion or "converted" in image_basename.lower()
    is_video_processing = isinstance(image_paths, list) and len(image_paths) > 1

    selected_prompt_text = PROMPT_TEXT
    if priority == "Less":
        if use_video_prompt: selected_prompt_text = PROMPT_TEXT_VIDEO_FAST
        elif use_png_prompt: selected_prompt_text = PROMPT_TEXT_PNG_FAST
        else: selected_prompt_text = PROMPT_TEXT_FAST
    elif priority == "Balanced":
        if use_video_prompt: selected_prompt_text = PROMPT_TEXT_VIDEO_BALANCED
        elif use_png_prompt: selected_prompt_text = PROMPT_TEXT_PNG_BALANCED
        else: selected_prompt_text = PROMPT_TEXT_BALANCED
    else:
        if use_video_prompt: selected_prompt_text = PROMPT_TEXT_VIDEO
        elif use_png_prompt: selected_prompt_text = PROMPT_TEXT_PNG
        else: selected_prompt_text = PROMPT_TEXT
    
    prompt_name = "UNKNOWN"
    if selected_prompt_text == PROMPT_TEXT: prompt_name = "PROMPT_TEXT (Detailed)"
    elif selected_prompt_text == PROMPT_TEXT_PNG: prompt_name = "PROMPT_TEXT_PNG (Detailed)"
    elif selected_prompt_text == PROMPT_TEXT_VIDEO: prompt_name = "PROMPT_TEXT_VIDEO (Detailed)"
    elif selected_prompt_text == PROMPT_TEXT_BALANCED: prompt_name = "PROMPT_TEXT_BALANCED (Balanced)"
    elif selected_prompt_text == PROMPT_TEXT_PNG_BALANCED: prompt_name = "PROMPT_TEXT_PNG_BALANCED (Balanced)"
    elif selected_prompt_text == PROMPT_TEXT_VIDEO_BALANCED: prompt_name = "PROMPT_TEXT_VIDEO_BALANCED (Balanced)"
    elif selected_prompt_text == PROMPT_TEXT_FAST: prompt_name = "PROMPT_TEXT_FAST (Less)"
    elif selected_prompt_text == PROMPT_TEXT_PNG_FAST: prompt_name = "PROMPT_TEXT_PNG_FAST (Less)"
    elif selected_prompt_text == PROMPT_TEXT_VIDEO_FAST: prompt_name = "PROMPT_TEXT_VIDEO_FAST (Less)"
    
    # CRITICAL FIX: Use same parts order as extension (IMAGE FIRST, TEXT SECOND)
    parts = []  # Start with empty parts array
    
    for img_path in image_paths:
        try:
            file_size = os.path.getsize(img_path)
            
            with open(img_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode("utf-8")
            
            # Use hardcoded mime_type like extension for consistency and reduced processing
            mime_type = "image/jpeg"  # Extension uses hardcoded jpeg for all images
            
            # Add image FIRST (like extension)
            parts.append({"inline_data": {"mime_type": mime_type, "data": image_data}})
            
        except Exception as e:
            log_message(f"Error reading image file ({os.path.basename(img_path)}): {e}", "error")
            return -3, None, "file_read", str(e)
    
    # Add text prompt AFTER images (like extension: IMAGE FIRST, TEXT SECOND)
    parts.append({"text": selected_prompt_text})

    max_output_tokens = 800
    # Cap output tokens to reduce cost/limits for metadata tasks
    if "gemini-2.5-pro" in model_to_use:
        max_output_tokens = 10000
    elif "gemini-2.5-flash" in model_to_use and "lite" not in model_to_use:
        max_output_tokens = 10000
    elif "gemini-2.5-flash-lite-preview-06-17" in model_to_use:
        max_output_tokens = 2000
    
    # Use structured output like extension for token efficiency
    payload = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": 0.2, 
            "maxOutputTokens": max_output_tokens,
            "topP": 0.8, 
            "topK": 40,
            "response_mime_type": "application/json",
            "response_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "maxLength": 180},
                    "description": {"type": "string", "maxLength": 500},
                    "keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 60
                    },
                    "adobe_stock_category": {"type": "string"},
                    "shutterstock_category": {"type": "string"}
                },
                "required": ["title", "description", "keywords", "adobe_stock_category", "shutterstock_category"]
            }
        }
    }
    
    # SDK DISABLED - Using pure REST API only for optimal quota usage
    # log_message(f"Using REST API for {model_to_use}", "info")
    
    # Use minimal headers like extension (no User-Agent to avoid rate limit triggers)
    headers = {"Content-Type": "application/json"}
    api_url = f"{api_endpoint}?key={current_api_key}"

    if check_stop_event(stop_event, f"API request dibatalkan sebelum POST: {image_basename}"):
        return -2, None, "stopped", "Process stopped before API POST"

    session = requests.Session()
    session.mount('https://', requests.adapters.HTTPAdapter(
        max_retries=requests.adapters.Retry(total=1, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504], allowed_methods=["POST"], respect_retry_after_header=True)
    ))
    
    response_event = threading.Event()
    response_container = {'response': None, 'error': None}

    def perform_api_request_in_thread():
        try:
            resp = session.post(api_url, headers=headers, json=payload, timeout=API_TIMEOUT, verify=True)
            response_container['response'] = resp
        except Exception as e_req:
            response_container['error'] = e_req
        finally:
            response_event.set()

    api_thread = threading.Thread(target=perform_api_request_in_thread)
    api_thread.daemon = True
    api_thread.start()

    while not response_event.is_set():
        if check_stop_event(stop_event, f"API request cancelled while waiting for response: {image_basename}"):
            return -2, None, "stopped", "Process stopped while waiting for API response"
        response_event.wait(0.1)
    
    if response_container['error']:
        e = response_container['error']
        err_msg = f"RequestException ({type(e).__name__}): {str(e)}"
        log_message(f"Error request API for {image_basename} to {model_to_use}: {err_msg}", "error")
        error_type = "timeout" if isinstance(e, requests.exceptions.Timeout) else "connection_error" if isinstance(e, (requests.exceptions.ConnectionError, requests.exceptions.SSLError)) else "request_exception"
        return -4, None, error_type, str(e)

    response = response_container['response']
    if response is None:
        log_message(f"Error: Response from API is None without error in container ({image_basename}, {model_to_use}). This should not happen.", "error")
        return -1, None, "internal_null_response", "Response object was None without explicit error."
    
    http_status_code = response.status_code
    try:
        response_data = response.json()
    except json.JSONDecodeError:
        log_message(f"Error: API response is not valid JSON (Status: {http_status_code}) from {model_to_use} for {image_basename}. Response: {response.text[:200]}...", "error")
        return http_status_code, None, "json_decode_error", response.text[:500]

    if http_status_code == 200:
        if "candidates" in response_data and response_data["candidates"]:
            # Enhanced debug for thinking models
            if "2.5" in model_to_use:
                candidate = response_data["candidates"][0]
                parts = candidate.get("content", {}).get("parts", [])
                log_message(f"Thinking model {model_to_use} - parts count: {len(parts)}, keys: {list(candidate.keys())}", "debug")
                if not parts:
                    log_message(f"Full response structure: {response_data}", "debug")
            return 200, response_data, None, None 
        elif "promptFeedback" in response_data and response_data.get("promptFeedback", {}).get("blockReason"):
            feedback = response_data["promptFeedback"]
            block_reason = feedback["blockReason"]
            log_message(f"Content blocked by Gemini ({model_to_use}) for {image_basename}. Reason: {block_reason}", "warning")
            return 200, response_data, "blocked", block_reason
        else:
            log_message(f"Success response (200) from {model_to_use} for {image_basename} but no clear 'candidates' or 'blockReason'. Data: {str(response_data)[:200]}...", "warning")
            return 200, response_data, "success_no_candidates_or_block", "No candidates or blockReason in 200 response."
    else:
        error_details = response_data.get("error", {})
        api_error_code = error_details.get("code", "UNKNOWN_API_ERR_CODE")
        api_error_message = error_details.get("message", "No specific error message from API.")
        
        log_message(f"API Error [{model_to_use}] untuk {image_basename}: HTTP {http_status_code}, Code API: {api_error_code} - {api_error_message}", "error")
        return http_status_code, response_data, "api_error", api_error_message

def _extract_metadata_from_text(generated_text: str, keyword_count: str) -> dict | None:
    """Extract metadata from Gemini response - handles both JSON structured output and legacy text format"""
    title = ""
    description = ""
    tags = []
    as_category = ""
    ss_category = ""
    
    try:
        # Try parsing as JSON first (structured output)
        try:
            json_data = json.loads(generated_text.strip())
            if isinstance(json_data, dict):
                title = json_data.get("title", "")
                description = json_data.get("description", "")
                
                # Handle keywords - could be array or comma-separated string
                keywords = json_data.get("keywords", [])
                if isinstance(keywords, list):
                    tags = [str(kw).strip() for kw in keywords if str(kw).strip()]
                elif isinstance(keywords, str):
                    tags = [kw.strip() for kw in keywords.split(",") if kw.strip()]
                
                # Remove duplicates while preserving order
                tags = list(dict.fromkeys(tags))
                
                # Apply keyword limit
                try:
                    max_kw = int(keyword_count)
                    if max_kw < 1: max_kw = 49
                except Exception:
                    max_kw = 49
                tags = tags[:max_kw]
                
                as_category = json_data.get("adobe_stock_category", "")
                ss_category = json_data.get("shutterstock_category", "")
                
                # log_message(f"Successfully parsed structured JSON output with {len(tags)} keywords", "debug")
                return {
                    "title": title,
                    "description": description,
                    "tags": tags,
                    "as_category": as_category,
                    "ss_category": ss_category
                }
        except (json.JSONDecodeError, TypeError) as json_error:
            # Fall back to regex parsing for legacy format
            # log_message(f"JSON parsing failed ({json_error}), falling back to regex parsing", "debug")
            pass
        
        # Legacy regex parsing for backward compatibility
        title_match = re.search(r"^Title:\s*(.*)", generated_text, re.MULTILINE | re.IGNORECASE)
        if title_match: title = title_match.group(1).strip()
        desc_match = re.search(r"^Description:\s*(.*)", generated_text, re.MULTILINE | re.IGNORECASE)
        if desc_match: description = desc_match.group(1).strip()
        keywords_match = re.search(r"^Keywords:\s*(.*)", generated_text, re.MULTILINE | re.IGNORECASE)
        if keywords_match:
            keywords_line = keywords_match.group(1).strip()
            keywords_line = re.split(r"AdobeStockCategory:|ShutterstockCategory:", keywords_line)[0].strip()
            tags = [k.strip() for k in keywords_line.split(",") if k.strip()]
            tags = list(dict.fromkeys(tags))
            try:
                max_kw = int(keyword_count)
                if max_kw < 1: max_kw = 49
            except Exception:
                max_kw = 49
            tags = tags[:max_kw]
        as_cat_match = re.search(r"AdobeStockCategory:\s*([\d]+\.?\s*[^\n]*)", generated_text)
        if as_cat_match:
            as_category = as_cat_match.group(1).strip()
        ss_cat_match = re.search(r"ShutterstockCategory:\s*([^\n]*)", generated_text)
        if ss_cat_match:
            ss_category = ss_cat_match.group(1).strip()
            
        log_message(f"Successfully parsed legacy text format with {len(tags)} keywords", "debug")
    except Exception as e:
        log_message(f"[ERROR] Failed to parse metadata from Gemini: {e}")
        return None
        
    return {
        "title": title,
        "description": description,
        "tags": tags,
        "as_category": as_category,
        "ss_category": ss_category
    }

def get_gemini_metadata(image_path, api_key, stop_event, use_png_prompt=False, use_video_prompt=False, selected_model_input=None, keyword_count="49", priority="Detailed", is_vector_conversion=False):
    is_multi_image = isinstance(image_path, list)
    
    if is_multi_image:
        image_basename = f"{os.path.basename(image_path[0])} (+{len(image_path)-1} other frames)"
        log_message(f"Starting process{len(image_path)} video frames with quality: {priority}, model input: {selected_model_input}")
    else:
        image_basename = os.path.basename(image_path)
        log_message(f"Starting process {image_basename} with quality: {priority}, model input: {selected_model_input}")
    
    # DEBUG: Artificial failure for testing Auto Retry
    if DEBUG_FORCE_FAILURE:
        import random
        if random.random() < DEBUG_FAILURE_RATE:
            log_message(f"🧪 DEBUG: Artificial failure triggered for {image_basename} (testing Auto Retry)", "warning")
            return {"error": "debug_artificial_failure", "message": "Simulated failure for Auto Retry testing"}
    
    allowed_api_ext = ('.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif')
    
    if is_multi_image:
        for img in image_path:
            _, ext = os.path.splitext(img)
            if not ext.lower() in allowed_api_ext:
                log_message(f"File type {ext.lower()} not supported for API call ({os.path.basename(img)}).", "warning")
                return None
    else:
        _, ext = os.path.splitext(image_path)
        if not ext.lower() in allowed_api_ext:
            log_message(f"File type {ext.lower()} not supported for API call ({image_basename}).", "warning")
            return None

    if check_stop_event(stop_event, f"get_gemini_metadata cancelled before loop retry: {image_basename}"):
        return "stopped"

    wait_for_api_key_cooldown(api_key, stop_event)
    if check_stop_event(stop_event, f"get_gemini_metadata cancelled after API key cooldown: {image_basename}"):
        return "stopped"

    current_retries = 0
    last_attempted_model = None
    
    model_to_use = DEFAULT_MODEL
    is_auto_rotate_mode = (selected_model_input is None or selected_model_input == "Auto Rotation")

    if not is_auto_rotate_mode:
        if selected_model_input not in GEMINI_MODELS:
            log_message(f"WARNING: Model input '{selected_model_input}' is not valid. Using default: {DEFAULT_MODEL}", "warning")
            model_to_use = DEFAULT_MODEL
        else:
            model_to_use = selected_model_input
            # log_message(f"Using fixed model: {model_to_use} (user selected)", "info")
    
    while current_retries < API_MAX_RETRIES:
        if check_stop_event(stop_event, f"get_gemini_metadata loop retry ({current_retries + 1}) cancelled: {image_basename}"):
            return "stopped"

        model_for_this_attempt = model_to_use
        if is_auto_rotate_mode:
            model_for_this_attempt = select_next_model() 
            # log_message(f"Auto Rotation: Model selected {model_for_this_attempt} for attempt {current_retries + 1}", "info")
        
        last_attempted_model = model_for_this_attempt

        # log_message(f"Attempt {current_retries + 1}/{API_MAX_RETRIES} using model: {model_for_this_attempt}", "info")
        
        http_status, response_data, error_type, error_detail = _attempt_gemini_request(
            image_path, api_key, model_for_this_attempt, stop_event,
            use_png_prompt, use_video_prompt, priority, image_basename, is_vector_conversion
        )
    
        if http_status == 200 and error_type is None:
            if response_data and "candidates" in response_data and response_data["candidates"]:
                candidate = response_data["candidates"][0]
                content = candidate.get("content", {})
                parts = content.get("parts", [])
                
                finish_reason = candidate.get("finishReason", "")
                if finish_reason == "MAX_TOKENS" and len(parts) == 0:
                    log_message(f"Response truncated due to MAX_TOKENS from {model_for_this_attempt} ({image_basename}). Consider increasing maxOutputTokens.", "warning")
                    error_type = "max_tokens_no_content"
                
                generated_text = ""
                if parts:
                    for part in parts:
                        if part.get("text") and not part.get("thought"):
                            generated_text = part.get("text", "")
                            break
                    
                    if not generated_text:
                        text_parts = [part for part in parts if part.get("text")]
                        if text_parts:
                            generated_text = text_parts[-1].get("text", "")
                    
                    if not generated_text:
                        for part in parts:
                            if part.get("text"):
                                generated_text = part.get("text", "")
                                break
                    
                    # Thinking models fallback: try direct text extraction
                    if not generated_text and "2.5" in model_for_this_attempt:
                        try:
                            # Alternative path for thinking models
                            alt_text = str(candidate.get("content", {}))
                            if "Title:" in alt_text or "Keywords:" in alt_text:
                                generated_text = alt_text
                                log_message(f"Thinking model fallback extraction succeeded for {model_for_this_attempt}", "info")
                        except Exception as e:
                            log_message(f"Thinking model fallback failed: {e}", "debug")
                    
                    if not generated_text:
                        log_message(f"Debug: Response parts structure from {model_for_this_attempt}: {[list(part.keys()) for part in parts]}", "debug")
                    else:
                        thinking_parts = [part for part in parts if part.get("thought")]
                        non_thinking_parts = [part for part in parts if part.get("text") and not part.get("thought")]
                
                if generated_text:
                    extracted_metadata = _extract_metadata_from_text(generated_text, keyword_count)
                    
                    if extracted_metadata:
                        log_message(f"Metadata successfully extracted from {model_for_this_attempt} for {image_basename}", "success")
                        # Small delay after success to avoid burst rate limits
                        time.sleep(SUCCESS_DELAY)
                        return extracted_metadata
                    else:
                        log_message(f"Failed to extract metadata structure (via helper) from Gemini text ({model_for_this_attempt}, {image_basename}).", "warning")
                        error_type = "extraction_failed"
                else:
                    # Enhanced debug for thinking models (2.5 series)
                    if "2.5" in model_for_this_attempt:
                        log_message(f"Thinking model {model_for_this_attempt} response structure: {[list(part.keys()) for part in parts] if parts else 'No parts found'}", "debug")
                    log_message(f"Gemini response structure is invalid (no 'parts'/'text') from {model_for_this_attempt} ({image_basename}).", "warning")
                    error_type = "invalid_response_structure"
            else:
                log_message(f"Success response (200) but no 'candidates' from {model_for_this_attempt} ({image_basename}).", "warning")
                error_type = "success_no_candidates_data"
        
        if error_type == "stopped":
            log_message(f"Processing stopped during API attempt for {image_basename}. Detail: {error_detail}", "warning")
            return "stopped"
        elif error_type == "blocked":
            log_message(f"Content blocked for {image_basename} by {model_for_this_attempt}. Reason: {error_detail}. No retry.", "error")
            return {"error": f"Content blocked by {model_for_this_attempt}: {error_detail}"}
        elif http_status == 429 or (error_type == "api_error" and response_data and response_data.get("error", {}).get("code") == 429):
            log_message(f"Rate limit (429) received for model {model_for_this_attempt} / API key ...{api_key[-4:]} on {image_basename}.", "warning")
            # Blacklist this API key immediately on 429
            blacklist_api_key(api_key, f'rate limit 429 - {model_for_this_attempt}')
            if not is_auto_rotate_mode:
                log_message(f"Warning: The model you selected ({model_for_this_attempt}) is reaching the quota limit. Try using a different model or Auto Rotation mode.", "warning")
        elif http_status in [400, 401, 403] or (error_type == "api_error" and response_data and response_data.get("error",{}).get("code",0) in [400,401,403]):
            err_msg = error_detail if error_detail else "Bad request/Auth error"
            log_message(f"Client error (HTTP {http_status}) for {image_basename} with {model_for_this_attempt}: {err_msg}. No retry.", "error")
            return {"error": f"{err_msg} (HTTP {http_status}, Model {model_for_this_attempt})"}

        current_retries += 1
        if current_retries < API_MAX_RETRIES:
            base_delay = API_RETRY_DELAY * (2 ** (current_retries -1 if current_retries > 0 else 0))
            jitter = random.uniform(0, 0.5 * base_delay)
            actual_delay = base_delay + jitter
            log_message(f"Waiting {actual_delay:.1f} seconds before retry ({current_retries + 1}/{API_MAX_RETRIES}) for {image_basename} (Last model: {model_for_this_attempt}, Error: {error_type or 'N/A'}) ...")
            
            wait_start_time = time.time()
            while time.time() - wait_start_time < actual_delay:
                if check_stop_event(stop_event, f"Retry delay stopped for {image_basename}"):
                    return "stopped"
                time.sleep(0.1)

    if is_auto_rotate_mode and last_attempted_model and http_status == 429:
        log_message(f"Last model '{last_attempted_model}' failed due to rate limit after all retries. {error_type}", "warning")
    
    log_message(f"All attempts ({current_retries}) failed for {image_basename}. Last model tried: {last_attempted_model}", "error")
    return {"error": f"Maximum retries exceeded for {image_basename}. Last model: {last_attempted_model}"}