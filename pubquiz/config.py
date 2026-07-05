"""Konfigurace aplikace.

Hodnoty lze přepsat proměnnými prostředí nebo souborem `.env` v kořeni
projektu (formát KEY=VALUE, viz `.env.example`). Na PythonAnywhere je
nejjednodušší vytvořit `.env` — viz DEPLOY.md.
"""
import os
from pathlib import Path

# Kořen projektu (složka nad balíčkem pubquiz/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Načtení .env, pokud existuje (python-dotenv je volitelný)
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


class Config:
    # Tajný klíč pro session (admin přihlášení). Na produkci nastav vlastní!
    SECRET_KEY = os.environ.get("SECRET_KEY", "zmen-me-na-neco-nahodneho")

    # Heslo do admin panelu (/admin)
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "kviz123")

    # Veřejná URL aplikace — používá se pro QR kód a odkaz na projektoru.
    # Výchozí = produkční adresa na PythonAnywhere (účet CharisPubQuizz).
    # Pro lokální testování s telefony přepiš v .env na IP počítače v síti.
    PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://charispubquizz.pythonanywhere.com")

    # Interval pollingu klientů v milisekundách (výchozí 2 s)
    POLL_INTERVAL_MS = _int("POLL_INTERVAL_MS", 2000)

    # Výchozí délka odpočtu po zavření odpovědí (sekundy); jde měnit i v adminu
    DEFAULT_COUNTDOWN_S = _int("DEFAULT_COUNTDOWN_S", 5)

    # Cesta k SQLite databázi (výchozí: kořen projektu)
    DB_PATH = os.environ.get("DB_PATH", str(BASE_DIR / "pubquiz.sqlite3"))

    # Složka s obrázky otázek
    MEDIA_DIR = os.environ.get("MEDIA_DIR", str(BASE_DIR / "media"))

    # Max. velikost uploadu (CSV / obrázky)
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
