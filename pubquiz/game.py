"""Herní engine: stavový automat, vyhodnocování odpovědí, pořadí.

Stav hry je jediný řádek v tabulce game_state a je autoritativní na
serveru — klienti (hráč, projektor, admin) si ho jen pollingem čtou.

Fáze hry (phase):
    lobby          čekárna: QR kód, přibývající týmy
    question       hraje se otázka (podstav q_state)
    results_set    pořadí v rámci právě dohrané sady
    results_total  celkové pořadí večera (se změnou pozic oproti stavu před sadou)
    review         opakované projetí sady se správnými odpověďmi
    finished       konec večera, finální pořadí

Podstavy otázky (q_state):
    shown      otázka je vidět, odpovědi zatím nejsou otevřené
    open       hráči mohou odpovídat / měnit odpověď
    countdown  admin zavřel odpovědi, běží odpočet — odpovídat stále lze
    locked     odpovědi definitivně zamčené a vyhodnocené
    revealed   na projektoru se ukazuje správná odpověď
"""
import json
import time

from .db import get_db, bump_version
from .text_utils import normalize_text, parse_number


# ---------------------------------------------------------------------------
# Čtení stavu
# ---------------------------------------------------------------------------

def get_state():
    db = get_db()
    return db.execute("SELECT * FROM game_state WHERE id = 1").fetchone()


def set_queue(state) -> list:
    return json.loads(state["set_queue"])


def current_set_id(state):
    queue = set_queue(state)
    if 0 <= state["set_index"] < len(queue):
        return queue[state["set_index"]]
    return None


def set_questions(set_id) -> list:
    db = get_db()
    return db.execute(
        "SELECT * FROM questions WHERE set_id = ? ORDER BY poradi", (set_id,)
    ).fetchall()


def current_question(state, index_field="question_index"):
    sid = current_set_id(state)
    if sid is None:
        return None
    qs = set_questions(sid)
    idx = state[index_field]
    if 0 <= idx < len(qs):
        return qs[idx]
    return None


def _update_state(**fields):
    """Zapíše změny do game_state a zvýší verzi."""
    db = get_db()
    cols = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE game_state SET {cols} WHERE id = 1", list(fields.values()))
    bump_version(db)
    db.commit()


def tick():
    """Líné dokončení odpočtu — volá se před každým čtením stavu i akcí.

    Na WSGI hostingu neběží žádný plánovač na pozadí, takže odpočet
    dokončí první request, který přijde po jeho vypršení (hráči pollují
    každé ~2 s, takže zpoždění je zanedbatelné).
    """
    state = get_state()
    if (
        state["phase"] == "question"
        and state["q_state"] == "countdown"
        and state["countdown_ends"] is not None
        and time.time() >= state["countdown_ends"]
    ):
        lock_and_evaluate(state)
        state = get_state()
    return state


# ---------------------------------------------------------------------------
# Akce admina — průběh hry
# ---------------------------------------------------------------------------

def start_game(set_ids: list):
    """Spustí kvíz s vybranými sadami v daném pořadí; ukáže první otázku."""
    _update_state(
        phase="question",
        set_queue=json.dumps(set_ids),
        set_index=0,
        question_index=0,
        q_state="shown",
        countdown_ends=None,
        review_index=-1,
    )


def open_answers():
    _update_state(q_state="open", countdown_ends=None)


def close_answers(countdown_secs: int):
    """Zavření odpovědí = start odpočtu; po něm se odpovědi zamknou."""
    if countdown_secs <= 0:
        state = get_state()
        lock_and_evaluate(state)
        return
    _update_state(
        q_state="countdown",
        countdown_secs=countdown_secs,
        countdown_ends=time.time() + countdown_secs,
    )


def reveal_answer():
    _update_state(q_state="revealed")


def next_question():
    """Posun na další otázku; po poslední otázce sady → výsledky sady."""
    state = get_state()
    sid = current_set_id(state)
    qs = set_questions(sid)
    if state["question_index"] + 1 < len(qs):
        _update_state(
            phase="question",
            question_index=state["question_index"] + 1,
            q_state="shown",
            countdown_ends=None,
        )
    else:
        _update_state(phase="results_set", q_state="locked", countdown_ends=None)


def prev_question():
    """Krok zpět (pojistka pro admina); odpovědi zůstávají, jak byly."""
    state = get_state()
    if state["question_index"] > 0:
        _update_state(
            phase="question",
            question_index=state["question_index"] - 1,
            q_state="locked",
        )


def show_total_results():
    _update_state(phase="results_total")


def start_review():
    _update_state(phase="review", review_index=0)


def review_move(delta: int):
    state = get_state()
    qs = set_questions(current_set_id(state))
    new = max(0, min(len(qs) - 1, state["review_index"] + delta))
    _update_state(review_index=new)


def end_review():
    _update_state(phase="results_total", review_index=-1)


def next_set():
    """Přechod na další sadu, nebo konec večera, pokud byla poslední."""
    state = get_state()
    queue = set_queue(state)
    if state["set_index"] + 1 < len(queue):
        _update_state(
            phase="question",
            set_index=state["set_index"] + 1,
            question_index=0,
            q_state="shown",
            countdown_ends=None,
            review_index=-1,
        )
    else:
        _update_state(phase="finished")


def reset_game():
    """Vrátí hru do lobby a smaže odpovědi (týmy a sady zůstávají)."""
    db = get_db()
    db.execute("DELETE FROM answers")
    db.commit()
    _update_state(
        phase="lobby",
        set_queue="[]",
        set_index=-1,
        question_index=-1,
        q_state="hidden",
        countdown_ends=None,
        review_index=-1,
    )


# ---------------------------------------------------------------------------
# Odpovědi hráčů
# ---------------------------------------------------------------------------

def answers_open(state) -> bool:
    """Hráč smí odpovídat ve stavech open a countdown (dokud odpočet běží)."""
    if state["phase"] != "question":
        return False
    if state["q_state"] == "open":
        return True
    if state["q_state"] == "countdown":
        return state["countdown_ends"] is None or time.time() < state["countdown_ends"]
    return False


def save_answer(team_id: int, question_id: int, odpoved: str):
    db = get_db()
    db.execute(
        """INSERT INTO answers (question_id, team_id, odpoved, updated_at)
           VALUES (?, ?, ?, datetime('now'))
           ON CONFLICT (question_id, team_id)
           DO UPDATE SET odpoved = excluded.odpoved, updated_at = excluded.updated_at""",
        (question_id, team_id, odpoved),
    )
    bump_version(db)
    db.commit()


# ---------------------------------------------------------------------------
# Vyhodnocování a bodování
# ---------------------------------------------------------------------------

def _auto_correct(question, odpoved: str):
    """Automatické vyhodnocení odpovědi (bez číselného bonusu). Vrací 0/1."""
    typ = question["typ"]
    if typ == "abcd":
        return 1 if normalize_text(odpoved) == normalize_text(question["spravna"]) else 0
    if typ == "pravdanepravda":
        return 1 if normalize_text(odpoved) == normalize_text(question["spravna"]) else 0
    if typ == "text":
        accepted = [question["spravna"]] + [
            a for a in (question["alt_odpovedi"] or "").split("|") if a.strip()
        ]
        norm = normalize_text(odpoved)
        return 1 if any(norm == normalize_text(a) for a in accepted) else 0
    if typ == "cislo":
        value = parse_number(odpoved)
        correct = parse_number(question["spravna"])
        if value is None or correct is None:
            return 0
        tol = question["tolerance"] if question["tolerance"] is not None else 0.0
        return 1 if abs(value - correct) <= tol else 0
    return 0


def _recompute_points(db, question):
    """Přepočítá body všech odpovědí u otázky (override má přednost).

    U typu `cislo` navíc přidělí +1 bonusový bod týmu (týmům) s nejmenším
    absolutním rozdílem od správné hodnoty — bez ohledu na toleranci.
    """
    rows = db.execute(
        "SELECT * FROM answers WHERE question_id = ?", (question["id"],)
    ).fetchall()

    # Bonus za nejbližší odhad (jen cislo, jen platné číselné odpovědi)
    bonus_ids = set()
    if question["typ"] == "cislo":
        correct = parse_number(question["spravna"])
        diffs = []
        for r in rows:
            v = parse_number(r["odpoved"])
            if v is not None and correct is not None:
                diffs.append((abs(v - correct), r["id"]))
        if diffs:
            best = min(d for d, _ in diffs)
            bonus_ids = {rid for d, rid in diffs if d == best}

    for r in rows:
        correct = r["override"] if r["override"] is not None else (r["auto_spravne"] or 0)
        bonus = 1 if r["id"] in bonus_ids else 0
        points = (question["body"] if correct else 0) + bonus
        db.execute(
            "UPDATE answers SET bonus = ?, body = ? WHERE id = ?",
            (bonus, points, r["id"]),
        )


def lock_and_evaluate(state):
    """Zamkne odpovědi aktuální otázky a vyhodnotí je."""
    question = current_question(state)
    db = get_db()
    if question is not None:
        rows = db.execute(
            "SELECT * FROM answers WHERE question_id = ?", (question["id"],)
        ).fetchall()
        for r in rows:
            db.execute(
                "UPDATE answers SET auto_spravne = ? WHERE id = ?",
                (_auto_correct(question, r["odpoved"]), r["id"]),
            )
        _recompute_points(db, question)
    db.execute(
        "UPDATE game_state SET q_state = 'locked', countdown_ends = NULL WHERE id = 1"
    )
    bump_version(db)
    db.commit()


def set_override(answer_id: int, value):
    """Ruční uznání/neuznání odpovědi adminem (value: 1/0/None) + přepočet."""
    db = get_db()
    row = db.execute("SELECT * FROM answers WHERE id = ?", (answer_id,)).fetchone()
    if row is None:
        return
    db.execute("UPDATE answers SET override = ? WHERE id = ?", (value, answer_id))
    question = db.execute(
        "SELECT * FROM questions WHERE id = ?", (row["question_id"],)
    ).fetchone()
    _recompute_points(db, question)
    bump_version(db)
    db.commit()


# ---------------------------------------------------------------------------
# Pořadí
# ---------------------------------------------------------------------------

def _rank(rows):
    """Z [(team_id, name, points), …] udělá pořadí; remíza = sdílené místo."""
    rows = sorted(rows, key=lambda r: -r[2])
    result = []
    for i, (tid, name, pts) in enumerate(rows):
        rank = result[i - 1]["rank"] if i > 0 and result[i - 1]["points"] == pts else i + 1
        result.append({"rank": rank, "team_id": tid, "name": name, "points": pts})
    return result


def _points_query(db, set_ids=None, exclude_set_id=None):
    """Součet bodů týmů, volitelně jen za dané sady / bez jedné sady."""
    sql = """
        SELECT t.id, t.name, COALESCE(SUM(a.body), 0) AS pts
        FROM teams t
        LEFT JOIN answers a ON a.team_id = t.id
        LEFT JOIN questions q ON q.id = a.question_id
    """
    where, params = [], []
    if set_ids is not None:
        placeholders = ",".join("?" * len(set_ids)) or "NULL"
        where.append(f"(q.set_id IN ({placeholders}) OR a.id IS NULL)")
        params.extend(set_ids)
    if exclude_set_id is not None:
        where.append("(q.set_id IS NULL OR q.set_id != ?)")
        params.append(exclude_set_id)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " GROUP BY t.id ORDER BY pts DESC, t.name"
    return [(r["id"], r["name"], r["pts"]) for r in db.execute(sql, params)]


def standings_total(state):
    """Celkové pořadí večera + změna pozice oproti stavu před aktuální sadou."""
    db = get_db()
    now = _rank(_points_query(db))
    sid = current_set_id(state)
    before = _rank(_points_query(db, exclude_set_id=sid)) if sid else now
    before_rank = {r["team_id"]: r["rank"] for r in before}
    for r in now:
        prev = before_rank.get(r["team_id"])
        r["change"] = (prev - r["rank"]) if prev is not None else 0
    return now


def standings_set(set_id):
    """Pořadí v rámci jedné sady."""
    db = get_db()
    return _rank(_points_query(db, set_ids=[set_id]))
