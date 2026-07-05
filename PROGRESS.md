# PROGRESS — stav vývoje pubkvízu

Poslední aktualizace: 2026-07-05. **Všechny fáze 0–7 jsou hotové**, aplikace
je funkční lokálně a připravená k nasazení na PythonAnywhere.

## Po fázích doplněno

- **Modrý vzhled dle konferencecharis.cz** — akcent = brandová modrá Charis
  `#0096d6` (z jejich theme.css), tmavé pozadí `#0b0f19`, světlejší modrá
  `--accent-soft #4cc3f0` pro texty na tmavém podkladu. Vše v
  `static/css/style.css` přes CSS proměnné.
- **Špeková sada vlajek** `sady_ukazky/vlajky_spek.csv` (10× abcd s obrázky):
  záměrně zaměnitelné dvojice — Čad×Rumunsko, Monako×Indonésie/Polsko,
  Lucembursko×Nizozemsko, Pobřeží slonoviny×Irsko, Slovinsko×Slovensko,
  Nový Zéland×Austrálie, Island×Norsko, Mali×Senegal, Katar×Bahrajn,
  Lichtenštejnsko×Haiti. Vlajky staženy z flagcdn.com do `media/` pod
  neutrálními názvy `vlajka01–10.png`, aby hráči nepoznali odpověď z URL
  obrázku. Otázky s obrázky ověřeny naživo (telefon i projektor).

## Stav fází

| Fáze | Obsah | Stav |
|---|---|---|
| 0 | Skeleton, Flask factory, konfigurace, SQLite schéma | ✅ hotovo |
| 1 | CSV import s validací + autodetekcí oddělovače, upload obrázků, ukázková CSV | ✅ hotovo |
| 2 | QR + lobby na projektoru, join stránka, persistence týmu, správa týmů | ✅ hotovo |
| 3 | Herní engine (fronta sad, posun otázek, otevřít/zavřít, odpočet), polling API | ✅ hotovo |
| 4 | Hráčské UI všech typů otázek, bodování vč. číselného bonusu, ruční override | ✅ hotovo |
| 5 | Výsledky sady, celkové pořadí se změnami pozic, review mód | ✅ hotovo |
| 6 | Tmavý design, mobile-first hráč, fullscreen projektor, edge cases | ✅ hotovo |
| 7 | README (vč. dokumentace CSV), DEPLOY.md pro PythonAnywhere | ✅ hotovo |

## Jak spustit

```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python app.py                      # http://127.0.0.1:5000, admin heslo: kviz123
.venv\Scripts\python tests\test_smoke.py   # integrační test celého toku
```

## Architektura (kde co je)

- `app.py` — vstupní bod (lokální běh i WSGI import).
- `pubquiz/config.py` — konfigurace z env/.env (heslo, PUBLIC_URL, polling, odpočet).
- `pubquiz/db.py` — SQLite schéma (teams, question_sets, questions, answers,
  game_state) + spojení per-request. Stav hry = jediný řádek `game_state`
  s čítačem `version`.
- `pubquiz/game.py` — stavový automat (fáze lobby → question → results_set →
  results_total → review → další sada → finished; podstavy otázky shown →
  open → countdown → locked → revealed), vyhodnocování, bodování, pořadí.
- `pubquiz/csv_import.py` — parser CSV (UTF-8 s/bez BOM, `,` i `;`, validace
  s čísly řádků).
- `pubquiz/payloads.py` — sestavení JSON stavů pro polling.
- `pubquiz/views_player.py`, `views_projector.py`, `views_admin.py` — routy.
- `templates/` + `static/js/*.js` — Jinja2 + vanilla JS, každá obrazovka má
  svůj polling klient. `static/css/style.css` — tmavý theme, akcent jantarová.

## Klíčová rozhodnutí (a proč)

- **Odpočet bez plánovače:** na WSGI neběží nic na pozadí, takže konec
  odpočtu dokončí „líně“ první příchozí request (`game.tick()` na začátku
  každého API volání). Při pollingu à 2 s je zpoždění zámku max ~2 s, hráčům
  navíc odpočet tiká lokálně v JS.
- **Identita týmu = token v localStorage** (+ hlavička `X-Team-Token`).
  Cookie by fungovala taky, ale localStorage přežije i zavření prohlížeče
  a nemá problémy se SameSite.
- **Číselný bonus je nezávislý na toleranci:** +1 dostane nejbližší tým
  (remíza → všichni nejbližší), i kdyby byl mimo pásmo — bod za pásmo je
  zvlášť. Ruční override mění bod za správnost, bonus za nejbližší zůstává.
- **Prázdná `tolerance` = 0** (nutná přesná shoda) — zdokumentováno v README.
- **CSV ponecháno dle zadání.** JSON by byl robustnější na uvozovky/čárky,
  ale CSV je editovatelné v Excelu, což je hlavní use-case; parser řeší
  středníky, BOM i desetinné čárky, takže rizika Excelu jsou pokrytá.
- **Překreslování UI podle `version`:** klienti překreslí DOM jen při změně
  čítače verze, takže rozepsaná textová odpověď na telefonu nemizí.
- **Smazané týmy:** hráč se smazaným týmem dostane při pollingu `team: null`
  a vrátí se na join obrazovku (řeší duplicitní/testovací týmy).

## Ověřeno

- `tests/test_smoke.py` — celý herní tok přes Flask test client: import CSV
  (oba oddělovače + chybová hlášení), join + duplicitní název, QR endpoint,
  start hry, změna odpovědi před zamčením, odmítnutí po zamčení, bodování
  čísel (pásmo + bonus), override + přepočet + zrušení override, reveal,
  výsledky sady, celkové pořadí, review, konec hry, správa týmů, reset. PROŠEL.
- Vizuálně v prohlížeči: join stránka, hráčská otázka (mobil 375px), odpočet,
  vyhodnocení „✔ Správně!", projektor (lobby s QR i otázka se správnou
  odpovědí), admin panel (řízení hry, tabulka odpovědí, sady, týmy, pořadí).

## Co by šlo dodělat (nice-to-have, nic z toho neblokuje provoz)

- Export výsledků večera do CSV.
- Zvukový gong při zamčení otázky.
- Zobrazení rozložení odpovědí (kolik týmů dalo A/B/C/D) na projektoru v review.
- Možnost editovat otázky přímo v adminu (teď jen reimport CSV).
