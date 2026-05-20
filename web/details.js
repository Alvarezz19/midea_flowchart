import { els, escapeHtml } from "./dom.js";
import { currentTab, findPoint, state } from "./state.js";

let detailsActions = {
  locatePoint: () => {},
  renderAll: () => {},
};

export function configureDetailsActions(actions) {
  detailsActions = actions;
}

export function renderDetails() {
  if (!state.data) return;
  const tab = currentTab();
  if (!tab) {
    els.detailTitle.textContent = "详情";
    els.detailContent.innerHTML = "";
    return;
  }
  const overviewNode = state.data.overview.nodes.find((node) => node.tabId === tab.id);
  els.detailTitle.textContent = overviewNode?.label || tab.label;
  const selectedPoint = state.selectedPointId ? findPoint(state.selectedPointId) : null;
  const selectedModule = state.selectedModuleId ? tab.detailGraph.nodes.find((node) => node.id === state.selectedModuleId) : null;
  els.detailContent.innerHTML = `
    <div class="metric-grid">
      ${metric("节点", tab.summary.nodeCount)}
      ${metric("点位", tab.summary.pointCount)}
      ${metric("子流程", tab.summary.moduleInstanceCount)}
      ${metric("异常", (tab.summary.namingStats.unmatched || 0) + (tab.summary.namingStats.conflict || 0))}
    </div>
    ${selectedPoint ? selectedPointTemplate(selectedPoint) : ""}
    ${selectedModule ? selectedModuleTemplate(selectedModule) : ""}
    ${detailGraphSection(tab)}
    ${matrixSection(tab)}
    ${moduleSection(tab)}
    ${pointSection("输入点", tab.inputPoints)}
    ${pointSection("输出点", tab.outputPoints)}
    ${pointSection("命名异常", tab.points.filter((point) => ["unmatched", "conflict"].includes(point.namingStatus)))}
    ${rawNodeSection(tab)}
  `;
  els.detailContent.querySelectorAll("[data-point-id]").forEach((item) => {
    item.addEventListener("click", () => detailsActions.locatePoint(item.dataset.pointId));
  });
  els.detailContent.querySelectorAll("[data-module-id]").forEach((item) => {
    item.addEventListener("click", () => {
      state.selectedModuleId = item.dataset.moduleId;
      detailsActions.renderAll();
    });
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

function selectedModuleTemplate(module) {
  const inputPoints = module.inputPointIds.map(findPoint).filter(Boolean).slice(0, 8);
  const outputPoints = module.outputPointIds.map(findPoint).filter(Boolean).slice(0, 8);
  return `
    <div class="section-title">当前模块</div>
    <div class="module-item active">
      <div class="item-title">${escapeHtml(module.label)}</div>
      <div class="item-meta">节点 ${module.stats.nodeCount} · 点位 ${module.stats.pointCount} · ${escapeHtml(module.status)}</div>
      <div class="badge-row">
        ${module.recognitionIssues.map((issue) => `<span class="badge bad">${escapeHtml(issue)}</span>`).join("")}
        ${module.stats.namingIssueCount ? `<span class="badge warn">命名异常 ${module.stats.namingIssueCount}</span>` : ""}
      </div>
    </div>
    ${miniPointList("模块输入", inputPoints)}
    ${miniPointList("模块输出", outputPoints)}
  `;
}

function detailGraphSection(tab) {
  const nodes = tab.detailGraph.nodes;
  if (!nodes.length) return "";
  return `
    <div class="section-title">模块详情图</div>
    ${nodes.map((node) => `
      <div class="module-item ${node.id === state.selectedModuleId ? "active" : ""}" data-module-id="${escapeHtml(node.id)}">
        <div class="item-title">${escapeHtml(node.label)}</div>
        <div class="item-meta">节点 ${node.stats.nodeCount} · 点位 ${node.stats.pointCount} · 输出 ${node.stats.outputPointCount}</div>
        <div class="badge-row">
          <span class="badge">${escapeHtml(node.kind)}</span>
          ${node.status === "incomplete" ? '<span class="badge bad">识别不完整</span>' : ""}
        </div>
      </div>`).join("")}`;
}

function matrixSection(tab) {
  const matrix = tab.statusMatrix;
  if (!matrix || !matrix.columns.length) return "";
  return `
    <div class="section-title">直膨状态矩阵</div>
    <div class="matrix-scroll">
      <table class="matrix-table">
        <thead>
          <tr><th>指标</th>${matrix.columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${matrix.rows.map((row) => `
            <tr>
              <th>${escapeHtml(row.metric)}</th>
              ${matrix.columns.map((column) => {
                const cell = row.cells[column.id];
                return `<td>${cell ? `<button class="matrix-cell" data-point-id="${escapeHtml(cell.pointId)}">${escapeHtml(cell.standardName || cell.rawName)}</button>` : ""}</td>`;
              }).join("")}
            </tr>`).join("")}
        </tbody>
      </table>
    </div>`;
}

function miniPointList(title, points) {
  if (!points.length) return "";
  return `
    <div class="section-title">${escapeHtml(title)}</div>
    ${points.map((point) => `
      <div class="point-item" data-point-id="${escapeHtml(point.id)}">
        <div class="item-title">${escapeHtml(point.displayName || point.rawName)}</div>
        <div class="item-meta">${escapeHtml(point.rawName)} · ${escapeHtml(point.namingStatus)}</div>
      </div>`).join("")}`;
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
