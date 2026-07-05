# Prompt pro Fable 5 — Webová aplikace pro vedení pubkvízu

> Zkopíruj celý tento text do Fable 5 jako zadání. Je psaný česky, aplikace i UI mají být v češtině.

---

## 1) Kontext a cíl

Naprogramuj mi **webovou aplikaci v Pythonu (Flask) pro vedení pubkvízu**, kterou budu hostovat na **pythonanywhere.com**. Aplikace má dvě hlavní role:

- **Admin / projektor** — ovládám kvíz, otázky se promítají na projektor.
- **Hráč / tým** — účastníci na svých telefonech odpovídají na otázky.

Aplikace načítá sady otázek z CSV, řídí průběh hry, počítá body, drží pořadí a po každé sadě umožní projet otázky se správnými odpověďmi.

**Klíčový požadavek na tebe:** rozplánuj práci do jasných **vývojových fází** a veď si soubor `PROGRESS.md`, kam po každé dokončené fázi zapíšeš stav. Kdyby došly kredity, musíš z `PROGRESS.md` a kódu jednoznačně poznat, kde navázat. Na konci každé fáze mi napiš krátké shrnutí, co je hotové a co je na řadě.

---

## 2) Technická omezení a stack (důležité pro PythonAnywhere)

Dodrž prosím tato omezení — plynou z toho, jak PythonAnywhere funguje:

- **NEPOUŽÍVEJ WebSockets ani Flask-SocketIO.** Standardní WSGI web app na PythonAnywhere je spolehlivě nepodporuje (existuje jen experimentální beta, kterou nechci). Živou synchronizaci (nová otázka na telefonech, živé pořadí) řeš přes **AJAX short-polling**: klienti se každé ~2 s doptávají serveru na aktuální stav.
- **Interval pollingu udělej konfigurovatelný** (výchozí 2 s).
- **Stav hry je autoritativní na serveru a ukládá se do databáze**, aby přežil reload aplikace i obnovení stránky na telefonu. Když se hráči obnoví/spadne telefon, musí se po znovunačtení vrátit do svého týmu a do aktuálního stavu hry.
- **Databáze: SQLite** (nejjednodušší, žádná konfigurace, pro ~15 týmů bohatě stačí). Ulož soubor DB do domovské složky projektu.
- **Bez build stepu na frontendu** (na PythonAnywhere není Node build). Použij **Jinja2 šablony + čisté (vanilla) JavaScripty**. Pokud chceš CSS framework, použij **Tailwind přes CDN** (načítá ho prohlížeč hráče, to je v pořádku) nebo prosté CSS. Žádný webpack/vite.
- **QR kód generuj na serveru** knihovnou `qrcode` + `Pillow` (žádné externí API — kvůli free-tier whitelistu). 
- **Obrázky otázek** ukládej do lokální `media/` složky a servíruj jako statické soubory.
- Používej jen běžné knihovny instalovatelné přes pip (Flask, qrcode, Pillow, případně `python-dotenv`). Vyhni se závislostem, které vyžadují kompilaci nebo systémové balíčky.

---

## 3) Uživatelské role a obrazovky

Chci **oddělené URL/obrazovky**:

1. **Projektorový pohled** (`/projektor`) — veřejný, fullscreen, jen zobrazuje. Na úvod ukazuje **QR kód + odkaz** pro připojení hráčů a seznam už připojených týmů. Během hry zobrazuje aktuální otázku (a případně obrázek), odpočet, po zavření otázky správnou odpověď, a mezi sadami pořadí.
2. **Admin ovládací panel** (`/admin`) — **chráněný jednoduchým heslem** (stačí jedno heslo v konfiguraci, přihlášení přes session). Odsud dělám úplně všechno: import CSV sad, výběr sad a jejich pořadí, spuštění kvízu, posun mezi otázkami, otevření/zavření odpovědí, spuštění odpočtu, ruční uznání/přepsání odpovědí, správa týmů, přepnutí do review módu.
3. **Hráčský pohled** (`/`, `/hrat` apod.) — **mobile-first**, hráči skoro výhradně na telefonech. Připojení přes QR → založení a pojmenování týmu → odpovídání na otázky.

Admin ovládání a projektor jsou **dvě samostatné obrazovky/URL** (typicky mám projektor na plátně a ovládání na svém notebooku).

---

## 4) Typy otázek

Podporuj tyto typy (typ je uvedený v CSV):

- **`abcd`** — čtyři možnosti A–D, právě jedna správná.
- **`pravdanepravda`** — pravda / nepravda.
- **`text`** — odpověď slovem nebo větou.
- **`cislo`** — číselný odhad.

Každá otázka může mít **obrázek** (např. „Vlajka které země to je?"). Obrázky chci podporovat od začátku.

---

## 5) Bodování (dodrž přesně)

- **ABCD, pravda/nepravda, text:** 1 bod za správnou odpověď.
- **Text — vyhodnocení:** automaticky porovnávej **case-insensitive**, s **ořezem mezer** a **tolerancí diakritiky** (např. „muz" = „muž"). Umožni v CSV zadat i alternativní správné odpovědi. Navíc musí mít **admin u každé textové (i jiné) otázky možnost ručně uznat/neuznat odpověď** a tím přepsat automatické rozhodnutí — přepočítej pak body.
- **Číslo — vyhodnocení (přesné pravidlo):**
  - U každé `cislo` otázky je v CSV **správná hodnota** a **tolerance** (absolutní odchylka, ±).
  - Každý tým, jehož odpověď je **uvnitř pásma** `[hodnota − tolerance, hodnota + tolerance]`, dostane **1 bod**.
  - Tým s **nejmenším absolutním rozdílem** od správné hodnoty dostane navíc **+1 bonusový bod**.
  - Pokud je **více týmů shodně nejblíž**, dostanou bonus **všichni** tito tými.
  - I zde má admin možnost výsledek ručně upravit.
- **Body za otázku** ať jdou volitelně přepsat v CSV (výchozí 1), pro případ obtížnějších otázek.
- **Pořadí:** celkové pořadí = součet bodů. **Remízu řeš jednoduše** — týmy se stejným počtem bodů sdílí umístění.

---

## 6) Herní tok (krok za krokem)

1. Admin **naimportuje sady otázek** (CSV, jedna sada = jeden CSV).
2. Hráči se přes QR **připojí a založí si týmy** (viz sekce 8). Admin je vidí přibývat na projektoru.
3. Admin **spustí kvíz** a **vybere, které sady** se použijí a **v jakém pořadí** (typicky 6 sad po 10 otázkách).
4. Admin **posouvá otázky jednu po druhé**. U každé otázky:
   - Otázka (+ obrázek) se objeví na projektoru i na telefonech hráčů.
   - Admin **otevře odpovědi**; hráči odpovídají a **mohou odpověď měnit, dokud není zamčeno**.
   - Admin **zavře odpovědi**, čímž spustí **odpočet** (výchozí **5 s**, ale **čas musí jít nastavit**). Po odpočtu se odpovědi definitivně zamknou.
   - Aplikace vyhodnotí a **sečte správné odpovědi**, drží průběžné pořadí.
   - Volitelně po zamčení ukáž na projektoru správnou odpověď.
5. Po **poslední otázce sady** ukaž:
   - jak týmy dopadly **v této sadě**, a
   - jak tato sada **ovlivnila celkové pořadí celého večera** (průběžné pořadí přes všechny sady).
6. Admin může **projet sadu ještě jednou v review módu** (viz sekce 9).
7. Pokračuje se další sadou.

Celý stav (která sada, která otázka, otevřeno/zavřeno, odpočet, odpovědi, body) je uložený v DB a autoritativní na serveru.

---

## 7) CSV formát sad otázek (dobře zdokumentuj!)

Jeden **CSV soubor = jedna sada otázek**. Vytvoř jasnou dokumentaci formátu (v README) a **ukázková CSV**.

Požadavky na parser:
- Kódování **UTF-8**.
- Podporuj **oddělovač čárku `,` i středník `;`** (autodetekce) — český Excel běžně ukládá se středníkem.
- Ignoruj prázdné řádky, ořízni mezery.
- Při importu **validuj** a srozumitelně nahlas chyby (chybějící sloupec, neznámý typ, chybějící správná odpověď u ABCD apod.).

Navržené sloupce (uprav, pokud najdeš lepší, ale zdokumentuj to):

| sloupec | význam |
|---|---|
| `typ` | `abcd` / `pravdanepravda` / `text` / `cislo` |
| `otazka` | text otázky |
| `obrazek` | (volitelné) název souboru obrázku v `media/`, jinak prázdné |
| `moznost_a`..`moznost_d` | možnosti pro `abcd` (jinak prázdné) |
| `spravna` | správná odpověď: `abcd` → `A/B/C/D`; `pravdanepravda` → `pravda`/`nepravda`; `text` → správný řetězec; `cislo` → číslo |
| `alt_odpovedi` | (volitelné, jen `text`) další uznávané odpovědi oddělené `\|` |
| `tolerance` | (jen `cislo`) absolutní tolerance ±; když prázdné, použij rozumný default |
| `body` | (volitelné) počet bodů za otázku, default 1 |

Pořadí otázek v sadě = pořadí řádků v CSV.

**Obrázky:** admin je nahrává přes admin panel do `media/` složky; v CSV se odkazují názvem souboru. Ošetři, že obrázek chybí (nespadni, jen ho nezobraz / upozorni admina).

Pokud si myslíš, že je pro tento účel vhodnější jiný formát než CSV (např. jednoduchý JSON), **navrhni ho v `PROGRESS.md`, ale ve výchozím stavu implementuj CSV** dle výše — musí to být dobře zdokumentované a snadno editovatelné v Excelu.

---

## 8) Připojení týmů + QR kód

- **Projektorová úvodní stránka** ukazuje **QR kód** (a i textový odkaz) směřující na hráčskou join stránku.
- Hráč naskenuje → otevře se **mobile-first** stránka → **založí tým a pojmenuje ho**.
- **Jedno zařízení = jeden tým** (odpovídá kapitán). Identitu týmu drž v prohlížeči (cookie/localStorage) + na serveru, aby po obnovení telefonu tým nezmizel a hráč se vrátil do své hry.
- **Admin vidí seznam připojených týmů** a může je **jednoduše spravovat** — přejmenovat a odstranit (např. duplicitní/testovací tým).
- Počítej s **cca 15 týmy**.
- QR kód musí obsahovat **veřejnou URL** aplikace (na PythonAnywhere `https://<uzivatel>.pythonanywhere.com` nebo `.eu.` varianta) — udělej to konfigurovatelné, ať QR ukazuje na správnou adresu po nasazení.

---

## 9) Výsledky a review mód

- **Po každé sadě:** na projektoru zobraz pořadí **v rámci sady** a následně **aktualizované celkové pořadí večera** (a ideálně naznač změnu pozice oproti stavu před sadou).
- **Review mód:** admin může sadu **projít znovu otázku po otázce**, na projektoru se u každé otázky ukáže **správná odpověď** (a případně jak týmy odpovídaly). Slouží k moderování „a správně bylo…".

---

## 10) Design

- **Moderní, minimalistický, tmavý (dark mode).** V pubu bývá šero — tmavé pozadí sedí projektoru i telefonům.
- Jedna **výrazná akcentní barva**, jinak střídmost, dobrá čitelnost na dálku (projektor) i na malém displeji (telefon).
- **Hráčská část důsledně mobile-first** — velká tlačítka pro ABCD/pravda-nepravda, pohodlné pole pro text a číslo, palcem ovladatelné.
- **Projektor** čitelný z dálky (velké písmo, vysoký kontrast, fullscreen).
- Jemné přechody mezi stavy (otázka → odpočet → zamčeno → správná odpověď).
- Vše česky.

---

## 11) Vývojové fáze (rozplánuj a veď `PROGRESS.md`)

Postupuj po fázích. Po **každé** fázi aktualizuj `PROGRESS.md` (co hotovo, co dál, jak spustit) a napiš mi shrnutí. Každá fáze má být sama o sobě spustitelná/otestovatelná.

- **Fáze 0 — Skeleton & architektura:** struktura projektu, Flask app, konfigurace (admin heslo, interval pollingu, default odpočtu, veřejná URL), SQLite datový model (týmy, sady, otázky, odpovědi, stav hry), inicializace DB, `PROGRESS.md`, běh lokálně.
- **Fáze 1 — Import a model otázek:** definice + dokumentace CSV formátu, admin nahrání CSV sady, parser s validací a autodetekcí oddělovače, nahrávání obrázků do `media/`, ukázková CSV (pro každý typ otázky + jedna smíšená sada) a pár ukázkových obrázků.
- **Fáze 2 — Připojení týmů & QR:** projektorová úvodní stránka s QR, hráčská join stránka (založení a pojmenování týmu), persistence týmu v prohlížeči + serveru, admin seznam týmů se správou (přejmenovat/smazat).
- **Fáze 3 — Herní engine & admin ovládání:** výběr sad a pořadí, spuštění kvízu, posun mezi otázkami, otevření/zavření odpovědí, konfigurovatelný odpočet, autoritativní stav v DB, polling endpointy pro hráče i projektor.
- **Fáze 4 — Odpovídání & bodování:** hráčské UI podle typu otázky, změna odpovědi před zamčením, bodovací logika všech typů včetně číselné tolerance + bonusu, průběžné počítání a pořadí, **ruční uznání/přepis správnosti adminem** s přepočtem bodů.
- **Fáze 5 — Výsledky & review:** pořadí po sadě + dopad na celkové pořadí večera, review mód se správnými odpověďmi.
- **Fáze 6 — Design & doladění:** tmavý minimalistický vzhled, mobile-first hráč, fullscreen projektor, přechody, čeština, ošetření okrajových stavů (výpadek telefonu, reload, chybějící obrázek, neočekávaný vstup).
- **Fáze 7 — Nasazení:** návod na PythonAnywhere (viz sekce 12) + lokální README.

---

## 12) Nasazení na PythonAnywhere — co po tobě chci

Vytvoř **krok-za-krokem návod** (v `README.md` nebo `DEPLOY.md`), který mě jako méně zkušeného uživatele provede nasazením. Zohledni tato fakta o PythonAnywhere:

- Jde o **WSGI hosting** (bez WebSockets — proto polling).
- **Statické soubory** (CSS/JS/obrázky z `media/`) se mapují v záložce *Web* (Static files) — v návodu ukaž konkrétní mapování.
- Adresa webu je `https://<uzivatel>.pythonanywhere.com` (US) nebo `https://<uzivatel>.eu.pythonanywhere.com` (EU) — vysvětli, jak podle toho nastavit veřejnou URL pro QR kód.
- Postup má obsahovat: nahrání kódu (git clone nebo upload), vytvoření **virtualenv** a instalaci závislostí (`requirements.txt`), nastavení **WSGI konfiguračního souboru**, **inicializaci SQLite DB**, nastavení **admin hesla** a **veřejné URL** v konfiguraci, mapování statiky, a **reload web app**.
- Přidej poznámku k **volbě tarifu:** free tarif stačí na testování, ale při ~15 týmech + projektor, co pollingem každé 2 s dotazují server, může být jeden slabší worker a CPU limit free tarifu úzké hrdlo; pro ostrou akci doporuč **placený tarif Hacker (~$5/měs.)** kvůli výkonu. Napiš to tak, ať vím, kdy free stačí a kdy raději upgradovat.
- Přidej i **rychlý lokální běh** (jak spustit na svém počítači pro přípravu otázek a testování).

---

## 13) Co chci na výstupu

- Funkční Flask aplikaci dle výše, spustitelnou lokálně i nasaditelnou na PythonAnywhere.
- `requirements.txt`.
- `README.md` s: popisem, lokálním během, **dokumentací CSV formátu**, a odkazem na deploy návod.
- `DEPLOY.md` (nebo sekci v README) — návod na PythonAnywhere.
- **Ukázková CSV** (každý typ otázky + jedna smíšená 10otázková sada) a pár ukázkových obrázků.
- `PROGRESS.md` s aktuálním stavem fází.

Piš přehledný, komentovaný kód. Kde volíš nějaké řešení (formát, knihovna, edge case), krátce to zdůvodni v `PROGRESS.md`. Postupuj po fázích a po každé mi dej vědět, kde jsme.
