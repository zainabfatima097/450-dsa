from bson import ObjectId
from flask import Blueprint, Response, jsonify, render_template, request
from flask_login import current_user, login_required

from app.extensions import db
from app.utils import utc_now
from notes_export import build_topic_notes_markdown, topic_notes_filename
from progress_export import build_progress_csv
from app.utils import trigger_discord_event

# ===== HELPER FUNCTIONS (keep existing ones) =====
def json_success(message=None, data=None):
    response = {"success": True}
    if message:
        response["message"] = message
    if data:
        response["data"] = data
    return jsonify(response)

def json_error(error, status_code=400):
    return jsonify({"success": False, "error": error}), status_code

# ===== PROJECTION CONSTANTS =====
QUESTION_STATUS_PROJECTION = {
    "_id": 1,
    "problem": 1,
    "difficulty": 1,
    "url": 1,
    "url2": 1,
}

BOOKMARKS_QUESTION_PROJECTION = {
    "_id": 1,
    "problem": 1,
    "topic": 1,
    "difficulty": 1,
    "url": 1,
    "url2": 1,
}

CSV_EXPORT_QUESTION_PROJECTION = {
    "topic": 1,
    "problem": 1,
    "difficulty": 1,
    "url": 1,
    "url2": 1,
}

tracker_bp = Blueprint("tracker", __name__)


@tracker_bp.route("/")
def index():
    topics = list(db.topic.find().sort("position", 1))
    total_questions = db.question.count_documents({})

    if current_user.is_authenticated:
        progress = current_user.progress
        done_questions = sum(1 for progress_item in progress.values() if progress_item.get("done"))
    else:
        progress = {}
        done_questions = 0

    all_questions = list(db.question.find())
    topic_question_count = {}
    for question in all_questions:
        topic_id = str(question["topic"])
        topic_question_count.setdefault(topic_id, []).append(str(question["_id"]))

    topic_progress = {}
    for topic in topics:
        topic_id = str(topic["_id"])
        topic_question_ids = topic_question_count.get(topic_id, [])
        if current_user.is_authenticated:
            topic_done = sum(1 for question_id in topic_question_ids if progress.get(question_id, {}).get("done"))
        else:
            topic_done = 0
        topic_progress[topic_id] = {"done": topic_done, "total": len(topic_question_ids)}

    return render_template(
        "index.html",
        topics=topics,
        total_questions=total_questions,
        done_questions=done_questions,
        topic_progress=topic_progress,
    )


@tracker_bp.route("/topic/<topic_id>")
def topic(topic_id):
    try:
        topic_doc = db.topic.find_one({"_id": ObjectId(topic_id)})
    except Exception:
        return "Topic not found", 404
    if not topic_doc:
        return "Topic not found", 404

    questions = list(db.question.find({"topic": topic_doc["_id"]}))
    
    total_count = len(questions)
    easy_count = sum(1 for q in questions if q.get('difficulty', 'Medium') == 'Easy')
    medium_count = sum(1 for q in questions if q.get('difficulty', 'Medium') == 'Medium')
    hard_count = sum(1 for q in questions if q.get('difficulty', 'Medium') == 'Hard')
    
    difficulty_filter = request.args.get('difficulty', 'all')
    
    if difficulty_filter != 'all':
        questions = [q for q in questions if q.get('difficulty', 'Medium') == difficulty_filter]
    
    progress_dict = current_user.progress if current_user.is_authenticated else {}
    
    return render_template(
        "topic.html", 
        topic=topic_doc, 
        questions=questions, 
        progress_dict=progress_dict,
        difficulty_filter=difficulty_filter,
        total_count=total_count,
        easy_count=easy_count,
        medium_count=medium_count,
        hard_count=hard_count
    )


@tracker_bp.route("/topic/<topic_id>/export-notes")
@login_required
def export_topic_notes(topic_id):
    try:
        topic_doc = db.topic.find_one({"_id": ObjectId(topic_id)})
    except Exception:
        return "Topic not found", 404
    if not topic_doc:
        return "Topic not found", 404

    questions = list(db.question.find({"topic": topic_doc["_id"]}))
    markdown = build_topic_notes_markdown(topic_doc["name"], questions, current_user.progress)
    response = Response(markdown, mimetype="text/markdown")
    response.headers["Content-Disposition"] = f'attachment; filename={topic_notes_filename(topic_doc["name"])}'
    return response


@tracker_bp.route("/update_question/<question_id>", methods=["POST"])
@login_required
def update_question(question_id):
    """Update the authenticated user's progress for a question."""
    try:
        question = db.question.find_one({"_id": ObjectId(question_id)}, QUESTION_STATUS_PROJECTION)
    except Exception:
        return json_error("Question not found", status_code=404)
    if not question:
        return json_error("Question not found", status_code=404)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return json_error("Request body must be a JSON object", status_code=400)

    # Validate boolean fields
    for field in ("done", "bookmark", "skipped"):
        if field in data and not isinstance(data[field], bool):
            return json_error(f"{field} must be a boolean", status_code=400)

    user_id = current_user.id
    update_fields = {}
    progress = current_user.progress
    existing = progress.get(question_id, {})
    message = ""

    if "done" in data:
        if data["done"] and not existing.get("done"):
            update_fields[f"progress.{question_id}.timestamp"] = utc_now()
            message = f"✅ Marked '{question.get('problem', 'Question')}' as complete!"
            
            # DISCORD MILESTONE TRIGGER (ADDED)
            current_user.reload()
            user_progress = current_user.progress
            done_count = sum(1 for item in user_progress.values() if item.get("done"))
            if done_count in [50, 100, 200]:
                trigger_discord_event("milestone", {
                    "user_name": current_user.name,
                    "milestone": done_count,
                    "total_solved": done_count
                })
        elif not data["done"] and existing.get("done"):
            message = f"📝 Marked '{question.get('problem', 'Question')}' as incomplete"
        update_fields[f"progress.{question_id}.done"] = data["done"]

    if "skipped" in data:
        if data["skipped"] and not existing.get("skipped"):
            message = f"⏭️ Marked '{question.get('problem', 'Question')}' as skipped for now"
            update_fields[f"progress.{question_id}.done"] = False
        elif not data["skipped"] and existing.get("skipped"):
            message = f"↩️ Removed skipped status for '{question.get('problem', 'Question')}'"
        update_fields[f"progress.{question_id}.skipped"] = data["skipped"]

    if "bookmark" in data:
        if data["bookmark"] and not existing.get("bookmark"):
            message = f"🔖 Added '{question.get('problem', 'Question')}' to bookmarks!"
        elif not data["bookmark"] and existing.get("bookmark"):
            message = f"📌 Removed '{question.get('problem', 'Question')}' from bookmarks"
        update_fields[f"progress.{question_id}.bookmark"] = data["bookmark"]

    if "notes" in data:
        update_fields[f"progress.{question_id}.notes"] = data["notes"]
        message = f"📝 Notes saved for '{question.get('problem', 'Question')}'!"

    if update_fields:
        db.user.update_one({"_id": user_id}, {"$set": update_fields})
        current_user.reload()
        return json_success(message=message)

    return json_success(message="No changes made")


@tracker_bp.route("/bookmarks")
@login_required
def bookmarks():
    progress = current_user.progress
    bookmarked_question_ids = [question_id for question_id, progress_item in progress.items() if progress_item.get("bookmark")]

    object_ids = []
    for question_id in bookmarked_question_ids:
        try:
            object_ids.append(ObjectId(question_id))
        except Exception:
            pass
    questions = list(db.question.find({"_id": {"$in": object_ids}}, BOOKMARKS_QUESTION_PROJECTION))

    topic_ids = list(set(question["topic"] for question in questions))
    topic_docs = {topic["_id"]: topic["name"] for topic in db.topic.find({"_id": {"$in": topic_ids}})}
    for question in questions:
        question["topic_name"] = topic_docs.get(question["topic"], "Unknown")

    return render_template("bookmarks.html", questions=questions, progress_dict=progress)


@tracker_bp.route("/export/csv")
@login_required
def export_csv():
    questions = list(db.question.find({}, CSV_EXPORT_QUESTION_PROJECTION))
    topic_ids = list({q.get('topic') for q in questions if q.get('topic')})
    topic_lookup = {
        topic['_id']: topic.get('name', 'Unknown')
        for topic in db.topic.find({'_id': {'$in': topic_ids}}, {'name': 1})
    }
    csv_content = build_progress_csv(questions, topic_lookup, current_user.progress)
    response = Response(csv_content, mimetype='text/csv')
    response.headers['Content-Disposition'] = 'attachment; filename=progress.csv'
    return response