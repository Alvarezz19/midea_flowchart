import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  Background,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow
} from '@xyflow/react';
import {
  AlertTriangle,
  Boxes,
  ChevronLeft,
  CircleDot,
  GitBranch,
  Layers,
  PanelRight,
  Search,
  Workflow
} from 'lucide-react';
import '@xyflow/react/dist/style.css';
import './styles.css';

const nodeTypes = {
  module: ModuleNode
};

function App() {
  const [manifest, setManifest] = useState(null);
  const [activeProjectId, setActiveProjectId] = useState('');
  const [diagram, setDiagram] = useState(null);
  const [view, setView] = useState({ type: 'overview', pageId: null });
  const [selected, setSelected] = useState(null);
  const [query, setQuery] = useState('');

  useEffect(() => {
    fetch('/data/manifest.json')
      .then((response) => response.json())
      .then((payload) => {
        setManifest(payload);
        setActiveProjectId(payload.projects[0]?.id ?? '');
      });
  }, []);

  useEffect(() => {
    const project = manifest?.projects.find((item) => item.id === activeProjectId);
    if (!project) return;
    fetch(project.path)
      .then((response) => response.json())
      .then((payload) => {
        setDiagram(payload);
        setView({ type: 'overview', pageId: null });
        setSelected(null);
      });
  }, [manifest, activeProjectId]);

  const projects = manifest?.projects ?? [];
  const activeProject = projects.find((item) => item.id === activeProjectId);
  const filteredProjects = projects.filter((project) =>
    `${project.family}${project.project}${project.profile}`.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <ReactFlowProvider>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="brand">
            <Workflow size={22} />
            <div>
              <h1>流程图工作台</h1>
              <span>控制程序抽象视图</span>
            </div>
          </div>
          <label className="search-box">
            <Search size={16} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="筛选项目" />
          </label>
          <div className="project-list">
            {filteredProjects.map((project) => (
              <button
                key={project.id}
                className={`project-item ${project.id === activeProjectId ? 'active' : ''}`}
                onClick={() => setActiveProjectId(project.id)}
              >
                <span className="project-family">{project.family}</span>
                <strong>{project.project}</strong>
                <span>{project.profile}</span>
              </button>
            ))}
          </div>
        </aside>

        <main className="main-panel">
          <TopBar
            diagram={diagram}
            activeProject={activeProject}
            view={view}
            onBack={() => {
              setView({ type: 'overview', pageId: null });
              setSelected(null);
            }}
          />
          <section className="content-grid">
            <div className="canvas-panel">
              {diagram ? (
                <DiagramCanvas
                  diagram={diagram}
                  view={view}
                  onOpenPage={(pageId) => {
                    setView({ type: 'page', pageId });
                    setSelected(null);
                  }}
                  onSelect={setSelected}
                />
              ) : (
                <div className="empty-state">正在读取图数据</div>
              )}
            </div>
            <DetailsPanel selected={selected} diagram={diagram} view={view} />
          </section>
        </main>
      </div>
    </ReactFlowProvider>
  );
}

function TopBar({ diagram, activeProject, view, onBack }) {
  const page = view.type === 'page' ? diagram?.pages?.[view.pageId] : null;
  return (
    <header className="topbar">
      <div className="breadcrumb">
        {view.type === 'page' && (
          <button className="icon-button" onClick={onBack} title="返回总览">
            <ChevronLeft size={18} />
          </button>
        )}
        <div>
          <h2>{page ? page.label : activeProject?.project ?? '项目'}</h2>
          <span>{page ? `${activeProject?.project} / 页面图` : `${activeProject?.family ?? ''} / 总览图`}</span>
        </div>
      </div>
      <div className="topbar-stats">
        <Metric label="Profile" value={diagram?.profile ?? '-'} />
        <Metric label="模块" value={page?.metrics.module_count ?? diagram?.overview.metrics.module_count ?? '-'} />
        <Metric label="连线" value={page?.metrics.edge_count ?? diagram?.overview.metrics.edge_count ?? '-'} />
      </div>
    </header>
  );
}

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DiagramCanvas({ diagram, view, onOpenPage, onSelect }) {
  const flow = useMemo(() => makeFlow(diagram, view), [diagram, view]);
  const { fitView } = useReactFlow();

  useEffect(() => {
    window.requestAnimationFrame(() => fitView({ padding: 0.18, duration: 250 }));
  }, [fitView, flow.nodes.length, view.type, view.pageId]);

  const handleNodeClick = useCallback(
    (_, node) => {
      onSelect(node.data.raw);
      if (view.type === 'overview' && node.data.raw.kind === 'tab') {
        onOpenPage(node.data.pageId);
      }
    },
    [onOpenPage, onSelect, view.type]
  );

  const handlePaneClick = useCallback(() => onSelect(null), [onSelect]);

  return (
    <ReactFlow
      nodes={flow.nodes}
      edges={flow.edges}
      nodeTypes={nodeTypes}
      fitView
      minZoom={0.25}
      maxZoom={1.6}
      onNodeClick={handleNodeClick}
      onPaneClick={handlePaneClick}
      proOptions={{ hideAttribution: true }}
    >
      <Background color="#d7dfec" gap={22} />
      <MiniMap pannable zoomable nodeStrokeWidth={3} />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}

function ModuleNode({ data, selected }) {
  const warningLevel = warningClass(data.raw);
  return (
    <div className={`module-node ${data.raw.kind} ${warningLevel} ${selected ? 'selected' : ''}`}>
      <Handle type="target" position={Position.Left} />
      <div className="module-heading">
        {iconForKind(data.raw.kind)}
        <strong>{data.label}</strong>
      </div>
      <div className="module-meta">
        <span>{data.primaryMetric}</span>
        {data.unmatched > 0 && (
          <span className="warning-pill">
            <AlertTriangle size={13} />
            {data.unmatched}
          </span>
        )}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

function DetailsPanel({ selected, diagram, view }) {
  const page = view.type === 'page' ? diagram?.pages?.[view.pageId] : null;
  const fallback = page
    ? {
        label: page.label,
        kind: 'page',
        source_node_count: page.metrics.source_node_count,
        edge_count: page.metrics.edge_count,
        unmatched_point_count: page.metrics.unmatched_point_count,
        compression_ratio: page.metrics.compression_ratio
      }
    : diagram
      ? {
          label: `${diagram.project} 总览`,
          kind: 'overview',
          source_node_count: diagram.trace.object_count,
          edge_count: diagram.overview.metrics.edge_count,
          unmatched_point_count: 0,
          compression_ratio: diagram.overview.metrics.compression_ratio
        }
      : null;
  const item = selected ?? fallback;

  return (
    <aside className="details-panel">
      <div className="details-title">
        <PanelRight size={18} />
        <span>详情</span>
      </div>
      {item ? (
        <div className="details-content">
          <h3>{item.label}</h3>
          <div className="detail-grid">
            <Metric label="类型" value={item.kind ?? '-'} />
            <Metric label="原始节点" value={item.source_node_count ?? item.node_count ?? '-'} />
            <Metric label="未匹配点位" value={item.unmatched_point_count ?? 0} />
            <Metric label="压缩率" value={item.compression_ratio ?? '-'} />
          </div>
          {item.type_counts && <TypeCounts counts={item.type_counts} />}
          {item.sample_points?.length > 0 && (
            <section>
              <h4>点位样例</h4>
              <div className="tag-list">
                {item.sample_points.map((point, index) => (
                  <span key={`${point}-${index}`}>{point}</span>
                ))}
              </div>
            </section>
          )}
          {item.source_node_ids?.length > 0 && (
            <section>
              <h4>追溯节点</h4>
              <code>{item.source_node_ids.slice(0, 24).join(', ')}</code>
            </section>
          )}
        </div>
      ) : (
        <div className="empty-state">选择一个模块查看详情</div>
      )}
    </aside>
  );
}

function TypeCounts({ counts }) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 8);
  return (
    <section>
      <h4>节点类型</h4>
      <div className="type-counts">
        {entries.map(([type, count]) => (
          <div key={type}>
            <span>{type}</span>
            <strong>{count}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

function makeFlow(diagram, view) {
  const source = view.type === 'overview' ? diagram.overview : diagram.pages[view.pageId];
  const nodes = source.nodes.map((item, index) => {
    const position = item.position ?? { x: (index % 4) * 320, y: Math.floor(index / 4) * 190 };
    return {
      id: item.id,
      type: 'module',
      position,
      data: {
        label: item.label,
        raw: item,
        pageId: view.type === 'overview' ? item.id.replace(/^tab:/, '') : null,
        unmatched: item.unmatched_point_count ?? 0,
        primaryMetric:
          item.kind === 'tab'
            ? `${item.node_count} 节点`
            : `${item.source_node_count ?? 0} 节点 / ${item.point_count ?? 0} 点位`
      }
    };
  });
  const edges = source.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.weight > 1 ? String(edge.weight) : undefined,
    animated: edge.weight >= 10,
    style: { strokeWidth: Math.min(1 + edge.weight / 8, 5) },
    markerEnd: { type: 'arrowclosed' }
  }));
  return { nodes, edges };
}

function iconForKind(kind) {
  if (kind === 'tab') return <Layers size={16} />;
  if (kind === 'subflow') return <Boxes size={16} />;
  if (kind === 'algorithm') return <GitBranch size={16} />;
  return <CircleDot size={16} />;
}

function warningClass(item) {
  const count = item.unmatched_point_count ?? 0;
  if (count > 10) return 'warn-high';
  if (count > 0) return 'warn-low';
  return '';
}

createRoot(document.getElementById('root')).render(<App />);
