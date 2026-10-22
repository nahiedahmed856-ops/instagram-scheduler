import os
import atexit
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from apscheduler.schedulers.background import BackgroundScheduler

import db
import drive_handler
import instagram_bot

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "super-secret-key-123456789")

# Initialize SQLite database
db.init_db()

# Interval in hours for automatic posting (default 3 hours)
POSTING_INTERVAL_HOURS = int(os.environ.get("POST_INTERVAL_HOURS", 3))

def process_single_post(post_dict: dict) -> bool:
    """Helper function to execute a single post from drive to instagram."""
    post_id = post_dict['id']
    drive_url = post_dict['drive_url']
    
    # Check login
    status = instagram_bot.check_login_status()
    if not status.get("logged_in"):
        print(f"[Worker] Cannot post ID {post_id}: Instagram not logged in.")
        db.update_post_status(post_id, 'failed', error_message="Instagram account is not logged in.")
        return False
        
    db.update_post_status(post_id, 'processing')
    
    try:
        print(f"[Worker] Downloading Google Drive file for Post #{post_id}...")
        file_path, media_type = drive_handler.download_drive_file(drive_url)
        
        # Build full caption
        caption_parts = []
        if post_dict.get('title'):
            caption_parts.append(post_dict['title'].strip())
        if post_dict.get('caption'):
            caption_parts.append(post_dict['caption'].strip())
        if post_dict.get('hashtags'):
            hashtags = post_dict['hashtags'].strip()
            # Ensure hashtags are separated
            caption_parts.append(f"\n{hashtags}")
            
        final_caption = "\n\n".join([p for p in caption_parts if p])
        
        print(f"[Worker] Uploading {media_type} to Instagram for Post #{post_id}...")
        instagram_bot.upload_post(file_path, media_type, final_caption)
        
        db.update_post_status(post_id, 'posted', media_type=media_type)
        print(f"[Worker] Post #{post_id} successfully published to Instagram!")
        return True
        
    except Exception as e:
        error_msg = str(e)
        print(f"[Worker] Error processing Post #{post_id}: {error_msg}")
        db.update_post_status(post_id, 'failed', error_message=error_msg)
        return False


def scheduled_worker_job():
    """Background job executed automatically every 3 hours."""
    print(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}] Running 3-Hour Scheduled Post Worker...")
    next_post = db.get_next_pending_post()
    if not next_post:
        print("[Worker] No pending posts in queue. Skipping.")
        return
        
    process_single_post(next_post)


# Setup APScheduler
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(
    func=scheduled_worker_job,
    trigger="interval",
    hours=POSTING_INTERVAL_HOURS,
    id="auto_instagram_poster",
    name="3-Hour Instagram Poster"
)
scheduler.start()
atexit.register(lambda: scheduler.shutdown(wait=False))


@app.route("/")
def index():
    login_info = instagram_bot.check_login_status()
    posts = db.get_all_posts()
    next_post = db.get_next_pending_post()
    return render_template(
        "dashboard.html",
        login_info=login_info,
        posts=posts,
        next_post=next_post,
        interval_hours=POSTING_INTERVAL_HOURS
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        code = request.form.get("verification_code", "").strip()
        two_factor_identifier = request.form.get("two_factor_identifier", "").strip()
        
        if not username or (not password and not code):
            flash("Username and password are required.", "danger")
            return render_template("login.html", username=username)
            
        result = instagram_bot.login_instagram(
            username=username,
            password=password,
            code=code if code else None,
            two_factor_identifier=two_factor_identifier if two_factor_identifier else None
        )
        
        if result.get("success"):
            flash(result.get("message", "Login successful!"), "success")
            return redirect(url_for("index"))
            
        elif result.get("needs_2fa"):
            flash("Instagram sent a 2FA / Verification code. Please enter it below.", "warning")
            return render_template(
                "login.html",
                username=username,
                password=password,
                needs_2fa=True,
                two_factor_identifier=result.get("two_factor_identifier")
            )
        else:
            flash(result.get("message", "Login failed. Check details."), "danger")
            return render_template("login.html", username=username)
            
    return render_template("login.html")


@app.route("/logout", methods=["POST", "GET"])
def logout():
    instagram_bot.logout_instagram()
    flash("Logged out successfully from Instagram.", "info")
    return redirect(url_for("index"))


@app.route("/add-post", methods=["POST"])
def add_new_post():
    drive_url = request.form.get("drive_url", "").strip()
    title = request.form.get("title", "").strip()
    caption = request.form.get("caption", "").strip()
    hashtags = request.form.get("hashtags", "").strip()
    
    if not drive_url:
        flash("Google Drive URL is required!", "danger")
        return redirect(url_for("index"))
        
    drive_id = drive_handler.extract_drive_id(drive_url)
    if not drive_id:
        flash("Invalid Google Drive link. Please make sure the link is public (Anyone with the link).", "danger")
        return redirect(url_for("index"))
        
    # Auto-format hashtags if user forgot '#'
    if hashtags:
        tags = [t if t.startswith('#') else f"#{t}" for t in hashtags.split()]
        hashtags = " ".join(tags)
        
    db.add_post(drive_url=drive_url, title=title, caption=caption, hashtags=hashtags)
    flash("Post added to the queue! It will be posted according to schedule.", "success")
    return redirect(url_for("index"))


@app.route("/post-now/<int:post_id>", methods=["POST"])
def post_now(post_id):
    """Trigger manual post execution immediately without waiting 3 hours."""
    post = db.get_post_by_id(post_id)
    if not post:
        flash("Post not found.", "danger")
        return redirect(url_for("index"))
        
    success = process_single_post(post)
    if success:
        flash(f"Post #{post_id} was successfully published to Instagram!", "success")
    else:
        post_updated = db.get_post_by_id(post_id)
        flash(f"Failed to publish Post #{post_id}: {post_updated.get('error_message')}", "danger")
        
    return redirect(url_for("index"))


@app.route("/delete-post/<int:post_id>", methods=["POST"])
def delete_post_route(post_id):
    db.delete_post(post_id)
    flash(f"Post #{post_id} removed from queue.", "info")
    return redirect(url_for("index"))


@app.route("/health")
@app.route("/ping")
def health():
    """
    Keep-alive endpoint for UptimeRobot.
    UptimeRobot should ping this URL every 5 minutes so Render never sleeps.
    """
    return jsonify({
        "status": "online",
        "service": "Instagram Auto Poster",
        "time_utc": datetime.utcnow().isoformat(),
        "login_status": instagram_bot.check_login_status().get("logged_in")
    })


@app.route("/api/cron", methods=["GET", "POST"])
def manual_cron():
    """External cron trigger endpoint if user wants to trigger posting via cron-job.org."""
    next_post = db.get_next_pending_post()
    if not next_post:
        return jsonify({"status": "empty", "message": "No pending posts in queue"})
    
    success = process_single_post(next_post)
    return jsonify({
        "status": "success" if success else "failed",
        "post_id": next_post['id']
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
