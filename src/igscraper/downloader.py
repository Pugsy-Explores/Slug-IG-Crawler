import requests
from pathlib import Path
from .logger import get_logger
import time
import subprocess

logger = get_logger(__name__)

def download_media(url: str, folder: Path, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Determine file extension
            content_type = response.headers.get('content-type', '')
            if 'image/jpeg' in content_type:
                ext = '.jpg'
            elif 'image/png' in content_type:
                ext = '.png'
            elif 'video/' in content_type:
                ext = '.mp4'
            else:
                ext = '.bin'
            
            # Save file
            file_path = folder / f"media{ext}"
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            return True
            
        except Exception as e:
            logger.error(f"Download attempt {attempt + 1} failed: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
    
    return False

def download_video_with_curl(video_info: dict, output_dir: Path) -> bool:
    """
    Downloads a video using the generated curl command from video_info.

    Args:
        video_info: A dictionary containing 'filename' and 'curl' command.
        output_dir: The directory to save the video in.

    Returns:
        True on success, False on failure.
    """
    filename = video_info.get("filename")
    curl_command = video_info.get("curl")

    if not filename or not curl_command:
        logger.error("Missing filename or curl command in video_info.")
        return False

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    # Modify the curl command to save to the correct path
    final_command = curl_command.replace(f'-o "{filename}"', f'-o "{str(output_path)}"')

    logger.info(f"Executing download command for: {filename}")
    try:
        process = subprocess.run(final_command, shell=True, check=True, capture_output=True, text=True)
        logger.info(f"Successfully downloaded {filename} to {output_path}")
        logger.debug(f"Curl output: {process.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to download {filename}. Error: {e.stderr}")
        return False
