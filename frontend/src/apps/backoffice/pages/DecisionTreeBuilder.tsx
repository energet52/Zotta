import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  addEdge,
  Panel,
  type Connection,
  type Edge,
  type Node,
  type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  GitBranch,
  Shield,
  BarChart3,
  ClipboardCheck,
  Save,
  CheckCircle,
  AlertTriangle,
  Play,
  Plus,
  ArrowLeft,
  Trash2,
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../../../api/client';

import { ConditionNode } from '../components/tree/ConditionNode';
import { StrategyNode } from '../components/tree/StrategyNode';
import { ScorecardGateNode } from '../components/tree/ScorecardGateNode';
import { AssessmentNode } from '../components/tree/AssessmentNode';
import { StartNode } from '../components/tree/StartNode';

const nodeTypes: NodeTypes = {
  condition: ConditionNode,
  strategy: StrategyNode,
  scorecardGate: ScorecardGateNode,
  assessment: AssessmentNode,
  annotation: StartNode,
};

interface ValidationError {
  severity: string;
  node_key: string | null;
  code: string;
  message: string;
}

interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationError[];
  stats: Record<string, number>;
}

interface TreeNode {
  id: number;
  node_key: string;
  node_type: string;
  label: string | null;
  condition_type: string | null;
  attribute: string | null;
  operator: string | null;
  branches: Record<string, unknown> | null;
  strategy_id: number | null;
  strategy_params: Record<string, unknown> | null;
  parent_node_id: number | null;
  branch_label: string | null;
  is_root: boolean;
  position_x: number;
  position_y: number;
  scorecard_id: number | null;
  null_branch: string | null;
  compound_conditions: Array<Record<string, unknown>> | null;
  compound_logic: string | null;
}

interface DecisionTree {
  id: number;
  product_id: number;
  name: string;
  description: string | null;
  version: number;
  status: string;
  default_strategy_id: number | null;
  nodes: TreeNode[];
  created_at: string;
  updated_at: string;
}

interface Strategy {
  id: number;
  name: string;
  evaluation_mode: string;
  status: string;
  version: number;
}

export default function DecisionTreeBuilder() {
  const { id: routeId, treeId: routeTreeId } = useParams<{ id?: string; treeId?: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([] as Node[]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([] as Edge[]);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [showValidation, setShowValidation] = useState(false);
  const [treeId, setTreeId] = useState<number | null>(routeTreeId ? Number(routeTreeId) : null);

  const enteredViaTree = !!routeTreeId;
  const productId = routeId;

  const { data: singleTree } = useQuery({
    queryKey: ['decision-tree', routeTreeId],
    queryFn: async () => {
      const res = await api.get(`/decision-trees/${routeTreeId}`);
      return res.data as DecisionTree;
    },
    enabled: enteredViaTree,
  });

  const resolvedProductId = enteredViaTree ? singleTree?.product_id?.toString() : productId;

  const { data: trees } = useQuery({
    queryKey: ['decision-trees', resolvedProductId],
    queryFn: async () => {
      const res = await api.get(`/decision-trees?product_id=${resolvedProductId}`);
      return res.data as DecisionTree[];
    },
    enabled: !!resolvedProductId,
  });

  const { data: strategies } = useQuery({
    queryKey: ['strategies'],
    queryFn: async () => {
      const res = await api.get('/strategies');
      return res.data as Strategy[];
    },
  });

  const activeTree = useMemo(() => {
    if (!trees) return null;
    if (treeId) return trees.find((t) => t.id === treeId) || null;
    return trees.find((t) => t.status === 'active') || trees[0] || null;
  }, [trees, treeId]);

  useEffect(() => {
    if (!activeTree) return;
    setTreeId(activeTree.id);
    const { flowNodes, flowEdges } = convertTreeToFlow(activeTree.nodes);
    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [activeTree, setNodes, setEdges]);

  const onConnect = useCallback(
    (params: Connection) => {
      const sourceNode = nodes.find((n) => n.id === params.source);
      const sourceData = sourceNode?.data as Record<string, unknown> | undefined;
      const branches = sourceData?.branches as Record<string, unknown> | undefined;
      const branchKeys = branches ? Object.keys(branches) : [];

      const existingLabels = edges
        .filter((e) => e.source === params.source)
        .map((e) => e.label as string)
        .filter(Boolean);

      if (branchKeys.length > 0) {
        const available = branchKeys.filter((k) => !existingLabels.includes(k));
        if (available.length === 0) return;
        setEdges((eds) => addEdge({
          ...params,
          label: available[0],
          animated: true,
          style: { strokeWidth: 2 },
        }, eds));
      } else {
        if (existingLabels.length > 0) return;
        setEdges((eds) => addEdge({
          ...params,
          animated: true,
          style: { strokeWidth: 2 },
        }, eds));
      }
    },
    [setEdges, nodes, edges],
  );

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!activeTree) return;
      const nodePayload = convertFlowToNodes(nodes, edges);
      await api.put(`/decision-trees/${activeTree.id}`, {
        nodes: nodePayload,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decision-trees'] });
    },
  });

  const validateMutation = useMutation({
    mutationFn: async () => {
      if (!activeTree) return null;
      const res = await api.post(`/decision-trees/${activeTree.id}/validate`);
      return res.data as ValidationResult;
    },
    onSuccess: (data) => {
      if (data) {
        setValidationResult(data);
        setShowValidation(true);
      }
    },
  });

  const activateMutation = useMutation({
    mutationFn: async () => {
      if (!activeTree) return;
      await api.post(`/decision-trees/${activeTree.id}/activate`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decision-trees'] });
    },
  });

  const createTreeMutation = useMutation({
    mutationFn: async () => {
      if (!resolvedProductId) throw new Error('No product selected');
      const res = await api.post('/decision-trees', {
        product_id: Number(resolvedProductId),
        name: `Decision Tree v1`,
        description: 'New decision tree',
        nodes: [],
      });
      return res.data as DecisionTree;
    },
    onSuccess: (data) => {
      setTreeId(data.id);
      queryClient.invalidateQueries({ queryKey: ['decision-trees'] });
    },
  });

  const addNode = useCallback(
    (type: 'condition' | 'strategy' | 'scorecardGate' | 'assessment') => {
      const newKey = `node_${Date.now()}`;
      const centerX = 250;
      const centerY = nodes.length * 120 + 50;

      const labels: Record<string, string> = {
        condition: 'New Condition',
        strategy: 'Assign Strategy',
        scorecardGate: 'Score Gate',
        assessment: 'Assessment',
      };

      const nodeData: Record<string, unknown> = {
        label: labels[type] || type,
        attribute: '',
        conditionType: 'binary',
        branches: {},
        strategyId: null,
        strategyName: '',
        assessmentId: null,
        scorecardId: null,
        nodeKey: newKey,
      };

      const newNode: Node = {
        id: newKey,
        type,
        position: { x: centerX, y: centerY },
        data: nodeData,
      };

      setNodes((nds) => [...nds, newNode]);
    },
    [nodes, setNodes],
  );

  const updateNodeData = useCallback(
    (nodeId: string, updates: Record<string, unknown>) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId ? { ...n, data: { ...n.data, ...updates } } : n,
        ),
      );
    },
    [setNodes],
  );

  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: {
          ...n.data,
          onDataChange: updateNodeData,
          assessmentOptions: (strategies || [])
            .flatMap((s) => (s as unknown as { assessments?: Array<{ id: number; name: string; rules?: unknown[] }> }).assessments || [])
            .map((a) => ({ id: a.id, name: a.name, ruleCount: (a.rules || []).length })),
        },
      })),
    );
  }, [updateNodeData, strategies, setNodes]);

  const onEdgeDoubleClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      const sourceNode = nodes.find((n) => n.id === edge.source);
      const sourceData = sourceNode?.data as Record<string, unknown> | undefined;
      const branches = sourceData?.branches as Record<string, unknown> | undefined;
      const branchKeys = branches ? Object.keys(branches) : [];

      let newLabel: string | null = null;
      if (branchKeys.length > 0) {
        newLabel = window.prompt(
          `Change branch label.\nAvailable: ${branchKeys.join(', ')}\n\nCurrent: "${edge.label || ''}"`,
          (edge.label as string) || '',
        );
      } else {
        newLabel = window.prompt('Edit branch label:', (edge.label as string) || '');
      }
      if (newLabel !== null) {
        setEdges((eds) => eds.map((e) => e.id === edge.id ? { ...e, label: newLabel || undefined } : e));
      }
    },
    [nodes, setEdges],
  );

  const deleteSelectedNode = useCallback(() => {
    if (!selectedNode) return;
    setNodes((nds) => nds.filter((n) => n.id !== selectedNode));
    setEdges((eds) => eds.filter((e) => e.source !== selectedNode && e.target !== selectedNode));
    setSelectedNode(null);
  }, [selectedNode, setNodes, setEdges]);

  return (
    <div className="h-screen flex flex-col" style={{ background: 'var(--color-bg)' }}>
      {/* Toolbar */}
      <div
        className="flex items-center justify-between px-4 py-2 border-b"
        style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}
      >
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(enteredViaTree ? '/backoffice/decision-trees' : `/backoffice/products/${productId}`)}
            className="p-1.5 rounded hover:bg-[var(--color-bg)] transition-colors"
          >
            <ArrowLeft size={18} className="text-[var(--color-text-secondary)]" />
          </button>
          <div>
            <h1 className="text-base font-semibold text-[var(--color-text)]">
              Decision Tree Builder
            </h1>
            <p className="text-xs text-[var(--color-text-secondary)]">
              {activeTree ? `${activeTree.name} v${activeTree.version} — ${activeTree.status}` : 'No tree configured'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {!activeTree && (
            <button
              onClick={() => createTreeMutation.mutate()}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded bg-blue-500 text-white hover:bg-blue-600 transition-colors"
            >
              <Plus size={14} /> Create Tree
            </button>
          )}

          {activeTree && (
            <>
              <button
                onClick={() => saveMutation.mutate()}
                disabled={saveMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
              >
                <Save size={14} /> Save
              </button>
              <button
                onClick={() => validateMutation.mutate()}
                disabled={validateMutation.isPending}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
              >
                <CheckCircle size={14} /> Validate
              </button>
              {activeTree.status !== 'active' && (
                <button
                  onClick={() => activateMutation.mutate()}
                  disabled={activateMutation.isPending}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded bg-emerald-500 text-white hover:bg-emerald-600 transition-colors"
                >
                  <Play size={14} /> Activate
                </button>
              )}
              {selectedNode && (
                <button
                  onClick={deleteSelectedNode}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded bg-red-500 text-white hover:bg-red-600 transition-colors"
                >
                  <Trash2 size={14} /> Delete
                </button>
              )}
            </>
          )}
        </div>
      </div>

      <div className="flex-1 flex">
        {/* Node Palette */}
        {activeTree && (
          <div
            className="w-48 border-r p-3 space-y-2 overflow-y-auto"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}
          >
            <p className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider mb-3">
              Add Node
            </p>
            <button
              onClick={() => addNode('condition')}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
            >
              <GitBranch size={14} className="text-blue-500" /> Condition
            </button>
            <button
              onClick={() => addNode('strategy')}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
            >
              <Shield size={14} className="text-emerald-500" /> Strategy
            </button>
            <button
              onClick={() => addNode('assessment')}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
            >
              <ClipboardCheck size={14} className="text-orange-500" /> Assessment
            </button>
            <button
              onClick={() => addNode('scorecardGate')}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm rounded border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
            >
              <BarChart3 size={14} className="text-purple-500" /> Scorecard Gate
            </button>

            {strategies && strategies.length > 0 && (
              <>
                <p className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider mt-4 mb-2">
                  Strategies
                </p>
                <div className="space-y-1 max-h-64 overflow-y-auto">
                  {strategies
                    .filter((s) => s.status !== 'archived')
                    .map((s) => (
                      <div
                        key={s.id}
                        className="px-2 py-1.5 text-xs rounded border border-[var(--color-border)] text-[var(--color-text)]"
                      >
                        <div className="font-medium truncate">{s.name}</div>
                        <div className="text-[var(--color-text-secondary)]">
                          v{s.version} · {s.evaluation_mode}
                        </div>
                      </div>
                    ))}
                </div>
              </>
            )}
          </div>
        )}

        {/* Canvas */}
        <div className="flex-1" ref={reactFlowWrapper}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onEdgeDoubleClick={onEdgeDoubleClick}
            onNodeClick={(_, node) => setSelectedNode(node.id)}
            onPaneClick={() => setSelectedNode(null)}
            nodeTypes={nodeTypes}
            fitView
            snapToGrid
            snapGrid={[15, 15]}
            deleteKeyCode="Backspace"
          >
            <Controls />
            <MiniMap
              nodeStrokeWidth={3}
              zoomable
              pannable
              style={{ background: 'var(--color-surface)' }}
            />
            <Background variant={BackgroundVariant.Dots} gap={16} size={1} />

            {!activeTree && (
              <Panel position="top-center">
                <div
                  className="mt-20 px-4 sm:px-6 py-4 rounded-lg border text-center"
                  style={{
                    background: 'var(--color-surface)',
                    borderColor: 'var(--color-border)',
                  }}
                >
                  <GitBranch size={32} className="mx-auto mb-2 text-[var(--color-text-secondary)]" />
                  <p className="text-sm font-medium text-[var(--color-text)]">No Decision Tree</p>
                  <p className="text-xs text-[var(--color-text-secondary)] mt-1">
                    This product uses the default single-strategy path.
                    <br />
                    Create a tree to enable multi-strategy routing.
                  </p>
                </div>
              </Panel>
            )}
          </ReactFlow>
        </div>

        {/* Validation Panel */}
        {showValidation && validationResult && (
          <div
            className="w-72 border-l p-3 overflow-y-auto"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}
          >
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">
                Validation
              </p>
              <button
                onClick={() => setShowValidation(false)}
                className="text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
              >
                Close
              </button>
            </div>

            <div
              className={`px-3 py-2 rounded-lg mb-3 text-sm font-medium ${
                validationResult.valid
                  ? 'bg-emerald-500/10 text-emerald-600'
                  : 'bg-red-500/10 text-red-600'
              }`}
            >
              {validationResult.valid ? 'Tree is valid' : `${validationResult.errors.length} error(s)`}
            </div>

            {validationResult.stats && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-3">
                {Object.entries(validationResult.stats).map(([k, v]) => (
                  <div key={k} className="px-2 py-1 rounded bg-[var(--color-bg)] text-xs">
                    <div className="text-[var(--color-text-secondary)]">{k.replace(/_/g, ' ')}</div>
                    <div className="font-medium text-[var(--color-text)]">{v}</div>
                  </div>
                ))}
              </div>
            )}

            {validationResult.errors.map((e, i) => (
              <div key={i} className="flex items-start gap-2 mb-2 px-2 py-1.5 rounded bg-red-500/5">
                <AlertTriangle size={12} className="text-red-500 mt-0.5 shrink-0" />
                <div className="text-xs">
                  <span className="font-medium text-red-600">{e.code}</span>
                  {e.node_key && (
                    <span className="text-[var(--color-text-secondary)]"> @ {e.node_key}</span>
                  )}
                  <p className="text-[var(--color-text-secondary)] mt-0.5">{e.message}</p>
                </div>
              </div>
            ))}

            {validationResult.warnings.map((w, i) => (
              <div key={i} className="flex items-start gap-2 mb-2 px-2 py-1.5 rounded bg-amber-500/5">
                <AlertTriangle size={12} className="text-amber-500 mt-0.5 shrink-0" />
                <div className="text-xs">
                  <span className="font-medium text-amber-600">{w.code}</span>
                  {w.node_key && (
                    <span className="text-[var(--color-text-secondary)]"> @ {w.node_key}</span>
                  )}
                  <p className="text-[var(--color-text-secondary)] mt-0.5">{w.message}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function convertTreeToFlow(treeNodes: TreeNode[]): { flowNodes: Node[]; flowEdges: Edge[] } {
  const flowNodes: Node[] = treeNodes.map((n) => {
    let type = 'condition';
    if (n.node_type === 'strategy') type = 'strategy';
    else if (n.node_type === 'assessment') type = 'assessment';
    else if (n.node_type === 'scorecard_gate') type = 'scorecardGate';
    else if (n.node_type === 'annotation') type = 'annotation';

    return {
      id: n.node_key,
      type,
      position: { x: n.position_x, y: n.position_y },
      data: {
        label: n.label || n.node_key,
        attribute: n.attribute,
        conditionType: n.condition_type,
        operator: n.operator,
        branches: n.branches || {},
        strategyId: n.strategy_id,
        strategyParams: n.strategy_params,
        assessmentId: (n as unknown as Record<string, unknown>).assessment_id || null,
        scorecardId: n.scorecard_id,
        nullBranch: n.null_branch,
        nodeKey: n.node_key,
        dbId: n.id,
      },
    };
  });

  const idToKey: Record<number, string> = {};
  treeNodes.forEach((n) => {
    idToKey[n.id] = n.node_key;
  });

  const flowEdges: Edge[] = treeNodes
    .filter((n) => n.parent_node_id !== null)
    .map((n) => ({
      id: `e-${idToKey[n.parent_node_id!]}-${n.node_key}`,
      source: idToKey[n.parent_node_id!] || '',
      target: n.node_key,
      label: n.branch_label || undefined,
      animated: true,
    }))
    .filter((e) => e.source !== '');

  return { flowNodes, flowEdges };
}

function convertFlowToNodes(
  flowNodes: Node[],
  flowEdges: Edge[],
): Array<Record<string, unknown>> {
  const parentMap: Record<string, { parentKey: string; branchLabel: string }> = {};
  flowEdges.forEach((e) => {
    parentMap[e.target] = {
      parentKey: e.source,
      branchLabel: (e.label as string) || '',
    };
  });

  const roots = flowNodes.filter((n) => !parentMap[n.id]);

  return flowNodes.map((n) => {
    const data = n.data as Record<string, unknown>;
    const parent = parentMap[n.id];
    const isRoot = roots.includes(n);

    return {
      node_key: n.id,
      node_type: n.type === 'scorecardGate' ? 'scorecard_gate' : n.type || 'condition',
      label: data.label || null,
      condition_type: data.conditionType || null,
      attribute: data.attribute || null,
      operator: data.operator || null,
      branches: data.branches || null,
      compound_conditions: data.compoundConditions || null,
      compound_logic: data.compoundLogic || null,
      strategy_id: data.strategyId || null,
      strategy_params: data.strategyParams || null,
      assessment_id: data.assessmentId || null,
      null_branch: data.nullBranch || null,
      null_strategy_id: null,
      scorecard_id: data.scorecardId || null,
      parent_node_key: parent?.parentKey || null,
      branch_label: parent?.branchLabel || null,
      is_root: isRoot,
      position_x: n.position.x,
      position_y: n.position.y,
    };
  });
}
