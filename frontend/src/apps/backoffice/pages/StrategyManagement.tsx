import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Shield,
  Plus,
  CheckCircle,
  CircleOff,
  Archive,
  GitBranch,
  BarChart3,
  AlertTriangle,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Search,
  Save,
  X,
  Trash2,
  Sparkles,
  HelpCircle,
  ClipboardCheck,
  ExternalLink,
  Undo2,
  Maximize2,
  Minimize2,
  Inbox,
} from 'lucide-react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Node,
  type Edge,
  type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { ConditionNode } from '../components/tree/ConditionNode';
import { StrategyNode } from '../components/tree/StrategyNode';
import { ScorecardGateNode } from '../components/tree/ScorecardGateNode';
import { AssessmentNode } from '../components/tree/AssessmentNode';
import { StartNode } from '../components/tree/StartNode';
import api from '../../../api/client';
import { adminApi } from '../../../api/endpoints';

const treeNodeTypes: NodeTypes = {
  condition: ConditionNode,
  strategy: StrategyNode,
  scorecardGate: ScorecardGateNode,
  assessment: AssessmentNode,
  annotation: StartNode,
};

interface RuleEntry {
  rule_id: string;
  name: string;
  field: string;
  operator: string;
  threshold: string | number | boolean | null;
  severity: string;
  outcome: string;
  reason_code: string;
  enabled: boolean;
  weight?: number;
  message?: string;
  action?: string;
  fail_on_null?: boolean;
}

interface AssessmentEntry {
  id: number;
  strategy_id: number;
  name: string;
  description: string | null;
  rules: RuleEntry[] | null;
  score_cutoffs: Record<string, number> | null;
  status: string;
  created_at: string;
  updated_at: string;
}

interface Strategy {
  id: number;
  name: string;
  description: string | null;
  evaluation_mode: string;
  version: number;
  status: string;
  rules_config_id: number | null;
  scorecard_id: number | null;
  knock_out_rules: RuleEntry[] | null;
  overlay_rules: RuleEntry[] | null;
  score_cutoffs: Record<string, number> | null;
  terms_matrix: Record<string, unknown> | null;
  reason_code_map: Record<string, string> | null;
  concentration_limits: Array<{ dimension: string; limit: number }> | null;
  decision_tree_id: number | null;
  assessments: AssessmentEntry[];
  created_at: string;
  updated_at: string;
  is_emergency_override: boolean;
  is_fallback: boolean;
  change_description: string | null;
  parent_version_id: number | null;
  created_by: number | null;
  approved_by: number | null;
  activated_at: string | null;
}

interface GenerateResult {
  status: string;
  questions?: string[];
  refusal_reason?: string;
  rule?: Record<string, unknown>;
}

const statusColors: Record<string, string> = {
  draft: 'text-gray-500 bg-gray-500/10',
  under_review: 'text-blue-500 bg-blue-500/10',
  simulation_testing: 'text-purple-500 bg-purple-500/10',
  approved: 'text-emerald-500 bg-emerald-500/10',
  active: 'text-green-600 bg-green-500/10',
  archived: 'text-gray-400 bg-gray-400/10',
};

const modeIcons: Record<string, typeof Shield> = {
  sequential: Shield,
  dual_path: GitBranch,
  scoring: BarChart3,
  hybrid: AlertTriangle,
};

const EMPTY_RULE: RuleEntry = {
  rule_id: '',
  name: '',
  field: '',
  operator: 'gte',
  threshold: '',
  severity: 'hard',
  outcome: 'decline',
  reason_code: '',
  enabled: true,
};

const FIELD_GROUPS: { label: string; fields: { value: string; label: string }[] }[] = [
  {
    label: 'Applicant',
    fields: [
      { value: 'applicant_age', label: 'Applicant Age' },
      { value: 'employment_type', label: 'Employment Type' },
      { value: 'years_employed', label: 'Years Employed' },
      { value: 'employment_months', label: 'Employment Months' },
      { value: 'job_title', label: 'Job Title' },
      { value: 'national_id', label: 'National ID' },
    ],
  },
  {
    label: 'Financial',
    fields: [
      { value: 'monthly_income', label: 'Monthly Income' },
      { value: 'monthly_expenses', label: 'Monthly Expenses' },
      { value: 'existing_debt', label: 'Existing Debt' },
      { value: 'debt_to_income_ratio', label: 'Debt-to-Income Ratio' },
      { value: 'loan_to_income_ratio', label: 'Loan-to-Income Ratio' },
      { value: 'loan_amount_requested', label: 'Loan Amount Requested' },
      { value: 'term_months', label: 'Loan Term (Months)' },
    ],
  },
  {
    label: 'Bureau Credit Score',
    fields: [
      { value: 'credit_score', label: 'Credit Score (Bureau)' },
      { value: 'risk_band', label: 'Risk Band (A–E)' },
    ],
  },
  {
    label: 'Internal Scorecard',
    fields: [
      { value: 'scorecard_score', label: 'Scorecard Score (Internal)' },
    ],
  },
  {
    label: 'Verification & Flags',
    fields: [
      { value: 'is_id_verified', label: 'ID Verified' },
      { value: 'has_active_debt_bureau', label: 'Active Debt Bureau' },
      { value: 'has_court_judgment', label: 'Court Judgment' },
      { value: 'has_duplicate_within_30_days', label: 'Duplicate (30 days)' },
    ],
  },
];

const ALL_FIELDS = FIELD_GROUPS.flatMap((g) => g.fields);

function getFieldLabel(value: string): string {
  return ALL_FIELDS.find((f) => f.value === value)?.label || value;
}

const CATEGORICAL_VALUES: Record<string, { value: string; label: string }[]> = {
  employment_type: [
    { value: 'employed', label: 'Employed' },
    { value: 'self_employed', label: 'Self-Employed' },
    { value: 'contract', label: 'Contract' },
    { value: 'unemployed', label: 'Unemployed' },
    { value: 'retired', label: 'Retired' },
  ],
  risk_band: [
    { value: 'A', label: 'A (Best)' },
    { value: 'B', label: 'B' },
    { value: 'C', label: 'C' },
    { value: 'D', label: 'D' },
    { value: 'E', label: 'E (Worst)' },
  ],
  is_id_verified: [
    { value: 'true', label: 'Yes (Verified)' },
    { value: 'false', label: 'No (Not Verified)' },
  ],
  has_active_debt_bureau: [
    { value: 'true', label: 'Yes' },
    { value: 'false', label: 'No' },
  ],
  has_court_judgment: [
    { value: 'true', label: 'Yes' },
    { value: 'false', label: 'No' },
  ],
  has_duplicate_within_30_days: [
    { value: 'true', label: 'Yes' },
    { value: 'false', label: 'No' },
  ],
};

const OPERATORS = [
  { value: 'gte', label: '>=' },
  { value: 'lte', label: '<=' },
  { value: 'gt', label: '>' },
  { value: 'lt', label: '<' },
  { value: 'eq', label: '=' },
  { value: 'neq', label: '!=' },
  { value: 'in', label: 'in' },
  { value: 'not_in', label: 'not in' },
  { value: 'between', label: 'between' },
];

export default function StrategyManagement() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [createForm, setCreateForm] = useState({
    name: '',
    description: '',
    evaluation_mode: 'dual_path',
  });

  const { data: strategies = [], isLoading } = useQuery({
    queryKey: ['strategies', statusFilter],
    queryFn: async () => {
      const params = statusFilter ? `?status=${statusFilter}` : '';
      const res = await api.get(`/strategies${params}`);
      return res.data as Strategy[];
    },
  });

  const { data: products = [] } = useQuery({
    queryKey: ['products-for-strategies'],
    queryFn: async () => {
      try {
        const res = await api.get('/admin/products');
        return res.data as { id: number; name: string; default_strategy_id?: number | null; decision_tree_id?: number | null }[];
      } catch {
        return [];
      }
    },
  });

  const fallbackStrategy = strategies.find((s) => s.is_fallback);

  const getLinkedProducts = (s: Strategy) => {
    const directlyLinked = products.filter((p) => p.default_strategy_id === s.id);
    if (s.is_fallback) {
      const unassigned = products.filter((p) => !p.default_strategy_id);
      return { direct: directlyLinked, defaulted: unassigned };
    }
    return { direct: directlyLinked, defaulted: [] };
  };

  const createMutation = useMutation({
    mutationFn: async () => {
      const res = await api.post('/strategies', createForm);
      return res.data as Strategy;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      setShowCreate(false);
      setCreateForm({ name: '', description: '', evaluation_mode: 'dual_path' });
      setEditId(data.id);
    },
  });

  const activateMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/strategies/${id}/activate`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['strategies'] }),
  });

  const deactivateMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/strategies/${id}/deactivate`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['strategies'] }),
  });

  const archiveMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/strategies/${id}/archive`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['strategies'] }),
  });

  const unarchiveMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.post(`/strategies/${id}/unarchive`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['strategies'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/strategies/${id}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['strategies'] }),
  });

  const filtered = strategies.filter(
    (s) =>
      s.name.toLowerCase().includes(search.toLowerCase()) ||
      (s.description || '').toLowerCase().includes(search.toLowerCase()),
  );
  const customStrategies = filtered.filter((s) => !s.is_fallback);
  const fallbackStrategies = filtered.filter((s) => s.is_fallback);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[var(--color-text)]">Decision Strategies</h1>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">
            Manage evaluation strategies for loan decisioning
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-blue-500 text-white hover:bg-blue-600 transition-colors"
          data-testid="btn-new-strategy"
        >
          <Plus size={16} /> New Strategy
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-md">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-secondary)]"
          />
          <input
            type="text"
            placeholder="Search strategies..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            data-testid="search-strategies"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
          data-testid="filter-status"
        >
          <option value="">All statuses</option>
          <option value="draft">Draft</option>
          <option value="active">Active</option>
          <option value="approved">Approved</option>
          <option value="archived">Archived</option>
        </select>
      </div>

      {/* Create form */}
      {showCreate && (
        <div
          className="mb-4 p-4 rounded-lg border"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}
          data-testid="create-strategy-form"
        >
          <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">Create Strategy</h3>
          <div className="grid grid-cols-2 gap-3">
            <input
              placeholder="Strategy name"
              value={createForm.name}
              onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
              className="px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)]"
              data-testid="input-strategy-name"
            />
            <input
              placeholder="Description (optional)"
              value={createForm.description}
              onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
              className="px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)]"
              data-testid="input-strategy-desc"
            />
          </div>
          <div className="flex items-center gap-2 mt-3">
            <button
              onClick={() => createMutation.mutate()}
              disabled={!createForm.name || createMutation.isPending}
              className="px-3 py-1.5 text-sm rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
              data-testid="btn-create-confirm"
            >
              Create
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-3 py-1.5 text-sm rounded border border-[var(--color-border)] text-[var(--color-text)]"
              data-testid="btn-create-cancel"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Strategy list */}
      <div className="space-y-2" data-testid="strategy-list">
        {isLoading && (
          <div className="text-center py-8 text-sm text-[var(--color-text-secondary)]">Loading...</div>
        )}
        {!isLoading && filtered.length === 0 && (
          <div className="text-center py-12" data-testid="empty-state">
            <Shield size={40} className="mx-auto mb-3 text-[var(--color-text-secondary)]" />
            <p className="text-sm text-[var(--color-text)]">No strategies found</p>
            <p className="text-xs text-[var(--color-text-secondary)] mt-1">
              Create your first strategy to get started
            </p>
          </div>
        )}
        {[...customStrategies, ...fallbackStrategies].map((s, idx) => {
          const ModeIcon = modeIcons[s.evaluation_mode] || Shield;
          const isExpanded = editId === s.id;
          const linked = getLinkedProducts(s);
          const allLinked = [...linked.direct, ...linked.defaulted];
          const showFallbackDivider = s.is_fallback && idx === customStrategies.length && customStrategies.length > 0;
          return (
            <div key={s.id}>
            {showFallbackDivider && (
              <div className="flex items-center gap-3 my-4">
                <div className="flex-1 border-t" style={{ borderColor: 'var(--color-border)' }} />
                <span className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">Fallback Strategy</span>
                <div className="flex-1 border-t" style={{ borderColor: 'var(--color-border)' }} />
              </div>
            )}
            <div data-testid={`strategy-row-${s.id}`}>
              <div
                className={`flex items-center gap-4 px-4 py-3 rounded-lg border transition-colors cursor-pointer ${
                  isExpanded ? 'border-blue-500/50 bg-blue-500/5' : s.is_fallback ? 'border-dashed hover:border-blue-500/30' : 'hover:border-blue-500/30'
                }`}
                style={isExpanded ? {} : { borderColor: 'var(--color-border)', background: s.is_fallback ? 'var(--color-bg)' : 'var(--color-surface)' }}
                onClick={() => setEditId(isExpanded ? null : s.id)}
              >
                <div className="p-2 rounded-lg bg-[var(--color-bg)]">
                  <ModeIcon size={20} className={s.is_fallback ? 'text-gray-400' : 'text-blue-500'} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-[var(--color-text)] truncate">
                      {s.name}
                    </span>
                    <span className="text-xs text-[var(--color-text-secondary)]">v{s.version}</span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[s.status] || ''}`}
                    >
                      {s.status.replace(/_/g, ' ')}
                    </span>
                    {s.is_fallback && (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-gray-500/10 text-gray-400">
                        fallback
                      </span>
                    )}
                    {s.is_emergency_override && (
                      <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-500">
                        emergency
                      </span>
                    )}
                  </div>
                  {s.description && (
                    <p className="text-xs text-[var(--color-text-secondary)] mt-0.5 truncate">
                      {s.description}
                    </p>
                  )}
                  <div className="flex items-center gap-3 mt-1 text-xs text-[var(--color-text-secondary)]">
                    {(s.assessments || []).length > 0 && (
                      <span>{s.assessments.length} assessment{s.assessments.length !== 1 ? 's' : ''}</span>
                    )}
                    {s.decision_tree_id && <span>decision tree</span>}
                    {allLinked.length > 0 && (
                      <span className="text-emerald-500">
                        {linked.direct.map((p) => p.name).join(', ')}
                        {linked.direct.length > 0 && linked.defaulted.length > 0 && ', '}
                        {linked.defaulted.length > 0 && (
                          <span className="text-gray-400 italic">
                            {linked.defaulted.map((p) => p.name).join(', ')} (default)
                          </span>
                        )}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {s.status !== 'active' && s.status !== 'archived' && (
                    <button
                      onClick={(e) => { e.stopPropagation(); activateMutation.mutate(s.id); }}
                      className="p-1.5 rounded text-emerald-500 hover:bg-emerald-500/10"
                      title="Activate"
                      data-testid={`btn-activate-${s.id}`}
                    >
                      <CheckCircle size={14} />
                    </button>
                  )}
                  {s.status === 'active' && (
                    <button
                      onClick={(e) => { e.stopPropagation(); deactivateMutation.mutate(s.id); }}
                      className="p-1.5 rounded text-amber-500 hover:bg-amber-500/10"
                      title="Deactivate (return to draft)"
                      data-testid={`btn-deactivate-${s.id}`}
                    >
                      <CircleOff size={14} />
                    </button>
                  )}
                  {s.status !== 'archived' && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (window.confirm(`Archive strategy "${s.name}"?`)) {
                          archiveMutation.mutate(s.id);
                        }
                      }}
                      className="p-1.5 rounded text-gray-400 hover:bg-gray-400/10"
                      title="Archive"
                      data-testid={`btn-archive-${s.id}`}
                    >
                      <Archive size={14} />
                    </button>
                  )}
                  {s.status === 'archived' && (
                    <button
                      onClick={(e) => { e.stopPropagation(); unarchiveMutation.mutate(s.id); }}
                      className="p-1.5 rounded text-blue-400 hover:bg-blue-400/10"
                      title="Unarchive (restore to draft)"
                      data-testid={`btn-unarchive-${s.id}`}
                    >
                      <Undo2 size={14} />
                    </button>
                  )}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (window.confirm(`Permanently delete strategy "${s.name}"? This will also delete its decision tree and assessments.`)) {
                        deleteMutation.mutate(s.id);
                      }
                    }}
                    className="p-1.5 rounded text-red-400 hover:bg-red-400/10"
                    title="Delete permanently"
                    data-testid={`btn-delete-strategy-${s.id}`}
                  >
                    <Trash2 size={14} />
                  </button>
                  <ChevronRight
                    size={16}
                    className={`text-[var(--color-text-secondary)] transition-transform ${
                      isExpanded ? 'rotate-90' : ''
                    }`}
                  />
                </div>
              </div>

              {/* ── Inline Edit Panel ── */}
              {isExpanded && (
                <StrategyEditPanel
                  strategy={s}
                  onClose={() => setEditId(null)}
                  onSaved={() => queryClient.invalidateQueries({ queryKey: ['strategies'] })}
                />
              )}
            </div>
            </div>
          );
        })}
      </div>

    </div>
  );
}

/* ── Strategy Edit Panel ────────────────────────────────────────── */

function StrategyEditPanel({
  strategy,
  onClose,
  onSaved,
}: {
  strategy: Strategy;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEditable = strategy.status !== 'archived';

  const [name, setName] = useState(strategy.name);
  const [description, setDescription] = useState(strategy.description || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSaved(false);
    try {
      await api.put(`/strategies/${strategy.id}`, {
        name,
        description: description || null,
      });
      setSaved(true);
      onSaved();
      setTimeout(() => setSaved(false), 2000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Save failed';
      if (typeof err === 'object' && err !== null && 'response' in err) {
        const resp = (err as { response?: { data?: { detail?: string } } }).response;
        setError(resp?.data?.detail || msg);
      } else {
        setError(msg);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="mt-1 rounded-lg border p-4 space-y-4"
      style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}
      data-testid={`strategy-editor-${strategy.id}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--color-text)]">
          Edit Strategy — {strategy.name} v{strategy.version}
        </h3>
        <div className="flex items-center gap-2">
          {isEditable && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1 px-3 py-1.5 text-sm rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
              data-testid="btn-save-strategy"
            >
              <Save size={14} /> {saving ? 'Saving...' : saved ? 'Saved' : 'Save'}
            </button>
          )}
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-[var(--color-bg)]"
            data-testid="btn-close-editor"
          >
            <X size={16} className="text-[var(--color-text-secondary)]" />
          </button>
        </div>
      </div>

      {error && (
        <div className="px-3 py-2 rounded bg-red-500/10 text-red-500 text-sm" data-testid="edit-error">
          {error}
        </div>
      )}
      {saved && (
        <div className="px-3 py-2 rounded bg-emerald-500/10 text-emerald-500 text-sm">
          Strategy saved successfully
        </div>
      )}

      {!isEditable && (
        <div className="px-3 py-2 rounded bg-amber-500/10 text-amber-600 text-sm">
          This strategy is archived and cannot be edited.
        </div>
      )}

      {/* Basic info */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-[var(--color-text-secondary)] block mb-1">Name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            disabled={!isEditable}
            className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] disabled:opacity-50"
            data-testid="edit-name"
          />
        </div>
        <div>
          <label className="text-xs text-[var(--color-text-secondary)] block mb-1">Description</label>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            disabled={!isEditable}
            className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] disabled:opacity-50"
            data-testid="edit-description"
          />
        </div>
      </div>

      {/* Decision Tree */}
      {strategy.decision_tree_id ? (
        <EmbeddedTreeViewer treeId={strategy.decision_tree_id} strategyId={strategy.id} assessments={strategy.assessments || []} />
      ) : (
        <NoTreePlaceholder strategyId={strategy.id} onTreeCreated={onSaved} />
      )}

      {/* Assessments */}
      <AssessmentManager strategyId={strategy.id} assessments={strategy.assessments || []} editable={isEditable} onChanged={onSaved} />
    </div>
  );
}

/* ── Embedded Tree Viewer ───────────────────────────────────────── */

interface TreeNodeData {
  id: number;
  node_key: string;
  node_type: string;
  label: string | null;
  condition_type: string | null;
  attribute: string | null;
  operator: string | null;
  branches: Record<string, unknown> | null;
  strategy_id: number | null;
  assessment_id: number | null;
  parent_node_id: number | null;
  branch_label: string | null;
  is_root: boolean;
  position_x: number;
  position_y: number;
}

interface DecisionTreeData {
  id: number;
  name: string;
  status: string;
  nodes: TreeNodeData[];
}

function NoTreePlaceholder({ strategyId, onTreeCreated }: { strategyId: number; onTreeCreated: () => void }) {
  const [creating, setCreating] = useState(false);

  const createTree = async () => {
    setCreating(true);
    try {
      const productsResp = await api.get('/admin/products');
      const products = productsResp.data as Array<{ id: number }>;
      const productId = products[0]?.id || 1;

      const treeResp = await api.post('/decision-trees', {
        product_id: productId,
        name: `Strategy ${strategyId} Tree`,
        description: 'Decision tree for this strategy',
        nodes: [],
      });
      const tree = treeResp.data as { id: number };

      await api.put(`/strategies/${strategyId}`, {
        decision_tree_id: tree.id,
      });
      onTreeCreated();
    } finally {
      setCreating(false);
    }
  };

  return (
    <div data-testid="no-tree-placeholder">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase">
          Decision Tree
        </h4>
      </div>
      <div
        className="rounded-lg border px-4 py-6 text-center"
        style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)' }}
      >
        <GitBranch size={24} className="mx-auto mb-2 text-[var(--color-text-secondary)]" />
        <p className="text-xs text-[var(--color-text-secondary)] mb-3">
          No decision tree configured. Create one to define branching logic with assessments.
        </p>
        <button
          onClick={createTree}
          disabled={creating}
          className="flex items-center gap-1 mx-auto px-3 py-1.5 text-xs rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
          data-testid="btn-create-tree-for-strategy"
        >
          <Plus size={12} /> {creating ? 'Creating...' : 'Create Decision Tree'}
        </button>
      </div>
    </div>
  );
}

function EmbeddedTreeViewer({ treeId, strategyId, assessments }: { treeId: number; strategyId: number; assessments: AssessmentEntry[] }) {
  const queryClient = useQueryClient();

  const { data: tree } = useQuery({
    queryKey: ['decision-tree-embed', treeId],
    queryFn: async () => {
      const res = await api.get(`/decision-trees/${treeId}`);
      return res.data as DecisionTreeData;
    },
  });

  const [nodes, setNodes, onNodesChange] = useNodesState([] as Node[]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([] as Edge[]);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [treeSaved, setTreeSaved] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [editingEdge, setEditingEdge] = useState<{ id: string; x: number; y: number; branches: string[]; current: string; usedLabels: string[] } | null>(null);
  const [showAiGen, setShowAiGen] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResult, setAiResult] = useState<{ status: string; tree?: { nodes: Array<Record<string, unknown>>; assessment_names?: string[] }; explanation?: string; questions?: string[]; refusal_reason?: string } | null>(null);

  const assessmentOptions = useMemo(
    () => assessments.map((a) => ({ id: a.id, name: a.name, ruleCount: (a.rules || []).length })),
    [assessments],
  );

  const updateNodeData = useCallback(
    (nodeId: string, updates: Record<string, unknown>) => {
      setNodes((nds) =>
        nds.map((n) => n.id === nodeId ? { ...n, data: { ...n.data, ...updates } } : n),
      );
    },
    [setNodes],
  );

  useEffect(() => {
    if (!tree || !tree.nodes) return;
    const idToKey: Record<number, string> = {};
    tree.nodes.forEach((n) => { idToKey[n.id] = n.node_key; });

    const flowNodes: Node[] = tree.nodes.map((n) => {
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
          assessmentId: n.assessment_id,
          nodeKey: n.node_key,
          onDataChange: updateNodeData,
          assessmentOptions,
        },
      };
    });

    const flowEdges: Edge[] = tree.nodes
      .filter((n) => n.parent_node_id !== null)
      .map((n) => ({
        id: `e-${idToKey[n.parent_node_id!]}-${n.node_key}`,
        source: idToKey[n.parent_node_id!] || '',
        target: n.node_key,
        label: n.branch_label || undefined,
        animated: true,
      }))
      .filter((e) => e.source !== '');

    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [tree, assessmentOptions, updateNodeData, setNodes, setEdges]);

  useEffect(() => {
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, onDataChange: updateNodeData, assessmentOptions },
      })),
    );
  }, [updateNodeData, assessmentOptions, setNodes]);

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
        if (available.length === 0) {
          return;
        }
        setEdges((eds) => addEdge({
          ...params,
          label: available[0],
          animated: true,
          style: { strokeWidth: 2 },
        }, eds));
      } else {
        if (existingLabels.length > 0) {
          return;
        }
        setEdges((eds) => addEdge({
          ...params,
          animated: true,
          style: { strokeWidth: 2 },
        }, eds));
      }
    },
    [setEdges, nodes, edges],
  );

  const addNode = useCallback(
    (type: 'condition' | 'assessment') => {
      const key = `node_${Date.now()}`;
      const y = nodes.length * 120 + 50;
      setNodes((nds) => [
        ...nds,
        {
          id: key,
          type,
          position: { x: 250, y },
          data: {
            label: type === 'condition' ? 'New Condition' : 'Assessment',
            attribute: '',
            conditionType: 'binary',
            branches: {},
            assessmentId: null,
            nodeKey: key,
            onDataChange: updateNodeData,
            assessmentOptions,
          },
        },
      ]);
    },
    [nodes, setNodes, updateNodeData, assessmentOptions],
  );

  const deleteSelected = useCallback(() => {
    if (!selectedNode) return;
    setNodes((nds) => nds.filter((n) => n.id !== selectedNode));
    setEdges((eds) => eds.filter((e) => e.source !== selectedNode && e.target !== selectedNode));
    setSelectedNode(null);
  }, [selectedNode, setNodes, setEdges]);

  const handleSave = async () => {
    setSaving(true);
    setTreeSaved(false);
    try {
      const parentMap: Record<string, { parentKey: string; branchLabel: string }> = {};
      edges.forEach((e) => {
        parentMap[e.target] = { parentKey: e.source, branchLabel: (e.label as string) || '' };
      });
      const roots = nodes.filter((n) => !parentMap[n.id]);

      const payload = nodes.map((n) => {
        const d = n.data as Record<string, unknown>;
        const parent = parentMap[n.id];
        return {
          node_key: n.id,
          node_type: n.type === 'scorecardGate' ? 'scorecard_gate' : n.type || 'condition',
          label: d.label || null,
          condition_type: d.conditionType || null,
          attribute: d.attribute || null,
          operator: d.operator || null,
          branches: d.branches || null,
          strategy_id: d.strategyId || null,
          assessment_id: d.assessmentId || null,
          null_branch: d.nullBranch || null,
          scorecard_id: d.scorecardId || null,
          parent_node_key: parent?.parentKey || null,
          branch_label: parent?.branchLabel || null,
          is_root: roots.includes(n),
          position_x: n.position.x,
          position_y: n.position.y,
        };
      });

      await api.put(`/decision-trees/${treeId}`, { nodes: payload });
      queryClient.invalidateQueries({ queryKey: ['decision-tree-embed', treeId] });
      setTreeSaved(true);
      setTimeout(() => setTreeSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  const onEdgeDoubleClick = useCallback(
    (event: React.MouseEvent, edge: Edge) => {
      const sourceNode = nodes.find((n) => n.id === edge.source);
      const sourceData = sourceNode?.data as Record<string, unknown> | undefined;
      const branches = sourceData?.branches as Record<string, unknown> | undefined;
      const branchKeys = branches ? Object.keys(branches) : [];

      if (branchKeys.length > 0) {
        const usedByOthers = edges
          .filter((e) => e.source === edge.source && e.id !== edge.id)
          .map((e) => e.label as string)
          .filter(Boolean);

        setEditingEdge({
          id: edge.id,
          x: event.clientX,
          y: event.clientY,
          branches: branchKeys,
          current: (edge.label as string) || '',
          usedLabels: usedByOthers,
        });
      }
    },
    [nodes, edges],
  );

  const applyEdgeLabel = useCallback(
    (label: string) => {
      if (!editingEdge) return;
      setEdges((eds) =>
        eds.map((e) => {
          if (e.id === editingEdge.id) return { ...e, label: label || undefined };
          if (e.source === eds.find((x) => x.id === editingEdge.id)?.source && e.label === label) {
            return { ...e, label: undefined };
          }
          return e;
        }),
      );
      setEditingEdge(null);
    },
    [editingEdge, setEdges],
  );

  const handleAiGenerate = async () => {
    if (!aiPrompt.trim() || !treeId) return;
    setAiLoading(true);
    setAiResult(null);
    try {
      const res = await api.post(`/strategies/${strategyId}/generate-tree`, {
        prompt: aiPrompt,
      });
      setAiResult(res.data);
    } catch {
      setAiResult({ status: 'refused', refusal_reason: 'Failed to connect to AI service.' });
    } finally {
      setAiLoading(false);
    }
  };

  const applyAiTree = async () => {
    if (!aiResult?.tree?.nodes || !treeId) return;
    await api.put(`/decision-trees/${treeId}`, { nodes: aiResult.tree.nodes });

    if (aiResult.tree.assessment_names) {
      for (const name of aiResult.tree.assessment_names) {
        await api.post(`/assessments/from-template?strategy_id=${strategyId}&name=${encodeURIComponent(name)}`);
      }
    }

    queryClient.invalidateQueries({ queryKey: ['decision-tree-embed', treeId] });
    queryClient.invalidateQueries({ queryKey: ['strategies'] });
    setAiResult(null);
    setShowAiGen(false);
    setAiPrompt('');
  };

  const edgePicker = editingEdge && (
    <div
      className="fixed z-[100]"
      style={{ left: editingEdge.x, top: editingEdge.y }}
    >
      <div
        className="rounded-lg border shadow-xl p-2 min-w-[180px]"
        style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
      >
        <div className="text-[10px] font-semibold text-[var(--color-text-secondary)] uppercase mb-1.5 px-1">
          Select Branch
        </div>
        {editingEdge.branches.map((b) => {
          const isCurrent = b === editingEdge.current;
          const isUsed = editingEdge.usedLabels.includes(b);
          return (
            <button
              key={b}
              onClick={() => applyEdgeLabel(b)}
              className={`w-full text-left px-2.5 py-1.5 text-xs rounded transition-colors ${
                isCurrent
                  ? 'bg-blue-500/10 text-blue-500 font-medium'
                  : isUsed
                    ? 'text-amber-500 hover:bg-amber-500/5'
                    : 'text-[var(--color-text)] hover:bg-[var(--color-bg)]'
              }`}
            >
              {b}
              {isCurrent && <span className="ml-2 text-[10px] text-blue-400">(current)</span>}
              {isUsed && !isCurrent && <span className="ml-2 text-[10px] text-amber-400">(swap)</span>}
            </button>
          );
        })}
        <div className="border-t mt-1.5 pt-1.5" style={{ borderColor: 'var(--color-border)' }}>
          <button
            onClick={() => setEditingEdge(null)}
            className="w-full text-left px-2.5 py-1 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)] rounded hover:bg-[var(--color-bg)]"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );

  if (!tree) return null;

  const toolbar = (
    <div className="flex items-center gap-2">
      <button
        onClick={() => addNode('condition')}
        className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
      >
        <GitBranch size={11} className="text-blue-500" /> Condition
      </button>
      <button
        onClick={() => addNode('assessment')}
        className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
      >
        <ClipboardCheck size={11} className="text-orange-500" /> Assessment
      </button>
      {selectedNode && (
        <button
          onClick={deleteSelected}
          className="flex items-center gap-1 px-2 py-1 text-xs rounded bg-red-500 text-white hover:bg-red-600"
          data-testid="btn-delete-tree-node"
        >
          <Trash2 size={11} /> Delete
        </button>
      )}
      <button
        onClick={handleSave}
        disabled={saving}
        className="flex items-center gap-1 px-2.5 py-1 text-xs rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
        data-testid="btn-save-tree"
      >
        <Save size={11} /> {saving ? '...' : 'Save Tree'}
      </button>
      <button
        onClick={() => setShowAiGen(!showAiGen)}
        className={`flex items-center gap-1 px-2 py-1 text-xs rounded border transition-colors ${
          showAiGen ? 'border-purple-500 bg-purple-500/10 text-purple-500' : 'border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-bg)]'
        }`}
        data-testid="btn-ai-generate-tree"
      >
        <Sparkles size={11} /> AI Generate
      </button>
      <button
        onClick={() => setFullscreen(!fullscreen)}
        className="flex items-center gap-1 px-2 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
        data-testid="btn-fullscreen-tree"
      >
        {fullscreen ? <Minimize2 size={11} /> : <Maximize2 size={11} />}
        {fullscreen ? 'Exit' : 'Full Screen'}
      </button>
    </div>
  );

  const canvas = (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      onEdgeDoubleClick={onEdgeDoubleClick}
      onNodeClick={(_, node) => setSelectedNode(node.id)}
      onPaneClick={() => setSelectedNode(null)}
      deleteKeyCode="Backspace"
      nodeTypes={treeNodeTypes}
      fitView
      snapToGrid
      snapGrid={[15, 15]}
      minZoom={0.2}
      maxZoom={2}
    >
      <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
      <Controls />
      <MiniMap nodeStrokeWidth={3} style={{ background: 'var(--color-surface)', height: 80, width: 120 }} />
    </ReactFlow>
  );

  if (fullscreen) {
    return (
      <>
        <div data-testid="embedded-tree-section" />
        <div className="fixed inset-0 z-50 flex flex-col" style={{ background: 'var(--color-bg)' }}>
          <div
            className="flex items-center justify-between px-4 py-2 border-b"
            style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}
          >
            <div>
              <h2 className="text-sm font-semibold text-[var(--color-text)]">Decision Tree Builder</h2>
              <p className="text-xs text-[var(--color-text-secondary)]">
                {tree.name} — {nodes.length} nodes
                {treeSaved && <span className="ml-2 text-emerald-500">Saved</span>}
              </p>
            </div>
            {toolbar}
          </div>
          <div className="flex-1">{canvas}</div>
          {edgePicker}
        </div>
      </>
    );
  }

  return (
    <div data-testid="embedded-tree-section">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase">
            Decision Tree
          </h4>
          <p className="text-xs text-[var(--color-text-secondary)]">
            {tree.name} — {nodes.length} nodes
            {treeSaved && <span className="ml-2 text-emerald-500">Saved</span>}
          </p>
        </div>
        {toolbar}
      </div>

      {showAiGen && (
        <div className="mb-2 p-3 rounded-lg border border-purple-500/30 bg-purple-500/5 space-y-2">
          <div className="flex items-center gap-2">
            <Sparkles size={14} className="text-purple-500" />
            <span className="text-xs font-semibold text-purple-500 uppercase">AI Decision Tree Generator</span>
          </div>
          <p className="text-xs text-[var(--color-text-secondary)]">
            Describe your lending strategy in plain language. The AI will generate the decision tree structure.
          </p>
          <textarea
            value={aiPrompt}
            onChange={(e) => setAiPrompt(e.target.value)}
            placeholder='e.g. "Split by new vs existing customer. For existing customers with income above $10,000 use relaxed rules, otherwise standard rules. For new customers, check bureau data - thin file gets enhanced verification, standard file gets normal assessment, thick file gets express processing."'
            rows={3}
            className="w-full px-2.5 py-1.5 text-xs bg-[var(--color-bg)] border border-[var(--color-border)] rounded focus:outline-none focus:border-purple-500 resize-none"
          />

          {aiResult?.status === 'refused' && (
            <div className="px-2 py-1.5 rounded bg-red-500/10 text-red-400 text-xs">
              {aiResult.refusal_reason}
            </div>
          )}

          {aiResult?.status === 'needs_clarification' && aiResult.questions && (
            <div className="px-2 py-1.5 rounded bg-amber-500/10 text-amber-400 text-xs">
              <div className="font-medium mb-1">Clarification needed:</div>
              {aiResult.questions.map((q, i) => <div key={i}>• {q}</div>)}
            </div>
          )}

          {aiResult?.status === 'complete' && aiResult.tree && (
            <div className="px-2 py-1.5 rounded bg-emerald-500/10 text-emerald-400 text-xs space-y-1">
              <div className="font-medium">Tree generated: {aiResult.tree.nodes.length} nodes</div>
              {aiResult.explanation && <div className="text-[var(--color-text-secondary)]">{aiResult.explanation}</div>}
              {aiResult.tree.assessment_names && (
                <div>Assessments: {aiResult.tree.assessment_names.join(', ')}</div>
              )}
              <button
                onClick={applyAiTree}
                className="mt-1 flex items-center gap-1 px-2.5 py-1 text-xs rounded bg-emerald-500 text-white hover:bg-emerald-600"
              >
                <CheckCircle size={11} /> Apply to Tree
              </button>
            </div>
          )}

          <div className="flex gap-2">
            <button
              onClick={handleAiGenerate}
              disabled={!aiPrompt.trim() || aiLoading}
              className="flex items-center gap-1 px-2.5 py-1 text-xs rounded bg-purple-500 text-white hover:bg-purple-600 disabled:opacity-50"
            >
              <Sparkles size={11} /> {aiLoading ? 'Generating...' : 'Generate'}
            </button>
            <button
              onClick={() => { setShowAiGen(false); setAiResult(null); setAiPrompt(''); }}
              className="px-2.5 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-secondary)]"
            >
              Close
            </button>
          </div>
        </div>
      )}

      <div
        className="rounded-lg border overflow-hidden relative"
        style={{ height: 350, borderColor: 'var(--color-border)' }}
      >
        {canvas}
      </div>
      {edgePicker}
    </div>
  );
}

/* ── Assessment Manager ────────────────────────────────────────── */

function AssessmentManager({
  strategyId,
  assessments,
  editable,
  onChanged,
}: {
  strategyId: number;
  assessments: AssessmentEntry[];
  editable: boolean;
  onChanged: () => void;
}) {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);

  const createFromTemplate = async () => {
    setCreating(true);
    try {
      await api.post(`/assessments/from-template?strategy_id=${strategyId}&name=New+Assessment`);
      onChanged();
    } finally {
      setCreating(false);
    }
  };

  const createBlank = async () => {
    setCreating(true);
    try {
      await api.post(`/strategies/${strategyId}/assessments`, {
        strategy_id: strategyId,
        name: 'New Assessment',
        rules: [],
      });
      onChanged();
    } finally {
      setCreating(false);
    }
  };

  const deleteAssessment = async (id: number) => {
    await api.delete(`/assessments/${id}`);
    onChanged();
  };

  return (
    <div data-testid="assessments-section">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase">
            Assessments
          </h4>
          <p className="text-xs text-[var(--color-text-secondary)]">
            Business rule sets evaluated at decision tree terminal nodes
          </p>
        </div>
        {editable && (
          <div className="flex items-center gap-2">
            <button
              onClick={createFromTemplate}
              disabled={creating}
              className="flex items-center gap-1 px-2.5 py-1 text-xs rounded bg-orange-500 text-white hover:bg-orange-600 disabled:opacity-50 transition-colors"
              data-testid="btn-new-assessment-template"
            >
              <ClipboardCheck size={12} /> {creating ? '...' : 'New from Template'}
            </button>
            <button
              onClick={createBlank}
              disabled={creating}
              className="flex items-center gap-1 px-2.5 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
              data-testid="btn-new-assessment-blank"
            >
              <Plus size={12} /> Blank
            </button>
          </div>
        )}
      </div>

      {assessments.length === 0 && (
        <p className="text-xs text-[var(--color-text-secondary)] italic">No assessments configured</p>
      )}

      {assessments.map((a) => (
        <div key={a.id} className="mb-2" data-testid={`assessment-${a.id}`}>
          <div
            className={`flex items-center justify-between px-3 py-2 rounded-lg border cursor-pointer transition-colors ${
              expandedId === a.id ? 'border-orange-500/50 bg-orange-500/5' : 'hover:border-orange-500/30'
            }`}
            style={expandedId === a.id ? {} : { borderColor: 'var(--color-border)', background: 'var(--color-bg)' }}
            onClick={() => setExpandedId(expandedId === a.id ? null : a.id)}
          >
            <div className="flex items-center gap-2">
              <ClipboardCheck size={14} className="text-orange-500" />
              <span className="text-sm font-medium text-[var(--color-text)]">{a.name}</span>
              <span className="text-xs text-[var(--color-text-secondary)]">
                {(a.rules || []).length} rules
              </span>
            </div>
            <div className="flex items-center gap-1">
              {editable && (
                <button
                  onClick={(e) => { e.stopPropagation(); deleteAssessment(a.id); }}
                  className="p-1 text-red-400 hover:text-red-500"
                  data-testid={`btn-delete-assessment-${a.id}`}
                >
                  <Trash2 size={12} />
                </button>
              )}
              <ChevronRight
                size={14}
                className={`text-[var(--color-text-secondary)] transition-transform ${
                  expandedId === a.id ? 'rotate-90' : ''
                }`}
              />
            </div>
          </div>

          {expandedId === a.id && (
            <AssessmentEditor assessment={a} editable={editable} onSaved={onChanged} />
          )}
        </div>
      ))}
    </div>
  );
}

/* ── Assessment Editor ─────────────────────────────────────────── */

function AssessmentEditor({
  assessment,
  editable,
  onSaved,
}: {
  assessment: AssessmentEntry;
  editable: boolean;
  onSaved: () => void;
}) {
  const [name, setName] = useState(assessment.name);
  const [rules, setRules] = useState<RuleEntry[]>(assessment.rules || []);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [showStats, setShowStats] = useState(false);

  const { data: ruleStats } = useQuery({
    queryKey: ['rule-stats', assessment.strategy_id],
    queryFn: async () => {
      const res = await api.get(`/strategies/${assessment.strategy_id}/rule-stats`);
      return res.data as { total_decisions: number; rules: Array<{ rule_id: string; name: string; total: number; passed: number; failed: number }> };
    },
    enabled: showStats,
  });

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put(`/assessments/${assessment.id}`, { name, rules });
      setSaved(true);
      onSaved();
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  const addRule = () => {
    setRules([...rules, {
      rule_id: `R${Date.now()}`, name: '', field: '', operator: 'gte',
      threshold: '', severity: 'hard', outcome: 'decline', reason_code: '', enabled: true,
    }]);
  };

  const updateRule = (idx: number, field: string, value: unknown) => {
    const updated = [...rules];
    (updated[idx] as unknown as Record<string, unknown>)[field] = value;
    setRules(updated);
  };

  const removeRule = (idx: number) => {
    setRules(rules.filter((_, i) => i !== idx));
  };

  return (
    <div
      className="mt-1 p-3 rounded-lg border space-y-3"
      style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}
      data-testid={`assessment-editor-${assessment.id}`}
    >
      <div className="flex items-center justify-between">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          disabled={!editable}
          className="flex-1 px-2 py-1 text-sm font-medium rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] disabled:opacity-50 mr-2"
          data-testid="assessment-name-input"
        />
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowStats(!showStats)}
            className={`flex items-center gap-1 px-2.5 py-1 text-xs rounded border transition-colors ${
              showStats ? 'border-purple-500 text-purple-500 bg-purple-500/5' : 'border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
            }`}
          >
            <BarChart3 size={12} /> Stats
          </button>
          {editable && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1 px-2.5 py-1 text-xs rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
              data-testid="btn-save-assessment"
            >
              <Save size={12} /> {saving ? '...' : saved ? 'Saved' : 'Save'}
            </button>
          )}
        </div>
      </div>

      {showStats && ruleStats && (
        <div className="rounded-lg border p-3 space-y-2" style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)' }}>
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase">Rule Performance</span>
            <span className="text-xs text-[var(--color-text-secondary)]">{ruleStats.total_decisions} decisions analyzed</span>
          </div>
          {ruleStats.rules.length === 0 && (
            <p className="text-xs text-[var(--color-text-secondary)] italic">No decision data yet</p>
          )}
          {ruleStats.rules.map((r) => {
            const passRate = r.total > 0 ? (r.passed / r.total) * 100 : 0;
            const failRate = r.total > 0 ? (r.failed / r.total) * 100 : 0;
            return (
              <div key={r.rule_id} className="flex items-center gap-2 text-xs">
                <span className="w-10 font-mono text-[var(--color-text-secondary)]">{r.rule_id}</span>
                <span className="flex-1 text-[var(--color-text)] truncate">{r.name}</span>
                <div className="w-24 h-1.5 rounded-full bg-[var(--color-border)] overflow-hidden flex">
                  <div className="h-full bg-emerald-500" style={{ width: `${passRate}%` }} />
                  <div className="h-full bg-red-500" style={{ width: `${failRate}%` }} />
                </div>
                <span className="w-8 text-right text-emerald-500">{r.passed}</span>
                <span className="w-8 text-right text-red-500">{r.failed}</span>
              </div>
            );
          })}
        </div>
      )}

      <RuleListEditor
        title="Assessment Rules"
        subtitle="Business rules evaluated for this assessment branch"
        rules={rules}
        addRule={addRule}
        updateRule={(idx, field, val) => updateRule(idx, field, val)}
        removeRule={removeRule}
        editable={editable}
        testIdPrefix={`assess-${assessment.id}`}
        onAiRuleAdded={(rule) => setRules((prev) => [...prev, rule])}
      />
    </div>
  );
}

/* ── Searchable Field Picker ─────────────────────────────────────── */

function FieldPicker({
  value,
  onChange,
  disabled,
}: {
  value: string;
  onChange: (val: string) => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  const lowerQ = query.toLowerCase();
  const filteredGroups = FIELD_GROUPS
    .map((g) => ({
      ...g,
      fields: g.fields.filter(
        (f) =>
          f.label.toLowerCase().includes(lowerQ) ||
          f.value.toLowerCase().includes(lowerQ) ||
          g.label.toLowerCase().includes(lowerQ),
      ),
    }))
    .filter((g) => g.fields.length > 0);

  return (
    <div ref={ref} className="col-span-2 relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => { if (!disabled) setOpen(!open); }}
        className="w-full text-left px-1.5 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] disabled:opacity-50 truncate"
      >
        {value ? getFieldLabel(value) : <span className="text-[var(--color-text-secondary)]">Field...</span>}
      </button>

      {open && (
        <div
          className="absolute z-50 mt-1 w-64 rounded-lg border shadow-lg overflow-hidden"
          style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
        >
          <div className="p-1.5 border-b" style={{ borderColor: 'var(--color-border)' }}>
            <div className="relative">
              <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-[var(--color-text-secondary)]" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search fields..."
                className="w-full pl-6 pr-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
          <div className="max-h-56 overflow-y-auto">
            {filteredGroups.length === 0 && (
              <p className="px-3 py-2 text-xs text-[var(--color-text-secondary)] italic">No matching fields</p>
            )}
            {filteredGroups.map((g) => (
              <div key={g.label}>
                <div className="px-2.5 py-1 text-[10px] font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider bg-[var(--color-bg)]">
                  {g.label}
                </div>
                {g.fields.map((f) => (
                  <button
                    key={f.value}
                    type="button"
                    onClick={() => { onChange(f.value); setOpen(false); setQuery(''); }}
                    className={`w-full text-left px-3 py-1.5 text-xs hover:bg-blue-500/10 transition-colors flex items-center justify-between ${
                      value === f.value ? 'text-blue-500 bg-blue-500/5 font-medium' : 'text-[var(--color-text)]'
                    }`}
                  >
                    {f.label}
                    {value === f.value && <CheckCircle size={11} className="text-blue-500 shrink-0" />}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Threshold Input (handles categorical vs free-text) ─────────── */

function ThresholdInput({
  field,
  value,
  onChange,
  disabled,
}: {
  field: string;
  value: string;
  onChange: (val: string) => void;
  disabled: boolean;
}) {
  const options = CATEGORICAL_VALUES[field];

  if (options) {
    return (
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="col-span-1 px-1.5 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] disabled:opacity-50"
      >
        <option value="">Value...</option>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    );
  }

  return (
    <input
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder="Threshold"
      disabled={disabled}
      className="col-span-1 px-1.5 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] disabled:opacity-50"
    />
  );
}

/* ── AI Rule Generator (inline, for strategy rules) ─────────────── */

function AiRuleGenerator({
  onRuleGenerated,
}: {
  onRuleGenerated: (rule: RuleEntry) => void;
}) {
  const [showAI, setShowAI] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResult, setAiResult] = useState<GenerateResult | null>(null);
  const [aiHistory, setAiHistory] = useState<Array<Record<string, string>>>([]);
  const [clarifyAnswers, setClarifyAnswers] = useState<string[]>([]);
  const [aiError, setAiError] = useState('');

  const handleGenerate = async () => {
    if (!aiPrompt.trim()) return;
    setAiLoading(true);
    setAiResult(null);
    setAiError('');

    try {
      const res = await adminApi.generateRule({
        prompt: aiPrompt,
        conversation_history: aiHistory.length > 0 ? aiHistory : undefined,
      });
      const data: GenerateResult = res.data;
      setAiResult(data);

      if (data.status === 'needs_clarification') {
        setAiHistory((prev) => [
          ...prev,
          { role: 'user', content: aiPrompt },
          { role: 'assistant', content: JSON.stringify(data) },
        ]);
        setClarifyAnswers(new Array(data.questions?.length ?? 0).fill(''));
      }
    } catch {
      setAiError('AI generation failed. Please try again.');
    } finally {
      setAiLoading(false);
    }
  };

  const handleClarifySubmit = async () => {
    const questions = aiResult?.questions ?? [];
    const answerText = questions
      .map((q, i) => `Q: ${q}\nA: ${clarifyAnswers[i] || '(not answered)'}`)
      .join('\n\n');

    setAiPrompt(answerText);
    setAiResult(null);
    setClarifyAnswers([]);
    setAiLoading(true);

    try {
      const res = await adminApi.generateRule({
        prompt: answerText,
        conversation_history: aiHistory,
      });
      setAiResult(res.data);
    } catch {
      setAiError('AI generation failed.');
    } finally {
      setAiLoading(false);
    }
  };

  const handleAddGeneratedRule = () => {
    if (!aiResult?.rule) return;
    const r = aiResult.rule;
    const newRule: RuleEntry = {
      rule_id: (r.rule_id as string) || `R${Date.now()}`,
      name: (r.name as string) || 'AI Rule',
      field: (r.field as string) || '',
      operator: (r.operator as string) || 'gte',
      threshold: r.threshold ?? null,
      severity: (r.severity as string) || 'hard',
      outcome: (r.outcome as string) || 'decline',
      reason_code: (r.reason_code as string) || '',
      enabled: true,
    };
    onRuleGenerated(newRule);
    handleDiscard();
  };

  const handleDiscard = () => {
    setAiResult(null);
    setAiPrompt('');
    setAiHistory([]);
    setClarifyAnswers([]);
    setAiError('');
  };

  return (
    <div className="mt-2">
      <button
        onClick={() => setShowAI(!showAI)}
        className="flex items-center gap-1.5 text-xs text-sky-400 hover:text-sky-300 transition-colors"
        data-testid="btn-ai-rule-toggle"
      >
        <Sparkles size={12} />
        <span className="font-medium">Add Rule with AI</span>
        {showAI ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>

      {showAI && (
        <div className="mt-2 p-3 rounded-lg border border-sky-500/20 bg-sky-500/5 space-y-3">
          <p className="text-xs text-[var(--color-text-secondary)]">
            Describe a rule in plain language. AI will transform it into a structured definition.
          </p>

          {aiError && (
            <div className="px-2 py-1.5 rounded bg-red-500/10 text-red-400 text-xs flex items-center gap-1.5">
              <AlertTriangle size={12} /> {aiError}
            </div>
          )}

          {/* Refusal */}
          {aiResult?.status === 'refused' && (
            <div className="px-3 py-2 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-start gap-2">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              <div>
                <div className="font-medium mb-0.5">Rule Refused</div>
                {aiResult.refusal_reason}
              </div>
            </div>
          )}

          {/* Prompt input */}
          {(!aiResult || aiResult.status === 'refused') && (
            <div className="space-y-2">
              <textarea
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                placeholder='e.g. "Decline if credit score below 350" or "Refer anyone with DTI above 60%"'
                rows={2}
                className="w-full px-2.5 py-1.5 text-xs bg-[var(--color-bg)] border border-[var(--color-border)] rounded focus:outline-none focus:border-sky-500 resize-none"
              />
              <button
                onClick={handleGenerate}
                disabled={!aiPrompt.trim() || aiLoading}
                className="flex items-center gap-1 px-2.5 py-1 text-xs rounded bg-sky-500 text-white hover:bg-sky-600 disabled:opacity-50 transition-colors"
              >
                <Sparkles size={11} /> {aiLoading ? 'Generating...' : 'Generate Rule'}
              </button>
            </div>
          )}

          {/* Clarifying Questions */}
          {aiResult?.status === 'needs_clarification' && aiResult.questions && (
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-amber-400 text-xs font-medium">
                <HelpCircle size={12} /> Clarifying Questions
              </div>
              {aiResult.questions.map((q, i) => (
                <div key={i} className="space-y-1">
                  <label className="text-xs text-[var(--color-text)]">{q}</label>
                  <input
                    type="text"
                    value={clarifyAnswers[i] || ''}
                    onChange={(e) => {
                      const updated = [...clarifyAnswers];
                      updated[i] = e.target.value;
                      setClarifyAnswers(updated);
                    }}
                    className="w-full px-2 py-1 text-xs bg-[var(--color-bg)] border border-[var(--color-border)] rounded focus:outline-none focus:border-sky-500"
                    placeholder="Your answer..."
                  />
                </div>
              ))}
              <div className="flex gap-2">
                <button
                  onClick={handleClarifySubmit}
                  disabled={aiLoading}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs rounded bg-sky-500 text-white hover:bg-sky-600 disabled:opacity-50"
                >
                  {aiLoading ? 'Submitting...' : 'Submit Answers'}
                </button>
                <button
                  onClick={handleDiscard}
                  className="px-2.5 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Generated Rule Preview */}
          {aiResult?.status === 'complete' && aiResult.rule && (
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-sky-400 text-xs font-medium">
                <CheckCircle size={12} /> Generated Rule Preview
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                <div>
                  <span className="text-[var(--color-text-secondary)]">ID:</span>{' '}
                  <span className="font-mono">{aiResult.rule.rule_id as string}</span>
                </div>
                <div>
                  <span className="text-[var(--color-text-secondary)]">Name:</span>{' '}
                  {aiResult.rule.name as string}
                </div>
                <div>
                  <span className="text-[var(--color-text-secondary)]">Field:</span>{' '}
                  <span className="font-mono">{aiResult.rule.field as string}</span>
                </div>
                <div>
                  <span className="text-[var(--color-text-secondary)]">Operator:</span>{' '}
                  <span className="font-mono">{aiResult.rule.operator as string}</span>
                </div>
                <div>
                  <span className="text-[var(--color-text-secondary)]">Threshold:</span>{' '}
                  <span className="font-mono">{String(aiResult.rule.threshold)}</span>
                </div>
                <div>
                  <span className="text-[var(--color-text-secondary)]">Severity:</span>{' '}
                  {aiResult.rule.severity as string}
                </div>
              </div>
              <div className="flex gap-2 pt-1">
                <button
                  onClick={handleAddGeneratedRule}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs rounded bg-emerald-500 text-white hover:bg-emerald-600"
                >
                  <Plus size={11} /> Add Rule
                </button>
                <button
                  onClick={handleDiscard}
                  className="flex items-center gap-1 px-2.5 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                >
                  <X size={11} /> Discard
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Rule List Editor (reused for knock-outs and overlays) ──────── */

function RuleListEditor({
  title,
  subtitle,
  rules,
  addRule,
  updateRule,
  removeRule,
  editable,
  testIdPrefix,
  onAiRuleAdded,
}: {
  title: string;
  subtitle: string;
  rules: RuleEntry[];
  addRule: () => void;
  updateRule: (idx: number, field: string, value: unknown) => void;
  removeRule: (idx: number) => void;
  editable: boolean;
  testIdPrefix: string;
  onAiRuleAdded: (rule: RuleEntry) => void;
}) {
  return (
    <div data-testid={`${testIdPrefix}-section`}>
      <div className="flex items-center justify-between mb-2">
        <div>
          <h4 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase">{title}</h4>
          <p className="text-xs text-[var(--color-text-secondary)]">{subtitle}</p>
        </div>
        {editable && (
          <button
            onClick={addRule}
            className="flex items-center gap-1 px-2.5 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-bg)] transition-colors"
            data-testid={`btn-add-${testIdPrefix}`}
          >
            <Plus size={12} /> Add Rule
          </button>
        )}
      </div>

      {rules.length === 0 && (
        <p className="text-xs text-[var(--color-text-secondary)] italic">No rules configured</p>
      )}

      {rules.map((rule, i) => (
        <div
          key={i}
          className="grid grid-cols-12 gap-1.5 mb-1.5 items-center"
          data-testid={`${testIdPrefix}-rule-${i}`}
        >
          <input
            value={rule.rule_id}
            onChange={(e) => updateRule(i, 'rule_id', e.target.value)}
            placeholder="ID"
            disabled={!editable}
            className="col-span-1 px-1.5 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] disabled:opacity-50"
          />
          <input
            value={rule.name}
            onChange={(e) => updateRule(i, 'name', e.target.value)}
            placeholder="Rule name"
            disabled={!editable}
            className="col-span-2 px-1.5 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] disabled:opacity-50"
          />
          <FieldPicker
            value={rule.field}
            onChange={(val) => updateRule(i, 'field', val)}
            disabled={!editable}
          />
          <select
            value={rule.operator}
            onChange={(e) => updateRule(i, 'operator', e.target.value)}
            disabled={!editable}
            className="col-span-1 px-1.5 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] disabled:opacity-50"
          >
            {OPERATORS.map((op) => (
              <option key={op.value} value={op.value}>{op.label}</option>
            ))}
          </select>
          <div className="col-span-1">
            <ThresholdInput
              field={rule.field}
              value={String(rule.threshold ?? '')}
              onChange={(val) => updateRule(i, 'threshold', val)}
              disabled={!editable}
            />
          </div>
          <select
            value={rule.severity}
            onChange={(e) => updateRule(i, 'severity', e.target.value)}
            disabled={!editable}
            className="col-span-1 px-1.5 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] disabled:opacity-50"
          >
            <option value="hard">Hard</option>
            <option value="refer">Refer</option>
          </select>
          <input
            value={rule.reason_code}
            onChange={(e) => updateRule(i, 'reason_code', e.target.value)}
            placeholder="Reason code"
            disabled={!editable}
            className="col-span-2 px-1.5 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] disabled:opacity-50"
          />
          {editable && (
            <div className="col-span-1 flex items-center gap-1">
              <input
                type="checkbox"
                checked={rule.enabled}
                onChange={(e) => updateRule(i, 'enabled', e.target.checked)}
                className="w-3 h-3"
                title="Enabled"
              />
              <button onClick={() => removeRule(i)} className="p-0.5 text-red-400 hover:text-red-500">
                <Trash2 size={11} />
              </button>
            </div>
          )}
          {!editable && (
            <div className="col-span-1 text-xs text-[var(--color-text-secondary)]">
              {rule.enabled ? 'on' : 'off'}
            </div>
          )}
        </div>
      ))}

      {editable && (
        <AiRuleGenerator onRuleGenerated={onAiRuleAdded} />
      )}
    </div>
  );
}
