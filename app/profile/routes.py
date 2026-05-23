import base64
import json
import os
import time

# import cloudinary
# import cloudinary.uploader
# import cloudinary.api
import requests
from flask import Blueprint, jsonify, render_template, request, send_file
from flask_login import current_user, login_required

from app.extensions import db
from app.extensions import limiter
from app.platforms.fetchers import (
    fetch_coding_ninjas,
    fetch_gfg,
    fetch_github,
    fetch_hr_badges,
    fetch_lc_badges,
    fetch_leetcode,
    fetch_leetcode_rating_history,
)
from app.utils import ensure_utc_datetime, normalize_coding_ninjas_profile_id, utc_now, compute_c_score, compute_user_platforms
from streaks import compute_streak
from profile_validation import build_profile_updates

profile_bp = Blueprint("profile", __name__)


def build_sync_platforms_response(platform_status):
    """
    Build standardized response for platform sync operations.
    """
    response = {"platforms": dict(platform_status)}
    
    # Check if any platform was actually attempted (not skipped)
    attempted = any(
        status.get("status") in ["synced", "failed"] 
        for status in platform_status.values()
    )
    
    # If no platforms were attempted, return False
    if not attempted:
        response["success"] = False
        response["error"] = "No platforms attempted to sync"
        return response
    
    # Check if ALL attempted platforms FAILED
    all_failed = all(
        status.get("status") == "failed" 
        for status in platform_status.values()
        if status.get("status") in ["synced", "failed"]
    )
    
    # If all attempted failed, return False with error message
    if all_failed:
        response["success"] = False
        response["error"] = "all platforms failed to sync"
        return response
    
    # Check if all attempted platforms succeeded
    all_success = all(
        status.get("status") != "failed" 
        for status in platform_status.values()
        if status.get("status") in ["synced", "failed"]
    )
    
    if all_success:
        response["success"] = True
        return response
    
    # Partial success (some succeeded, some failed)
    response["success"] = True
    response["partial_success"] = True
    return response

@profile_bp.route("/sync_platforms", methods=["POST"])
@login_required
@limiter.limit("5 per minute")
def sync_platforms():
    data = request.json
    now = utc_now()
    user_id = current_user.id

    last_sync = current_user.last_sync
    if last_sync:
        last_sync = ensure_utc_datetime(last_sync)
        diff = (now - last_sync).total_seconds()
        if diff < 600:
            remaining = int(600 - diff)
            mins = remaining // 60
            secs = remaining % 60
            return jsonify({
                "success": False,
                "error": f"Please wait {mins}m {secs}s before syncing again.",
                "message": f"Rate limit: wait {mins}m {secs}s"
            })

    update_fields = {"last_sync": now}

    lc_user = current_user.leetcode_username or ""
    gh_user = current_user.github_username or ""
    gfg_user = current_user.gfg_username or ""
    hr_user = current_user.hackerrank_username or ""
    cn_user = current_user.codingninjas_username or ""

    if "leetcode" in data:
        lc_user = data.get("leetcode", "").strip()
        update_fields["leetcode_username"] = lc_user
    if "github" in data:
        gh_user = data.get("github", "").strip()
        update_fields["github_username"] = gh_user
    if "gfg" in data:
        gfg_user = data.get("gfg", "").strip()
        update_fields["gfg_username"] = gfg_user
    if "hackerrank" in data:
        hr_user = data.get("hackerrank", "").strip()
        update_fields["hackerrank_username"] = hr_user
    if "codingninjas" in data:
        cn_user = normalize_coding_ninjas_profile_id(data.get("codingninjas", ""))
        update_fields["codingninjas_username"] = cn_user

    combined = {}
    totals = {}
    platform_status = {}
    
    if lc_user:
        try:
            lc = fetch_leetcode(lc_user)
            if lc.get("calendar"):
                for key, value in lc.get("calendar", {}).items():
                    combined[key] = combined.get(key, 0) + value
            if lc.get("total"):
                totals["LeetCode"] = lc.get("total")
            if lc.get("difficulty"):
                totals["LeetCode_Easy"] = lc["difficulty"].get("Easy", 0)
                totals["LeetCode_Medium"] = lc["difficulty"].get("Medium", 0)
                totals["LeetCode_Hard"] = lc["difficulty"].get("Hard", 0)
            if lc.get("contest"):
                totals["LeetCode_Contests"] = lc["contest"].get("attendedContestsCount", 0)
                totals["LeetCode_Rating"] = int(lc["contest"].get("rating", 0))
                totals["LeetCode_GlobalRank"] = lc["contest"].get("globalRanking", 0)

            rating_history = fetch_leetcode_rating_history(lc_user)
            if rating_history:
                update_fields["rating_history"] = rating_history

            lc_badges = fetch_lc_badges(lc_user)
            update_fields["lc_badges_json"] = json.dumps(lc_badges)
            platform_status["leetcode"] = {"status": "synced"}
        except Exception as e:
            platform_status["leetcode"] = {"status": "failed", "error": str(e)}
    else:
        platform_status["leetcode"] = {"status": "skipped"}

    if gh_user:
        try:
            gh = fetch_github(gh_user)
            for key, value in gh.get("calendar", {}).items():
                combined[key] = combined.get(key, 0) + value
            if gh.get("stats"):
                totals["GitHub_Issues"] = gh["stats"]["issues"]
                totals["GitHub_PRs"] = gh["stats"]["prs"]
                totals["GitHub_Merged_PRs"] = gh["stats"]["merged_prs"]
                totals["GitHub_Commits"] = gh["stats"]["commits"]
            platform_status["github"] = {"status": "synced"}
        except Exception as e:
            platform_status["github"] = {"status": "failed", "error": str(e)}
    else:
        platform_status["github"] = {"status": "skipped"}

    if gfg_user:
        try:
            gfg = fetch_gfg(gfg_user)
            if gfg.get("total"):
                totals["GFG"] = int(gfg.get("total", 0))
            platform_status["gfg"] = {"status": "synced"}
        except Exception as e:
            platform_status["gfg"] = {"status": "failed", "error": str(e)}
    else:
        platform_status["gfg"] = {"status": "skipped"}

    if cn_user:
        try:
            cn = fetch_coding_ninjas(cn_user)
            if cn.get("total"):
                totals["Coding Ninjas"] = int(cn.get("total", 0))
            platform_status["codingninjas"] = {"status": "synced"}
        except Exception as e:
            platform_status["codingninjas"] = {"status": "failed", "error": str(e)}
    else:
        platform_status["codingninjas"] = {"status": "skipped"}

    if hr_user:
        try:
            hr_badges, hr_solved = fetch_hr_badges(hr_user)
            update_fields["hr_badges_json"] = json.dumps(hr_badges)
            if hr_solved > 0:
                totals["HackerRank"] = hr_solved
            platform_status["hackerrank"] = {"status": "synced"}
        except Exception as e:
            platform_status["hackerrank"] = {"status": "failed", "error": str(e)}
    else:
        platform_status["hackerrank"] = {"status": "skipped"}

    update_fields["external_daily_counts"] = combined
    update_fields["external_totals"] = totals
    db.user.update_one({"_id": user_id}, {"$set": update_fields})
    current_user.reload()
    
    return jsonify(build_sync_platforms_response(platform_status))


@profile_bp.route("/edit_profile", methods=["POST"])
@login_required
def edit_profile():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No data"}), 400
    update_fields, error = build_profile_updates(data)
    if error:
        return jsonify({"success": False, "error": error, "message": error}), 400
    if update_fields:
        db.user.update_one({"_id": current_user.id}, {"$set": update_fields})
        current_user.reload()
        return jsonify({"success": True, "message": "Profile updated successfully! ✅"})
    
    return jsonify({"success": False, "error": "No changes made", "message": "No changes to save"})


card_cache = {}
CACHE_TTL = 3600

@profile_bp.route("/u/<user_id>/card.png")
def public_card(user_id):
    from bson.objectid import ObjectId
    try:
        user = db.user.find_one({"_id": ObjectId(user_id)})
    except Exception:
        return "Invalid User ID", 400
        
    if not user:
        return "User not found", 404
        
    current_time = time.time()
    if user_id in card_cache:
        cached_time, cached_image = card_cache[user_id]
        if current_time - cached_time < CACHE_TTL:
            cached_image.seek(0)
            return send_file(cached_image, mimetype="image/png")
            
    # Import generate_progress_card inside the try block
    # This ensures the patch works correctly
    from card_generator import generate_progress_card
    
    try:
        name = user.get("name", "Anonymous")
        
        # Calculate real stats using compute_c_score
        stats = compute_c_score(user)
        c_score = stats.get("c_score", 0)
        dsa_done = stats.get("dsa_done", 0)
        
        total_questions = db.question.count_documents({})
        dsa_progress = round((dsa_done / total_questions * 100) if total_questions > 0 else 0, 1)
        
        progress_data = user.get("progress", {})
        current_streak, _ = compute_streak(progress_data)
        
        all_questions = list(db.question.find())
        solved_items = {qid: p for qid, p in progress_data.items() if p.get("done")}
        platforms = compute_user_platforms(solved_items, user.get("external_totals", {}), all_questions)

        img_io = generate_progress_card(name, c_score, dsa_progress, current_streak, platforms)
        img_io.seek(0)
        
        card_cache[user_id] = (current_time, img_io)
        return send_file(img_io, mimetype="image/png")
        
    except Exception as e:
        print(f"Card generation error: {e}")
        # Clear cache to prevent serving cached error
        if user_id in card_cache:
            del card_cache[user_id]
        # Return 500 for any exception
        return "Internal Server Error", 500


@profile_bp.route("/search_universities")
def search_universities():
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])
    try:
        response = requests.get(
            "https://universities.hipolabs.com/search",
            params={"name": query},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            seen = set()
            results = []
            for university in data[:30]:
                name = university.get("name", "")
                country = university.get("country", "")
                label = f"{name}, {country}" if country else name
                if label not in seen:
                    seen.add(label)
                    results.append({"name": name, "country": country, "label": label})
            return jsonify(results)
        return jsonify([])
    except Exception:
        return jsonify([])


@profile_bp.route("/upload_photo", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def upload_photo():
    return jsonify({
        "success": False,
        "error": "Photo upload disabled (Cloudinary not configured)",
        "message": "Photo upload not available"
    })


@profile_bp.route("/profile")
@login_required
def profile():
    topics = list(db.topic.find().sort("position", 1))
    user = current_user

    all_questions = list(db.question.find())
    solved_items = {
        question_id: progress
        for question_id, progress in user.progress.items()
        if progress.get("done")
    }

    difficulty_map = {str(q["_id"]): q.get("difficulty", "Medium") for q in all_questions}
    
    dsa_easy = 0
    dsa_medium = 0
    dsa_hard = 0
    
    for q_id in solved_items.keys():
        diff = difficulty_map.get(q_id, "Medium")
        if diff == "Easy":
            dsa_easy += 1
        elif diff == "Medium":
            dsa_medium += 1
        elif diff == "Hard":
            dsa_hard += 1

    daily_counts = {}

    topic_question_count = {}
    for question in all_questions:
        topic_id = str(question["topic"])
        topic_question_count.setdefault(topic_id, []).append(str(question["_id"]))

        question_id = str(question["_id"])
        if question_id in solved_items:
            solved_at = solved_items[question_id].get("timestamp") or utc_now()
            day = solved_at.strftime("%Y-%m-%d")
            daily_counts[day] = daily_counts.get(day, 0) + 1

    ext_daily = user.external_daily_counts
    if ext_daily:
        for day, count in ext_daily.items():
            daily_counts[day] = daily_counts.get(day, 0) + count

    total_active_days = len(daily_counts)
    sorted_dates = sorted(daily_counts.keys())
    cumulative_data = []
    cumulative_sum = 0
    for day in sorted_dates:
        cumulative_sum += daily_counts[day]
        cumulative_data.append({"x": day, "y": cumulative_sum})

    topic_progress = []
    dsa_done = len(solved_items)

    ext_totals = user.external_totals or {}
    platforms = compute_user_platforms(solved_items, ext_totals, all_questions)

    lc_easy = dsa_easy
    lc_medium = dsa_medium
    lc_hard = dsa_hard
    
    lc_contests = ext_totals.get("LeetCode_Contests", 0)
    lc_rating = ext_totals.get("LeetCode_Rating", 0)
    lc_rank = ext_totals.get("LeetCode_GlobalRank", 0)
    gh_issues = ext_totals.get("GitHub_Issues", 0)
    gh_prs = ext_totals.get("GitHub_PRs", 0)
    gh_merged = ext_totals.get("GitHub_Merged_PRs", 0)
    gh_commits = ext_totals.get("GitHub_Commits", 0)

    global_total_solved = sum(platforms.values())
    total_questions = len(all_questions)

    for topic_doc in topics:
        topic_id = str(topic_doc["_id"])
        topic_question_ids = topic_question_count.get(topic_id, [])
        topic_done = sum(
            1 for question_id in topic_question_ids
            if question_id in solved_items
        )
        percent = (topic_done / len(topic_question_ids) * 100) if topic_question_ids else 0
        topic_progress.append({
            "name": topic_doc["name"],
            "done": topic_done,
            "total": len(topic_question_ids),
            "percent": round(percent, 1),
        })

    topic_progress.sort(key=lambda item: item["done"], reverse=True)
    overall_percent = round(
        (dsa_done / total_questions * 100) if total_questions > 0 else 0,
        1
    )
    rating_history = list(user.rating_history or [])

    lc_badges = []
    hr_badges = []
    try:
        lc_badges = json.loads(user.lc_badges_json or "[]")
    except json.JSONDecodeError:
        print("Unable to handle leetcode badges")

    try:
        hr_badges = [
            badge for badge in json.loads(user.hr_badges_json or "[]")
            if int(badge.get("stars", 0)) > 0
        ]
    except (json.JSONDecodeError, ValueError):
        print("Unable to handle hackerrank badges")

    return render_template(
        "profile.html",
        user=user,
        topic_progress=topic_progress,
        dsa_done=dsa_done,
        global_total_solved=global_total_solved,
        total_questions=total_questions,
        overall_percent=overall_percent,
        platforms=platforms,
        lc_easy=lc_easy,
        lc_medium=lc_medium,
        lc_hard=lc_hard,
        lc_contests=lc_contests,
        lc_rating=lc_rating,
        lc_rank=lc_rank,
        gh_issues=gh_issues,
        gh_prs=gh_prs,
        gh_merged=gh_merged,
        gh_commits=gh_commits,
        daily_counts=daily_counts,
        cumulative_data=cumulative_data,
        total_active_days=total_active_days,
        rating_history=rating_history,
        lc_badges=lc_badges,
        hr_badges=hr_badges,
    )