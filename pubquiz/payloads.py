"""Sestavování JSON odpovědí pro polling klientů (hráč / projektor / admin)."""
import time

from flask import current_app

from . import game
from .db import get_db


def question_public(q):
    """Otázka pro hráče/projektor — BEZ správné odpovědi."""
    return {
        "id": q["id"],
        "typ": q["typ"],
        "otazka": q["otazka"],
        "obrazek": q["obrazek"],
        "moznosti": {
            "A": q["moznost_a"], "B": q["moznost_b"],
            "C": q["moznost_c"], "D": q["moznost_d"],
        } if q["typ"] == "abcd" else None,
        "body": q["body"],
    }


def correct_answer_text(q):
    """Lidsky čitelná správná odpověď pro projekci."""
    if q["typ"] == "abcd":
        letter = q["spravna"]
        option = q[f"moznost_{letter.lower()}"]
        return f"{letter}) {option}"
    if q["typ"] == "pravdanepravda":
        return q["spravna"].capitalize()
    if q["typ"] == "cislo":
        tol = q["tolerance"]
        return f"{q['spravna']}" + (f" (±{tol:g})" if tol else "")
    alts = [a.strip() for a in (q["alt_odpovedi"] or "").split("|") if a.strip()]
    return q["spravna"] + (f" (uznáváno i: {', '.join(alts)})" if alts else "")


def base_state(state):
    """Společný základ pro všechny polling odpovědi."""
    payload = {
        "version": state["version"],
        "phase": state["phase"],
        "q_state": state["q_state"],
        "poll_interval_ms": current_app.config["POLL_INTERVAL_MS"],
        "countdown_remaining": None,
        "set_number": state["set_index"] + 1,
        "set_count": len(game.set_queue(state)),
    }
    if state["q_state"] == "countdown" and state["countdown_ends"]:
        payload["countdown_remaining"] = max(0, round(state["countdown_ends"] - time.time(), 1))

    sid = game.current_set_id(state)
    if sid is not None:
        db = get_db()
        s = db.execute("SELECT name FROM question_sets WHERE id = ?", (sid,)).fetchone()
        qs = game.set_questions(sid)
        payload["set_name"] = s["name"] if s else None
        payload["question_number"] = state["question_index"] + 1
        payload["question_count"] = len(qs)

    if state["phase"] == "question":
        q = game.current_question(state)
        if q is not None:
            payload["question"] = question_public(q)
            if state["q_state"] == "revealed":
                payload["correct_answer"] = correct_answer_text(q)

    if state["phase"] == "results_set" and sid is not None:
        payload["standings_set"] = game.standings_set(sid)
    if state["phase"] in ("results_total", "finished"):
        payload["standings_total"] = game.standings_total(state)

    if state["phase"] == "review":
        q = game.current_question(state, index_field="review_index")
        if q is not None:
            payload["question_number"] = state["review_index"] + 1
            payload["question"] = question_public(q)
            payload["correct_answer"] = correct_answer_text(q)
            payload["review_answers"] = team_answers(q)
    return payload


def team_answers(q):
    """Odpovědi týmů k otázce (pro review na projektoru a pro admina)."""
    db = get_db()
    rows = db.execute(
        """SELECT a.*, t.name AS team_name FROM answers a
           JOIN teams t ON t.id = a.team_id
           WHERE a.question_id = ? ORDER BY t.name""",
        (q["id"],),
    ).fetchall()
    return [
        {
            "answer_id": r["id"],
            "team": r["team_name"],
            "odpoved": r["odpoved"],
            "auto_spravne": r["auto_spravne"],
            "override": r["override"],
            "spravne": r["override"] if r["override"] is not None else r["auto_spravne"],
            "bonus": r["bonus"],
            "body": r["body"],
        }
        for r in rows
    ]
