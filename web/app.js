import {
  analyzeContent as requestContentAnalysis,
  analyzeSample as requestSampleAnalysis,
  loadSamples as requestSamples,
} from "./api.js";
import { configureCanvasActions, renderCanvas } from "./canvas.js";
import { configureDetailsActions, renderDetails } from "./details.js";
import { els, escapeHtml, setStatus } from "./dom.js";
import { configureDrag, finishCanvasNodeDrag, handleCanvasNodeDrag } from "./drag.js";
import { findModuleByPoint, findPoint, state } from "./state.js";

configureCanvasActions({ selectTab, locatePoint, renderAll });
configureDetailsActions({ locatePoint, renderAll });
configureDrag({ renderCanvas });

init();

async function init() {
  bindEvents();
  await loadSamples();
  const preferred = state.samples.find((item) => item.id.includes("三山经开区")) || state.samples[0];
  if (preferred) {
    els.sampleSelect.value = preferred.id;
    await analyzeSample(preferred.id);
  }
}

function bindEvents() {
  els.sampleSelect.addEventListener("change", () => analyzeSample(els.sampleSelect.value));
  els.fileInput.addEventListener("change", handleFileUpload);
  els.searchInput.addEventListener("input", handleSearch);
  els.searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      const first = els.searchResults.querySelector("[data-point-id]");
      if (first) {
        locatePoint(first.dataset.pointId);
      }
    }
  });
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => {
      setView(button.dataset.view);
    });
  });
  els.exportButton.addEventListener("click", exportCurrentData);
  els.pasteButton.addEventListener("click", openPasteDialog);
  els.pasteClose.addEventListener("click", closePasteDialog);
  els.pasteCancel.addEventListener("click", closePasteDialog);
  els.pasteSubmit.addEventListener("click", handlePasteSubmit);
  els.backButton.addEventListener("click", () => setView("overview"));
  document.querySelectorAll("[data-edge-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      state.edgeMode = button.dataset.edgeMode;
      document.querySelectorAll("[data-edge-mode]").forEach((item) => item.classList.toggle("active", item === button));
      renderCanvas();
    });
  });
  window.addEventListener("pointermove", handleCanvasNodeDrag);
  window.addEventListener("pointerup", finishCanvasNodeDrag);
}

async function loadSamples() {
  setStatus("读取示例项目");
  state.samples = await requestSamples();
  els.sampleSelect.innerHTML = state.samples
    .map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`)
    .join("");
}

async function analyzeSample(sampleId) {
  setStatus("解析示例项目");
  const response = await requestSampleAnalysis(sampleId);
  await applyAnalyzeResponse(response);
}

async function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  setStatus("上传并解析 JSON");
  const content = await file.text();
  await analyzeContent(file.name, content);
}

async function handlePasteSubmit() {
  const content = els.pasteTextarea.value.trim();
  if (!content) {
    setStatus("粘贴内容为空");
    return;
  }
  closePasteDialog();
  await analyzeContent("pasted.json", content);
}

async function analyzeContent(filename, content) {
  setStatus("解析 JSON");
  const response = await requestContentAnalysis(filename, content);
  await applyAnalyzeResponse(response);
}

async function applyAnalyzeResponse(response) {
  const payload = await response.json();
  if (!response.ok) {
    setStatus(`解析失败：${payload.error || response.statusText}`);
    return;
  }
  state.data = payload;
  state.selectedTabId = payload.overview.nodes[0]?.tabId || null;
  state.selectedPointId = null;
  state.selectedRawNodeId = null;
  state.selectedModuleId = null;
  state.edgeMode = "primary";
  document.querySelectorAll("[data-edge-mode]").forEach((item) => item.classList.toggle("active", item.dataset.edgeMode === "primary"));
  renderAll();
  setStatus("解析完成");
}

function setView(view) {
  state.view = view;
  document.querySelectorAll("[data-view]").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  renderCanvas();
  renderDetails();
  renderBackButton();
  renderEdgeModeControls();
}

function renderAll() {
  renderHeader();
  renderSidebar();
  renderCanvas();
  renderDetails();
  renderBackButton();
  renderEdgeModeControls();
}

function renderHeader() {
  const project = state.data.project;
  els.subtitle.textContent = `${project.sourcePath} · ${project.profile}`;
  els.statsText.textContent = `页签 ${project.tabCount} · 节点 ${project.nodeCount} · 连线 ${project.edgeCount} · 点位 ${project.pointCount}`;
}

function renderSidebar() {
  const nodesByTab = new Map(state.data.overview.nodes.map((node) => [node.tabId, node]));
  els.tabList.innerHTML = state.data.tabs
    .map((tab) => {
      const node = nodesByTab.get(tab.id);
      const issueCount = node?.stats.namingIssueCount || 0;
      return `
        <div class="nav-item ${tab.id === state.selectedTabId ? "active" : ""}" data-tab-id="${escapeHtml(tab.id)}">
          <div class="item-title">${escapeHtml(node?.label || tab.label)}</div>
          <div class="item-meta">${escapeHtml(tab.label)} · ${tab.summary.nodeCount} 节点 · ${tab.summary.pointCount} 点位</div>
          <div class="badge-row">
            <span class="badge">${escapeHtml(tab.role)}</span>
            ${issueCount ? `<span class="badge bad">异常 ${issueCount}</span>` : ""}
          </div>
        </div>`;
    })
    .join("");

  els.tabList.querySelectorAll("[data-tab-id]").forEach((item) => {
    item.addEventListener("click", () => selectTab(item.dataset.tabId));
  });

  const issues = state.data.namingIssues.slice(0, 300);
  els.issueList.innerHTML = issues.length
    ? issues.map((point) => issueTemplate(point)).join("")
    : '<div class="item-meta">暂无命名异常</div>';
  els.issueList.querySelectorAll("[data-point-id]").forEach((item) => {
    item.addEventListener("click", () => locatePoint(item.dataset.pointId));
  });
}

function issueTemplate(point) {
  const statusClass = point.namingStatus === "unmatched" ? "bad" : "warn";
  return `
    <div class="issue-item ${point.id === state.selectedPointId ? "active" : ""}" data-point-id="${escapeHtml(point.id)}">
      <div class="item-title">${escapeHtml(point.displayName || point.rawName)}</div>
      <div class="item-meta">${escapeHtml(point.rawName)} · ${escapeHtml(point.group)}</div>
      <div class="badge-row"><span class="badge ${statusClass}">${escapeHtml(point.namingStatus)}</span></div>
    </div>`;
}

function selectTab(tabId) {
  state.selectedTabId = tabId;
  state.selectedPointId = null;
  state.selectedRawNodeId = null;
  state.selectedModuleId = null;
  if (state.view === "overview") {
    setView("detail");
    return;
  }
  renderAll();
}

function locatePoint(pointId) {
  const point = findPoint(pointId);
  if (!point) return;
  state.selectedPointId = pointId;
  state.selectedRawNodeId = point.nodeId;
  state.selectedTabId = point.tabId;
  state.selectedModuleId = findModuleByPoint(point.tabId, pointId)?.id || null;
  els.searchResults.classList.add("hidden");
  renderAll();
}

function handleSearch() {
  const query = els.searchInput.value.trim().toUpperCase();
  if (!query || !state.data) {
    els.searchResults.classList.add("hidden");
    els.searchResults.innerHTML = "";
    return;
  }
  const points = state.data.tabs.flatMap((tab) => tab.points);
  const matches = points.filter((point) => {
    const haystack = [point.rawName, point.displayName, point.group, point.nodeType, ...point.candidateNames]
      .join(" ")
      .toUpperCase();
    return haystack.includes(query);
  }).slice(0, 30);
  els.searchResults.innerHTML = matches.length
    ? matches.map((point) => `
      <div class="search-row" data-point-id="${escapeHtml(point.id)}">
        <div class="item-title">${escapeHtml(point.displayName || point.rawName)}</div>
        <div class="item-meta">${escapeHtml(point.rawName)} · ${escapeHtml(point.group)} · ${escapeHtml(point.namingStatus)}</div>
      </div>`).join("")
    : '<div class="search-row"><div class="item-meta">无匹配结果</div></div>';
  els.searchResults.classList.remove("hidden");
  els.searchResults.querySelectorAll("[data-point-id]").forEach((item) => {
    item.addEventListener("click", () => locatePoint(item.dataset.pointId));
  });
}

function exportCurrentData() {
  if (!state.data) return;
  const blob = new Blob([JSON.stringify(state.data, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "midea_flowchart_project_view.json";
  link.click();
  URL.revokeObjectURL(url);
}

function openPasteDialog() {
  els.pasteDialog.classList.remove("hidden");
  els.pasteTextarea.focus();
}

function closePasteDialog() {
  els.pasteDialog.classList.add("hidden");
}

function renderBackButton() {
  els.backButton.classList.toggle("hidden", state.view === "overview");
}

function renderEdgeModeControls() {
  els.edgeModeControls.classList.toggle("hidden", state.view !== "detail");
}
