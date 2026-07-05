"""Import sady otázek z CSV s validací a autodetekcí oddělovače.

Formát je zdokumentovaný v README.md. Jedna sada = jeden CSV soubor.
Podporujeme oddělovač `,` i `;` (český Excel ukládá se středníkem)
a UTF-8 s BOM i bez (Excel BOM přidává).
"""
import csv
import io
from pathlib import Path

from .db import get_db, bump_version
from .text_utils import parse_number

REQUIRED_COLUMNS = {"typ", "otazka", "spravna"}
ALL_COLUMNS = REQUIRED_COLUMNS | {
    "obrazek", "moznost_a", "moznost_b", "moznost_c", "moznost_d",
    "alt_odpovedi", "tolerance", "body",
}
VALID_TYPES = {"abcd", "pravdanepravda", "text", "cislo"}


class CsvImportError(Exception):
    """Chyby importu — nese seznam srozumitelných hlášek pro admina."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("; ".join(errors))


def _detect_delimiter(header_line: str) -> str:
    """Autodetekce: víc středníků než čárek v hlavičce → středník."""
    return ";" if header_line.count(";") > header_line.count(",") else ","


def parse_csv(raw: bytes):
    """Zparsuje CSV do seznamu slovníků otázek. Při chybách vyhodí CsvImportError."""
    try:
        text = raw.decode("utf-8-sig")  # zvládne UTF-8 s BOM i bez
    except UnicodeDecodeError:
        raise CsvImportError(
            ["Soubor není v kódování UTF-8. Ulož CSV jako „CSV UTF-8“ (Excel to umí)."]
        )

    lines = text.splitlines()
    if not lines:
        raise CsvImportError(["Soubor je prázdný."])

    delimiter = _detect_delimiter(lines[0])
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if reader.fieldnames is None:
        raise CsvImportError(["Soubor nemá hlavičku."])

    fieldnames = [f.strip().lower() for f in reader.fieldnames]
    reader.fieldnames = fieldnames

    missing = REQUIRED_COLUMNS - set(fieldnames)
    if missing:
        raise CsvImportError(
            [f"V hlavičce chybí povinné sloupce: {', '.join(sorted(missing))}."]
        )
    unknown = set(fieldnames) - ALL_COLUMNS
    errors = []
    if unknown:
        errors.append(
            f"Neznámé sloupce (budou ignorovány? ne — oprav hlavičku): {', '.join(sorted(unknown))}."
        )

    questions = []
    for lineno, row in enumerate(reader, start=2):  # řádek 1 = hlavička
        get = lambda k: (row.get(k) or "").strip()
        # přeskoč úplně prázdné řádky
        if not any(get(k) for k in fieldnames):
            continue

        typ = get("typ").lower()
        otazka = get("otazka")
        spravna = get("spravna")
        err = lambda msg: errors.append(f"Řádek {lineno}: {msg}")

        if typ not in VALID_TYPES:
            err(f"neznámý typ „{typ}“ (povolené: {', '.join(sorted(VALID_TYPES))}).")
            continue
        if not otazka:
            err("chybí text otázky.")
            continue
        if not spravna:
            err("chybí správná odpověď (sloupec `spravna`).")
            continue

        q = {
            "typ": typ,
            "otazka": otazka,
            "obrazek": get("obrazek") or None,
            "moznost_a": get("moznost_a") or None,
            "moznost_b": get("moznost_b") or None,
            "moznost_c": get("moznost_c") or None,
            "moznost_d": get("moznost_d") or None,
            "spravna": spravna,
            "alt_odpovedi": get("alt_odpovedi") or None,
            "tolerance": None,
            "body": 1,
        }

        if typ == "abcd":
            if spravna.strip().upper() not in {"A", "B", "C", "D"}:
                err("u typu abcd musí být `spravna` jedno z A/B/C/D.")
                continue
            q["spravna"] = spravna.strip().upper()
            missing_opts = [
                x.upper() for x in "abcd" if not q[f"moznost_{x}"]
            ]
            if missing_opts:
                err(f"u typu abcd chybí možnosti: {', '.join(missing_opts)}.")
                continue

        if typ == "pravdanepravda":
            val = spravna.strip().lower()
            if val not in {"pravda", "nepravda"}:
                err("u typu pravdanepravda musí být `spravna` „pravda“ nebo „nepravda“.")
                continue
            q["spravna"] = val

        if typ == "cislo":
            if parse_number(spravna) is None:
                err(f"u typu cislo musí být `spravna` číslo (je „{spravna}“).")
                continue
            tol_raw = get("tolerance")
            if tol_raw:
                tol = parse_number(tol_raw)
                if tol is None or tol < 0:
                    err(f"tolerance musí být nezáporné číslo (je „{tol_raw}“).")
                    continue
                q["tolerance"] = tol
            else:
                q["tolerance"] = 0.0  # bez tolerance = musí trefit přesně

        body_raw = get("body")
        if body_raw:
            body = parse_number(body_raw)
            if body is None or body <= 0 or body != int(body):
                err(f"body musí být kladné celé číslo (je „{body_raw}“).")
                continue
            q["body"] = int(body)

        questions.append(q)

    if errors:
        raise CsvImportError(errors)
    if not questions:
        raise CsvImportError(["Soubor neobsahuje žádné otázky."])
    return questions


def sync_folder(sets_dir) -> dict:
    """Naimportuje všechna CSV ze složky, která ještě nejsou v DB.

    Sada se pozná podle názvu = jméno souboru bez přípony; existující se
    přeskočí (import je tedy idempotentní — volá se při každém startu
    aplikace). Chce-li admin sadu aktualizovat, smaže ji v panelu a znovu
    načte složku. Vadná CSV import nezastaví, chyby se vrací zvlášť.
    """
    db = get_db()
    existing = {r["name"] for r in db.execute("SELECT name FROM question_sets")}
    imported, skipped, errors = [], [], {}
    for path in sorted(Path(sets_dir).glob("*.csv")):
        name = path.stem
        if name in existing:
            skipped.append(name)
            continue
        try:
            import_set(name, path.read_bytes())
            imported.append(name)
        except (CsvImportError, OSError) as e:
            errors[name] = e.errors if isinstance(e, CsvImportError) else [str(e)]
    return {"imported": imported, "skipped": skipped, "errors": errors}


def import_set(name: str, raw: bytes) -> int:
    """Naimportuje CSV jako novou sadu. Vrací id sady."""
    questions = parse_csv(raw)
    db = get_db()
    cur = db.execute("INSERT INTO question_sets (name) VALUES (?)", (name,))
    set_id = cur.lastrowid
    for i, q in enumerate(questions):
        db.execute(
            """INSERT INTO questions
               (set_id, poradi, typ, otazka, obrazek, moznost_a, moznost_b,
                moznost_c, moznost_d, spravna, alt_odpovedi, tolerance, body)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (set_id, i, q["typ"], q["otazka"], q["obrazek"], q["moznost_a"],
             q["moznost_b"], q["moznost_c"], q["moznost_d"], q["spravna"],
             q["alt_odpovedi"], q["tolerance"], q["body"]),
        )
    bump_version(db)
    db.commit()
    return set_id
