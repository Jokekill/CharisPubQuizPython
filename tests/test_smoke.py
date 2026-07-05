"""Integrační smoke test celého herního toku přes Flask test client.

Spuštění:  python -m pytest tests/  nebo  python tests/test_smoke.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Testovací konfigurace přes env — musí být před importem aplikace
_tmp = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(_tmp, "test.sqlite3")
os.environ["ADMIN_PASSWORD"] = "test123"

from pubquiz import create_app  # noqa: E402


def make_client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def admin_login(c):
    r = c.post("/admin/login", data={"password": "test123"}, follow_redirects=False)
    assert r.status_code == 302


def test_full_flow():
    c = make_client()
    admin_login(c)

    # --- import CSV (středníková i čárková varianta) ---
    base = os.path.join(os.path.dirname(__file__), "..", "sady_ukazky")
    for fname in ("ukazka_mix.csv", "ukazka_cislo.csv"):
        with open(os.path.join(base, fname), "rb") as f:
            r = c.post("/admin/api/import-csv", data={"file": (f, fname)})
        assert r.status_code == 200, r.get_json()

    # nevalidní CSV musí vrátit srozumitelnou chybu
    import io
    bad = io.BytesIO("typ,otazka\nabcd,Chybi spravna\n".encode())
    r = c.post("/admin/api/import-csv", data={"file": (bad, "bad.csv")})
    assert r.status_code == 400
    assert "spravna" in str(r.get_json())

    state = c.get("/admin/api/stav").get_json()
    sets = {s["name"]: s for s in state["sets"]}
    assert sets["ukazka_mix"]["question_count"] == 10
    assert sets["ukazka_cislo"]["question_count"] == 5

    # --- připojení týmů ---
    tokens = {}
    for name in ("Alfa", "Beta", "Gama"):
        r = c.post("/api/join", json={"name": name})
        assert r.status_code == 200
        tokens[name] = r.get_json()["token"]
    # duplicitní název odmítnout
    assert c.post("/api/join", json={"name": "alfa"}).status_code == 400

    # projektor v lobby vidí týmy a QR endpoint funguje
    p = c.get("/api/projektor").get_json()
    assert p["phase"] == "lobby" and set(p["teams"]) == {"Alfa", "Beta", "Gama"}
    assert c.get("/qr.png").status_code == 200

    # --- start hry se sadou cislo (bonusová logika) ---
    sid = sets["ukazka_cislo"]["id"]
    r = c.post("/admin/api/hra/start", json={"set_ids": [sid]})
    assert r.status_code == 200

    def act(action, **kw):
        r = c.post("/admin/api/hra/akce", json=dict(action=action, **kw))
        assert r.status_code == 200, r.get_json()

    def answer(team, val, expect=200):
        r = c.post("/api/odpoved", json={"odpoved": val},
                   headers={"X-Team-Token": tokens[team]})
        assert r.status_code == expect, r.get_json()

    # Otázka 1: Vltava 430 ±30. Alfa 425 (pásmo+nejblíž=2b), Beta 400 (pásmo=1b), Gama 100 (0b)
    answer("Alfa", "425", expect=409)  # odpovědi ještě nejsou otevřené
    act("open")
    answer("Alfa", "999")
    answer("Alfa", "425")  # změna odpovědi před zamčením
    answer("Beta", "400")
    answer("Gama", "100")
    act("close", countdown=0)  # okamžité zamčení

    st = c.get("/admin/api/stav").get_json()
    assert st["q_state"] == "locked"
    pts = {a["team"]: a["body"] for a in st["answers"]}
    assert pts == {"Alfa": 2, "Beta": 1, "Gama": 0}, pts

    # po zamčení už odpověď nejde změnit
    answer("Alfa", "430", expect=409)

    # hráč vidí svůj výsledek
    h = c.get("/api/hrac", headers={"X-Team-Token": tokens["Alfa"]}).get_json()
    assert h["my_result"]["spravne"] is True and h["my_result"]["body"] == 2

    # ruční neuznání Alfy → ztratí bod za pásmo, bonus за nejblíž zůstává
    aid = next(a["answer_id"] for a in st["answers"] if a["team"] == "Alfa")
    r = c.post("/admin/api/odpoved/override", json={"answer_id": aid, "value": 0})
    assert r.status_code == 200
    st = c.get("/admin/api/stav").get_json()
    pts = {a["team"]: a["body"] for a in st["answers"]}
    assert pts["Alfa"] == 1, pts  # jen bonus
    # zrušení zásahu → zpět na 2
    c.post("/admin/api/odpoved/override", json={"answer_id": aid, "value": None})
    st = c.get("/admin/api/stav").get_json()
    assert {a["team"]: a["body"] for a in st["answers"]}["Alfa"] == 2

    act("reveal")
    p = c.get("/api/projektor").get_json()
    assert p["q_state"] == "revealed" and "430" in p["correct_answer"]

    # projet zbylé otázky bez odpovědí
    for _ in range(4):
        act("next")
        s = c.get("/api/projektor").get_json()
        if s["phase"] == "question":
            act("open")
            act("close", countdown=0)
    act("next")

    s = c.get("/api/projektor").get_json()
    assert s["phase"] == "results_set"
    ranks = {r["name"]: r["rank"] for r in s["standings_set"]}
    assert ranks["Alfa"] == 1 and ranks["Beta"] == 2 and ranks["Gama"] == 3

    act("total_results")
    s = c.get("/api/projektor").get_json()
    assert s["phase"] == "results_total"
    assert s["standings_total"][0]["name"] == "Alfa"

    # review mód
    act("review_start")
    s = c.get("/api/projektor").get_json()
    assert s["phase"] == "review" and s["correct_answer"]
    assert any(a["team"] == "Alfa" and a["spravne"] for a in s["review_answers"])
    act("review_next")
    act("review_end")

    # konec (jediná sada) → finished
    act("next_set")
    s = c.get("/api/projektor").get_json()
    assert s["phase"] == "finished"
    assert s["standings_total"][0]["points"] == 2

    # správa týmů
    st = c.get("/admin/api/stav").get_json()
    gid = next(t["id"] for t in st["teams"] if t["name"] == "Gama")
    c.post("/admin/api/tym/prejmenovat", json={"team_id": gid, "name": "Gama2"})
    c.post("/admin/api/tym/smazat", json={"team_id": gid})
    st = c.get("/admin/api/stav").get_json()
    assert all(t["name"] != "Gama2" for t in st["teams"])

    # smazaný tým dostane na pollingu team=None (návrat na join obrazovku)
    h = c.get("/api/hrac", headers={"X-Team-Token": tokens["Gama"]}).get_json()
    assert h["team"] is None

    # reset hry
    act("reset")
    s = c.get("/api/projektor").get_json()
    assert s["phase"] == "lobby"

    print("SMOKE TEST OK")


def test_text_normalization():
    from pubquiz.text_utils import normalize_text, parse_number
    assert normalize_text("  MUŽ ") == "muz"
    assert normalize_text("Sněžka") == normalize_text("snezka")
    assert parse_number("10,5") == 10.5
    assert parse_number("  1 348 ") == 1348.0
    assert parse_number("abc") is None
    print("NORMALIZATION OK")


if __name__ == "__main__":
    test_text_normalization()
    test_full_flow()
