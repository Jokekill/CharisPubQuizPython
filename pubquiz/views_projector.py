"""Projektorový pohled: fullscreen obrazovka + QR kód generovaný na serveru."""
import io

import qrcode
from flask import Blueprint, current_app, jsonify, render_template, send_file

from . import game
from .db import get_db
from .payloads import base_state

bp = Blueprint("projector", __name__)


@bp.route("/projektor")
def projector():
    return render_template("projektor.html")


@bp.get("/qr.png")
def qr_png():
    """QR kód s veřejnou URL aplikace — generujeme lokálně (bez externích API)."""
    url = current_app.config["PUBLIC_URL"].rstrip("/") + "/"
    img = qrcode.make(url, box_size=12, border=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


@bp.get("/api/projektor")
def projector_state():
    """Polling endpoint projektoru."""
    state = game.tick()
    payload = base_state(state)
    payload["public_url"] = current_app.config["PUBLIC_URL"].rstrip("/") + "/"
    if state["phase"] == "lobby":
        db = get_db()
        teams = db.execute("SELECT name FROM teams ORDER BY created_at").fetchall()
        payload["teams"] = [t["name"] for t in teams]
    return jsonify(payload)
