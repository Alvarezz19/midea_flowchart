import { appendDefs, clearSvg, els, KIND_COLOR, svgEl, svgText } from "./dom.js";
import { consumeSuppressedClick, startCanvasNodeDrag } from "./drag.js";
import { currentTab, state } from "./state.js";

let canvasActions = {
  selectTab: () => {},
  locatePoint: () => {},
  renderAll: () => {},
};

export function configureCanvasActions(actions) {
  canvasActions = actions;
}

export function renderCanvas() {
  if (!state.data) return;
  if (state.view === "raw") {
    renderRawCanvas();
  } else if (state.view === "detail") {
    renderDetailCanvas();
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

function renderDetailCanvas() {
  const svg = els.canvas;
  clearSvg(svg);
  svg.setAttribute("viewBox", "0 0 1180 660");
  appendDefs(svg);
  const tab = currentTab();
  if (!tab || !tab.detailGraph) return;
  const nodes = tab.detailGraph.nodes;
  const nodeMap = new Map(nodes.map((node) => [node.id, node]));
  const edges = state.edgeMode === "support" ? tab.detailGraph.supportEdges || tab.detailGraph.edges : tab.detailGraph.edges;
  for (const edge of edges) {
    const source = nodeMap.get(edge.source);
    const target = nodeMap.get(edge.target);
    if (!source || !target) continue;
    if (state.edgeMode === "support" && state.selectedModuleId && edge.source !== state.selectedModuleId && edge.target !== state.selectedModuleId) {
      continue;
    }
    svg.appendChild(detailEdgeElement(source, target, edge, state.edgeMode));
  }
  for (const node of nodes) {
    svg.appendChild(detailNodeElement(node));
  }
  if (tab.statusMatrix && tab.statusMatrix.columns.length) {
    svg.appendChild(matrixPreviewElement(tab.statusMatrix));
  }
  if (tab.detailGraph.note) {
    svg.appendChild(svgText(tab.detailGraph.note, 80, 610, 13, "700", "#6a6a60", 80));
  }
}

function detailEdgeElement(source, target, edge, mode = "primary") {
  const route = smoothRouteBetweenCards(source.position, target.position, 220, 108, 34 + edgeIndexOffset(edge.id));
  const path = svgEl("path", {
    d: route.path,
    class: `edge-path ${edge.supportCount ? "" : "weak"} ${mode === "support" ? "support" : ""}`,
    "marker-end": "url(#arrow)",
  });
  const title = svgEl("title");
  title.textContent = edge.supportDirection
    ? `${edge.label} · 原始连线 ${edge.supportCount}（正向 ${edge.directSupportCount} / 反向 ${edge.reverseSupportCount}）`
    : `${edge.label} · 原始连线 ${edge.supportCount}`;
  path.appendChild(title);
  return path;
}

function detailNodeElement(node) {
  const group = svgEl("g", {
    class: `canvas-node module-node ${node.id === state.selectedModuleId ? "active" : ""} ${node.status === "incomplete" ? "issue" : ""}`,
    transform: `translate(${node.position.x}, ${node.position.y})`,
  });
  group.addEventListener("pointerdown", (event) => startCanvasNodeDrag(event, node, 220, 108));
  group.addEventListener("click", () => {
    if (consumeSuppressedClick()) return;
    state.selectedModuleId = node.id;
    canvasActions.renderAll();
  });
  group.appendChild(svgEl("rect", {
    width: 220,
    height: 108,
    rx: 7,
    fill: "#fffdf6",
    stroke: KIND_COLOR[node.kind] || "#88877f",
  }));
  group.appendChild(svgText(node.label, 14, 25, 14, "800", "#20211e", 20));
  group.appendChild(svgText(`节点 ${node.stats.nodeCount}  点位 ${node.stats.pointCount}`, 14, 50, 12));
  group.appendChild(svgText(`输入 ${node.stats.inputPointCount}  输出 ${node.stats.outputPointCount}  变量 ${node.stats.softwarePointCount || 0}`, 14, 72, 12));
  const issueText = node.recognitionIssues.length ? node.recognitionIssues[0] : `命名异常 ${node.stats.namingIssueCount}`;
  group.appendChild(svgText(issueText, 14, 94, 11, "700", node.recognitionIssues.length ? "#b33f35" : "#6a6a60", 24));
  return group;
}

function matrixPreviewElement(matrix) {
  const group = svgEl("g", { transform: "translate(80, 500)" });
  group.appendChild(svgText(`状态矩阵 ${matrix.columnCount} 台外机 · ${matrix.rowCount} 项指标`, 0, 0, 13, "800"));
  const columns = matrix.columns.slice(0, 4);
  columns.forEach((column, index) => {
    group.appendChild(svgText(column.label, 130 + index * 90, 26, 11, "700", "#6a6a60"));
  });
  matrix.rows.slice(0, 4).forEach((row, rowIndex) => {
    group.appendChild(svgText(row.metric, 0, 52 + rowIndex * 24, 11, "700"));
    columns.forEach((column, columnIndex) => {
      const cell = row.cells[column.id];
      group.appendChild(svgText(cell ? cell.standardName || cell.rawName : "-", 130 + columnIndex * 90, 52 + rowIndex * 24, 11));
    });
  });
  return group;
}

function edgeElement(source, target, edge) {
  const route = smoothRouteBetweenCards(source.position, target.position, 210, 116, 42 + edgeIndexOffset(edge.id));
  const path = svgEl("path", {
    d: route.path,
    class: `edge-path ${edge.supportCount ? "" : "weak"}`,
    "marker-end": "url(#arrow)",
  });
  const title = svgEl("title");
  title.textContent = `${edge.label} · 原始连线 ${edge.supportCount}`;
  path.appendChild(title);
  return path;
}

function overviewNodeElement(node) {
  const group = svgEl("g", {
    class: `canvas-node ${node.tabId === state.selectedTabId ? "active" : ""} ${node.stats.namingIssueCount ? "issue" : ""}`,
    transform: `translate(${node.position.x}, ${node.position.y})`,
  });
  group.addEventListener("pointerdown", (event) => startCanvasNodeDrag(event, node, 210, 116));
  group.addEventListener("click", () => {
    if (consumeSuppressedClick()) return;
    canvasActions.selectTab(node.tabId);
  });
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
        canvasActions.locatePoint(node.pointId);
      } else {
        state.selectedTabId = node.tabId;
        canvasActions.renderAll();
      }
    });
    svg.appendChild(dot);
  }
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

function smoothRouteBetweenCards(sourcePosition, targetPosition, width, height, offset) {
  const sourceCenter = {
    x: sourcePosition.x + width / 2,
    y: sourcePosition.y + height / 2,
  };
  const targetCenter = {
    x: targetPosition.x + width / 2,
    y: targetPosition.y + height / 2,
  };
  const dx = targetCenter.x - sourceCenter.x;
  const dy = targetCenter.y - sourceCenter.y;
  const horizontal = Math.abs(dx) >= Math.abs(dy) * 0.8;
  if (horizontal) {
    const forward = dx >= 0;
    const start = anchor(sourcePosition, width, height, forward ? "right" : "left");
    const end = anchor(targetPosition, width, height, forward ? "left" : "right");
    const bend = Math.max(70, Math.abs(end.x - start.x) * 0.45);
    const sign = forward ? 1 : -1;
    return {
      path: `M ${start.x} ${start.y} C ${start.x + sign * bend} ${start.y}, ${end.x - sign * bend} ${end.y}, ${end.x} ${end.y}`,
    };
  }
  const downward = dy >= 0;
  const start = anchor(sourcePosition, width, height, downward ? "bottom" : "top");
  const end = anchor(targetPosition, width, height, downward ? "top" : "bottom");
  const bend = Math.max(70, Math.abs(end.y - start.y) * 0.55 + offset);
  const sign = downward ? 1 : -1;
  return {
    path: `M ${start.x} ${start.y} C ${start.x} ${start.y + sign * bend}, ${end.x} ${end.y - sign * bend}, ${end.x} ${end.y}`,
  };
}

function anchor(position, width, height, side) {
  if (side === "left") return { x: position.x, y: position.y + height / 2 };
  if (side === "right") return { x: position.x + width, y: position.y + height / 2 };
  if (side === "top") return { x: position.x + width / 2, y: position.y };
  return { x: position.x + width / 2, y: position.y + height };
}

function edgeIndexOffset(edgeId) {
  const digits = String(edgeId).match(/\d+/);
  return digits ? Number(digits[0]) % 7 * 8 : 0;
}
