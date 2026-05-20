import { els } from "./dom.js";
import { state } from "./state.js";

let renderCanvasCallback = () => {};

export function configureDrag(actions) {
  renderCanvasCallback = actions.renderCanvas;
}

export function startCanvasNodeDrag(event, node, width, height) {
  if (event.button !== 0) return;
  event.preventDefault();
  const point = svgPointFromEvent(event);
  state.drag = {
    node,
    width,
    height,
    offsetX: point.x - node.position.x,
    offsetY: point.y - node.position.y,
    startX: point.x,
    startY: point.y,
    moved: false,
  };
}

export function handleCanvasNodeDrag(event) {
  if (!state.drag) return;
  const point = svgPointFromEvent(event);
  const nextX = clamp(point.x - state.drag.offsetX, 24, 1120 - state.drag.width);
  const nextY = clamp(point.y - state.drag.offsetY, 24, 636 - state.drag.height);
  if (Math.abs(point.x - state.drag.startX) > 3 || Math.abs(point.y - state.drag.startY) > 3) {
    state.drag.moved = true;
  }
  state.drag.node.position.x = Math.round(nextX);
  state.drag.node.position.y = Math.round(nextY);
  requestCanvasRender();
}

export function finishCanvasNodeDrag() {
  if (!state.drag) return;
  if (state.drag.moved) {
    state.suppressNextClick = true;
    window.setTimeout(() => {
      state.suppressNextClick = false;
    }, 0);
  }
  state.drag = null;
}

export function consumeSuppressedClick() {
  if (!state.suppressNextClick) return false;
  state.suppressNextClick = false;
  return true;
}

function requestCanvasRender() {
  if (state.dragFrame) return;
  state.dragFrame = window.requestAnimationFrame(() => {
    state.dragFrame = null;
    renderCanvasCallback();
  });
}

function svgPointFromEvent(event) {
  const point = els.canvas.createSVGPoint();
  point.x = event.clientX;
  point.y = event.clientY;
  return point.matrixTransform(els.canvas.getScreenCTM().inverse());
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}
