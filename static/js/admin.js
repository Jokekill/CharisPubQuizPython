/* Admin klient: polling stavu + ovládací akce. */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  let pollMs = 2000;
  let lastVersion = -1;
  let queue = [];          // lokálně sestavovaná fronta sad před startem
  let state = null;

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function api(path, body) {
    return fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    }).then((r) => r.json().then((j) => ({ ok: r.ok, data: j })));
  }

  function msg(text, isError = false) {
    const m = $("admin-msg");
    m.textContent = text;
    m.style.borderColor = isError ? "var(--bad)" : "var(--accent)";
    m.classList.remove("hidden");
    clearTimeout(msg._t);
    msg._t = setTimeout(() => m.classList.add("hidden"), 4000);
  }

  function action(name, extra) {
    api("/admin/api/hra/akce", Object.assign({ action: name }, extra || {}))
      .then(({ ok, data }) => { if (!ok) msg(data.error || "Chyba.", true); refresh(); });
  }

  // ---------- polling ----------

  function poll() {
    fetch("/admin/api/stav")
      .then((r) => {
        if (r.status === 401) { location.href = "/admin/login"; throw new Error(); }
        return r.json();
      })
      .then((s) => {
        pollMs = s.poll_interval_ms || 2000;
        state = s;
        if (s.version !== lastVersion) { lastVersion = s.version; render(s); }
        renderPhasePill(s);
      })
      .catch(() => {})
      .finally(() => setTimeout(poll, pollMs));
  }

  function refresh() { lastVersion = -1; }

  // ---------- vykreslení ----------

  const PHASE_LABELS = {
    lobby: "Lobby — připojování týmů",
    question: "Hraje se otázka",
    results_set: "Výsledky sady",
    results_total: "Celkové pořadí",
    review: "Rekapitulace",
    finished: "Konec kvízu",
  };

  function renderPhasePill(s) {
    $("game-phase").textContent = PHASE_LABELS[s.phase] || s.phase;
  }

  function render(s) {
    renderGameControls(s);
    renderAnswers(s);
    renderSets(s);
    renderTeams(s);
    $("standings-box").innerHTML = standings(s.standings_total);
  }

  function renderGameControls(s) {
    const c = $("game-controls");
    let html = "";

    if (s.phase === "lobby") {
      html += `<p class="muted">Klikáním na sady vlevo dole sestav pořadí, pak spusť kvíz.</p>
        <p><strong>Fronta sad:</strong> <span id="queue-label">${queue.length
          ? queue.map((id, i) => `${i + 1}. ${esc(setName(s, id))}`).join(" → ")
          : "<span class='muted'>prázdná — klikni na „+“ u sady</span>"}</span>
          ${queue.length ? `<button class="small secondary" id="queue-clear">vyčistit</button>` : ""}</p>
        <button id="start-game" ${queue.length ? "" : "disabled"}>▶ Spustit kvíz</button>`;
    }

    if (s.phase === "question") {
      const q = s.admin_question;
      html += `<p><strong>Otázka ${s.question_number}/${s.question_count}:</strong> ${esc(q ? q.otazka : "")}<br>
        <span class="muted">Správně: <strong class="ok">${esc(correctLabel(q))}</strong>${q && q.body > 1 ? ` · za ${q.body} b.` : ""}</span></p>
        <div class="row">`;
      if (s.q_state === "open")
        html += `<label class="muted">Odpočet:
            <input type="number" id="cd-secs" value="${DEFAULT_COUNTDOWN}" min="0" max="120" style="width:75px; padding:8px"> s
          </label>
          <button data-act="close-cd">🔴 Zavřít odpovědi (odpočet)</button>`;
      if (s.q_state === "countdown")
        html += `<span class="status-pill countdown">⏳ Odpočet běží…</span>`;
      if (s.q_state === "locked")
        html += `<button data-act="reveal">👁 Ukázat správnou odpověď</button>
          <button class="secondary small" data-act="open">↺ Znovu otevřít odpovědi</button>`;
      if (s.q_state === "locked" || s.q_state === "revealed")
        html += `<button data-act="next">⏭ Další otázka</button>`;
      html += `<button class="secondary small" data-act="prev" ${s.question_number > 1 ? "" : "disabled"}>← předchozí</button></div>`;
    }

    if (s.phase === "results_set") {
      html += `<p>Na projektoru je pořadí sady.</p><div class="row">
        <button data-act="total_results">📊 Ukázat celkové pořadí</button>
        <button class="secondary" data-act="review_start">📋 Rekapitulace sady</button></div>`;
    }

    if (s.phase === "results_total") {
      html += `<p>Na projektoru je celkové pořadí večera.</p><div class="row">
        <button data-act="next_set">⏭ ${s.set_number < s.set_count ? "Další sada" : "Ukončit kvíz"}</button>
        <button class="secondary" data-act="review_start">📋 Rekapitulace sady</button></div>`;
    }

    if (s.phase === "review") {
      html += `<p><strong>Rekapitulace — otázka ${s.question_number}/${s.question_count}</strong></p>
        <div class="row">
        <button class="secondary" data-act="review_prev">← Předchozí</button>
        <button data-act="review_next">Další →</button>
        <button class="secondary" data-act="review_end">Ukončit rekapitulaci</button></div>`;
    }

    if (s.phase === "finished") {
      html += `<p>🏆 Kvíz skončil. Na projektoru je konečné pořadí.</p>`;
    }

    c.innerHTML = html;

    c.querySelectorAll("[data-act]").forEach((b) => {
      const act = b.dataset.act;
      if (act === "close-cd") {
        b.addEventListener("click", () => {
          const secs = parseInt($("cd-secs").value, 10);
          action("close", { countdown: isNaN(secs) ? DEFAULT_COUNTDOWN : secs });
        });
      } else {
        b.addEventListener("click", () => action(act));
      }
    });
    const start = $("start-game");
    if (start) start.addEventListener("click", () => {
      api("/admin/api/hra/start", { set_ids: queue })
        .then(({ ok, data }) => { if (!ok) msg(data.error, true); else queue = []; refresh(); });
    });
    const qc = $("queue-clear");
    if (qc) qc.addEventListener("click", () => { queue = []; refresh(); });
  }

  function setName(s, id) {
    const f = (s.sets || []).find((x) => x.id === id);
    return f ? f.name : "?";
  }

  function correctLabel(q) {
    if (!q) return "";
    if (q.typ === "abcd") return `${q.spravna}) ${q["moznost_" + q.spravna.toLowerCase()]}`;
    if (q.typ === "cislo") return q.spravna + (q.tolerance ? ` ±${q.tolerance}` : "");
    return q.spravna;
  }

  // ---------- odpovědi týmů ----------

  function renderAnswers(s) {
    const card = $("answers-card");
    if (!s.answers || (s.phase !== "question" && s.phase !== "review")) {
      card.classList.add("hidden");
      return;
    }
    card.classList.remove("hidden");
    $("answered-count").textContent = `(${s.answers.length}/${(s.teams || []).length} týmů odpovědělo)`;

    const evaluated = s.answers.some((a) => a.spravne !== null);
    let html = `<table class="answers-table">
      <tr><th>Tým</th><th>Odpověď</th><th>Stav</th><th>Body</th><th>Ruční zásah</th></tr>`;
    html += s.answers.map((a) => {
      let badge = "<span class='muted'>—</span>";
      if (a.spravne === 1) badge = `<span class="badge ok">✔ správně</span>`;
      if (a.spravne === 0) badge = `<span class="badge bad">✘ špatně</span>`;
      if (a.bonus) badge += ` <span class="badge bonus">+1 nejblíž</span>`;
      if (a.override !== null) badge += ` <span class="badge override">ručně</span>`;
      return `<tr>
        <td>${esc(a.team)}</td>
        <td><strong>${esc(a.odpoved)}</strong></td>
        <td>${badge}</td>
        <td>${a.spravne === null ? "" : a.body}</td>
        <td class="row" style="gap:6px">
          <button class="small secondary" data-ov="1" data-id="${a.answer_id}" ${!evaluated ? "disabled" : ""}>uznat</button>
          <button class="small secondary" data-ov="0" data-id="${a.answer_id}" ${!evaluated ? "disabled" : ""}>neuznat</button>
          ${a.override !== null ? `<button class="small secondary" data-ov="null" data-id="${a.answer_id}">↺ auto</button>` : ""}
        </td></tr>`;
    }).join("");
    html += `</table>`;
    if (!evaluated) html += `<p class="muted" style="font-size:.85rem">Ruční uznání je možné po zamčení odpovědí (vyhodnocení).</p>`;
    $("answers-box").innerHTML = html;

    $("answers-box").querySelectorAll("[data-ov]").forEach((b) =>
      b.addEventListener("click", () => {
        const v = b.dataset.ov === "null" ? null : parseInt(b.dataset.ov, 10);
        api("/admin/api/odpoved/override", { answer_id: parseInt(b.dataset.id, 10), value: v })
          .then(() => refresh());
      }));
  }

  // ---------- sady ----------

  function renderSets(s) {
    const inLobby = s.phase === "lobby";
    $("sets-list").innerHTML = (s.sets || []).map((set) => `
      <div class="list-item">
        <span>${esc(set.name)} <span class="muted">(${set.question_count} ot.)</span></span>
        <span class="row" style="gap:6px">
          ${inLobby ? `<button class="small" data-add="${set.id}">+ do fronty</button>` : ""}
          <button class="small danger" data-del="${set.id}">smazat</button>
        </span>
      </div>`).join("") || "<p class='muted'>Zatím žádné sady — naimportuj CSV níže.</p>";

    $("sets-list").querySelectorAll("[data-add]").forEach((b) =>
      b.addEventListener("click", () => {
        const id = parseInt(b.dataset.add, 10);
        if (!queue.includes(id)) queue.push(id);
        refresh();
      }));
    $("sets-list").querySelectorAll("[data-del]").forEach((b) =>
      b.addEventListener("click", () => {
        if (!confirm("Opravdu smazat sadu včetně otázek?")) return;
        api("/admin/api/smazat-sadu", { set_id: parseInt(b.dataset.del, 10) })
          .then(({ ok, data }) => { if (!ok) msg(data.error, true); refresh(); });
      }));
  }

  // ---------- týmy ----------

  function renderTeams(s) {
    $("team-count").textContent = `(${(s.teams || []).length})`;
    $("teams-list").innerHTML = (s.teams || []).map((t) => `
      <div class="list-item">
        <span>${esc(t.name)}</span>
        <span class="row" style="gap:6px">
          <button class="small secondary" data-ren="${t.id}" data-name="${esc(t.name)}">přejmenovat</button>
          <button class="small danger" data-delteam="${t.id}">smazat</button>
        </span>
      </div>`).join("") || "<p class='muted'>Zatím se nepřipojil žádný tým.</p>";

    $("teams-list").querySelectorAll("[data-ren]").forEach((b) =>
      b.addEventListener("click", () => {
        const name = prompt("Nový název týmu:", b.dataset.name);
        if (!name) return;
        api("/admin/api/tym/prejmenovat", { team_id: parseInt(b.dataset.ren, 10), name })
          .then(() => refresh());
      }));
    $("teams-list").querySelectorAll("[data-delteam]").forEach((b) =>
      b.addEventListener("click", () => {
        if (!confirm("Opravdu smazat tým? Přijde o všechny body.")) return;
        api("/admin/api/tym/smazat", { team_id: parseInt(b.dataset.delteam, 10) })
          .then(() => refresh());
      }));
  }

  // ---------- pořadí ----------

  function standings(rows) {
    if (!rows || !rows.length) return "<p class='muted'>Žádné týmy.</p>";
    return `<table class="standings"><tr><th>#</th><th>Tým</th><th style="text-align:right">Body</th></tr>`
      + rows.map((r) => `<tr><td class="rank">${r.rank}.</td><td>${esc(r.name)}</td><td class="pts">${r.points}</td></tr>`).join("")
      + `</table>`;
  }

  // ---------- uploady ----------

  $("sets-sync").addEventListener("click", () => {
    api("/admin/api/nacist-slozku").then(({ ok, data }) => {
      if (!ok) return msg(data.error || "Chyba.", true);
      const errNames = Object.keys(data.errors || {});
      let parts = [];
      parts.push(data.imported.length ? `Nové sady: ${data.imported.join(", ")}.` : "Žádné nové sady.");
      if (errNames.length) parts.push(`Chyby: ${errNames.map(n => n + " (" + data.errors[n].join("; ") + ")").join(", ")}`);
      msg(parts.join(" "), errNames.length > 0);
      refresh();
    });
  });

  $("csv-upload").addEventListener("click", () => {
    const f = $("csv-file").files[0];
    if (!f) return msg("Vyber CSV soubor.", true);
    const fd = new FormData();
    fd.append("file", f);
    fetch("/admin/api/import-csv", { method: "POST", body: fd })
      .then((r) => r.json().then((j) => ({ ok: r.ok, data: j })))
      .then(({ ok, data }) => {
        if (!ok) msg((data.error || "Chyba") + " " + (data.errors || []).join(" "), true);
        else { msg(`Sada „${data.name}“ naimportována.`); $("csv-file").value = ""; }
        refresh();
      });
  });

  $("img-upload").addEventListener("click", () => {
    const f = $("img-file").files[0];
    if (!f) return msg("Vyber obrázek.", true);
    const fd = new FormData();
    fd.append("file", f);
    fetch("/admin/api/nahrat-obrazek", { method: "POST", body: fd })
      .then((r) => r.json().then((j) => ({ ok: r.ok, data: j })))
      .then(({ ok, data }) => {
        if (!ok) msg(data.error || "Chyba", true);
        else { msg(`Obrázek uložen jako „${data.filename}“ — tímto názvem ho odkazuj v CSV.`); $("img-file").value = ""; }
      });
  });

  $("reset-btn").addEventListener("click", () => {
    if (!confirm("Opravdu resetovat hru? Smažou se VŠECHNY odpovědi a body.")) return;
    action("reset");
  });

  poll();
})();
