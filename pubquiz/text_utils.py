"""Normalizace textu a čísel pro vyhodnocování odpovědí."""
import unicodedata


def normalize_text(s: str) -> str:
    """Normalizace pro porovnání: ořez mezer, lowercase, bez diakritiky.

    „ Muž " → "muz", takže „muz" == „Muž".
    """
    s = (s or "").strip().lower()
    # NFD rozloží znaky na základ + diakritické znaménko, znaménka zahodíme
    decomposed = unicodedata.normalize("NFD", s)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    # sjednocení vícenásobných mezer
    return " ".join(stripped.split())


def parse_number(s: str):
    """Převede řetězec na float; toleruje českou desetinnou čárku a mezery.

    Vrací None, když převod nejde.
    """
    if s is None:
        return None
    cleaned = str(s).strip().replace(" ", "").replace(" ", "").replace(",", ".")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None
