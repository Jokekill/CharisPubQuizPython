"""Hráčská část: join stránka, založení týmu, polling stavu, odesílání odpovědí.

Identita týmu = náhodný token uložený v localStorage telefonu a v DB.
Po obnovení stránky / pádu prohlížeče se hráč automaticky vrátí do hry.
"""
import secrets

from flask import Blueprint, current_app, jsonify, render_template, request

from . import game
from .db import get_db, bump_version
from .payloads import base_state

bp = Blueprint("player", __name__)

MAX_TEAM_NAME = 30
MAX_ANSWER_LEN = 200


@bp.route("/")
@bp.route("/hrat")
def index():
    return render_template("hrac.html")


def _team_from_token():
    token = request.headers.get("X-Team-Token") or request.args.get("token") or ""
    if not token:
        return None
    db = get_db()
    return db.execute("SELECT * FROM teams WHERE token = ?", (token,)).fetchone()


@bp.post("/api/join")
def join():
    """Založení týmu. Vrací token, který si telefon uloží do localStorage."""
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()[:MAX_TEAM_NAME]
    if not name:
        return jsonify({"error": "Zadejte název týmu."}), 400
    db = get_db()
    existing = db.execute(
        "SELECT id FROM teams WHERE lower(name) = lower(?)", (name,)
    ).fetchone()
    if existing:
        return jsonify({"error": "Tým s tímto názvem už existuje, zvolte jiný."}), 400
    token = secrets.token_urlsafe(16)
    db.execute("INSERT INTO teams (name, token) VALUES (?, ?)", (name, token))
    bump_version(db)
    db.commit()
    return jsonify({"token": token, "name": name})


@bp.get("/api/hrac")
def player_state():
    """Polling endpoint hráče — kompletní stav pro vykreslení obrazovky."""
    state = game.tick()
    payload = base_state(state)

    team = _team_from_token()
    if team is None:
        payload["team"] = None  # token neplatný / tým smazán → zpět na join
        return jsonify(payload)

    payload["team"] = {"id": team["id"], "name": team["name"]}
    payload["answers_open"] = game.answers_open(state)

    # Vlastní odpověď týmu na aktuální otázku (aby po reloadu nezmizela)
    q = None
    if state["phase"] == "question":
        q = game.current_question(state)
    if q is not None:
        db = get_db()
        a = db.execute(
            "SELECT * FROM answers WHERE question_id = ? AND team_id = ?",
            (q["id"], team["id"]),
        ).fetchone()
        if a:
            payload["my_answer"] = a["odpoved"]
            if state["q_state"] in ("locked", "revealed") and a["auto_spravne"] is not None:
                correct = a["override"] if a["override"] is not None else a["auto_spravne"]
                payload["my_result"] = {"spravne": bool(correct), "body": a["body"]}
    return jsonify(payload)


@bp.post("/api/odpoved")
def submit_answer():
    """Uložení/změna odpovědi — jen dokud jsou odpovědi otevřené."""
    team = _team_from_token()
    if team is None:
        return jsonify({"error": "Neplatný tým. Načtěte stránku znovu."}), 403
    state = game.tick()
    if not game.answers_open(state):
        return jsonify({"error": "Odpovědi jsou zamčené."}), 409
    q = game.current_question(state)
    if q is None:
        return jsonify({"error": "Žádná aktivní otázka."}), 409
    data = request.get_json(silent=True) or {}
    odpoved = (str(data.get("odpoved") or "")).strip()[:MAX_ANSWER_LEN]
    if not odpoved:
        return jsonify({"error": "Prázdná odpověď."}), 400
    game.save_answer(team["id"], q["id"], odpoved)
    return jsonify({"ok": True, "odpoved": odpoved})
