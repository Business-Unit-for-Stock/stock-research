"use strict";

const PAGE_SIZE = 50;
const SOURCE_LABELS = {
  a_stock_data_reference: "a-stock-data 接口参考",
  plate_rotation_ths: "同花顺板块榜",
  plate_rotation_kaipan: "开盘啦强度榜",
  akshare_industry: "东财行业",
  akshare_concept: "东财概念",
};
const FAMILY_LABELS = { eastmoney: "东方财富", ths: "同花顺", kaipan: "开盘啦" };
const UNIVERSE_LABELS = { industry: "行业", concept: "概念", plate: "板块" };
const LIFECYCLE_LABELS = {
  multi_source_current: "多源当前",
  multi_source_persistent: "多源持续",
  single_source_current: "单源当前",
  single_source_persistent: "单源持续",
};
const COMMIT_KEYS = {
  a_stock_data_reference: "a_stock_data",
  plate_rotation_ths: "plate_rotation_skill",
  plate_rotation_kaipan: "plate_rotation_skill",
  akshare_industry: "akshare",
  akshare_concept: "akshare",
};

const state = { data: null, filtered: [], page: 1 };

function byId(id) {
  return document.getElementById(id);
}

function textCell(value, className = "") {
  const cell = document.createElement("td");
  cell.textContent = value ?? "-";
  if (className) cell.className = className;
  return cell;
}

function splitValues(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function sourceText(value) {
  return splitValues(value).map((item) => FAMILY_LABELS[item] || item).join(" / ");
}

function universeText(value) {
  return splitValues(value).map((item) => UNIVERSE_LABELS[item] || item).join(" / ");
}

function scoreText(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : "-";
}

function createPill(label, className) {
  const pill = document.createElement("span");
  pill.className = className;
  pill.textContent = label;
  return pill;
}

function renderHeader(data) {
  const generated = data.generated_at ? new Date(data.generated_at).toLocaleString("zh-CN") : "未知";
  byId("run-meta").textContent = `数据日期 ${data.as_of_date || "-"} · 更新于 ${generated}`;
  byId("metric-evidence").textContent = Number(data.records.direction_evidence || 0).toLocaleString("zh-CN");
  byId("metric-analysis").textContent = Number(data.records.direction_analysis || 0).toLocaleString("zh-CN");
  byId("metric-confirmed").textContent = Number(data.records.confirmed_directions || 0).toLocaleString("zh-CN");

  const runtimeSources = Object.entries(data.source_status).filter(([key]) => key !== "a_stock_data_reference");
  const successful = runtimeSources.filter(([, status]) => status.ok).length;
  byId("metric-sources").textContent = `${successful}/${runtimeSources.length}`;
  byId("scope-label").textContent = data.parameters.scope === "complete_current_lists"
    ? "完整当前榜单"
    : String(data.parameters.scope || "未标注范围");

  const failed = runtimeSources.filter(([, status]) => !status.ok);
  const badge = byId("health-badge");
  const message = byId("health-message");
  if (failed.length === 0) {
    badge.textContent = "来源完整";
    badge.className = "health-badge is-good";
    message.textContent = "";
  } else {
    badge.textContent = `${failed.length} 个来源异常`;
    badge.className = "health-badge is-warn";
    message.className = "health-message is-warn";
    message.textContent = failed
      .map(([key, status]) => `${SOURCE_LABELS[key] || key}：${status.error || status.note || "失败"}`)
      .join("；");
  }
}

function renderSources(data) {
  const entries = Object.entries(data.source_status);
  const sourceBody = byId("source-body");
  const bars = byId("source-bars");
  sourceBody.replaceChildren();
  bars.replaceChildren();

  const rowCounts = entries.map(([, status]) => Number(status.rows || 0));
  const maxRows = Math.max(1, ...rowCounts);
  for (const [key, status] of entries) {
    const row = document.createElement("tr");
    row.append(textCell(SOURCE_LABELS[key] || key));
    const statusCell = document.createElement("td");
    statusCell.append(createPill(status.ok ? "正常" : "异常", `status-pill ${status.ok ? "is-good" : "is-bad"}`));
    row.append(statusCell);
    row.append(textCell(status.rows == null ? "-" : Number(status.rows).toLocaleString("zh-CN"), "number-cell"));
    row.append(textCell(status.attempts == null ? "-" : status.attempts, "number-cell"));
    const commitKey = COMMIT_KEYS[key];
    const commit = status.commit || (commitKey ? data.fork_commits[commitKey] : "");
    row.append(textCell(commit ? String(commit).slice(0, 8) : "-", "muted-cell"));
    sourceBody.append(row);

    if (status.rows != null) {
      const item = document.createElement("div");
      const head = document.createElement("div");
      head.className = "source-bar__head";
      const label = document.createElement("span");
      label.textContent = SOURCE_LABELS[key] || key;
      const count = document.createElement("strong");
      count.textContent = Number(status.rows).toLocaleString("zh-CN");
      head.append(label, count);
      const track = document.createElement("div");
      track.className = "source-bar__track";
      const fill = document.createElement("div");
      fill.className = "source-bar__fill";
      fill.style.width = `${Math.max(0, Number(status.rows)) / maxRows * 100}%`;
      track.append(fill);
      item.append(head, track);
      bars.append(item);
    }
  }
}

function appendDirectionRow(body, record, index, includeIndex) {
  const row = document.createElement("tr");
  if (includeIndex) row.append(textCell(index, "number-cell muted-cell"));
  row.append(textCell(record.name || record.canonical_name, "direction-name"));

  if (includeIndex) {
    const evidenceCell = document.createElement("td");
    const isCross = record.evidence_level === "cross_source";
    evidenceCell.append(createPill(isCross ? `多源 ${record.evidence_count}` : "单源", `evidence-pill ${isCross ? "is-cross" : "is-single"}`));
    row.append(evidenceCell);
  }
  row.append(textCell(sourceText(record.source_families)));
  row.append(textCell(universeText(record.universes)));
  row.append(textCell(record.best_rank, "number-cell"));
  row.append(textCell(scoreText(record.consensus_rank_score), "number-cell"));
  row.append(textCell(LIFECYCLE_LABELS[record.lifecycle] || record.lifecycle || "-"));
  if (includeIndex) row.append(textCell(record.quality_notes || "-", "muted-cell"));
  body.append(row);
}

function renderConfirmed(data) {
  const body = byId("confirmed-body");
  body.replaceChildren();
  if (!data.confirmed.length) {
    const row = document.createElement("tr");
    const cell = textCell("当前没有多源一致方向", "empty-row");
    cell.colSpan = 6;
    row.append(cell);
    body.append(row);
    return;
  }
  data.confirmed.forEach((record) => appendDirectionRow(body, record, 0, false));
}

function fillFilter(id, values, labels) {
  const select = byId(id);
  for (const value of [...values].sort()) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = labels[value] || value;
    select.append(option);
  }
}

function setupFilters(data) {
  const sources = new Set();
  const universes = new Set();
  data.analysis.forEach((record) => {
    splitValues(record.source_families).forEach((value) => sources.add(value));
    splitValues(record.universes).forEach((value) => universes.add(value));
  });
  fillFilter("source-filter", sources, FAMILY_LABELS);
  fillFilter("universe-filter", universes, UNIVERSE_LABELS);

  ["search-input", "evidence-filter", "source-filter", "universe-filter", "sort-select"].forEach((id) => {
    const eventName = id === "search-input" ? "input" : "change";
    byId(id).addEventListener(eventName, () => {
      state.page = 1;
      applyFilters();
    });
  });
  byId("previous-page").addEventListener("click", () => {
    if (state.page > 1) {
      state.page -= 1;
      renderAnalysis();
    }
  });
  byId("next-page").addEventListener("click", () => {
    if (state.page * PAGE_SIZE < state.filtered.length) {
      state.page += 1;
      renderAnalysis();
    }
  });
}

function applyFilters() {
  const query = byId("search-input").value.trim().toLocaleLowerCase("zh-CN");
  const evidence = byId("evidence-filter").value;
  const source = byId("source-filter").value;
  const universe = byId("universe-filter").value;
  const sort = byId("sort-select").value;

  state.filtered = state.data.analysis.filter((record) => {
    const searchable = `${record.name} ${record.canonical_name} ${record.source_families} ${record.universes}`.toLocaleLowerCase("zh-CN");
    return (!query || searchable.includes(query))
      && (evidence === "all" || record.evidence_level === evidence)
      && (source === "all" || splitValues(record.source_families).includes(source))
      && (universe === "all" || splitValues(record.universes).includes(universe));
  });

  if (sort === "score") {
    state.filtered.sort((a, b) => b.consensus_rank_score - a.consensus_rank_score);
  } else if (sort === "rank") {
    state.filtered.sort((a, b) => a.best_rank - b.best_rank);
  } else if (sort === "name") {
    state.filtered.sort((a, b) => String(a.name).localeCompare(String(b.name), "zh-CN"));
  } else {
    state.filtered.sort((a, b) => b.evidence_count - a.evidence_count
      || b.consensus_rank_score - a.consensus_rank_score
      || a.best_rank - b.best_rank);
  }
  renderAnalysis();
}

function renderAnalysis() {
  const body = byId("analysis-body");
  body.replaceChildren();
  const totalPages = Math.max(1, Math.ceil(state.filtered.length / PAGE_SIZE));
  state.page = Math.min(state.page, totalPages);
  const start = (state.page - 1) * PAGE_SIZE;
  const pageRows = state.filtered.slice(start, start + PAGE_SIZE);

  if (!pageRows.length) {
    const row = document.createElement("tr");
    const cell = textCell("没有符合条件的方向", "empty-row");
    cell.colSpan = 9;
    row.append(cell);
    body.append(row);
  } else {
    pageRows.forEach((record, offset) => appendDirectionRow(body, record, start + offset + 1, true));
  }
  byId("result-count").textContent = `${state.filtered.length.toLocaleString("zh-CN")} 个方向`;
  byId("page-label").textContent = `${state.page} / ${totalPages}`;
  byId("previous-page").disabled = state.page <= 1;
  byId("next-page").disabled = state.page >= totalPages;
}

async function start() {
  try {
    const response = await fetch("./data/dashboard.json", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    renderHeader(state.data);
    renderSources(state.data);
    renderConfirmed(state.data);
    setupFilters(state.data);
    applyFilters();
  } catch (error) {
    byId("run-meta").textContent = "数据载入失败";
    const badge = byId("health-badge");
    badge.textContent = "页面异常";
    badge.className = "health-badge is-warn";
    const message = byId("health-message");
    message.className = "health-message is-warn";
    message.textContent = String(error);
  }
}

start();
