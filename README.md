# 🍺 Pubkvíz

Webová aplikace pro vedení pubkvízu (Flask + SQLite), stavěná pro hostování na
[PythonAnywhere](https://www.pythonanywhere.com). Tři obrazovky:

| URL | K čemu |
|---|---|
| `/` | **Hráč** — mobilní stránka: založení týmu přes QR, odpovídání na otázky |
| `/projektor` | **Projektor** — fullscreen pohled: QR pro připojení, otázky, odpočet, pořadí |
| `/admin` | **Admin** — ovládání kvízu (chráněno heslem): import CSV, výběr sad, posun otázek, uznávání odpovědí, správa týmů |

Živá synchronizace běží přes **AJAX short-polling** (výchozí 2 s) — žádné
WebSockets, což je záměr kvůli WSGI hostingu. Stav hry je autoritativní na
serveru v SQLite, takže reload telefonu ani restart aplikace o nic nepřipraví.

## Rychlý lokální běh

```
python -m venv .venv
.venv\Scripts\activate          # Windows (na Linuxu: source .venv/bin/activate)
pip install -r requirements.txt
python app.py
```

Aplikace běží na http://127.0.0.1:5000. Admin: http://127.0.0.1:5000/admin,
výchozí heslo **kviz123** (změň v `.env`, viz `.env.example`).

Aby se telefony připojily i lokálně (testování v obýváku), spusť
`python app.py` s `host="0.0.0.0"` v `app.py` a v `.env` nastav
`PUBLIC_URL=http://IP-tvého-počítače:5000` — QR kód pak povede správně.

Testy: `.venv\Scripts\python tests\test_smoke.py`

## Průběh večera

1. CSV sady ve složce `sady_ukazky/` se **načtou automaticky při startu
   aplikace** — stačí soubory nahrát na server (git pull nebo záložka Files
   na PythonAnywhere) a dát Reload, případně v adminu kliknout na
   „🔄 Načíst CSV ze složky“. Ručně jde CSV nahrát i přes formulář v adminu.
2. Otevři `/projektor` na plátně — ukazuje QR, hráči zakládají týmy.
3. V adminu klikáním sestav frontu sad a spusť kvíz.
4. U každé otázky: **Otevřít odpovědi** → hráči odpovídají (mohou měnit) →
   **Zavřít odpovědi** spustí odpočet (výchozí 5 s, nastavitelný) → po
   odpočtu se odpovědi zamknou a automaticky vyhodnotí → volitelně
   **Ukázat správnou odpověď** → **Další otázka**.
5. V tabulce „Odpovědi týmů“ můžeš kdykoli po zamčení ručně **uznat/neuznat**
   jakoukoli odpověď — body se přepočítají.
6. Po poslední otázce sady se ukáže pořadí sady, pak celkové pořadí večera
   (se šipkami změn pozic) a volitelně **rekapitulace** otázek se správnými
   odpověďmi.
7. Další sada… a na konci konečné pořadí.

## Formát CSV sady otázek

**Jeden CSV soubor = jedna sada**, název sady = jméno souboru. Kódování
**UTF-8** (v Excelu „Uložit jako → CSV UTF-8“), oddělovač **čárka nebo
středník** (pozná se automaticky). Pořadí otázek = pořadí řádků. Ukázky jsou
ve složce [sady_ukazky/](sady_ukazky/) — CSV z této složky se importují
automaticky při startu (už naimportované se přeskočí; chceš-li sadu po úpravě
souboru obnovit, smaž ji v adminu a klikni „Načíst CSV ze složky“).

### Sloupce

| sloupec | povinné | význam |
|---|---|---|
| `typ` | ✔ | `abcd` / `pravdanepravda` / `text` / `cislo` |
| `otazka` | ✔ | text otázky |
| `spravna` | ✔ | správná odpověď — viz níže podle typu |
| `obrazek` | – | název souboru obrázku ve složce `media/` (nahrává se přes admin) |
| `moznost_a`–`moznost_d` | u `abcd` | texty možností A–D |
| `alt_odpovedi` | – | jen `text`: další uznávané odpovědi oddělené `\|` |
| `tolerance` | – | jen `cislo`: absolutní tolerance ± (prázdné = musí trefit přesně) |
| `body` | – | body za otázku, výchozí 1 |

### Hodnota `spravna` podle typu

- `abcd` → písmeno `A`/`B`/`C`/`D`
- `pravdanepravda` → `pravda` nebo `nepravda`
- `text` → správný řetězec (porovnává se bez ohledu na velikost písmen,
  mezery a diakritiku — „muž“ = „MUZ“)
- `cislo` → číslo (desetinná čárka i tečka fungují)

### Bodování

- Správná odpověď = počet bodů ze sloupce `body` (výchozí 1).
- `cislo`: bod dostane každý tým v pásmu `hodnota ± tolerance`; tým s
  **nejmenší absolutní odchylkou** dostane navíc **+1 bonusový bod**
  (při shodě všichni nejbližší).
- Remízy v pořadí: týmy se stejným součtem sdílí umístění.
- Admin může každou odpověď ručně uznat/neuznat — přepíše automatiku
  a body se přepočítají.

### Ukázka (středníkový formát z českého Excelu)

```csv
typ;otazka;obrazek;moznost_a;moznost_b;moznost_c;moznost_d;spravna;alt_odpovedi;tolerance;body
abcd;Hlavní město Austrálie?;;Sydney;Melbourne;Canberra;Perth;C;;;
text;Nejvyšší hora ČR?;;;;;;Sněžka;Snezka;;
cislo;Kolik km měří Vltava?;;;;;;430;;30;
pravdanepravda;Banán je bobule.;;;;;;pravda;;;
```

## Konfigurace

Zkopíruj `.env.example` na `.env` a nastav:

- `ADMIN_PASSWORD` — heslo do admin panelu
- `SECRET_KEY` — náhodný řetězec pro session
- `PUBLIC_URL` — veřejná adresa aplikace (obsah QR kódu!)
- `POLL_INTERVAL_MS` — interval pollingu (výchozí 2000)
- `DEFAULT_COUNTDOWN_S` — výchozí odpočet (výchozí 5)

## Nasazení na PythonAnywhere

Krok za krokem v **[DEPLOY.md](DEPLOY.md)**.

## Struktura projektu

```
app.py                 vstupní bod (lokálně i pro WSGI)
pubquiz/               aplikace: config, db, herní engine, CSV import, views
templates/             Jinja2 šablony (hráč, projektor, admin)
static/                CSS + vanilla JS (žádný build step)
media/                 obrázky otázek
sady_ukazky/           ukázková CSV pro každý typ otázky + smíšená sada
tests/test_smoke.py    integrační test celého herního toku
```
