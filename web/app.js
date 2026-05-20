const state = {
  samples: [],
  data: null,
  selectedTabId: null,
  selectedPointId: null,
  selectedRawNodeId: null,
  view: "overview",
};

const els = {
  sampleSelect: document.querySelector("#sample-select"),
  fileInput: document.querySelector("#file-input"),
  searchInput: document.querySelector("#search-input"),
  searchResults: document.querySelector("#search-results"),
  tabList: document.querySelector("#tab-list"),
  issueList: document.querySelector("#issue-list"),
  detailTitle: document.querySelector("#detail-title"),
  detailContent: document.querySelector("#detail-content"),
  canvas: document.querySelector("#flow-canvas"),
  statusText: document.querySelector("#status-text"),
  statsText: document.querySelector("#stats-text"),
  subtitle: document.querySelector("#project-subtitle"),
  exportButton: document.querySelector("#export-button"),
};

const KIND_COLOR = {
  boundary: "#2f6f9f",
  communication: "#7555a5",
  control: "#317d55",
  schedule: "#c47a21",
  alarm: "#b33f35",
  output: "#155c42",
  unknown: "#88877f",
};

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
      state.view = button.dataset.view;
      document.querySelectorAll("[data-view]").forEach((item) => item.classList.toggle("active", item === button));
      renderCanvas();
    });
  });
  els.exportButton.addEventListener("click", exportCurrentData);
}

async function loadSamples() {
  setStatus("读取示例项目");
  const response = await fetch("/api/samples");
  state.samples = await response.json();
  els.sampleSelect.innerHTML = state.samples
    .map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)}</option>`)
    .join("");
}

async function analyzeSample(sampleId) {
  setStatus("解析示例项目");
  const response = await fetch(`/api/analyze?sample=${encodeURIComponent(sampleId)}`);
  await applyAnalyzeResponse(response);
}

async function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) return;
  setStatus("上传并解析 JSON");
  const content = await file.text();
  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({ filename: file.name, content }),
  });
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
  renderAll();
  setStatus("解析完成");
}

function renderAll() {
  renderHeader();
  renderSidebar();
  renderCanvas();
  renderDetails();
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
  renderAll();
}

function locatePoint(pointId) {
  const point = findPoint(pointId);
  if (!point) return;
  state.selectedPointId = pointId;
  state.selectedRawNodeId = point.nodeId;
  state.selectedTabId = point.tabId;
  els.searchResults.classList.add("hidden");
  renderAll();
}

function renderCanvas() {
  if (!state.data) return;
  if (state.view === "raw") {
    renderRawCanvas();
  } else {
    renderOverviewCanvas();
  }
}

function renderOverviewCanvas() {
  const svg = els.canvas;
  clearSvg(svg);
  svg.setAttribute("viewBox", "0 0 1180 660");
  appendDefs(svg);

  const nodes = state.data.overview.nodes;
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  for (const edge of state.data.overview.edges) {
    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    if (!source || !target) continue;
    svg.appendChild(edgeElement(source, target, edge));
  }
  for (const node of nodes) {
    svg.appendChild(overviewNodeElement(node));
  }
}

function edgeElement(source, target, edge) {
  const sx = source.position.x + 210;
  const sy = source.position.y + 58;
  const tx = target.position.x;
  const ty = target.position.y + 58;
  const mid = Math.max(60, Math.abs(tx - sx) / 2);
  const path = svgEl("path", {
    d: `M ${sx} ${sy} C ${sx + mid} ${sy}, ${tx - mid} ${ty}, ${tx} ${ty}`,
    class: `edge-path ${edge.supportCount ? "" : "weak"}`,
    "marker-end": "url(#arrow)",
  });
  const title = svgEl("title");
  title.textContent = `${edge.label} · 支撑 ${edge.supportCount}`;
  path.appendChild(title);
  return path;
}

function overviewNodeElement(node) {
  const group = svgEl("g", {
    class: `canvas-node ${node.tabId === state.selectedTabId ? "active" : ""} ${node.stats.namingIssueCount ? "issue" : ""}`,
    transform: `translate(${node.position.x}, ${node.position.y})`,
  });
  group.addEventListener("click", () => selectTab(node.tabId));
  group.appendChild(svgEl("rect", {
    width: 210,
    height: 116,
    rx: 7,
    fill: "#fffdf6",
    stroke: KIND_COLOR[node.kind] || "#88877f",
  }));
  group.appendChild(svgText(node.label, 14, 26, 16, "800"));
  group.appendChild(svgText(node.sourceLabel, 14, 48, 11, "500", "#6a6a60", 180));
  group.appendChild(svgText(`节点 ${node.stats.nodeCount}  点位 ${node.stats.pointCount}  子流程 ${node.stats.moduleInstanceCount}`, 14, 74, 12));
  const issueText = node.stats.namingIssueCount
    ? `命名异常 ${node.stats.namingIssueCount}`
    : `命名已匹配 ${node.stats.matched}`;
  group.appendChild(svgText(issueText, 14, 96, 12, "700", node.stats.namingIssueCount ? "#b33f35" : "#317d55"));
  return group;
}

function renderRawCanvas() {
  const svg = els.canvas;
  clearSvg(svg);
  const nodes = state.data.rawGraph.nodes.filter((node) => node.x !== null && node.y !== null);
  if (!nodes.length) return;
  const minX = Math.min(...nodes.map((node) => node.x));
  const maxX = Math.max(...nodes.map((node) => node.x));
  const minY = Math.min(...nodes.map((node) => node.y));
  const maxY = Math.max(...nodes.map((node) => node.y));
  const width = Math.max(1180, maxX - minX + 220);
  const height = Math.max(660, maxY - minY + 220);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  const selectedId = state.selectedRawNodeId;
  const visibleEdges = selectedId
    ? state.data.rawGraph.edges.filter((edge) => edge.source === selectedId || edge.target === selectedId)
    : state.data.rawGraph.edges.slice(0, 600);
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  for (const edge of visibleEdges) {
    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    if (!source || !target) continue;
    const x1 = source.x - minX + 80;
    const y1 = source.y - minY + 80;
    const x2 = target.x - minX + 80;
    const y2 = target.y - minY + 80;
    svg.appendChild(svgEl("line", { x1, y1, x2, y2, stroke: "#cbc2ad", "stroke-width": 1 }));
  }
  for (const node of nodes) {
    const dot = svgEl("circle", {
      class: `raw-dot ${node.id === selectedId ? "active" : ""}`,
      cx: node.x - minX + 80,
      cy: node.y - minY + 80,
      r: node.pointId ? 6 : 4,
      fill: rawNodeColor(node),
      stroke: "#fffdf6",
      "stroke-width": 1.5,
    });
    const title = svgEl("title");
    title.textContent = `${node.name} · ${node.type}`;
    dot.appendChild(title);
    dot.addEventListener("click", () => {
      state.selectedRawNodeId = node.id;
      if (node.pointId) {
        locatePoint(node.pointId);
      } else {
        state.selectedTabId = node.tabId;
        renderAll();
      }
    });
    svg.appendChild(dot);
  }
}

function renderDetails() {
  const tab = state.data.tabs.find((item) => item.id === state.selectedTabId) || state.data.tabs[0];
  if (!tab) {
    els.detailTitle.textContent = "详情";
    els.detailContent.innerHTML = "";
    return;
  }
  const overviewNode = state.data.overview.nodes.find((node) => node.tabId === tab.id);
  els.detailTitle.textContent = overviewNode?.label || tab.label;
  const selectedPoint = state.selectedPointId ? findPoint(state.selectedPointId) : null;
  els.detailContent.innerHTML = `
    <div class="metric-grid">
      ${metric("节点", tab.summary.nodeCount)}
      ${metric("点位", tab.summary.pointCount)}
      ${metric("子流程", tab.summary.moduleInstanceCount)}
      ${metric("异常", (tab.summary.namingStats.unmatched || 0) + (tab.summary.namingStats.conflict || 0))}
    </div>
    ${selectedPoint ? selectedPointTemplate(selectedPoint) : ""}
    ${moduleSection(tab)}
    ${pointSection("输入点", tab.inputPoints)}
    ${pointSection("输出点", tab.outputPoints)}
    ${pointSection("命名异常", tab.points.filter((point) => ["unmatched", "conflict"].includes(point.namingStatus)))}
    ${rawNodeSection(tab)}
  `;
  els.detailContent.querySelectorAll("[data-point-id]").forEach((item) => {
    item.addEventListener("click", () => locatePoint(item.dataset.pointId));
  });
}

function metric(label, value) {
  return `<div class="metric"><div class="metric-value">${value}</div><div class="metric-label">${escapeHtml(label)}</div></div>`;
}

function selectedPointTemplate(point) {
  const candidates = point.namingCandidates
    .slice(0, 4)
    .map((item) => `<div class="item-meta">${escapeHtml(item.object_name || "")} · ${escapeHtml(item.chinese_desc || "")}</div>`)
    .join("");
  return `
    <div class="section-title">当前定位</div>
    <div class="point-item active">
      <div class="item-title">${escapeHtml(point.displayName || point.rawName)}</div>
      <div class="item-meta">${escapeHtml(point.rawName)} · ${escapeHtml(point.nodeType)} · ${escapeHtml(point.group)}</div>
      <div class="badge-row"><span class="badge ${point.namingStatus === "unmatched" ? "bad" : "warn"}">${escapeHtml(point.namingStatus)}</span></div>
      ${candidates}
    </div>`;
}

function moduleSection(tab) {
  if (!tab.moduleInstances.length) return "";
  return `
    <div class="section-title">子流程实例</div>
    ${tab.moduleInstances.slice(0, 12).map((item) => `
      <div class="module-item">
        <div class="item-title">${escapeHtml(item.name)}</div>
        <div class="item-meta">${escapeHtml(item.subflowName)} · 输入 ${item.inputs} · 输出 ${item.outputs}</div>
      </div>`).join("")}`;
}

function pointSection(title, points) {
  if (!points.length) return "";
  return `
    <div class="section-title">${escapeHtml(title)}</div>
    ${points.slice(0, 24).map((point) => `
      <div class="point-item ${point.id === state.selectedPointId ? "active" : ""}" data-point-id="${escapeHtml(point.id)}">
        <div class="item-title">${escapeHtml(point.displayName || point.rawName)}</div>
        <div class="item-meta">${escapeHtml(point.rawName)} · ${escapeHtml(point.group)}</div>
        <div class="badge-row"><span class="badge ${point.namingStatus === "unmatched" ? "bad" : point.namingStatus === "conflict" ? "warn" : ""}">${escapeHtml(point.namingStatus)}</span></div>
      </div>`).join("")}`;
}

function rawNodeSection(tab) {
  return `
    <div class="section-title">原始节点</div>
    ${tab.rawNodes.slice(0, 60).map((node) => `
      <div class="raw-item">
        <div class="item-title">${escapeHtml(node.name)}</div>
        <div class="item-meta">${escapeHtml(node.type)} · ${escapeHtml(node.id)}</div>
      </div>`).join("")}`;
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

function findPoint(pointId) {
  for (const tab of state.data.tabs) {
    const point = tab.points.find((item) => item.id === pointId);
    if (point) return point;
  }
  return null;
}

function rawNodeColor(node) {
  if (node.namingStatus === "unmatched") return "#d6a92f";
  if (node.namingStatus === "conflict") return "#b33f35";
  if (node.role === "control_logic") return "#317d55";
  if (node.role === "algorithm") return "#c47a21";
  if (node.role === "module_instance") return "#7555a5";
  if (node.pointId) return "#2f6f9f";
  return "#8b877c";
}

function appendDefs(svg) {
  const defs = svgEl("defs");
  const marker = svgEl("marker", {
    id: "arrow",
    viewBox: "0 0 10 10",
    refX: 9,
    refY: 5,
    markerWidth: 7,
    markerHeight: 7,
    orient: "auto-start-reverse",
  });
  marker.appendChild(svgEl("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#7b776b" }));
  defs.appendChild(marker);
  svg.appendChild(defs);
}

function svgText(text, x, y, size = 12, weight = "500", fill = "#20211e", maxChars = 22) {
  const node = svgEl("text", { x, y, fill, "font-size": size, "font-weight": weight });
  node.textContent = text.length > maxChars ? `${text.slice(0, maxChars - 1)}…` : text;
  return node;
}

function svgEl(tag, attrs = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) {
    element.setAttribute(key, value);
  }
  return element;
}

function clearSvg(svg) {
  while (svg.firstChild) svg.removeChild(svg.firstChild);
}

function setStatus(text) {
  els.statusText.textContent = text;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
