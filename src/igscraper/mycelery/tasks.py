from celery import Celery
from ..config import load_config
from pathlib import Path
import os
import os
import random
import subprocess
import logging
from typing import List, Dict, Optional
from ..logger import get_logger
from ..utils import _set_bytestart_zero, _build_curl_for_entry_,classify_mp4_files,combine_audio_video
from .celery_app import app

logger = get_logger(__name__)

@app.task
def write_and_run_full_download_script_(
    video_results: list[dict],
    media_path: str,
    out_script_path: str = "download_full_media.sh",
    redact_cookies: bool = True,
    make_executable: bool = True,
    run_script: bool = False,
    sleep_between: float | None = 1.0,
    rnd_sleep_jitter: float = 0.5,
) -> dict:
    """
    Write a bash script that downloads full files (bytestart=0) for videos found.
    Saves output media into `media_path`.
    Returns metadata dict. Optionally runs the script and classifies downloaded mp4 files.
    """

    media_dir = os.path.abspath(media_path)
    os.makedirs(media_dir, exist_ok=True)

    commands = []

    for idx, item in enumerate(video_results):
        video_url = item.get("primaryUrl")
        video_fn = item.get("filename").replace(".mp4", f"_{idx}.mp4") if item.get("filename") else f"video_{idx}.mp4"
        headers = item.get("headers") or {}

        if video_url:
            fixed_url = _set_bytestart_zero(video_url)
            curl_cmd = _build_curl_for_entry_(
                fixed_url, video_fn, headers, redact_cookies=redact_cookies
            )
            commands.append(curl_cmd)

    # craft script
    header = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f'cd "{media_dir}"',
        'echo "Starting full-file downloads (bytestart=0)..."',
        ""
    ]
    body = []
    for i, cmd in enumerate(commands, start=1):
        body.append(f'echo "---- Running command {i}/{len(commands)} ----"')
        body.append(cmd)
        if sleep_between and sleep_between > 0:
            jitter = random.uniform(-rnd_sleep_jitter, rnd_sleep_jitter)
            sleep_time = max(0.0, float(sleep_between) + jitter)
            body.append(f"sleep {sleep_time:.2f}")
        body.append("")

    script_text = "\n".join(header + body)
    with open(out_script_path, "w", encoding="utf-8") as fh:
        fh.write(script_text)
    if make_executable:
        os.chmod(out_script_path, 0o755)

    result = {
        "script_path": os.path.abspath(out_script_path),
        "commands_written": commands,
        "media_dir": media_dir,
        "run": None,
        "classification": None
    }

    if run_script:
        proc = subprocess.Popen(
            ["bash", result["script_path"]],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = proc.communicate()
        result["run"] = {
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr
        }

        if proc.returncode != 0:
            logger.error("Download script failed with code %s", proc.returncode)
            if stderr:
                logger.error("stderr:\n%s", stderr.strip())
        else:
            # classify only if download script succeeded
            classification = classify_mp4_files(media_path)
            result["classification"] = classification
            logger.info("Classified downloaded mp4 files: %s", classification)

    return result
