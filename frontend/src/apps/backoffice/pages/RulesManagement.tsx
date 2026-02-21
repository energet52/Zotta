import { useEffect, useState, useCallback } from 'react';
import {
  Save,
  Trash2,
  Sparkles,
  ToggleLeft,
  ToggleRight,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle,
  HelpCircle,
  Loader2,
  Plus,
  X,
  Info,
  History,
  BarChart3,
  Brain,
  Clock,
  User,
  Shield,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { adminApi } from '../../../api/endpoints';

/* ── Types ─────────────────────────────────────────────── */

interface RuleEntry {
  rule_id: string;
  name: string;
  description: string;
  field: string;
  operator: string;
  threshold: unknown;
  outcome: string;
  severity: string;
  type: string;
  is_custom: boolean;
  enabled: boolean;
}

interface AllowedField {
  label: string;
  type: string;
  unit?: string;
  description: string;
  values?: string[];
}

interface GenerateResult {
  status: string;
  questions?: string[];
  refusal_reason?: string;
  rule?: Record<string, unknown>;
  explanation?: string;
}

interface RuleStats {
  total: number;
  passed: number;
  failed: number;
  decline: number;
  refer: number;
}

interface HistoryChange {
  rule_id: string;
  change_type: 'added' | 'removed' | 'modified';
  name?: string;
  fields?: Record<string, { old: unknown; new: unknown }>;
}

interface HistoryEntry {
  id: number;
  action: string;
  version: number;
  new_version: number;
  user_name: string;
  created_at: string;
  changes: HistoryChange[];
  details: string;
}

interface AiRecommendation {
  rule_id: string;
  rule_name: string;
  current_declines?: number;
  total_evaluated?: number;
  decline_rate?: number;
  recommendation?: string;
  change?: string;
  projected_impact?: string;
  risk: string;
  rationale?: string;
}

interface AiAnalysis {
  summary: string;
  total_applications: number;
  rules_evaluated: number;
  top_decliners: AiRecommendation[];
  recommendations: AiRecommendation[];
  ai_powered: boolean;
}

type Tab = 'rules' | 'history' | 'analysis';

/* ── Helpers ───────────────────────────────────────────── */

const OUTCOME_OPTIONS = [
  { value: 'decline', label: 'Decline' },
  { value: 'refer', label: 'Refer' },
  { value: 'pass', label: 'Pass' },
  { value: 'disable', label: 'Disable' },
];

function outcomeStripe(outcome: string) {
  switch (outcome) {
    case 'decline': return 'border-l-red-500';
    case 'refer': return 'border-l-amber-500';
    case 'pass': return 'border-l-green-500';
    case 'disable': return 'border-l-gray-500';
    default: return 'border-l-gray-500';
  }
}

function outcomeBadge(outcome: string) {
  const colors: Record<string, string> = {
    decline: 'text-red-400 bg-red-500/10 border-red-500/30',
    refer: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
    pass: 'text-green-400 bg-green-500/10 border-green-500/30',
    disable: 'text-gray-400 bg-gray-500/10 border-gray-500/30',
  };
  const label = OUTCOME_OPTIONS.find(o => o.value === outcome)?.label ?? outcome;
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border ${colors[outcome] ?? colors.disable}`}>
      {label}
    </span>
  );
}

function formatThreshold(threshold: unknown): string {
  if (threshold === null || threshold === undefined) return '';
  if (typeof threshold === 'object' && !Array.isArray(threshold)) {
    return JSON.stringify(threshold);
  }
  if (Array.isArray(threshold)) {
    return threshold.join(', ');
  }
  return String(threshold);
}

function isEditableThreshold(threshold: unknown): boolean {
  if (threshold === null || threshold === undefined) return true;
  if (typeof threshold === 'number' || typeof threshold === 'string' || typeof threshold === 'boolean') return true;
  return false;
}

function riskBadge(risk: string) {
  const colors: Record<string, string> = {
    low: 'text-green-400 bg-green-500/10 border-green-500/30',
    medium: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
    high: 'text-red-400 bg-red-500/10 border-red-500/30',
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border ${colors[risk] ?? colors.medium}`}>
      {risk}
    </span>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

/* ── Main Component ────────────────────────────────────── */

export default function RulesManagement() {
  const [rules, setRules] = useState<RuleEntry[]>([]);
  const [allowedFields, setAllowedFields] = useState<Record<string, AllowedField>>({});
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Tab state
  const [activeTab, setActiveTab] = useState<Tab>('rules');

  // AI generator state
  const [showAI, setShowAI] = useState(false);
  const [aiPrompt, setAiPrompt] = useState('');
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResult, setAiResult] = useState<GenerateResult | null>(null);
  const [aiHistory, setAiHistory] = useState<Array<Record<string, string>>>([]);
  const [clarifyAnswers, setClarifyAnswers] = useState<string[]>([]);

  // Expanded rule (for details)
  const [expandedRule, setExpandedRule] = useState<string | null>(null);

  // Per-rule stats
  const [ruleStats, setRuleStats] = useState<Record<string, RuleStats>>({});
  const [statsLoading, setStatsLoading] = useState(false);

  // History
  const [historyEntries, setHistoryEntries] = useState<HistoryEntry[]>([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [expandedHistoryId, setExpandedHistoryId] = useState<number | null>(null);

  // AI Analysis
  const [analysis, setAnalysis] = useState<AiAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  const loadRules = useCallback(async () => {
    try {
      setLoading(true);
      const res = await adminApi.getRules();
      setRules(res.data.rules);
      setAllowedFields(res.data.allowed_fields);
      setVersion(res.data.version);
      setDirty(false);
      setError('');
    } catch {
      setError('Failed to load rules');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadStats = useCallback(async () => {
    try {
      setStatsLoading(true);
      const res = await adminApi.getRulesStats();
      setRuleStats(res.data);
    } catch {
      // Stats are supplementary — don't block the UI
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      setHistoryLoading(true);
      const res = await adminApi.getRulesHistory({ limit: 50, offset: 0 });
      setHistoryEntries(res.data.entries);
      setHistoryTotal(res.data.total);
    } catch {
      setError('Failed to load rules history');
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => { loadRules(); loadStats(); }, [loadRules, loadStats]);

  useEffect(() => {
    if (activeTab === 'history') loadHistory();
  }, [activeTab, loadHistory]);

  // Auto-hide success message
  useEffect(() => {
    if (successMsg) {
      const t = setTimeout(() => setSuccessMsg(''), 3000);
      return () => clearTimeout(t);
    }
  }, [successMsg]);

  /* ── Rule mutations ─────────────────────────────────── */

  const updateRule = (ruleId: string, updates: Partial<RuleEntry>) => {
    setRules(prev => prev.map(r =>
      r.rule_id === ruleId ? { ...r, ...updates } : r
    ));
    setDirty(true);
  };

  const toggleEnabled = (ruleId: string) => {
    const rule = rules.find(r => r.rule_id === ruleId);
    if (rule) updateRule(ruleId, { enabled: !rule.enabled });
  };

  const handleOutcomeChange = (ruleId: string, outcome: string) => {
    const severity = outcome === 'decline' ? 'hard' : outcome === 'refer' ? 'refer' : 'soft';
    updateRule(ruleId, { outcome, severity });
  };

  const handleThresholdChange = (ruleId: string, value: string) => {
    let parsed: unknown = value;
    const num = Number(value);
    if (!isNaN(num) && value.trim() !== '') {
      parsed = num;
    }
    updateRule(ruleId, { threshold: parsed });
  };

  const handleDeleteRule = async (ruleId: string) => {
    const rule = rules.find(r => r.rule_id === ruleId);
    const label = rule ? `"${rule.name}"` : ruleId;
    const msg = rule && !rule.is_custom
      ? `⚠️ "${rule.name}" is a built-in system rule.\n\nDeleting it will permanently remove it from the decision engine. Are you sure?`
      : `Delete rule ${label}?`;
    if (!confirm(msg)) return;
    try {
      await adminApi.deleteRule(ruleId);
      setSuccessMsg(`Rule ${label} deleted`);
      await loadRules();
    } catch {
      setError(`Failed to delete rule ${label}`);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError('');
      await adminApi.updateRules({
        rules: rules.map(r => ({
          rule_id: r.rule_id,
          name: r.name,
          description: r.description,
          field: r.field,
          operator: r.operator,
          threshold: r.threshold,
          outcome: r.outcome,
          severity: r.severity,
          type: r.type,
          is_custom: r.is_custom,
          enabled: r.enabled,
        })),
      });
      setSuccessMsg('Rules saved successfully');
      await loadRules();
      loadStats();
    } catch {
      setError('Failed to save rules');
    } finally {
      setSaving(false);
    }
  };

  /* ── AI Rule Generator ──────────────────────────────── */

  const handleGenerate = async () => {
    if (!aiPrompt.trim()) return;
    setAiLoading(true);
    setAiResult(null);
    setError('');

    try {
      const res = await adminApi.generateRule({
        prompt: aiPrompt,
        conversation_history: aiHistory.length > 0 ? aiHistory : undefined,
      });
      const data: GenerateResult = res.data;
      setAiResult(data);

      if (data.status === 'needs_clarification') {
        setAiHistory(prev => [
          ...prev,
          { role: 'user', content: aiPrompt },
          { role: 'assistant', content: JSON.stringify(data) },
        ]);
        setClarifyAnswers(new Array(data.questions?.length ?? 0).fill(''));
      }
    } catch {
      setError('AI generation failed. Please try again.');
    } finally {
      setAiLoading(false);
    }
  };

  const handleClarifySubmit = async () => {
    const questions = aiResult?.questions ?? [];
    const answerText = questions.map((q, i) =>
      `Q: ${q}\nA: ${clarifyAnswers[i] || '(not answered)'}`
    ).join('\n\n');

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
      setError('AI generation failed.');
    } finally {
      setAiLoading(false);
    }
  };

  const handleAddGeneratedRule = () => {
    if (!aiResult?.rule) return;
    const r = aiResult.rule;
    const newRule: RuleEntry = {
      rule_id: (r.rule_id as string) || `RC_${Date.now().toString(36).toUpperCase()}`,
      name: (r.name as string) || 'Custom Rule',
      description: (r.description as string) || '',
      field: (r.field as string) || '',
      operator: (r.operator as string) || 'gte',
      threshold: r.threshold ?? null,
      outcome: (r.outcome as string) || 'refer',
      severity: (r.severity as string) || 'refer',
      type: 'threshold',
      is_custom: true,
      enabled: true,
    };
    setRules(prev => [...prev, newRule]);
    setDirty(true);
    setAiResult(null);
    setAiPrompt('');
    setAiHistory([]);
    setSuccessMsg(`Rule "${newRule.name}" added. Remember to save changes.`);
  };

  const handleDiscardGenerated = () => {
    setAiResult(null);
    setAiPrompt('');
    setAiHistory([]);
    setClarifyAnswers([]);
  };

  /* ── AI Analysis ────────────────────────────────────── */

  const handleAnalyze = async () => {
    try {
      setAnalysisLoading(true);
      setError('');
      const res = await adminApi.analyzeRules();
      setAnalysis(res.data);
    } catch {
      setError('Failed to run AI analysis');
    } finally {
      setAnalysisLoading(false);
    }
  };

  /* ── Render ─────────────────────────────────────────── */

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-[var(--color-text-muted)]">
        <Loader2 className="animate-spin mr-2" size={20} /> Loading rules...
      </div>
    );
  }

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'rules', label: 'Rules', icon: <Shield size={16} /> },
    { id: 'history', label: 'History', icon: <History size={16} /> },
    { id: 'analysis', label: 'AI Analysis', icon: <Brain size={16} /> },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">Underwriting Rules</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            Config version {version} &middot; {rules.length} rules
          </p>
        </div>
        {activeTab === 'rules' && (
          <div className="flex items-center gap-3">
            {dirty && (
              <span className="text-xs text-amber-400 flex items-center gap-1">
                <AlertTriangle size={14} /> Unsaved changes
              </span>
            )}
            <Button onClick={handleSave} isLoading={saving} disabled={!dirty} size="sm">
              <Save size={16} className="mr-1.5" /> Save Changes
            </Button>
          </div>
        )}
      </div>

      {/* Messages */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg text-sm flex items-center gap-2">
          <AlertTriangle size={16} /> {error}
          <button onClick={() => setError('')} className="ml-auto"><X size={14} /></button>
        </div>
      )}
      {successMsg && (
        <div className="bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg text-sm flex items-center gap-2">
          <CheckCircle size={16} /> {successMsg}
        </div>
      )}

      {/* Tab navigation */}
      <div className="flex flex-nowrap gap-1 border-b border-[var(--color-border)] overflow-x-auto max-w-full">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`shrink-0 flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              activeTab === tab.id
                ? 'border-[var(--color-primary)] text-[var(--color-primary)]'
                : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
            }`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* ═══════════════ RULES TAB ═══════════════ */}
      {activeTab === 'rules' && (
        <>
          {/* Rules list — card rows */}
          <div className="space-y-2">
            {rules.map(rule => {
              const isExpanded = expandedRule === rule.rule_id;
              const fieldMeta = allowedFields[rule.field];
              const editable = isEditableThreshold(rule.threshold);
              const stats = ruleStats[rule.rule_id];

              return (
                <div
                  key={rule.rule_id}
                  className={`rounded-lg border border-[var(--color-border)] border-l-4 transition-colors ${
                    !rule.enabled ? 'opacity-50 border-l-gray-600 bg-[var(--color-surface)]/60' : `${outcomeStripe(rule.outcome)} bg-[var(--color-surface)]`
                  }`}
                >
                  {/* Main row */}
                  <div className="flex items-center gap-3 px-4 py-3">
                    {/* ID + badge */}
                    <div className="w-24 shrink-0 overflow-hidden">
                      <span className="font-mono text-xs text-[var(--color-text-muted)] block truncate">{rule.rule_id}</span>
                      {rule.is_custom && (
                        <span className="text-[10px] text-sky-400 bg-sky-500/10 px-1 rounded">AI</span>
                      )}
                    </div>

                    {/* Name — click to expand */}
                    <button
                      onClick={() => setExpandedRule(isExpanded ? null : rule.rule_id)}
                      className="flex-1 min-w-0 text-left flex items-center gap-1.5"
                    >
                      <span className="font-medium text-sm truncate">{rule.name}</span>
                      <span className="text-[var(--color-text-muted)] shrink-0">
                        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </span>
                    </button>

                    {/* Stats badges */}
                    {stats && !statsLoading && (
                      <div className="flex items-center gap-1.5 shrink-0">
                        {stats.decline > 0 && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/30 font-medium" title="Declines">
                            {stats.decline} decl
                          </span>
                        )}
                        {stats.refer > 0 && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/30 font-medium" title="Refers">
                            {stats.refer} ref
                          </span>
                        )}
                        {stats.passed > 0 && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-500/10 text-green-400 border border-green-500/30 font-medium" title="Passed">
                            {stats.passed} pass
                          </span>
                        )}
                      </div>
                    )}

                    {/* Threshold — always editable inline */}
                    <div className="w-28 shrink-0">
                      {editable ? (
                        <input
                          type="text"
                          value={formatThreshold(rule.threshold)}
                          onChange={e => handleThresholdChange(rule.rule_id, e.target.value)}
                          className="w-full px-2 py-1 text-xs font-mono bg-[var(--color-bg)] border border-[var(--color-border)] rounded focus:outline-none focus:border-[var(--color-primary)] text-center"
                        />
                      ) : (
                        <span className="text-xs font-mono text-[var(--color-text-muted)] block text-center truncate" title={formatThreshold(rule.threshold)}>
                          {formatThreshold(rule.threshold).length > 14
                            ? formatThreshold(rule.threshold).slice(0, 14) + '...'
                            : formatThreshold(rule.threshold)}
                        </span>
                      )}
                    </div>

                    {/* Outcome dropdown */}
                    <select
                      value={rule.outcome}
                      onChange={e => handleOutcomeChange(rule.rule_id, e.target.value)}
                      className="w-24 shrink-0 px-2 py-1 text-xs bg-[var(--color-bg)] border border-[var(--color-border)] rounded focus:outline-none focus:border-[var(--color-primary)]"
                    >
                      {OUTCOME_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>

                    {/* Enabled toggle */}
                    <button
                      onClick={() => toggleEnabled(rule.rule_id)}
                      className="shrink-0 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                      title={rule.enabled ? 'Enabled — click to disable' : 'Disabled — click to enable'}
                    >
                      {rule.enabled ? (
                        <ToggleRight size={24} className="text-green-400" />
                      ) : (
                        <ToggleLeft size={24} className="text-gray-500" />
                      )}
                    </button>

                    {/* Delete */}
                    <div className="w-7 shrink-0 text-center">
                      <button
                        onClick={() => handleDeleteRule(rule.rule_id)}
                        className="p-1 rounded hover:bg-red-500/10 text-red-400"
                        title="Delete rule"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>

                  {/* Expanded details */}
                  {isExpanded && (
                    <div className="px-4 pb-3 pt-0 border-t border-[var(--color-border)] mx-4 mb-3 space-y-2">
                      <div className="pt-2 text-xs text-[var(--color-text-muted)]">{rule.description}</div>
                      <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-[var(--color-text-muted)]">
                        <span>Field: <span className="font-mono text-[var(--color-text)]">{rule.field}</span></span>
                        <span>Operator: <span className="font-mono text-[var(--color-text)]">{rule.operator}</span></span>
                        <span>Type: <span className="font-mono text-[var(--color-text)]">{rule.type}</span></span>
                        <span>Severity: <span className="font-mono text-[var(--color-text)]">{rule.severity}</span></span>
                      </div>

                      {/* Per-rule stats detail */}
                      {stats && (
                        <div className="flex gap-4 text-xs mt-1">
                          <span className="flex items-center gap-1"><BarChart3 size={12} className="text-[var(--color-text-muted)]" /> {stats.total} evaluated</span>
                          <span className="text-green-400">{stats.passed} passed</span>
                          <span className="text-red-400">{stats.decline} declined</span>
                          <span className="text-amber-400">{stats.refer} referred</span>
                        </div>
                      )}

                      {fieldMeta && (
                        <div className="text-xs text-[var(--color-text-muted)] flex items-center gap-1">
                          <Info size={12} /> {fieldMeta.description}
                          {fieldMeta.unit && <span className="text-[var(--color-text)]">({fieldMeta.unit})</span>}
                        </div>
                      )}
                      {/* For complex thresholds, show full JSON and allow editing */}
                      {!editable && (
                        <div className="space-y-1">
                          <label className="text-xs text-[var(--color-text-muted)]">Threshold (JSON):</label>
                          <textarea
                            value={formatThreshold(rule.threshold)}
                            onChange={e => {
                              try {
                                const parsed = JSON.parse(e.target.value);
                                updateRule(rule.rule_id, { threshold: parsed });
                              } catch {
                                updateRule(rule.rule_id, { threshold: e.target.value });
                              }
                            }}
                            rows={3}
                            className="w-full px-2 py-1.5 text-xs font-mono bg-[var(--color-bg)] border border-[var(--color-border)] rounded focus:outline-none focus:border-[var(--color-primary)] resize-none"
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Legend */}
          <div className="flex flex-wrap items-center gap-4 text-xs text-[var(--color-text-muted)]">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm bg-red-500/30 border border-red-500/50" /> Decline
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm bg-amber-500/30 border border-amber-500/50" /> Refer
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm bg-green-500/30 border border-green-500/50" /> Pass
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-sm bg-gray-500/30 border border-gray-500/50" /> Disabled
            </span>
          </div>

          {/* AI Rule Generator */}
          <Card>
            <button
              onClick={() => setShowAI(!showAI)}
              className="flex items-center justify-between w-full text-left"
            >
              <div className="flex items-center gap-2">
                <Sparkles size={18} className="text-sky-400" />
                <span className="font-medium">Add Rule with AI</span>
              </div>
              {showAI ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>

            {showAI && (
              <div className="mt-4 space-y-4">
                <p className="text-sm text-[var(--color-text-muted)]">
                  Describe a new underwriting rule in plain language. The AI will transform it into a
                  structured rule definition. If details are missing, it will ask clarifying questions.
                </p>

                {/* Prompt input */}
                {(!aiResult || aiResult.status === 'refused') && (
                  <div className="space-y-3">
                    <textarea
                      value={aiPrompt}
                      onChange={e => setAiPrompt(e.target.value)}
                      placeholder='e.g. "Decline applicants with a credit score below 350" or "Refer anyone requesting more than TTD 200,000 loan amount"'
                      rows={3}
                      className="w-full px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg focus:outline-none focus:border-[var(--color-primary)] resize-none"
                    />
                    <div className="flex flex-wrap items-center gap-3">
                      <Button
                        onClick={handleGenerate}
                        isLoading={aiLoading}
                        disabled={!aiPrompt.trim()}
                        size="sm"
                      >
                        <Sparkles size={14} className="mr-1.5" /> Generate Rule
                      </Button>
                      <span className="text-xs text-[var(--color-text-muted)]">
                        Powered by GPT-5.2 &middot; Rules based on gender, race, religion, etc. are blocked.
                      </span>
                    </div>
                  </div>
                )}

                {/* Refusal */}
                {aiResult?.status === 'refused' && (
                  <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg text-sm flex items-start gap-2">
                    <AlertTriangle size={16} className="mt-0.5 shrink-0" />
                    <div>
                      <div className="font-medium mb-1">Rule Refused</div>
                      {aiResult.refusal_reason}
                    </div>
                  </div>
                )}

                {/* Clarifying Questions */}
                {aiResult?.status === 'needs_clarification' && aiResult.questions && (
                  <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 space-y-3">
                    <div className="flex items-center gap-2 text-amber-400 text-sm font-medium">
                      <HelpCircle size={16} /> Clarifying Questions
                    </div>
                    {aiResult.questions.map((q, i) => (
                      <div key={i} className="space-y-1">
                        <label className="text-sm text-[var(--color-text)]">{q}</label>
                        <input
                          type="text"
                          value={clarifyAnswers[i] || ''}
                          onChange={e => {
                            const updated = [...clarifyAnswers];
                            updated[i] = e.target.value;
                            setClarifyAnswers(updated);
                          }}
                          className="w-full px-3 py-1.5 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded focus:outline-none focus:border-[var(--color-primary)]"
                          placeholder="Your answer..."
                        />
                      </div>
                    ))}
                    <div className="flex gap-2 pt-1">
                      <Button size="sm" onClick={handleClarifySubmit} isLoading={aiLoading}>
                        Submit Answers
                      </Button>
                      <Button size="sm" variant="ghost" onClick={handleDiscardGenerated}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}

                {/* Generated Rule Preview */}
                {aiResult?.status === 'complete' && aiResult.rule && (
                  <div className="bg-sky-500/10 border border-sky-500/30 rounded-lg p-4 space-y-3">
                    <div className="flex items-center gap-2 text-sky-400 text-sm font-medium">
                      <CheckCircle size={16} /> Generated Rule Preview
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
                      <div>
                        <span className="text-[var(--color-text-muted)]">ID:</span>{' '}
                        <span className="font-mono">{aiResult.rule.rule_id as string}</span>
                      </div>
                      <div>
                        <span className="text-[var(--color-text-muted)]">Name:</span>{' '}
                        {aiResult.rule.name as string}
                      </div>
                      <div>
                        <span className="text-[var(--color-text-muted)]">Field:</span>{' '}
                        <span className="font-mono">{aiResult.rule.field as string}</span>
                      </div>
                      <div>
                        <span className="text-[var(--color-text-muted)]">Operator:</span>{' '}
                        <span className="font-mono">{aiResult.rule.operator as string}</span>
                      </div>
                      <div>
                        <span className="text-[var(--color-text-muted)]">Threshold:</span>{' '}
                        <span className="font-mono">{formatThreshold(aiResult.rule.threshold)}</span>
                      </div>
                      <div>
                        <span className="text-[var(--color-text-muted)]">Outcome:</span>{' '}
                        {outcomeBadge(aiResult.rule.outcome as string)}
                      </div>
                    </div>

                    {aiResult.rule.description != null && (
                      <p className="text-sm text-[var(--color-text-muted)]">
                        {String(aiResult.rule.description)}
                      </p>
                    )}

                    {aiResult.explanation && (
                      <p className="text-xs text-[var(--color-text-muted)] italic">
                        {aiResult.explanation}
                      </p>
                    )}

                    <div className="flex gap-2 pt-1">
                      <Button size="sm" onClick={handleAddGeneratedRule}>
                        <Plus size={14} className="mr-1" /> Add Rule
                      </Button>
                      <Button size="sm" variant="ghost" onClick={handleDiscardGenerated}>
                        <X size={14} className="mr-1" /> Discard
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>
        </>
      )}

      {/* ═══════════════ HISTORY TAB ═══════════════ */}
      {activeTab === 'history' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-[var(--color-text-muted)]">
              {historyTotal} total audit entries
            </p>
            <Button size="sm" variant="ghost" onClick={loadHistory} disabled={historyLoading}>
              {historyLoading ? <Loader2 size={14} className="animate-spin mr-1" /> : null}
              Refresh
            </Button>
          </div>

          {historyLoading && historyEntries.length === 0 ? (
            <div className="flex items-center justify-center h-32 text-[var(--color-text-muted)]">
              <Loader2 className="animate-spin mr-2" size={20} /> Loading history...
            </div>
          ) : historyEntries.length === 0 ? (
            <Card>
              <p className="text-sm text-[var(--color-text-muted)] text-center py-8">
                No rules audit entries yet. Changes will appear here after rules are updated.
              </p>
            </Card>
          ) : (
            <div className="space-y-2">
              {historyEntries.map(entry => {
                const isExpanded = expandedHistoryId === entry.id;
                return (
                  <div
                    key={entry.id}
                    className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]"
                  >
                    <button
                      onClick={() => setExpandedHistoryId(isExpanded ? null : entry.id)}
                      className="flex items-center gap-3 px-4 py-3 w-full text-left"
                    >
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                        entry.action === 'rules_updated' ? 'bg-sky-500/10 text-sky-400' : 'bg-red-500/10 text-red-400'
                      }`}>
                        {entry.action === 'rules_updated' ? <Save size={14} /> : <Trash2 size={14} />}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 text-sm">
                          <span className="font-medium">
                            {entry.action === 'rules_updated' ? 'Rules Updated' : entry.action}
                          </span>
                          <span className="text-xs text-[var(--color-text-muted)] font-mono">
                            v{entry.version} → v{entry.new_version}
                          </span>
                          {entry.changes.length > 0 && (
                            <span className="text-xs text-[var(--color-text-muted)]">
                              ({entry.changes.length} change{entry.changes.length !== 1 ? 's' : ''})
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3 text-xs text-[var(--color-text-muted)] mt-0.5">
                          <span className="flex items-center gap-1">
                            <User size={10} /> {entry.user_name}
                          </span>
                          <span className="flex items-center gap-1">
                            <Clock size={10} /> {formatDate(entry.created_at)}
                          </span>
                        </div>
                      </div>

                      <span className="text-[var(--color-text-muted)] shrink-0">
                        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </span>
                    </button>

                    {isExpanded && entry.changes.length > 0 && (
                      <div className="px-4 pb-3 border-t border-[var(--color-border)] mx-4 mb-3 pt-3 space-y-2">
                        {entry.changes.map((change, idx) => (
                          <div
                            key={idx}
                            className={`text-xs rounded-md px-3 py-2 ${
                              change.change_type === 'added'
                                ? 'bg-green-500/10 border border-green-500/20'
                                : change.change_type === 'removed'
                                ? 'bg-red-500/10 border border-red-500/20'
                                : 'bg-sky-500/10 border border-sky-500/20'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <span className={`font-medium uppercase text-[10px] ${
                                change.change_type === 'added' ? 'text-green-400' :
                                change.change_type === 'removed' ? 'text-red-400' : 'text-sky-400'
                              }`}>
                                {change.change_type}
                              </span>
                              <span className="font-mono">{change.rule_id}</span>
                              {change.name && <span className="text-[var(--color-text-muted)]">({change.name})</span>}
                            </div>
                            {change.change_type === 'modified' && change.fields && (
                              <div className="mt-1 space-y-0.5">
                                {Object.entries(change.fields).map(([field, vals]) => (
                                  <div key={field} className="text-[var(--color-text-muted)]">
                                    <span className="font-mono">{field}:</span>{' '}
                                    <span className="text-red-400 line-through">{String(vals.old)}</span>{' → '}
                                    <span className="text-green-400">{String(vals.new)}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                        {entry.details && (
                          <p className="text-xs text-[var(--color-text-muted)] italic mt-2">{entry.details}</p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ═══════════════ AI ANALYSIS TAB ═══════════════ */}
      {activeTab === 'analysis' && (
        <div className="space-y-6">
          <Card>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Brain size={20} className="text-purple-400" />
                <div>
                  <h2 className="font-semibold">AI Rules Analysis</h2>
                  <p className="text-xs text-[var(--color-text-muted)]">
                    Analyze your rules configuration for optimization opportunities
                  </p>
                </div>
              </div>
              <Button onClick={handleAnalyze} isLoading={analysisLoading} size="sm">
                <Sparkles size={14} className="mr-1.5" /> Analyze Rules
              </Button>
            </div>
          </Card>

          {analysisLoading && (
            <div className="flex items-center justify-center h-32 text-[var(--color-text-muted)]">
              <Loader2 className="animate-spin mr-2" size={20} /> Running AI analysis...
            </div>
          )}

          {analysis && !analysisLoading && (
            <>
              {/* Summary */}
              <Card>
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <BarChart3 size={16} className="text-sky-400" />
                    <h3 className="font-medium">Summary</h3>
                    {analysis.ai_powered ? (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/30">AI-Powered</span>
                    ) : (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-gray-500/10 text-gray-400 border border-gray-500/30">Deterministic</span>
                    )}
                  </div>
                  <p className="text-sm text-[var(--color-text-muted)]">{analysis.summary}</p>
                  <div className="flex gap-6 text-sm">
                    <div>
                      <span className="text-[var(--color-text-muted)]">Total Applications:</span>{' '}
                      <span className="font-medium">{analysis.total_applications}</span>
                    </div>
                    <div>
                      <span className="text-[var(--color-text-muted)]">Rules Evaluated:</span>{' '}
                      <span className="font-medium">{analysis.rules_evaluated}</span>
                    </div>
                  </div>
                </div>
              </Card>

              {/* Top Decliners */}
              {analysis.top_decliners && analysis.top_decliners.length > 0 && (
                <Card>
                  <h3 className="font-medium mb-3 flex items-center gap-2">
                    <AlertTriangle size={16} className="text-red-400" />
                    Top Rules Causing Declines
                  </h3>
                  <div className="space-y-2">
                    {analysis.top_decliners.map((d, idx) => (
                      <div
                        key={idx}
                        className="flex items-center gap-3 px-3 py-2 rounded-md bg-[var(--color-bg)] border border-[var(--color-border)]"
                      >
                        <span className="font-mono text-xs w-12 shrink-0 text-[var(--color-text-muted)]">{d.rule_id}</span>
                        <span className="text-sm flex-1 min-w-0 truncate">{d.rule_name}</span>
                        <div className="flex items-center gap-3 text-xs shrink-0">
                          <span className="text-red-400 font-medium">{d.current_declines ?? 0} declines</span>
                          {d.decline_rate != null && (
                            <span className="text-[var(--color-text-muted)]">{d.decline_rate}% rate</span>
                          )}
                          {riskBadge(d.risk)}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {/* Recommendations */}
              {analysis.recommendations && analysis.recommendations.length > 0 && (
                <Card>
                  <h3 className="font-medium mb-3 flex items-center gap-2">
                    <Sparkles size={16} className="text-sky-400" />
                    Recommendations
                  </h3>
                  <div className="space-y-3">
                    {analysis.recommendations.map((rec, idx) => (
                      <div
                        key={idx}
                        className="px-4 py-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] space-y-1.5"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs text-[var(--color-text-muted)]">{rec.rule_id}</span>
                          <span className="text-sm font-medium">{rec.rule_name}</span>
                          {riskBadge(rec.risk)}
                          {rec.projected_impact && (
                            <span className="text-xs text-green-400 ml-auto">{rec.projected_impact}</span>
                          )}
                        </div>
                        <p className="text-sm text-[var(--color-text-muted)]">
                          {rec.change || rec.recommendation}
                        </p>
                        {rec.rationale && (
                          <p className="text-xs text-[var(--color-text-muted)] italic">{rec.rationale}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
