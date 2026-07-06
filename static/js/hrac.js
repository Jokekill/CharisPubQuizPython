/* Hráčský klient: polling stavu + odesílání odpovědí.
   Identita týmu = token v localStorage, přežije reload i pád prohlížeče. */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  let token = localStorage.getItem("pubquiz_token") || "";
  let pollMs = 2000;
  let lastVersion = -1;
  let lastState = null;
  let pendingAnswer = null;   // lokálně vybraná odpověď čekající na potvrzení
  let currentQid = null;      // id právě zobrazené otázky (reset výběru při změně)
  let countdownTimer = null;

  // ---------- pomocné ----------

  function api(path, opts = {}) {
    opts.headers = Object.assign(
      { "Content-Type": "application/json", "X-Team-Token": token },
      opts.headers || {}
    );
    return fetch(path, opts).then((r) => r.json().then((j) => ({ ok: r.ok, data: j })));
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  // ---------- založení týmu ----------

  $("join-btn").addEventListener("click", join);
  $("team-name").addEventListener("keydown", (e) => { if (e.key === "Enter") join(); });

  function join() {
    const name = $("team-name").value.trim();
    if (!name) return;
    api("/api/join", { method: "POST", body: JSON.stringify({ name }) }).then(({ ok, data }) => {
      if (!ok) {
        $("join-error").textContent = data.error || "Chyba.";
        $("join-error").classList.remove("hidden");
        return;
      }
      token = data.token;
      localStorage.setItem("pubquiz_token", token);
      lastVersion = -1;
      poll();
    });
  }

  // ---------- polling ----------

  function poll() {
    api("/api/hrac")
      .then(({ data }) => {
        $("conn-error").classList.add("hidden");
        pollMs = data.poll_interval_ms || 2000;
        render(data);
      })
      .catch(() => $("conn-error").classList.remove("hidden"))
      .finally(() => setTimeout(poll, pollMs));
  }

  // ---------- vykreslení ----------

  function render(s) {
    if (!s.team) {
      // token neplatný / tým smazán → zpět na join
      $("join-screen").classList.remove("hidden");
      $("game-screen").classList.add("hidden");
      return;
    }
    $("join-screen").classList.add("hidden");
    $("game-screen").classList.remove("hidden");
    $("my-team").textContent = "Tým: " + s.team.name;
    renderPill(s);

    // Nová otázka → zahodit lokálně vybranou odpověď z té minulé
    const qid = s.question ? s.question.id : null;
    if (qid !== currentQid) {
      currentQid = qid;
      pendingAnswer = null;
      lastState = null;
    }

    // Překreslujeme jen při změně stavu (aby nezmizel rozepsaný text)
    const key = s.version + "|" + (pendingAnswer || "");
    if (lastState === key) return;
    lastState = key;

    const c = $("content");
    if (s.phase === "lobby") {
      c.innerHTML = `<h2>Jste ve hře! 🎉</h2>
        <p class="muted">Čekáme na start kvízu. Sledujte projektor.</p>`;
    } else if (s.phase === "question" && s.question) {
      renderQuestion(c, s);
    } else if (s.phase === "results_set") {
      c.innerHTML = `<h2>Konec sady</h2><p class="muted">Pořadí je na projektoru.</p>`
        + standings(s.standings_set);
    } else if (s.phase === "results_total" || s.phase === "finished") {
      c.innerHTML = `<h2>${s.phase === "finished" ? "Konečné pořadí 🏆" : "Průběžné pořadí"}</h2>`
        + standings(s.standings_total);
    } else if (s.phase === "review" && s.question) {
      c.innerHTML = `<h2>Otázka ${esc(s.question_number)}</h2>
        <p>${esc(s.question.otazka)}</p>
        <p class="ok"><strong>Správně: ${esc(s.correct_answer)}</strong></p>`;
    } else {
      c.innerHTML = `<p class="muted">Čekejte…</p>`;
    }
  }

  function renderPill(s) {
    const pill = $("status-pill");
    pill.className = "status-pill";
    if (s.phase !== "question") { pill.textContent = ""; pill.classList.add("hidden"); return; }
    pill.classList.remove("hidden");
    if (s.q_state === "open") { pill.textContent = "Odpovědi otevřené"; pill.classList.add("open"); }
    else if (s.q_state === "countdown") { startPillCountdown(s); }
    else if (s.q_state === "shown") { pill.textContent = "Čekejte na otevření"; }
    else { pill.textContent = "Zamčeno"; pill.classList.add("locked"); }
  }

  function startPillCountdown(s) {
    clearInterval(countdownTimer);
    let remaining = Math.ceil(s.countdown_remaining ?? 0);
    const pill = $("status-pill");
    pill.classList.add("countdown");
    const tick = () => {
      pill.textContent = remaining > 0 ? `Zamyká se za ${remaining} s` : "Zamčeno";
      remaining--;
      if (remaining < -1) clearInterval(countdownTimer);
    };
    tick();
    countdownTimer = setInterval(tick, 1000);
  }

  function renderQuestion(c, s) {
    const q = s.question;
    const open = s.answers_open;
    const my = pendingAnswer !== null ? pendingAnswer : (s.my_answer ?? null);
    let html = `<p class="muted">Otázka ${esc(s.question_number)}/${esc(s.question_count)}`
      + (q.body > 1 ? ` · za ${esc(q.body)} b.` : "") + `</p>
      <h2 style="font-size:1.3rem">${esc(q.otazka)}</h2>`;
    if (q.obrazek) html += `<img class="question-image" src="/media/${encodeURIComponent(q.obrazek)}" alt="" onerror="this.remove()">`;

    if (s.q_state === "shown") {
      html += `<p class="muted">Odpovědi se brzy otevřou…</p>`;
    } else if (q.typ === "abcd") {
      html += `<div class="answer-grid">` + ["A", "B", "C", "D"].map((L) =>
        `<button class="answer-btn ${my === L ? "selected" : ""}" data-val="${L}" ${open ? "" : "disabled"}>
           <span class="letter">${L}</span> ${esc(q.moznosti[L])}</button>`).join("") + `</div>`;
    } else if (q.typ === "pravdanepravda") {
      html += `<div class="answer-grid">` + [["pravda", "✔ Pravda"], ["nepravda", "✘ Nepravda"]].map(([v, t]) =>
        `<button class="answer-btn ${my === v ? "selected" : ""}" data-val="${v}" ${open ? "" : "disabled"}>${t}</button>`).join("") + `</div>`;
    } else {
      const inputType = q.typ === "cislo" ? `inputmode="decimal"` : "";
      html += `<div class="answer-grid">
        <input type="text" id="free-answer" ${inputType} placeholder="${q.typ === "cislo" ? "Váš odhad (číslo)" : "Vaše odpověď"}"
               value="${esc(my ?? "")}" ${open ? "" : "disabled"} autocomplete="off">
        <button id="send-answer" ${open ? "" : "disabled"}>Odeslat odpověď</button>
      </div>`;
    }

    if (my !== null && s.q_state !== "shown") {
      html += `<p class="muted" style="margin-top:14px">Vaše odpověď: <strong class="accent">${esc(my)}</strong>`
        + (open ? " — můžete ji změnit." : "") + `</p>`;
    }
    if (s.my_result) {
      html += s.my_result.spravne
        ? `<p class="ok"><strong>✔ Správně! +${s.my_result.body} b.</strong></p>`
        : `<p class="bad"><strong>✘ Bohužel špatně.</strong></p>`;
    }
    if (s.correct_answer) html += `<p class="ok">Správná odpověď: <strong>${esc(s.correct_answer)}</strong></p>`;

    c.innerHTML = html;
    c.classList.add("fade");

    c.querySelectorAll(".answer-btn").forEach((b) =>
      b.addEventListener("click", () => sendAnswer(b.dataset.val)));
    const send = $("send-answer");
    if (send) {
      send.addEventListener("click", () => {
        const v = $("free-answer").value.trim();
        if (v) sendAnswer(v);
      });
      $("free-answer").addEventListener("keydown", (e) => { if (e.key === "Enter") send.click(); });
    }
  }

  function sendAnswer(val) {
    pendingAnswer = val;
    lastState = null; // vynutit překreslení s vybranou odpovědí
    api("/api/odpoved", { method: "POST", body: JSON.stringify({ odpoved: val }) })
      .then(({ ok, data }) => {
        if (!ok) { pendingAnswer = null; }
      });
  }

  function standings(rows) {
    if (!rows || !rows.length) return "<p class='muted'>Zatím žádné body.</p>";
    return `<table class="standings"><tr><th>#</th><th>Tým</th><th style="text-align:right">Body</th></tr>`
      + rows.map((r) => `<tr><td class="rank">${r.rank}.</td><td>${esc(r.name)}</td><td class="pts">${r.points}</td></tr>`).join("")
      + `</table>`;
  }

  poll();
})();
