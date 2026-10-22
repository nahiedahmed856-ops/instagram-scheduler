import os
import re
import tempfile
import mimetypes
from pathlib import Path
from PIL import Image
import requests
import gdown

def extract_drive_id(url: str) -> str:
    """
    Extract file ID from various Google Drive link formats:
    - https://drive.google.com/file/d/1abcXYZ_123/view?usp=sharing
    - https://drive.google.com/open?id=1abcXYZ_123
    - https://drive.google.com/uc?id=1abcXYZ_123
    """
    if not url:
        return None
    
    # Check for /file/d/<id>
    match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    
    # Check for id=<id>
    match = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    
    # Direct ID string passed
    if re.match(r'^[a-zA-Z0-9_-]{25,}$', url.strip()):
        return url.strip()
        
    return None


def download_with_requests(file_id: str, destination: str) -> bool:
    """Fallback direct streaming downloader from Google Drive."""
    session = requests.Session()
    url = f"https://docs.google.com/uc?export=download&id={file_id}&confirm=t"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    
    response = session.get(url, headers=headers, stream=True, timeout=60)
    
    # Check for virus scan confirmation token for large files
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            url = f"https://docs.google.com/uc?export=download&id={file_id}&confirm={value}"
            response = session.get(url, headers=headers, stream=True, timeout=60)
            break
            
    if response.status_code == 200:
        with open(destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=32768):
                if chunk:
                    f.write(chunk)
        return os.path.exists(destination) and os.path.getsize(destination) > 1000
    return False


def download_drive_file(drive_url: str, output_dir: str = None) -> tuple[str, str]:
    """
    Downloads file from Google Drive using gdown or direct requests fallback.
    Returns (file_path, media_type) where media_type is 'image' or 'video'.
    """
    file_id = extract_drive_id(drive_url)
    if not file_id:
        raise ValueError("Invalid Google Drive URL. Please make sure the link is public (Anyone with the link).")
    
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="ig_post_")
    os.makedirs(output_dir, exist_ok=True)
    
    temp_target = os.path.join(output_dir, f"raw_{file_id}")
    download_success = False
    
    # Method 1: Try gdown with ID parameter (Standard API)
    try:
        output_path = gdown.download(id=file_id, output=temp_target, quiet=True)
        if output_path and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            download_success = True
    except Exception as gdown_err:
        print(f"[Warning] gdown download error: {gdown_err}")
    
    # Method 2: Direct HTTP streaming fallback if gdown failed
    if not download_success:
        print("[Info] Trying direct HTTP download fallback from Google Drive...")
        download_success = download_with_requests(file_id, temp_target)
        
    if not download_success or not os.path.exists(temp_target):
        raise RuntimeError("Google Drive থেকে ফাইল ডাউনলোড করা যায়নি। নিশ্চিত করুন ফাইলের শেয়ার অপশনে 'Anyone with the link' দেওয়া আছে।")
        
    output_path = temp_target
    
    # Detect file type
    mime_type, _ = mimetypes.guess_type(output_path)
    ext = Path(output_path).suffix.lower()
    
    is_video = ext in ['.mp4', '.mov', '.avi', '.mkv'] or (mime_type and mime_type.startswith('video'))
    
    if is_video:
        # Standardize video to .mp4
        final_path = os.path.join(output_dir, f"video_{file_id}.mp4")
        if output_path != final_path:
            if os.path.exists(final_path):
                os.remove(final_path)
            os.rename(output_path, final_path)
        return final_path, 'video'
    else:
        # Check if it might be an image
        final_path = os.path.join(output_dir, f"photo_{file_id}.jpg")
        try:
            with Image.open(output_path) as img:
                rgb_img = img.convert('RGB')
                rgb_img.save(final_path, 'JPEG', quality=95)
            if output_path != final_path and os.path.exists(output_path):
                os.remove(output_path)
            return final_path, 'image'
        except Exception:
            # If PIL fails to open it as image, test if it's a video file without extension
            final_path = os.path.join(output_dir, f"video_{file_id}.mp4")
            if os.path.exists(final_path):
                os.remove(final_path)
            os.rename(output_path, final_path)
            return final_path, 'video'
