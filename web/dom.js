export const els = {
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
  pasteButton: document.querySelector("#paste-button"),
  pasteDialog: document.querySelector("#paste-dialog"),
  pasteTextarea: document.querySelector("#paste-textarea"),
  pasteSubmit: document.querySelector("#paste-submit"),
  pasteClose: document.querySelector("#paste-close"),
  pasteCancel: document.querySelector("#paste-cancel"),
  backButton: document.querySelector("#back-button"),
  edgeModeControls: document.querySelector("#edge-mode-controls"),
};

export const KIND_COLOR = {
  boundary: "#2f6f9f",
  communication: "#7555a5",
  control: "#317d55",
  schedule: "#c47a21",
  alarm: "#b33f35",
  output: "#155c42",
  unknown: "#88877f",
};

export function appendDefs(svg) {
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

export function svgText(text, x, y, size = 12, weight = "500", fill = "#20211e", maxChars = 22) {
  const node = svgEl("text", { x, y, fill, "font-size": size, "font-weight": weight });
  node.textContent = text.length > maxChars ? `${text.slice(0, maxChars - 1)}…` : text;
  return node;
}

export function svgEl(tag, attrs = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attrs)) {
    element.setAttribute(key, value);
  }
  return element;
}

export function clearSvg(svg) {
  while (svg.firstChild) svg.removeChild(svg.firstChild);
}

export function setStatus(text) {
  els.statusText.textContent = text;
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
