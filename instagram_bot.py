import json
import os
import re
import shutil
from pathlib import Path
from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword,
    TwoFactorRequired,
    ChallengeRequired,
    PleaseWaitFewMinutes,
    LoginRequired
)
import db

SESSION_SETTINGS_KEY = "ig_session_settings"
USERNAME_KEY = "ig_username"

def get_client() -> Client:
    """Creates and configures an instagrapi Client instance."""
    cl = Client()
    cl.request_timeout = 25
    cl.delay_range = [1, 2]
    
    # Try loading saved session from DB
    saved_settings = db.get_setting(SESSION_SETTINGS_KEY)
    if saved_settings:
        try:
            settings_dict = json.loads(saved_settings)
            cl.set_settings(settings_dict)
        except Exception as e:
            print(f"[Warning] Failed to load session settings: {e}")
            
    return cl

def save_client_session(cl: Client, username: str):
    """Saves client cookies and device settings into database."""
    settings = cl.get_settings()
    db.set_setting(SESSION_SETTINGS_KEY, json.dumps(settings))
    db.set_setting(USERNAME_KEY, username)

def extract_sessionid(cookie_input: str) -> str:
    """Extracts sessionid from raw string, header, or Cookie-Editor JSON."""
    s = cookie_input.strip()
    if not s:
        return ""
        
    # Check if JSON array (Cookie-Editor export)
    if s.startswith('[') and 'sessionid' in s:
        try:
            items = json.loads(s)
            for item in items:
                if item.get('name') == 'sessionid':
                    return item.get('value', '').strip()
        except Exception:
            pass
            
    # Check if standard cookie header "sessionid=xyz; ds_user_id=123"
    match = re.search(r'sessionid=([^;\s]+)', s)
    if match:
        return match.group(1).strip()
        
    # Treat as raw sessionid string
    return s.strip('"\'')

def login_instagram_by_cookie(cookie_data: str) -> dict:
    """
    Logs in using sessionid cookie instantly without password or 2FA challenge.
    """
    sessionid = extract_sessionid(cookie_data)
    if not sessionid:
        return {"success": False, "message": "ভুল কুকি ফরম্যাট! কোনো sessionid পাওয়া যায়নি।"}
    
    cl = get_client()
    try:
        print(f"[Login] Attempting login by sessionid: {sessionid[:12]}...")
        cl.login_by_sessionid(sessionid)
        
        # Get username of logged-in account
        username = "User"
        try:
            user_info = cl.account_info()
            username = getattr(user_info, 'username', 'User')
        except Exception:
            try:
                user_info = cl.user_info(cl.user_id)
                username = getattr(user_info, 'username', f"user_{cl.user_id}")
            except Exception:
                username = f"user_{cl.user_id}"
                
        save_client_session(cl, username)
        print(f"[Login] Successfully logged in as @{username} via Cookie!")
        return {"success": True, "message": f"@{username} হিসেবে কুকিজ দিয়ে সফলভাবে লগইন সম্পন্ন হয়েছে!"}
        
    except Exception as e:
        print(f"[Cookie Login Error]: {e}")
        return {"success": False, "message": f"Cookie দিয়ে লগইন ব্যর্থ: {str(e)}। কুকি এক্সপায়ার বা ভুল হতে পারে।"}

def check_login_status() -> dict:
    """
    Checks if there is an active logged-in Instagram session.
    Returns: {"logged_in": bool, "username": str}
    """
    saved_username = db.get_setting(USERNAME_KEY)
    saved_settings = db.get_setting(SESSION_SETTINGS_KEY)
    
    if not saved_username or not saved_settings:
        return {"logged_in": False, "username": None}
    
    cl = get_client()
    try:
        # Quick validation check
        cl.get_timeline_feed()
        return {"logged_in": True, "username": saved_username}
    except Exception as e:
        print(f"[Check Login] Session expired or invalid: {e}")
        return {"logged_in": False, "username": saved_username}

def login_instagram(username: str, password: str, code: str = None, two_factor_identifier: str = None) -> dict:
    """
    Handles Instagram login, including 2FA code verification.
    """
    cl = get_client()
    username = username.strip()
    
    try:
        if code and two_factor_identifier:
            # Completing 2FA
            print(f"[Login] Attempting 2FA verification for {username}...")
            cl.two_factor_login(code=code.strip())
            save_client_session(cl, username)
            return {"success": True, "message": "Successfully logged in with 2FA!"}
        
        # Standard login attempt
        print(f"[Login] Logging in user {username}...")
        cl.login(username, password)
        save_client_session(cl, username)
        return {"success": True, "message": "Successfully logged into Instagram!"}
        
    except TwoFactorRequired as e:
        # Instagram requires 2FA SMS or Authenticator App code
        print(f"[Login] 2FA Required for {username}")
        # Save temporary state
        return {
            "success": False,
            "needs_2fa": True,
            "two_factor_identifier": getattr(e, 'two_factor_identifier', ''),
            "message": "Two-Factor Authentication (2FA) is required. Please enter the OTP code."
        }
        
    except BadPassword:
        return {"success": False, "message": "Incorrect password. Please try again."}
        
    except ChallengeRequired:
        return {
            "success": False,
            "message": "Instagram triggered a security challenge (New location). Open the Instagram app on your phone and tap 'This Was Me', then retry."
        }
        
    except PleaseWaitFewMinutes:
        return {"success": False, "message": "Instagram requested to wait a few minutes before trying again."}
        
    except Exception as e:
        return {"success": False, "message": f"Login failed: {str(e)}"}

def logout_instagram():
    """Clears stored session and username."""
    db.remove_setting(SESSION_SETTINGS_KEY)
    db.remove_setting(USERNAME_KEY)

def upload_post(file_path: str, media_type: str, caption: str) -> dict:
    """
    Uploads a photo or video/reel to Instagram.
    Cleans up file after upload.
    """
    cl = get_client()
    username = db.get_setting(USERNAME_KEY)
    
    if not username:
        raise LoginRequired("No active Instagram login found. Please log in first.")
    
    try:
        print(f"[Instagram Upload] Starting {media_type} upload...")
        media_info = None
        
        if media_type == 'image':
            media_info = cl.photo_upload(
                path=Path(file_path),
                caption=caption
            )
        elif media_type == 'video':
            # clip_upload handles Reels/Videos automatically and fits standard feeds
            media_info = cl.clip_upload(
                path=Path(file_path),
                caption=caption
            )
        else:
            raise ValueError(f"Unsupported media type: {media_type}")
            
        print(f"[Instagram Upload] Post successful! Media ID: {media_info.pk if hasattr(media_info, 'pk') else 'Done'}")
        return {"success": True, "media_id": str(getattr(media_info, 'pk', 'unknown'))}
        
    except Exception as e:
        print(f"[Instagram Upload Error]: {str(e)}")
        raise e
        
    finally:
        # Cleanup temporary downloaded files
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
            # Remove parent temp directory if empty or prefixed
            parent_dir = os.path.dirname(file_path)
            if "ig_post_" in parent_dir and os.path.exists(parent_dir):
                shutil.rmtree(parent_dir, ignore_errors=True)
        except Exception as cleanup_err:
            print(f"[Cleanup Error]: {cleanup_err}")
