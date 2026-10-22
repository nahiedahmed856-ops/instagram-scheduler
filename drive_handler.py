import os
import re
import tempfile
import mimetypes
from pathlib import Path
from PIL import Image
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


def download_drive_file(drive_url: str, output_dir: str = None) -> tuple[str, str]:
    """
    Downloads file from Google Drive using gdown.
    Returns (file_path, media_type) where media_type is 'image' or 'video'.
    """
    file_id = extract_drive_id(drive_url)
    if not file_id:
        raise ValueError("Invalid Google Drive URL. Please make sure the link is public and formatted correctly.")
    
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="ig_post_")
    os.makedirs(output_dir, exist_ok=True)
    
    download_url = f"https://drive.google.com/uc?id={file_id}"
    
    # Use gdown to download public file
    temp_target = os.path.join(output_dir, f"raw_{file_id}")
    output_path = gdown.download(download_url, temp_target, quiet=False, fuzzy=True)
    
    if not output_path or not os.path.exists(output_path):
        raise RuntimeError("Failed to download file from Google Drive. Please ensure 'Anyone with the link' has view access.")
    
    # Detect file type
    mime_type, _ = mimetypes.guess_type(output_path)
    
    # Inspect extension or magic bytes if unknown
    ext = Path(output_path).suffix.lower()
    
    is_video = ext in ['.mp4', '.mov', '.avi', '.mkv'] or (mime_type and mime_type.startswith('video'))
    
    if is_video:
        # Standardize video to .mp4
        final_path = os.path.join(output_dir, f"video_{file_id}.mp4")
        if output_path != final_path:
            os.rename(output_path, final_path)
        return final_path, 'video'
    else:
        # It's an image. Convert to high quality RGB JPEG for Instagram compatibility
        final_path = os.path.join(output_dir, f"photo_{file_id}.jpg")
        try:
            with Image.open(output_path) as img:
                rgb_img = img.convert('RGB')
                rgb_img.save(final_path, 'JPEG', quality=95)
            if output_path != final_path and os.path.exists(output_path):
                os.remove(output_path)
            return final_path, 'image'
        except Exception as e:
            # If not PIL readable, could still be video or raw file
            if os.path.getsize(output_path) > 1024 * 1024 * 2: # > 2MB likely video
                final_path = os.path.join(output_dir, f"video_{file_id}.mp4")
                os.rename(output_path, final_path)
                return final_path, 'video'
            raise RuntimeError(f"Could not process image: {str(e)}")
