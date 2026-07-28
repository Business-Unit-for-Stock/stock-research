"use strict";

const PAGE_SIZE = 50;
const SOURCE_LABELS = {
  plate_rotation_ths: "同花顺板块榜",
  plate_rotation_kaipan: "开盘啦强度榜",
  akshare_industry: "东方财富行业",
  akshare_concept: "东方财富概念",
};
const SOURCE_SCOPE_LABELS = {
  upstream_selected_current_list: "上游精选 Top10",
  complete_returned_list: "接口返回全表",
};
const METHOD_LABELS = { a_stock_data: "a-stock-data" };
const FAMILY_LABELS = { eastmoney: "东方财富", ths: "同花顺", kaipan: "开盘啦" };
const UNIVERSE_LABELS = { industry: "行业", concept: "概念", plate: "板块" };
const LIFECYCLE_LABELS = {
  multi_source_current: "多源当前",
  multi_source_persistent: "多源持续",
  single_source_current: "单源当前",
  single_source_persistent: "单源持续",
};
const COMMIT_KEYS = {
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
  const values = splitValues(value);
  return values.length ? values.map((item) => FAMILY_LABELS[item] || item).join(" / ") : "-";
}

function universeText(value) {
  return splitValues(value).map((item) => UNIVERSE_LABELS[item] || item).join(" / ");
}

function createPill(label, className) {
  const pill = document.createElement("span");
  pill.className = className;
  pill.textContent = label;
  return pill;
}

function classification(record) {
  if (record.strength_level === "multi_source_strong") {
    return [`多源强势 ${record.strong_source_count}`, "is-strong"];
  }
  if (record.coverage_level === "multi_source_coverage") {
    return [`多源覆盖 ${record.evidence_count}`, "is-coverage"];
  }
  if (record.strength_level === "single_source_strong") {
    return ["单源强势", "is-single-strong"];
  }
  return ["单一来源", "is-single"];
}

function renderHeader(data) {
  const generated = data.generated_at ? new Date(data.generated_at).toLocaleString("zh-CN") : "未知";
  byId("run-meta").textContent = `数据日期 ${data.as_of_date || "-"} · 更新于 ${generated}`;
  byId("metric-evidence").textContent = Number(data.records.direction_evidence || 0).toLocaleString("zh-CN");
  byId("metric-analysis").textContent = Number(data.records.direction_analysis || 0).toLocaleString("zh-CN");
  byId("metric-strong").textContent = Number(data.records.multi_source_strong || 0).toLocaleString("zh-CN");
  byId("metric-coverage").textContent = Number(data.records.multi_source_coverage || 0).toLocaleString("zh-CN");

  const runtimeSources = Object.entries(data.source_status);
  const successful = runtimeSources.filter(([, status]) => status.ok).length;
  byId("metric-sources").textContent = `${successful}/${runtimeSources.length}`;
  byId("scope-label").textContent = data.parameters.scope === "complete_provider_responses"
    ? "接口完整响应（本地未截断）"
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
    row.append(textCell(SOURCE_SCOPE_LABELS[status.scope] || status.scope || "-"));
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

function renderMethodReferences(data) {
  const body = byId("reference-body");
  body.replaceChildren();
  const entries = Object.entries(data.method_references || {});
  if (!entries.length) {
    const row = document.createElement("tr");
    const cell = textCell("没有方法参考记录", "empty-row");
    cell.colSpan = 5;
    row.append(cell);
    body.append(row);
    return;
  }
  for (const [key, reference] of entries) {
    const row = document.createElement("tr");
    row.append(textCell(METHOD_LABELS[key] || key, "direction-name"));
    row.append(textCell(reference.purpose || reference.note || "-"));
    row.append(textCell(reference.runtime_requests ? "是" : "否"));
    const statusCell = document.createElement("td");
    statusCell.append(createPill(reference.available ? "已固定版本" : "不可用", `status-pill ${reference.available ? "is-good" : "is-bad"}`));
    row.append(statusCell);
    row.append(textCell(reference.commit ? String(reference.commit).slice(0, 8) : "-", "muted-cell"));
    body.append(row);
  }
}

function appendFeaturedRow(body, record, strongFirst) {
  const row = document.createElement("tr");
  row.append(textCell(record.name || record.canonical_name, "direction-name"));
  if (strongFirst) {
    row.append(textCell(sourceText(record.strong_source_families)));
    row.append(textCell(sourceText(record.source_families)));
  } else {
    row.append(textCell(sourceText(record.source_families)));
    row.append(textCell(sourceText(record.strong_source_families)));
  }
  row.append(textCell(universeText(record.universes)));
  row.append(textCell(LIFECYCLE_LABELS[record.lifecycle] || record.lifecycle || "-"));
  body.append(row);
}

function renderFeatured(bodyId, records, emptyText, strongFirst) {
  const body = byId(bodyId);
  body.replaceChildren();
  if (!records.length) {
    const row = document.createElement("tr");
    const cell = textCell(emptyText, "empty-row");
    cell.colSpan = 5;
    row.append(cell);
    body.append(row);
    return;
  }
  records.forEach((record) => appendFeaturedRow(body, record, strongFirst));
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

  ["search-input", "classification-filter", "source-filter", "universe-filter", "sort-select"].forEach((id) => {
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

function matchesClassification(record, value) {
  if (value === "multi_source_strong") return record.strength_level === value;
  if (value === "multi_source_coverage") return record.coverage_level === value;
  if (value === "single_source") return record.coverage_level === value;
  return true;
}

function priority(record) {
  if (record.strength_level === "multi_source_strong") return 2;
  if (record.coverage_level === "multi_source_coverage") return 1;
  return 0;
}

function applyFilters() {
  const query = byId("search-input").value.trim().toLocaleLowerCase("zh-CN");
  const classificationValue = byId("classification-filter").value;
  const source = byId("source-filter").value;
  const universe = byId("universe-filter").value;
  const sort = byId("sort-select").value;

  state.filtered = state.data.analysis.filter((record) => {
    const searchable = `${record.name} ${record.canonical_name} ${record.source_families} ${record.universes}`.toLocaleLowerCase("zh-CN");
    return (!query || searchable.includes(query))
      && matchesClassification(record, classificationValue)
      && (source === "all" || splitValues(record.source_families).includes(source))
      && (universe === "all" || splitValues(record.universes).includes(universe));
  });

  if (sort === "strong") {
    state.filtered.sort((a, b) => b.strong_source_count - a.strong_source_count
      || b.evidence_count - a.evidence_count);
  } else if (sort === "coverage") {
    state.filtered.sort((a, b) => b.evidence_count - a.evidence_count
      || b.strong_source_count - a.strong_source_count);
  } else if (sort === "name") {
    state.filtered.sort((a, b) => String(a.name).localeCompare(String(b.name), "zh-CN"));
  } else {
    state.filtered.sort((a, b) => priority(b) - priority(a)
      || b.strong_source_count - a.strong_source_count
      || b.evidence_count - a.evidence_count
      || String(a.name).localeCompare(String(b.name), "zh-CN"));
  }
  renderAnalysis();
}

function appendAnalysisRow(body, record, index) {
  const row = document.createElement("tr");
  row.append(textCell(index, "number-cell muted-cell"));
  row.append(textCell(record.name || record.canonical_name, "direction-name"));
  const classificationCell = document.createElement("td");
  const [label, className] = classification(record);
  classificationCell.append(createPill(label, `evidence-pill ${className}`));
  row.append(classificationCell);
  row.append(textCell(sourceText(record.source_families)));
  row.append(textCell(sourceText(record.strong_source_families)));
  row.append(textCell(universeText(record.universes)));
  row.append(textCell(LIFECYCLE_LABELS[record.lifecycle] || record.lifecycle || "-"));
  row.append(textCell(record.quality_notes || "-", "muted-cell"));
  body.append(row);
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
    cell.colSpan = 8;
    row.append(cell);
    body.append(row);
  } else {
    pageRows.forEach((record, offset) => appendAnalysisRow(body, record, start + offset + 1));
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
    renderMethodReferences(state.data);
    renderFeatured("strong-body", state.data.strong, "当前没有多源强势方向", true);
    renderFeatured("coverage-body", state.data.coverage, "当前没有多源覆盖方向", false);
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
