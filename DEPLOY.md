# Nasazení na PythonAnywhere — krok za krokem

Návod je napsaný přímo pro tento projekt:

- **PythonAnywhere účet:** `CharisPubQuizz` (US server www.pythonanywhere.com)
- **Veřejná adresa webu:** `https://charispubquizz.pythonanywhere.com`
- **GitHub repozitář:** `https://github.com/Jokekill/CharisPubQuizPython`

Adresa `https://charispubquizz.pythonanywhere.com` je zároveň výchozí
`PUBLIC_URL` v aplikaci — **QR kód na projektoru na ni míří automaticky**,
i kdybys žádný `.env` nevytvořil.

## 1. Nahrání kódu

Na PythonAnywhere otevři **Consoles → Bash** a naklonuj repozitář:

```bash
cd ~
git clone https://github.com/Jokekill/CharisPubQuizPython.git pubquiz
cd pubquiz
```

(Při pozdějších aktualizacích pak stačí `cd ~/pubquiz && git pull` + Reload.)

## 2. Virtualenv a závislosti

Ve stejné bash konzoli:

```bash
mkvirtualenv pubquiz-venv --python=python3.12
pip install -r ~/pubquiz/requirements.txt
```

(Kdyby `mkvirtualenv` nebyl k dispozici: `python3.12 -m venv ~/.virtualenvs/pubquiz-venv`
a pak `source ~/.virtualenvs/pubquiz-venv/bin/activate`.)

## 3. Vytvoření webové aplikace

1. Záložka **Web → Add a new web app**.
2. Zvol **Manual configuration** (NE „Flask“ — ten vytváří vlastní skeleton)
   a Python 3.12.
3. Na stránce webové aplikace nastav:
   - **Source code:** `/home/CharisPubQuizz/pubquiz`
   - **Virtualenv:** `/home/CharisPubQuizz/.virtualenvs/pubquiz-venv`

## 4. Konfigurace aplikace (.env)

V bash konzoli:

```bash
cd ~/pubquiz
cp .env.example .env
nano .env
```

Povinně změň heslo a tajný klíč (PUBLIC_URL už je v souboru správně):

```
ADMIN_PASSWORD=silne-heslo-ktere-nikdo-neuhodne
SECRET_KEY=dlouhy-nahodny-retezec        # vygeneruj: python -c "import secrets;print(secrets.token_hex(32))"
PUBLIC_URL=https://charispubquizz.pythonanywhere.com
```

## 5. WSGI soubor

Na záložce **Web** klikni na odkaz **WSGI configuration file**
(`/var/www/charispubquizz_pythonanywhere_com_wsgi.py`) a **celý obsah nahraď** tímto:

```python
import sys

path = '/home/CharisPubQuizz/pubquiz'
if path not in sys.path:
    sys.path.insert(0, path)

from app import app as application  # noqa
```

## 6. Inicializace databáze

Databáze (SQLite soubor `pubquiz.sqlite3` v `~/pubquiz`) se vytvoří
automaticky při prvním startu aplikace — není potřeba nic ručně spouštět.
Chceš-li ověřit, že vše funguje, ještě před Reloadem:

```bash
cd ~/pubquiz
workon pubquiz-venv
python -c "from pubquiz import create_app; create_app(); print('DB OK')"
```

Pro **úplný reset** (nový večer od nuly) stačí soubor smazat:
`rm ~/pubquiz/pubquiz.sqlite3` a dát Reload. (Menší reset — smazání odpovědí
při zachování týmů a sad — je přímo v admin panelu.)

## 7. Statické soubory

Na záložce **Web** v sekci **Static files** přidej dvě mapování:

| URL | Directory |
|---|---|
| `/static/` | `/home/CharisPubQuizz/pubquiz/static` |
| `/media/`  | `/home/CharisPubQuizz/pubquiz/media` |

Tím bude CSS/JS i obrázky otázek servírovat přímo webserver (rychlejší a
nezatěžuje to Python workera). Aplikace má pro `/media/` i vlastní fallback
routu, takže obrázky fungují, i kdybys na mapování zapomněl — ale nastav ho.

## 8. Reload a test

Na záložce **Web** klikni na velké zelené **Reload**. Pak otevři:

- `https://charispubquizz.pythonanywhere.com/admin` — přihlas se; sady ze
  složky `sady_ukazky/` (včetně `vlajky_spek`) už tam budou načtené
  automaticky. Vlastní kvízové CSV stačí nahrát do téže složky (záložka
  *Files* nebo git) a dát Reload či v adminu „Načíst CSV ze složky“,
- `https://charispubquizz.pythonanywhere.com/projektor` — musí ukázat QR kód
  mířící na `https://charispubquizz.pythonanywhere.com/`,
- naskenuj QR telefonem a založ testovací tým.

Po každé změně kódu (`git pull`) nebo `.env` je potřeba **Reload** znovu.

## Volba tarifu — kdy stačí free?

- **Free tarif stačí na testování a přípravu otázek** (pár zařízení, klidový
  provoz).
- Při ostré akci polluje každý klient server každé ~2 s. Při ~15 týmech +
  projektor + admin je to ~8–9 requestů za sekundu. Free tarif má **jednoho
  slabšího workera a denní CPU limit (100 s)** — requesty se budou frontovat,
  hráčům se zpozdí otázky a limit můžeš během večera vyčerpat.
- **Pro ostrý kvíz na konferenci doporučuji tarif Hacker (~5 $/měsíc)** —
  víc CPU a rychlejší worker; jde zaplatit jen na měsíc, kdy se kvíz koná.
  Případně můžeš v `.env` zvednout `POLL_INTERVAL_MS` na 3000–4000, čímž
  zátěž znatelně klesne za cenu o něco pomalejších reakcí na telefonech.

## Řešení potíží

- **Chyba po Reloadu** → záložka Web → odkazy na *Error log* a *Server log*.
- **QR vede na špatnou adresu** → zkontroluj `PUBLIC_URL` v `.env` + Reload.
- **Hráčům se nic neděje** → zkontroluj v prohlížeči telefonu, že stránka
  běží přes `https://` a že aplikace odpovídá na `/api/hrac`.
- **Import CSV hlásí kódování** → v Excelu ulož jako „CSV UTF-8 (s oddělovači)“.
