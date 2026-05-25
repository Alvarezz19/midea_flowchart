export const state = {
  samples: [],
  data: null,
  selectedTabId: null,
  selectedPointId: null,
  selectedRawNodeId: null,
  selectedModuleId: null,
  view: "overview",
  edgeMode: "primary",
  drag: null,
  dragFrame: null,
  suppressNextClick: false,
};

export function findPoint(pointId) {
  for (const tab of state.data.tabs) {
    const point = tab.points.find((item) => item.id === pointId);
    if (point) return point;
  }
  return null;
}

export function findModuleByPoint(tabId, pointId) {
  const tab = state.data.tabs.find((item) => item.id === tabId);
  if (!tab || !tab.detailGraph) return null;
  return tab.detailGraph.nodes.find(
    (node) =>
      node.inputPointIds.includes(pointId) ||
      node.outputPointIds.includes(pointId) ||
      (node.softwarePointIds || []).includes(pointId)
  );
}

export function currentTab() {
  return state.data.tabs.find((item) => item.id === state.selectedTabId) || state.data.tabs[0];
}
