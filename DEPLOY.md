# Nasazení na PythonAnywhere — krok za krokem

Návod počítá s tím, že máš účet na www.pythonanywhere.com (US) nebo
eu.pythonanywhere.com (EU). Tvoje webová adresa pak bude:

- US: `https://TVOJEJMENO.pythonanywhere.com`
- EU: `https://TVOJEJMENO.eu.pythonanywhere.com`

Tu adresu budeš potřebovat v kroku 4 (QR kód musí ukazovat na ni).

## 1. Nahrání kódu

Otevři **Consoles → Bash** a naklonuj repozitář (nebo nahraj ZIP přes záložku
*Files* a rozbal ho):

```bash
cd ~
git clone https://github.com/TVUJUCET/CharisPubQuizPython.git pubquiz
cd pubquiz
```

(Dál předpokládám, že kód je v `~/pubquiz`.)

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
   - **Source code:** `/home/TVOJEJMENO/pubquiz`
   - **Virtualenv:** `/home/TVOJEJMENO/.virtualenvs/pubquiz-venv`

## 4. Konfigurace aplikace (.env)

V bash konzoli:

```bash
cd ~/pubquiz
cp .env.example .env
nano .env
```

Nastav:

```
ADMIN_PASSWORD=silne-heslo-ktere-nikdo-neuhodne
SECRET_KEY=dlouhy-nahodny-retezec        # vygeneruj třeba: python -c "import secrets;print(secrets.token_hex(32))"
PUBLIC_URL=https://TVOJEJMENO.pythonanywhere.com
```

**`PUBLIC_URL` je adresa, na kterou povede QR kód na projektoru** — použij
přesně svou doménu včetně `https://` (EU účty mají `.eu.pythonanywhere.com`).

## 5. WSGI soubor

Na záložce **Web** klikni na odkaz **WSGI configuration file**
(`/var/www/TVOJEJMENO_pythonanywhere_com_wsgi.py`) a **celý obsah nahraď** tímto:

```python
import sys

path = '/home/TVOJEJMENO/pubquiz'
if path not in sys.path:
    sys.path.insert(0, path)

from app import app as application  # noqa
```

## 6. Inicializace databáze

Databáze (SQLite soubor `pubquiz.sqlite3` v `~/pubquiz`) se vytvoří
automaticky při prvním startu aplikace — není potřeba nic ručně spouštět.
Chceš-li ji vytvořit předem / ověřit, že vše funguje:

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
| `/static/` | `/home/TVOJEJMENO/pubquiz/static` |
| `/media/`  | `/home/TVOJEJMENO/pubquiz/media` |

Tím bude CSS/JS i obrázky otázek servírovat přímo webserver (rychlejší a
nezatěžuje to Python workera). Aplikace má pro `/media/` i vlastní fallback
routu, takže obrázky fungují, i kdybys na mapování zapomněl — ale nastav ho.

## 8. Reload a test

Na záložce **Web** klikni na velké zelené **Reload**. Pak otevři:

- `https://TVOJEJMENO.pythonanywhere.com/admin` — přihlas se, naimportuj
  ukázkové CSV ze `sady_ukazky/`,
- `https://TVOJEJMENO.pythonanywhere.com/projektor` — musí ukázat QR kód
  s tvou veřejnou adresou,
- naskenuj QR telefonem a založ testovací tým.

Po každé změně kódu nebo `.env` je potřeba **Reload** znovu.

## Volba tarifu — kdy stačí free?

- **Free tarif stačí na testování a přípravu otázek** (pár zařízení, klidový
  provoz).
- Při ostré akci polluje každý klient server každé ~2 s. Při ~15 týmech +
  projektor + admin je to ~8–9 requestů za sekundu. Free tarif má **jednoho
  slabšího workera a denní CPU limit (100 s)** — requesty se budou frontovat,
  hráčům se zpozdí otázky a limit můžeš během večera vyčerpat.
- **Pro ostrý kvíz doporučuji tarif Hacker (~5 $/měsíc)** — víc CPU, rychlejší
  worker, a jde zaplatit jen na měsíc, kdy se kvíz koná. Případně můžeš
  v `.env` zvednout `POLL_INTERVAL_MS` na 3000–4000, čímž zátěž znatelně
  klesne za cenu o něco pomalejších reakcí na telefonech.

## Řešení potíží

- **Chyba po Reloadu** → záložka Web → odkazy na *Error log* a *Server log*.
- **QR vede na špatnou adresu** → zkontroluj `PUBLIC_URL` v `.env` + Reload.
- **Hráčům se nic neděje** → zkontroluj v prohlížeči telefonu, že stránka
  běží přes `https://` a že aplikace odpovídá na `/api/hrac`.
- **Import CSV hlásí kódování** → v Excelu ulož jako „CSV UTF-8 (s oddělovači)“.
