import base64
import json
import os
from urllib.parse import parse_qs, urlparse
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import quote, urljoin

import requests
import runpod


WORK_ROOT = Path(os.environ.get("WORK_ROOT", "/tmp/fusioninteract-ace-step"))
ACESTEP_HOME = Path(os.environ.get("ACESTEP_HOME", "/opt/ACE-Step-1.5"))
ACESTEP_API_HOST = os.environ.get("ACESTEP_API_HOST", "127.0.0.1")
ACESTEP_API_PORT = int(os.environ.get("ACESTEP_API_PORT", "8001"))
ACESTEP_API_URL = f"http://{ACESTEP_API_HOST}:{ACESTEP_API_PORT}"
ACESTEP_API_KEY = os.environ.get("ACESTEP_API_KEY", "").strip()
ACESTEP_PROCESS = None
ACESTEP_LOG_PATH = Path(os.environ.get("ACESTEP_LOG_PATH", "/tmp/ace-step-api.log"))
WORKER_VERSION = "20260708-casing-storage-v2"

BUNNY_STORAGE_HOST = os.environ.get("BUNNY_STORAGE_HOST", "https://storage.bunnycdn.com").rstrip("/")
if BUNNY_STORAGE_HOST and "://" not in BUNNY_STORAGE_HOST:
    BUNNY_STORAGE_HOST = f"https://{BUNNY_STORAGE_HOST}"
BUNNY_STORAGE_ZONE = os.environ.get("BUNNY_STORAGE_ZONE", "").strip("/")
BUNNY_STORAGE_ACCESS_KEY = os.environ.get("BUNNY_STORAGE_ACCESS_KEY", "")
BUNNY_PUBLIC_BASE_URL = os.environ.get("BUNNY_PUBLIC_BASE_URL", "").rstrip("/")


def _bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _safe_name(value, default="ace-music"):
    value = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or ""))
    value = "-".join(part for part in value.split("-") if part)
    return (value or default)[:90]


def _get_ci(mapping, key, default=None):
    if not isinstance(mapping, dict):
        return default
    if key in mapping:
        return mapping[key]
    upper_key = key.upper()
    if upper_key in mapping:
        return mapping[upper_key]
    lower_key = key.lower()
    for item_key, item_value in mapping.items():
        if str(item_key).lower() == lower_key:
            return item_value
    return default


def _headers():
    headers = {"Content-Type": "application/json"}
    if ACESTEP_API_KEY:
        headers["Authorization"] = f"Bearer {ACESTEP_API_KEY}"
    return headers


def _download(url, target, headers=None):
    with requests.get(url, headers=headers or {}, stream=True, timeout=600) as response:
        response.raise_for_status()
        with target.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)


def _write_base64_audio(encoded_audio, target):
    if "," in encoded_audio[:200]:
        encoded_audio = encoded_audio.split(",", 1)[1]
    target.write_bytes(base64.b64decode(encoded_audio, validate=True))


def _content_type(path):
    return {
        ".aac": "audio/aac",
        ".flac": "audio/flac",
        ".mp3": "audio/mpeg",
        ".opus": "audio/ogg",
        ".wav": "audio/wav",
    }.get(path.suffix.lower(), "application/octet-stream")


def _upload_to_bunny(local_path, remote_path):
    if not (BUNNY_STORAGE_ZONE and BUNNY_STORAGE_ACCESS_KEY):
        return {"public_url": None, "storage_url": None}
    remote_path = remote_path.strip("/")
    url = f"{BUNNY_STORAGE_HOST}/{BUNNY_STORAGE_ZONE}/{quote(remote_path, safe='/')}"
    headers = {
        "AccessKey": BUNNY_STORAGE_ACCESS_KEY,
        "Content-Type": _content_type(local_path),
    }
    with local_path.open("rb") as handle:
        response = requests.put(url, headers=headers, data=handle, timeout=900)
    response.raise_for_status()
    storage_url = f"bunny-storage://{remote_path}"
    public_url = None
    if BUNNY_PUBLIC_BASE_URL:
        public_url = f"{BUNNY_PUBLIC_BASE_URL}/{quote(remote_path, safe='/')}"
    return {"public_url": public_url, "storage_url": storage_url}


def _ace_command():
    uv_bin = os.environ.get("ACESTEP_UV_BIN", "").strip() or shutil.which("uv") or "/root/.local/bin/uv"
    command = [
        uv_bin,
        "run",
        "--project",
        str(ACESTEP_HOME),
        "python",
        "-m",
        "acestep.api_server",
        "--host",
        ACESTEP_API_HOST,
        "--port",
        str(ACESTEP_API_PORT),
    ]
    api_key = os.environ.get("ACESTEP_API_KEY", "").strip()
    if api_key:
        command.extend(["--api-key", api_key])
    return command


def _tail_ace_log(max_chars=4000):
    try:
        if not ACESTEP_LOG_PATH.exists():
            return ""
        data = ACESTEP_LOG_PATH.read_text(errors="replace")
        return data[-max_chars:]
    except Exception as exc:
        return f"Could not read ACE-Step log: {exc}"


def _start_api_if_needed():
    global ACESTEP_PROCESS
    try:
        response = requests.get(f"{ACESTEP_API_URL}/health", timeout=3)
        if response.status_code < 500:
            return
    except Exception:
        pass

    if ACESTEP_PROCESS and ACESTEP_PROCESS.poll() is None:
        return

    print("ace-step-worker - starting ACE-Step API server...")
    print("ace-step-worker - command:", " ".join(_ace_command()))
    ACESTEP_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_handle = ACESTEP_LOG_PATH.open("ab")
    ACESTEP_PROCESS = subprocess.Popen(
        _ace_command(),
        cwd=str(ACESTEP_HOME),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
    )


def _wait_for_api(timeout_seconds=1800):
    _start_api_if_needed()
    deadline = time.time() + timeout_seconds
    last_error = ""
    while time.time() < deadline:
        if ACESTEP_PROCESS and ACESTEP_PROCESS.poll() is not None:
            raise RuntimeError(f"ACE-Step API exited with code {ACESTEP_PROCESS.returncode}. Log tail: {_tail_ace_log()}")
        try:
            response = requests.get(f"{ACESTEP_API_URL}/health", timeout=10)
            if response.status_code < 500:
                print("ace-step-worker - ACE-Step API is ready")
                return
            last_error = f"HTTP {response.status_code}: {response.text[:300]}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(5)
    raise TimeoutError(f"ACE-Step API did not become ready: {last_error}. Log tail: {_tail_ace_log()}")


def _unwrap_response(response, label):
    try:
        data = response.json()
    except Exception as exc:
        raise RuntimeError(f"{label} returned non-JSON response: {response.text[:500]}") from exc
    if response.status_code >= 400 or data.get("code", 200) >= 400 or data.get("error"):
        raise RuntimeError(f"{label} failed: {data.get('error') or response.text[:500]}")
    return data.get("data")


def _query_task(task_id):
    response = requests.post(
        f"{ACESTEP_API_URL}/query_result",
        headers=_headers(),
        json={"task_id_list": [task_id]},
        timeout=120,
    )
    data = _unwrap_response(response, "query_result")
    if not data:
        return {}
    return data[0]


def _parse_result(result_value):
    if isinstance(result_value, str):
        if not result_value.strip():
            return []
        return json.loads(result_value)
    if isinstance(result_value, list):
        return result_value
    if isinstance(result_value, dict):
        return [result_value]
    return []


def _extension_from_audio_value(file_value, default=".wav"):
    parsed = urlparse(file_value)
    path_candidates = [parsed.path]
    query_path = parse_qs(parsed.query).get("path", [""])[0]
    if query_path:
        path_candidates.insert(0, query_path)
    for candidate in path_candidates:
        extension = os.path.splitext(candidate)[1].lower()
        if extension in {".flac", ".mp3", ".opus", ".aac", ".wav"}:
            return extension
    return default


def _download_outputs(outputs, work_dir):
    downloaded = []
    for index, item in enumerate(outputs, start=1):
        file_value = (item.get("file") or item.get("url") or "").strip()
        if not file_value:
            continue
        extension = _extension_from_audio_value(file_value)
        target = work_dir / f"ace-step-output-{index}{extension}"
        audio_url = file_value if file_value.startswith("http") else urljoin(f"{ACESTEP_API_URL}/", file_value.lstrip("/"))
        _download(audio_url, target, headers={"Authorization": f"Bearer {ACESTEP_API_KEY}"} if ACESTEP_API_KEY else {})
        downloaded.append({"path": target, "source": file_value, "metadata": item})
    return downloaded


def _stage_optional_audio(job_input, work_dir, key_prefix):
    url = (_get_ci(job_input, f"{key_prefix}_audio_url") or "").strip()
    encoded = (_get_ci(job_input, f"{key_prefix}_audio_base64") or "").strip()
    if not url and not encoded:
        return ""
    extension = _safe_name(_get_ci(job_input, f"{key_prefix}_audio_extension") or "wav", "wav")
    target = work_dir / f"{key_prefix}-audio.{extension}"
    if encoded:
        _write_base64_audio(encoded, target)
    else:
        download_headers = _get_ci(job_input, "download_headers")
        _download(url, target, headers=download_headers if isinstance(download_headers, dict) else {})
    return str(target)


def handler(job):
    start_time = time.time()
    job_input = job.get("input") or {}
    request_id = _safe_name(_get_ci(job_input, "request_id") or job.get("id") or uuid.uuid4().hex, "ace-job")
    title = _safe_name(_get_ci(job_input, "title") or request_id, "ace-music")
    work_dir = WORK_ROOT / request_id
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        _wait_for_api(int(_get_ci(job_input, "api_start_timeout_seconds") or os.environ.get("ACESTEP_API_START_TIMEOUT_SECONDS", "1800")))

        audio_format = (_get_ci(job_input, "audio_format") or os.environ.get("ACESTEP_OUTPUT_FORMAT", "wav")).lower()
        if audio_format not in {"flac", "mp3", "opus", "aac", "wav", "wav32"}:
            return {"ok": False, "error": "audio_format must be flac, mp3, opus, aac, wav, or wav32", "audio_format": audio_format}

        duration_seconds = float(_get_ci(job_input, "duration_seconds") or _get_ci(job_input, "audio_duration") or os.environ.get("ACESTEP_DEFAULT_DURATION_SECONDS", "60"))
        duration_seconds = max(10.0, min(600.0, duration_seconds))
        batch_size = int(_get_ci(job_input, "batch_size") or os.environ.get("ACESTEP_DEFAULT_BATCH_SIZE", "1"))
        batch_size = max(1, min(8, batch_size))

        payload = {
            "prompt": (_get_ci(job_input, "prompt") or _get_ci(job_input, "description") or "").strip(),
            "lyrics": (_get_ci(job_input, "lyrics") or "").strip(),
            "sample_query": (_get_ci(job_input, "sample_query") or "").strip(),
            "sample_mode": _bool(_get_ci(job_input, "sample_mode"), False),
            "use_format": _bool(_get_ci(job_input, "use_format"), True),
            "thinking": _bool(_get_ci(job_input, "thinking"), _bool(os.environ.get("ACESTEP_DEFAULT_THINKING"), True)),
            "vocal_language": _get_ci(job_input, "vocal_language") or "en",
            "audio_format": audio_format,
            "audio_duration": duration_seconds,
            "model": _get_ci(job_input, "model") or os.environ.get("ACESTEP_CONFIG_PATH", "acestep-v15-xl-sft"),
            "lm_model_path": _get_ci(job_input, "lm_model_path") or os.environ.get("ACESTEP_LM_MODEL_PATH", "acestep-5Hz-lm-4B"),
            "lm_backend": _get_ci(job_input, "lm_backend") or os.environ.get("ACESTEP_LM_BACKEND", "vllm"),
            "inference_steps": int(_get_ci(job_input, "inference_steps") or os.environ.get("ACESTEP_DEFAULT_INFERENCE_STEPS", "64")),
            "guidance_scale": float(_get_ci(job_input, "guidance_scale") or os.environ.get("ACESTEP_DEFAULT_GUIDANCE_SCALE", "7.0")),
            "batch_size": batch_size,
            "metas": _get_ci(job_input, "metas") if isinstance(_get_ci(job_input, "metas"), dict) else {},
        }
        for optional_key in ("bpm", "key_scale", "time_signature", "infer_method", "shift", "timesteps", "use_adg", "cfg_interval_start", "cfg_interval_end"):
            optional_value = _get_ci(job_input, optional_key)
            if optional_value not in (None, ""):
                payload[optional_key] = optional_value
        seed_value = _get_ci(job_input, "seed")
        if seed_value is not None and str(seed_value).strip() not in {"", "-1"}:
            payload["seed"] = int(seed_value)
            payload["use_random_seed"] = False

        reference_path = _stage_optional_audio(job_input, work_dir, "reference")
        source_path = _stage_optional_audio(job_input, work_dir, "source")
        if reference_path:
            payload["reference_audio_path"] = reference_path
        if source_path:
            payload["src_audio_path"] = source_path
            payload["task_type"] = _get_ci(job_input, "task_type") or "repaint"
        elif _get_ci(job_input, "task_type"):
            payload["task_type"] = _get_ci(job_input, "task_type")

        submit_started = time.time()
        response = requests.post(f"{ACESTEP_API_URL}/release_task", headers=_headers(), json=payload, timeout=180)
        submit_data = _unwrap_response(response, "release_task")
        task_id = submit_data.get("task_id") if isinstance(submit_data, dict) else ""
        if not task_id:
            raise RuntimeError(f"ACE-Step did not return a task_id: {submit_data}")

        poll_attempts = int(_get_ci(job_input, "poll_attempts") or os.environ.get("ACESTEP_POLL_ATTEMPTS", "720"))
        poll_sleep_seconds = float(_get_ci(job_input, "poll_sleep_seconds") or os.environ.get("ACESTEP_POLL_SLEEP_SECONDS", "5"))
        last_status = {}
        for _ in range(max(1, poll_attempts)):
            time.sleep(max(1.0, poll_sleep_seconds))
            last_status = _query_task(task_id)
            status_value = int(last_status.get("status", 0))
            if status_value == 1:
                break
            if status_value == 2:
                raise RuntimeError(f"ACE-Step task failed: {last_status}")
        else:
            raise TimeoutError(f"ACE-Step task timed out: {last_status}")

        result_items = _parse_result(last_status.get("result"))
        downloaded = _download_outputs(result_items, work_dir)
        upload_prefix = (_get_ci(job_input, "upload_prefix") or f"media/fusioninteract/ace-step/{request_id}").strip("/")
        outputs = []
        for index, item in enumerate(downloaded, start=1):
            local_path = item["path"]
            remote_path = f"{upload_prefix}/{title}-{index}{local_path.suffix.lower()}"
            upload_result = _upload_to_bunny(local_path, remote_path)
            public_url = upload_result.get("public_url")
            storage_url = upload_result.get("storage_url")
            audio_base64 = ""
            if not (public_url or storage_url) or _bool(_get_ci(job_input, "return_base64"), False):
                audio_base64 = base64.b64encode(local_path.read_bytes()).decode("utf-8")
            outputs.append({
                "file_name": local_path.name,
                "bytes": local_path.stat().st_size,
                "content_type": _content_type(local_path),
                "url": storage_url or public_url,
                "public_url": public_url,
                "storage_url": storage_url,
                "base64": audio_base64,
                "metadata": item["metadata"],
            })

        return {
            "ok": True,
            "worker_version": WORKER_VERSION,
            "provider": "ace_step",
            "task_id": task_id,
            "model": payload.get("model"),
            "lm_model_path": payload.get("lm_model_path"),
            "thinking": payload.get("thinking"),
            "audio_format": audio_format,
            "duration_seconds": duration_seconds,
            "batch_size": batch_size,
            "metadata": {
                "prompt": payload.get("prompt"),
                "lyrics_provided": bool(payload.get("lyrics")),
                "inference_steps": payload.get("inference_steps"),
                "guidance_scale": payload.get("guidance_scale"),
                "worker_version": WORKER_VERSION,
            },
            "output_count": len(outputs),
            "outputs": outputs,
            "timing": {
                "submit_seconds": round(time.time() - submit_started, 3),
                "total_seconds": round(time.time() - start_time, 3),
            },
        }
    except Exception as exc:
        return {
            "ok": False,
            "provider": "ace_step",
            "error": str(exc),
            "timing": {"total_seconds": round(time.time() - start_time, 3)},
        }
    finally:
        if not _bool(_get_ci(job_input, "keep_work_dir"), False):
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
