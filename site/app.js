const subsets = {
  D1: {name: "Data filtering", color: "#5081c9"},
  D2: {name: "Processing plans", color: "#8a74c6"},
  D3: {name: "Output quality", color: "#49a098"},
  D4: {name: "Information sufficiency", color: "#c99143"},
  D5: {name: "Evidence & privacy", color: "#c6778c"},
  D6: {name: "Workflow control", color: "#79a15c"}
};
const percent = value => value == null ? "—" : `${(value * 100).toFixed(1)}%`;
const number = value => value == null ? "—" : value.toFixed(4);
let entries = [], view = "overall", selected = null;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function showDetail(row, scroll = false) {
  selected = row.id;
  const panel = document.getElementById("detail");
  panel.hidden = false;
  document.getElementById("detail-title").textContent = row.model;
  document.getElementById("detail-meta").textContent = `${row.backend} · ${row.evaluated_at} · ${row.overall.correct}/${row.overall.total} correct`;
  const grid = document.getElementById("detail-grid");
  grid.replaceChildren();
  for (const [key, info] of Object.entries(subsets)) {
    const score = row.by_subset[key];
    const card = element("div", undefined, "subset-card");
    card.style.setProperty("--subset-color", info.color);
    card.append(element("span", `${key} · ${info.name}`), element("strong", percent(score.accuracy)));
    const meter = element("meter");
    meter.min = 0; meter.max = 1; meter.value = score.accuracy;
    meter.setAttribute("aria-label", `${key} accuracy`);
    card.append(meter, element("small", `${score.correct}/${score.total} correct · ${score.valid}/${score.total} valid`));
    grid.append(card);
  }
  document.getElementById("inference-note").textContent = row.inference_note;
  const identity = document.getElementById("run-identity");
  identity.replaceChildren();
  const fields = {"Entry": row.id, "Evaluated model": row.model_id};
  if (row.model_revision) fields["Model revision"] = row.model_revision;
  for (const [key, value] of Object.entries(row.evidence)) {
    if (typeof value === "string") fields[key.replaceAll("_", " ")] = value;
  }
  for (const [name, value] of Object.entries(fields)) identity.append(element("dt", name), element("dd", value));
  document.getElementById("run-settings").textContent = JSON.stringify(row.settings, null, 2);
  document.querySelectorAll("#rows tr").forEach(tr => {
    const active = tr.dataset.id === selected;
    tr.classList.toggle("selected", active);
    tr.querySelector("button").setAttribute("aria-pressed", String(active));
  });
  if (scroll) panel.scrollIntoView({behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth", block: "nearest"});
}

function renderTable() {
  const header = element("tr");
  const labels = view === "overall" ? ["Rank", "Model", "Accuracy ↑", "Valid answers", "ECE10 ↓", "Brier ↓"] : ["Rank", "Model", ...Object.keys(subsets)];
  for (const label of labels) {
    const th = element("th", label); th.scope = "col";
    if (subsets[label]) th.title = subsets[label].name;
    header.append(th);
  }
  document.getElementById("columns").replaceChildren(header);
  document.getElementById("table-caption").textContent = view === "overall" ? "Model accuracy, valid answers and calibration" : "D1–D6 accuracy; rank follows overall accuracy";
  const body = document.getElementById("rows");
  body.replaceChildren();
  let rank = 0, previous = null;
  entries.forEach((row, index) => {
    const score = row.overall;
    if (score.accuracy !== previous) rank = index + 1;
    previous = score.accuracy;
    const tr = element("tr"); tr.dataset.id = row.id;
    tr.classList.toggle("selected", selected === row.id);
    const model = element("td", undefined, "model-cell");
    const button = element("button", row.model, "model-name");
    button.type = "button";
    button.setAttribute("aria-pressed", String(selected === row.id));
    button.setAttribute("aria-controls", "detail");
    button.addEventListener("click", () => showDetail(row, true));
    model.append(button, element("span", row.backend, "minor"));
    tr.append(element("td", String(rank), "rank"), model);
    if (view === "overall") {
      [percent(score.accuracy), `${score.valid}/${score.total}`, number(score.ece), number(score.brier)].forEach((value, i) => tr.append(element("td", value, i === 0 ? "score" : "numeric")));
    } else {
      for (const [key, info] of Object.entries(subsets)) {
        const s = row.by_subset[key];
        const cell = element("td", percent(s.accuracy), "subset-score");
        cell.style.setProperty("--subset-color", info.color);
        cell.style.setProperty("--score-width", `${s.accuracy * 100}%`);
        cell.title = `${info.name}: ${s.correct}/${s.total} correct; ${s.valid}/${s.total} valid`;
        tr.append(cell);
      }
    }
    body.append(tr);
  });
  document.querySelectorAll("[data-view]").forEach(button => button.setAttribute("aria-pressed", String(button.dataset.view === view)));
}

async function loadBoard() {
  const response = await fetch("../results/leaderboard.json");
  if (!response.ok) throw new Error(`Result data: HTTP ${response.status}`);
  const board = await response.json();
  if (board.schema !== "datajevbench.board.v1" || board.release !== "0.5" || !Array.isArray(board.entries)) throw new Error("Unexpected result format");
  const compare = (a, b) => a < b ? -1 : a > b ? 1 : 0;
  entries = [...board.entries].sort((a, b) => b.overall.accuracy - a.overall.accuracy || compare(a.model.toLowerCase(), b.model.toLowerCase()) || compare(a.id, b.id));
  const status = document.getElementById("board-status");
  document.getElementById("snapshot").textContent = `${board.evaluated_at} · ${entries.length} models`;
  if (!entries.length) { status.textContent = "This result snapshot contains 0 entries."; return; }
  renderTable();
  document.getElementById("result-table").hidden = false;
  status.hidden = true;
  showDetail(entries[0]);
  document.querySelectorAll("[data-view]").forEach(button => {
    button.disabled = false;
    button.addEventListener("click", () => { view = button.dataset.view; renderTable(); });
  });
}

loadBoard().catch(error => {
  const status = document.getElementById("board-status");
  status.hidden = false;
  status.textContent = "Open Result data to read the snapshot. The interactive table loads when this page is served over HTTP.";
  console.error(error);
});
