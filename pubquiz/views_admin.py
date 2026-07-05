"""Admin panel: přihlášení heslem, import CSV, správa týmů, řízení hry."""
import functools
import os

from flask import (
    Blueprint, current_app, jsonify, redirect, render_template, request,
    session, url_for,
)
from werkzeug.utils import secure_filename

from . import game
from .csv_import import CsvImportError, import_set
from .db import get_db, bump_version
from .payloads import base_state, team_answers

bp = Blueprint("admin", __name__, url_prefix="/admin")

ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            if request.path.startswith("/admin/api"):
                return jsonify({"error": "Nepřihlášen."}), 401
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Přihlášení
# ---------------------------------------------------------------------------

@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == current_app.config["ADMIN_PASSWORD"]:
            session["is_admin"] = True
            session.permanent = True
            return redirect(url_for("admin.panel"))
        error = "Špatné heslo."
    return render_template("admin_login.html", error=error)


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


@bp.route("/")
@login_required
def panel():
    return render_template(
        "admin.html",
        default_countdown=current_app.config["DEFAULT_COUNTDOWN_S"],
    )


# ---------------------------------------------------------------------------
# Polling stavu pro admin panel
# ---------------------------------------------------------------------------

@bp.get("/api/stav")
@login_required
def admin_state():
    state = game.tick()
    payload = base_state(state)
    db = get_db()

    payload["teams"] = [
        dict(r) for r in db.execute(
            "SELECT id, name, created_at FROM teams ORDER BY created_at"
        )
    ]
    payload["sets"] = [
        dict(r) for r in db.execute(
            """SELECT s.id, s.name, COUNT(q.id) AS question_count
               FROM question_sets s LEFT JOIN questions q ON q.set_id = s.id
               GROUP BY s.id ORDER BY s.name"""
        )
    ]
    payload["set_queue"] = game.set_queue(state)

    # Aktuální otázka včetně správné odpovědi a odpovědí týmů
    q = None
    if state["phase"] == "question":
        q = game.current_question(state)
    elif state["phase"] == "review":
        q = game.current_question(state, index_field="review_index")
    if q is not None:
        payload["admin_question"] = dict(q)
        payload["answers"] = team_answers(q)
        payload["answered_count"] = sum(1 for a in payload["answers"])

    # Průběžné pořadí má admin k dispozici vždy
    payload["standings_total"] = game.standings_total(state)
    if state["phase"] in ("results_set", "results_total", "review"):
        sid = game.current_set_id(state)
        if sid is not None:
            payload["standings_set"] = game.standings_set(sid)
    return jsonify(payload)


# ---------------------------------------------------------------------------
# Sady otázek a obrázky
# ---------------------------------------------------------------------------

@bp.post("/api/import-csv")
@login_required
def upload_csv():
    f = request.files.get("file")
    if f is None or not f.filename:
        return jsonify({"error": "Vyberte CSV soubor."}), 400
    name = (request.form.get("name") or "").strip() or os.path.splitext(f.filename)[0]
    try:
        set_id = import_set(name, f.read())
    except CsvImportError as e:
        return jsonify({"error": "Import selhal:", "errors": e.errors}), 400
    return jsonify({"ok": True, "set_id": set_id, "name": name})


@bp.post("/api/smazat-sadu")
@login_required
def delete_set():
    set_id = (request.get_json(silent=True) or {}).get("set_id")
    state = game.get_state()
    if set_id in game.set_queue(state) and state["phase"] != "lobby":
        return jsonify({"error": "Sada je součástí rozehrané hry."}), 409
    db = get_db()
    db.execute("DELETE FROM question_sets WHERE id = ?", (set_id,))
    bump_version(db)
    db.commit()
    return jsonify({"ok": True})


@bp.post("/api/nahrat-obrazek")
@login_required
def upload_image():
    f = request.files.get("file")
    if f is None or not f.filename:
        return jsonify({"error": "Vyberte obrázek."}), 400
    filename = secure_filename(f.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        return jsonify({"error": f"Nepodporovaný formát {ext}. Povolené: png, jpg, gif, webp."}), 400
    media_dir = current_app.config["MEDIA_DIR"]
    os.makedirs(media_dir, exist_ok=True)
    f.save(os.path.join(media_dir, filename))
    return jsonify({"ok": True, "filename": filename})


# ---------------------------------------------------------------------------
# Týmy
# ---------------------------------------------------------------------------

@bp.post("/api/tym/prejmenovat")
@login_required
def rename_team():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()[:30]
    if not name:
        return jsonify({"error": "Prázdný název."}), 400
    db = get_db()
    db.execute("UPDATE teams SET name = ? WHERE id = ?", (name, data.get("team_id")))
    bump_version(db)
    db.commit()
    return jsonify({"ok": True})


@bp.post("/api/tym/smazat")
@login_required
def delete_team():
    data = request.get_json(silent=True) or {}
    db = get_db()
    db.execute("DELETE FROM teams WHERE id = ?", (data.get("team_id"),))
    bump_version(db)
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Řízení hry
# ---------------------------------------------------------------------------

@bp.post("/api/hra/start")
@login_required
def start_game():
    set_ids = (request.get_json(silent=True) or {}).get("set_ids") or []
    db = get_db()
    valid = {r["id"] for r in db.execute("SELECT id FROM question_sets")}
    set_ids = [int(s) for s in set_ids if int(s) in valid]
    if not set_ids:
        return jsonify({"error": "Vyberte alespoň jednu sadu."}), 400
    game.start_game(set_ids)
    return jsonify({"ok": True})


@bp.post("/api/hra/akce")
@login_required
def game_action():
    """Jednotný endpoint pro herní akce admina."""
    data = request.get_json(silent=True) or {}
    action = data.get("action")
    game.tick()

    if action == "open":
        game.open_answers()
    elif action == "close":
        try:
            secs = int(data.get("countdown", current_app.config["DEFAULT_COUNTDOWN_S"]))
        except (TypeError, ValueError):
            secs = current_app.config["DEFAULT_COUNTDOWN_S"]
        game.close_answers(max(0, min(120, secs)))
    elif action == "reveal":
        game.reveal_answer()
    elif action == "next":
        game.next_question()
    elif action == "prev":
        game.prev_question()
    elif action == "total_results":
        game.show_total_results()
    elif action == "review_start":
        game.start_review()
    elif action == "review_next":
        game.review_move(+1)
    elif action == "review_prev":
        game.review_move(-1)
    elif action == "review_end":
        game.end_review()
    elif action == "next_set":
        game.next_set()
    elif action == "reset":
        game.reset_game()
    else:
        return jsonify({"error": f"Neznámá akce „{action}“."}), 400
    return jsonify({"ok": True})


@bp.post("/api/odpoved/override")
@login_required
def override_answer():
    """Ruční uznání (1) / neuznání (0) / zrušení zásahu (null) + přepočet bodů."""
    data = request.get_json(silent=True) or {}
    value = data.get("value")
    if value not in (0, 1, None):
        return jsonify({"error": "value musí být 0, 1 nebo null."}), 400
    game.set_override(data.get("answer_id"), value)
    return jsonify({"ok": True})
