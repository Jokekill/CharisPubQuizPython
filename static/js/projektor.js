/* Projektorový klient: jen zobrazuje stav hry, polluje server. */
(function () {
  "use strict";

  const content = document.getElementById("proj-content");
  const headSet = document.getElementById("proj-set");
  const headProgress = document.getElementById("proj-progress");
  let pollMs = 2000;
  let lastKey = null;
  let countdownTimer = null;

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function poll() {
    fetch("/api/projektor")
      .then((r) => r.json())
      .then((s) => { pollMs = s.poll_interval_ms || 2000; render(s); })
      .catch(() => {})
      .finally(() => setTimeout(poll, pollMs));
  }

  function render(s) {
    headSet.textContent = s.set_name ? `${esc0(s.set_name)} (${s.set_number}/${s.set_count})` : "";
    headProgress.textContent =
      (s.phase === "question" || s.phase === "review") && s.question_number
        ? `Otázka ${s.question_number}/${s.question_count}` : "";

    const key = s.version + "|" + (s.phase === "question" ? s.q_state : "");
    if (key === lastKey) return;
    lastKey = key;
    clearInterval(countdownTimer);

    let html = "";
    if (s.phase === "lobby") {
      html = `<h1 style="font-size:clamp(2.5rem,6vw,5rem)">🧩 Pubkvíz</h1>
        <p class="proj-status" style="margin:0 0 2vh">Konference Charis</p>
        <p class="proj-url">${esc(s.public_url)}</p>
        <img class="proj-qr" src="/qr.png" alt="QR kód pro připojení">
        <p class="proj-status">Naskenujte QR a založte tým</p>
        <div class="proj-teams">${(s.teams || []).map((t) => `<span>${esc(t)}</span>`).join("")}</div>`;
    } else if (s.phase === "question" && s.question) {
      html = questionHtml(s);
    } else if (s.phase === "results_set") {
      html = `<h1 style="font-size:clamp(2rem,5vw,4rem)">Výsledky sady${s.set_name ? ": " + esc(s.set_name) : ""}</h1>`
        + standings(s.standings_set);
    } else if (s.phase === "results_total" || s.phase === "finished") {
      html = `<h1 style="font-size:clamp(2rem,5vw,4rem)">${s.phase === "finished" ? "🏆 Konečné pořadí" : "Průběžné pořadí večera"}</h1>`
        + standings(s.standings_total, true);
    } else if (s.phase === "review" && s.question) {
      html = reviewHtml(s);
    }
    content.innerHTML = `<div class="fade" style="display:flex;flex-direction:column;align-items:center">${html}</div>`;

    if (s.phase === "question" && s.q_state === "countdown") startCountdown(s.countdown_remaining);
  }

  function esc0(x) { return String(x).replace(/[<>&]/g, ""); }

  function questionHtml(s) {
    const q = s.question;
    let html = `<div class="proj-question">${esc(q.otazka)}</div>`;
    if (q.obrazek) html += `<img class="proj-image" src="/media/${encodeURIComponent(q.obrazek)}" alt="" onerror="this.remove()">`;
    if (q.typ === "abcd") {
      html += `<div class="proj-options">` + ["A", "B", "C", "D"].map((L) =>
        `<div><span class="letter">${L})</span>${esc(q.moznosti[L])}</div>`).join("") + `</div>`;
    }
    if (s.q_state === "shown") html += `<p class="proj-status">Připravte se…</p>`;
    if (s.q_state === "open") html += `<p class="proj-status ok" style="color:var(--ok)">Odpovídejte na telefonech!</p>`;
    if (s.q_state === "countdown") html += `<div class="proj-countdown" id="proj-cd"></div>`;
    if (s.q_state === "locked") html += `<p class="proj-status">🔒 Odpovědi zamčeny</p>`;
    if (s.q_state === "revealed" && s.correct_answer)
      html += `<div class="proj-answer">✔ ${esc(s.correct_answer)}</div>`;
    return html;
  }

  function reviewHtml(s) {
    const q = s.question;
    let html = `<p class="proj-status" style="margin:0 0 2vh">📋 Rekapitulace</p>
      <div class="proj-question" style="font-size:clamp(1.6rem,4vw,3rem)">${esc(q.otazka)}</div>`;
    if (q.obrazek) html += `<img class="proj-image" style="max-height:30vh" src="/media/${encodeURIComponent(q.obrazek)}" alt="" onerror="this.remove()">`;
    html += `<div class="proj-answer">✔ ${esc(s.correct_answer)}</div>`;
    const correct = (s.review_answers || []).filter((a) => a.spravne).map((a) => a.team);
    if (correct.length)
      html += `<p class="proj-status">Správně: ${correct.map(esc).join(", ")}</p>`;
    else if ((s.review_answers || []).length)
      html += `<p class="proj-status">Správně neměl nikdo 😅</p>`;
    return html;
  }

  function startCountdown(remaining) {
    let r = Math.ceil(remaining ?? 0);
    const el = () => document.getElementById("proj-cd");
    const tick = () => {
      const e = el();
      if (!e) return clearInterval(countdownTimer);
      e.textContent = r > 0 ? r : "🔒";
      r--;
      if (r < -1) clearInterval(countdownTimer);
    };
    tick();
    countdownTimer = setInterval(tick, 1000);
  }

  function standings(rows, withChange = false) {
    if (!rows || !rows.length) return "<p class='proj-status'>Žádné výsledky.</p>";
    return `<table class="standings proj-standings">
      <tr><th>#</th><th>Tým</th>${withChange ? "<th></th>" : ""}<th style="text-align:right">Body</th></tr>`
      + rows.map((r) => {
        let ch = "";
        if (withChange && r.change > 0) ch = `<td class="change-up">▲ ${r.change}</td>`;
        else if (withChange && r.change < 0) ch = `<td class="change-down">▼ ${-r.change}</td>`;
        else if (withChange) ch = `<td></td>`;
        return `<tr><td class="rank">${r.rank}.</td><td>${esc(r.name)}</td>${ch}<td class="pts">${r.points}</td></tr>`;
      }).join("") + `</table>`;
  }

  poll();
})();
