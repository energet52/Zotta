import { useEffect, useState, useCallback } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, ChevronDown, ChevronRight, Edit3, Save, X, Copy,
  Download, Play, RefreshCw, AlertTriangle, AlertCircle,
  CheckCircle, Activity, TrendingUp, BarChart3, FileText,
  Clock, Shield, Zap, Target, Hash, Layers,
  Info, Sliders, GitBranch,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import Input from '../../../components/ui/Input';
import Badge from '../../../components/ui/Badge';
import { scorecardsApi } from '../../../api/endpoints';

/* ═══════════════════════════════════════════════════════════
   Type Definitions
   ═══════════════════════════════════════════════════════════ */

interface Bin {
  id: number;
  bin_type: string;
  label: string;
  points: number;
  min_value: number | null;
  max_value: number | null;
  category_value: string | null;
}

interface Characteristic {
  id: number;
  code: string;
  name: string;
  data_field: string;
  is_active: boolean;
  weight_multiplier: number;
  bins: Bin[];
}

interface Scorecard {
  id: number;
  name: string;
  version: number;
  status: string;
  base_score: number;
  auto_approve_threshold: number;
  manual_review_threshold: number;
  auto_decline_threshold: number;
  script: string;
  characteristics: Characteristic[];
  created_at: string;
  updated_at: string;
  total_characteristics: number;
  total_bins: number;
  [key: string]: unknown;
}

interface CharacteristicScore {
  code: string;
  name: string;
  value: unknown;
  bin_label: string;
  weighted_points: number;
}

interface LiveCalcResult {
  total_score: number;
  characteristic_scores: CharacteristicScore[];
  decision: string;
  reason_codes: string[];
  top_positive_factors: string[];
  top_negative_factors: string[];
}

interface PerformanceSnapshot {
  total_scored: number;
  approval_rate: number;
  default_rate: number;
  gini: number;
  ks: number;
  psi: number;
  avg_score: number;
  score_distribution: { band: string; count: number; pct: number }[];
  score_band_analysis: {
    band: string;
    count: number;
    pct_of_total: number;
    approved: number;
    approval_rate: number;
    default_count: number;
    default_rate: number;
  }[];
}

interface PerformanceHistory {
  date: string;
  total_scored: number;
  approval_rate: number;
  default_rate: number;
  gini: number;
  ks: number;
  psi: number;
}

interface AlertItem {
  type: string;
  severity: string;
  title: string;
  message: string;
  recommendation: string;
  is_acknowledged: boolean;
}

interface ChangeLogEntry {
  change_type: string;
  field_path: string;
  old_value: string;
  new_value: string;
  justification: string;
  proposed_by_name: string;
  created_at: string;
}

interface WhatIfChange {
  code: string;
  name: string;
  original_value: unknown;
  modified_value: unknown;
  original_points: number;
  modified_points: number;
  point_change: number;
}

interface WhatIfResult {
  base_score: number;
  base_decision: string;
  modified_score: number;
  modified_decision: string;
  score_change: number;
  changes: WhatIfChange[];
}

type TabId = 'overview' | 'script' | 'performance' | 'audit';

/* ═══════════════════════════════════════════════════════════
   Helpers
   ═══════════════════════════════════════════════════════════ */

const fmt = (n: number | null | undefined, decimals = 0) => {
  if (n == null) return '—';
  return n.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
};

const pct = (n: number | null | undefined, decimals = 1) => {
  if (n == null) return '—';
  return `${(n * 100).toFixed(decimals)}%`;
};

const pctRaw = (n: number | null | undefined, decimals = 1) => {
  if (n == null) return '—';
  return `${n.toFixed(decimals)}%`;
};

const statusBadge = (status: string) => {
  const map: Record<string, 'success' | 'warning' | 'info' | 'danger' | 'default' | 'purple' | 'cyan'> = {
    champion: 'success',
    active: 'success',
    shadow: 'info',
    challenger: 'purple',
    draft: 'default',
    retired: 'danger',
    development: 'warning',
  };
  return <Badge variant={map[status] || 'default'}>{status}</Badge>;
};

const severityColor = (severity: string) => {
  switch (severity) {
    case 'critical': return 'text-red-400';
    case 'warning': return 'text-amber-400';
    case 'info': return 'text-sky-400';
    default: return 'text-[var(--color-text-muted)]';
  }
};

const severityIcon = (severity: string) => {
  switch (severity) {
    case 'critical': return <AlertCircle size={16} className="text-red-400" />;
    case 'warning': return <AlertTriangle size={16} className="text-amber-400" />;
    default: return <Info size={16} className="text-sky-400" />;
  }
};

const decisionBadge = (decision: string) => {
  const d = decision?.toLowerCase() || '';
  if (d.includes('approve')) return <Badge variant="success">{decision}</Badge>;
  if (d.includes('decline') || d.includes('reject')) return <Badge variant="danger">{decision}</Badge>;
  if (d.includes('review') || d.includes('manual')) return <Badge variant="warning">{decision}</Badge>;
  return <Badge variant="default">{decision}</Badge>;
};

/* ═══════════════════════════════════════════════════════════
   Create Scorecard Form (when id === 'new')
   ═══════════════════════════════════════════════════════════ */

export function CreateScorecardForm() {
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    name: '',
    description: '',
    base_score: '0',
    min_score: '100',
    max_score: '850',
  });

  const handleChange = (field: string, value: string) => {
    setForm(prev => ({ ...prev, [field]: value }));
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) {
      setError('Scorecard name is required');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const { data } = await scorecardsApi.create({
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        base_score: parseFloat(form.base_score) || 0,
        min_score: parseFloat(form.min_score) || 100,
        max_score: parseFloat(form.max_score) || 850,
        characteristics: [],
      });
      navigate(`/backoffice/scorecards/${data.id}`, { replace: true });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || 'Failed to create scorecard');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          to="/backoffice/scorecards"
          className="p-2 rounded-lg hover:bg-[var(--color-surface-hover)] transition-colors"
        >
          <ArrowLeft size={20} />
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Create New Scorecard</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Define the basic parameters for a new scoring model
          </p>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      <Card className="p-6">
        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium mb-1.5">
              Scorecard Name <span className="text-red-400">*</span>
            </label>
            <Input
              value={form.name}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleChange('name', e.target.value)}
              placeholder="e.g. Hire Purchase v2.0"
              className="w-full"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium mb-1.5">Description</label>
            <textarea
              value={form.description}
              onChange={(e) => handleChange('description', e.target.value)}
              placeholder="Describe the purpose and target population for this scorecard..."
              rows={3}
              className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:ring-2 focus:ring-[var(--color-primary)] focus:border-transparent resize-none"
            />
          </div>

          {/* Score Parameters */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1.5">Base Score</label>
              <Input
                type="number"
                value={form.base_score}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleChange('base_score', e.target.value)}
                className="w-full"
              />
              <p className="text-xs text-[var(--color-text-muted)] mt-1">Starting score before characteristics</p>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">Min Score</label>
              <Input
                type="number"
                value={form.min_score}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleChange('min_score', e.target.value)}
                className="w-full"
              />
              <p className="text-xs text-[var(--color-text-muted)] mt-1">Score floor</p>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1.5">Max Score</label>
              <Input
                type="number"
                value={form.max_score}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleChange('max_score', e.target.value)}
                className="w-full"
              />
              <p className="text-xs text-[var(--color-text-muted)] mt-1">Score ceiling</p>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 text-sm text-blue-300 flex items-start gap-2">
            <Info size={16} className="mt-0.5 flex-shrink-0" />
            <span>
              After creating the scorecard, you can add characteristics and bins by importing a CSV
              or editing directly on the scorecard detail page.
            </span>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 pt-2">
            <Button type="submit" disabled={saving}>
              {saving ? (
                <span className="flex items-center gap-2">
                  <RefreshCw size={14} className="animate-spin" /> Creating...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Save size={14} /> Create Scorecard
                </span>
              )}
            </Button>
            <Link to="/backoffice/scorecards">
              <Button type="button" variant="secondary">Cancel</Button>
            </Link>
          </div>
        </form>
      </Card>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Main Component
   ═══════════════════════════════════════════════════════════ */

export default function ScorecardDetail() {
  const { id } = useParams<{ id: string }>();
  const scorecardId = Number(id);

  // ── State ──
  const [scorecard, setScorecard] = useState<Scorecard | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>('overview');

  // Overview
  const [expandedChars, setExpandedChars] = useState<Set<number>>(new Set());
  const [editingBin, setEditingBin] = useState<number | null>(null);
  const [editPoints, setEditPoints] = useState('');
  const [editJustification, setEditJustification] = useState('');
  const [savingBin, setSavingBin] = useState(false);
  const [editingWeight, setEditingWeight] = useState<number | null>(null);
  const [weightForm, setWeightForm] = useState({ multiplier: 1, justification: '' });
  const [savingWeight, setSavingWeight] = useState(false);

  // Script tab
  const [script, setScript] = useState('');
  const [editedScript, setEditedScript] = useState('');
  const [editingScript, setEditingScript] = useState(false);
  const [savingScript, setSavingScript] = useState(false);
  const [scriptSaveError, setScriptSaveError] = useState('');
  const [loadingScript, setLoadingScript] = useState(false);
  const [copied, setCopied] = useState(false);

  // Live calc
  const [calcInputs, setCalcInputs] = useState<Record<string, string>>({});
  const [calcResult, setCalcResult] = useState<LiveCalcResult | null>(null);
  const [calculating, setCalculating] = useState(false);

  // What-if
  const [whatIfAppId, setWhatIfAppId] = useState('');
  const [whatIfMods, setWhatIfMods] = useState<Record<string, string>>({});
  const [whatIfResult, setWhatIfResult] = useState<WhatIfResult | null>(null);
  const [whatIfLoading, setWhatIfLoading] = useState(false);

  // Performance tab
  const [perfSnapshot, setPerfSnapshot] = useState<PerformanceSnapshot | null>(null);
  const [perfHistory, setPerfHistory] = useState<PerformanceHistory[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loadingPerf, setLoadingPerf] = useState(false);

  // Audit tab
  const [changeLog, setChangeLog] = useState<ChangeLogEntry[]>([]);
  const [loadingLog, setLoadingLog] = useState(false);

  // ── Data loading ──
  const loadScorecard = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await scorecardsApi.get(scorecardId);
      setScorecard(data);
      // Keep script in sync with scorecard data (reverse direction)
      if (data.script) {
        setScript(data.script);
      }
    } catch (e) {
      console.error('Failed to load scorecard', e);
    } finally {
      setLoading(false);
    }
  }, [scorecardId]);

  const loadScript = useCallback(async () => {
    setLoadingScript(true);
    try {
      const { data } = await scorecardsApi.getScript(scorecardId);
      setScript(data.script || scorecard?.script || '');
    } catch {
      setScript(scorecard?.script || '');
    } finally {
      setLoadingScript(false);
    }
  }, [scorecardId, scorecard?.script]);

  const loadPerformance = useCallback(async () => {
    setLoadingPerf(true);
    try {
      const [perfRes, alertRes] = await Promise.all([
        scorecardsApi.getPerformance(scorecardId),
        scorecardsApi.getAlerts(scorecardId),
      ]);
      setPerfSnapshot(perfRes.data.snapshot || perfRes.data);
      setPerfHistory(perfRes.data.history || []);
      setAlerts(alertRes.data || []);
    } catch (e) {
      console.error('Failed to load performance', e);
    } finally {
      setLoadingPerf(false);
    }
  }, [scorecardId]);

  const loadChangeLog = useCallback(async () => {
    setLoadingLog(true);
    try {
      const { data } = await scorecardsApi.getChangeLog(scorecardId);
      setChangeLog(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error('Failed to load change log', e);
    } finally {
      setLoadingLog(false);
    }
  }, [scorecardId]);

  useEffect(() => { loadScorecard(); }, [loadScorecard]);

  useEffect(() => {
    if (activeTab === 'script') loadScript();
    if (activeTab === 'performance') loadPerformance();
    if (activeTab === 'audit') loadChangeLog();
  }, [activeTab, loadScript, loadPerformance, loadChangeLog]);

  // ── Actions ──
  const handleSaveBinPoints = async (binId: number) => {
    setSavingBin(true);
    try {
      await scorecardsApi.editPoints(scorecardId, {
        bin_id: binId,
        new_points: parseFloat(editPoints),
        justification: editJustification,
      });
      setEditingBin(null);
      setEditPoints('');
      setEditJustification('');
      await loadScorecard();
    } catch (e) {
      console.error('Failed to save bin points', e);
    } finally {
      setSavingBin(false);
    }
  };


  const handleSaveWeight = async (charId: number) => {
    setSavingWeight(true);
    try {
      await scorecardsApi.weightScale(scorecardId, {
        characteristic_id: charId,
        multiplier: parseFloat(String(weightForm.multiplier)),
        justification: weightForm.justification,
      });
      setEditingWeight(null);
      setWeightForm({ multiplier: 1, justification: '' });
      await loadScorecard();
    } catch (e) {
      console.error('Failed to save weight', e);
    } finally {
      setSavingWeight(false);
    }
  };

  const handleCopyScript = () => {
    navigator.clipboard.writeText(editingScript ? editedScript : script);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadScript = () => {
    const content = editingScript ? editedScript : script;
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `scorecard_${scorecardId}_script.py`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleEditScript = () => {
    setEditedScript(script);
    setEditingScript(true);
    setScriptSaveError('');
  };

  const handleCancelEditScript = () => {
    setEditingScript(false);
    setEditedScript('');
    setScriptSaveError('');
  };

  const handleSaveScript = async () => {
    setSavingScript(true);
    setScriptSaveError('');
    try {
      const { data } = await scorecardsApi.saveScript(scorecardId, {
        script: editedScript,
        justification: 'Script edited via UI',
      });
      // Refresh scorecard data (characteristics & bins updated on the backend)
      setScorecard(data);
      // Regenerate script from returned data
      setScript(data.script || editedScript);
      setEditingScript(false);
      setEditedScript('');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setScriptSaveError(detail || 'Failed to save script');
    } finally {
      setSavingScript(false);
    }
  };

  const handleLiveCalculate = async () => {
    setCalculating(true);
    try {
      const applicantData: Record<string, unknown> = {};
      Object.entries(calcInputs).forEach(([key, val]) => {
        const num = parseFloat(val);
        applicantData[key] = isNaN(num) ? val : num;
      });
      const { data } = await scorecardsApi.liveCalculate(scorecardId, applicantData);
      setCalcResult(data);
    } catch (e) {
      console.error('Live calc failed', e);
    } finally {
      setCalculating(false);
    }
  };

  const handleWhatIf = async () => {
    if (!whatIfAppId) return;
    setWhatIfLoading(true);
    try {
      const modifications: Record<string, unknown> = {};
      Object.entries(whatIfMods).forEach(([key, val]) => {
        if (val !== '') {
          const num = parseFloat(val);
          modifications[key] = isNaN(num) ? val : num;
        }
      });
      const { data } = await scorecardsApi.whatIf(scorecardId, {
        application_id: parseInt(whatIfAppId),
        modifications,
      });
      setWhatIfResult(data);
    } catch (e) {
      console.error('What-if failed', e);
    } finally {
      setWhatIfLoading(false);
    }
  };

  const toggleChar = (charId: number) => {
    setExpandedChars(prev => {
      const next = new Set(prev);
      if (next.has(charId)) next.delete(charId);
      else next.add(charId);
      return next;
    });
  };

  // ── Loading state ──
  if (loading || !scorecard) {
    return (
      <div className="flex items-center justify-center h-96">
        <RefreshCw className="animate-spin text-[var(--color-primary)]" size={32} />
      </div>
    );
  }

  // ── Tab definitions ──
  const tabs: { id: TabId; label: string; icon: React.ReactNode }[] = [
    { id: 'overview', label: 'Overview', icon: <Layers size={16} /> },
    { id: 'script', label: 'Score Script', icon: <FileText size={16} /> },
    { id: 'performance', label: 'Performance', icon: <BarChart3 size={16} /> },
    { id: 'audit', label: 'Audit Trail', icon: <Clock size={16} /> },
  ];

  /* ═══════════════════════════════════════════════════════════
     RENDER
     ═══════════════════════════════════════════════════════════ */

  return (
    <div className="space-y-6">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/backoffice/scorecards"
            className="p-2 rounded-lg hover:bg-[var(--color-surface)] border border-[var(--color-border)] transition-colors"
          >
            <ArrowLeft size={20} className="text-[var(--color-text-muted)]" />
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-[var(--color-text)]">{scorecard.name}</h1>
              {statusBadge(scorecard.status)}
              <Badge variant="info">v{scorecard.version}</Badge>
            </div>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              ID #{scorecard.id} &middot; {scorecard.total_characteristics || scorecard.characteristics?.length || 0} characteristics &middot; {scorecard.total_bins || '—'} bins &middot; Base score: {fmt(scorecard.base_score)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" onClick={loadScorecard}>
            <RefreshCw size={14} className="mr-1" /> Refresh
          </Button>
        </div>
      </div>

      {/* ── Tabs ── */}
      <div className="flex gap-1 p-1 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.id
                ? 'bg-[var(--color-primary)] text-white shadow-lg'
                : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg)]'
            }`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* ═══════════════════ OVERVIEW TAB ═══════════════════ */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* ── KPI Row ── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card padding="sm">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-blue-500/15">
                  <Target size={18} className="text-blue-400" />
                </div>
                <div>
                  <div className="text-xs text-[var(--color-text-muted)]">Base Score</div>
                  <div className="text-lg font-bold text-[var(--color-text)]">{fmt(scorecard.base_score)}</div>
                </div>
              </div>
            </Card>
          </div>
          {/* Cutoff thresholds are managed in Rules Management (R21) */}

          {/* ── Characteristics Accordion ── */}
          <Card>
            <h2 className="text-lg font-semibold text-[var(--color-text)] flex items-center gap-2 mb-4">
              <Layers size={18} /> Characteristics &amp; Bins
            </h2>
            <div className="space-y-2">
              {scorecard.characteristics?.map(char => (
                <div key={char.id} className="border border-[var(--color-border)] rounded-lg overflow-hidden">
                  {/* Characteristic header */}
                  <button
                    onClick={() => toggleChar(char.id)}
                    className="w-full flex items-center justify-between px-4 py-3 hover:bg-[var(--color-bg)] transition-colors text-left"
                  >
                    <div className="flex items-center gap-3">
                      {expandedChars.has(char.id)
                        ? <ChevronDown size={16} className="text-[var(--color-text-muted)]" />
                        : <ChevronRight size={16} className="text-[var(--color-text-muted)]" />
                      }
                      <div>
                        <span className="font-medium text-[var(--color-text)]">{char.name}</span>
                        <span className="ml-2 text-xs text-[var(--color-text-muted)]">({char.code})</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {!char.is_active && <Badge variant="danger">Inactive</Badge>}
                      <span className="text-xs text-[var(--color-text-muted)]">
                        {char.bins?.length || 0} bins
                      </span>
                      <span className="text-xs text-[var(--color-text-muted)]">
                        Weight: {char.weight_multiplier}x
                      </span>
                      {editingWeight !== char.id && (
                        <button
                          onClick={e => { e.stopPropagation(); setEditingWeight(char.id); setWeightForm({ multiplier: char.weight_multiplier, justification: '' }); }}
                          className="p-1 rounded hover:bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-primary)]"
                          title="Scale weight"
                        >
                          <Sliders size={14} />
                        </button>
                      )}
                    </div>
                  </button>

                  {/* Weight editor */}
                  {editingWeight === char.id && (
                    <div className="px-4 py-3 bg-[var(--color-bg)] border-t border-[var(--color-border)] flex items-end gap-3" onClick={e => e.stopPropagation()}>
                      <Input
                        label="Multiplier"
                        type="number"
                        step="0.1"
                        value={weightForm.multiplier}
                        onChange={e => setWeightForm(f => ({ ...f, multiplier: parseFloat(e.target.value) || 1 }))}
                        className="!w-28"
                      />
                      <Input
                        label="Justification"
                        value={weightForm.justification}
                        onChange={e => setWeightForm(f => ({ ...f, justification: e.target.value }))}
                        placeholder="Reason..."
                      />
                      <Button size="sm" onClick={() => handleSaveWeight(char.id)} isLoading={savingWeight}>
                        <Save size={14} />
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => setEditingWeight(null)}>
                        <X size={14} />
                      </Button>
                    </div>
                  )}

                  {/* Expanded bins table */}
                  {expandedChars.has(char.id) && (
                    <div className="border-t border-[var(--color-border)]">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-[var(--color-bg)]">
                            <th className="px-4 py-2 text-left text-xs font-medium text-[var(--color-text-muted)]">Label</th>
                            <th className="px-4 py-2 text-left text-xs font-medium text-[var(--color-text-muted)]">Type</th>
                            <th className="px-4 py-2 text-right text-xs font-medium text-[var(--color-text-muted)]">Range / Category</th>
                            <th className="px-4 py-2 text-right text-xs font-medium text-[var(--color-text-muted)]">Points</th>
                            <th className="px-4 py-2 text-right text-xs font-medium text-[var(--color-text-muted)]">Weighted</th>
                            <th className="px-4 py-2 text-center text-xs font-medium text-[var(--color-text-muted)]">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[var(--color-border)]">
                          {char.bins?.map(bin => (
                            <tr key={bin.id} className="hover:bg-[var(--color-bg)] transition-colors">
                              <td className="px-4 py-2.5 text-[var(--color-text)]">{bin.label}</td>
                              <td className="px-4 py-2.5">
                                <span className="text-xs px-2 py-0.5 rounded-md bg-[var(--color-bg)] text-[var(--color-text-muted)] border border-[var(--color-border)]">
                                  {bin.bin_type}
                                </span>
                              </td>
                              <td className="px-4 py-2.5 text-right text-[var(--color-text-muted)] text-xs font-mono">
                                {bin.category_value
                                  ? bin.category_value
                                  : bin.min_value != null || bin.max_value != null
                                    ? `${bin.min_value ?? '−∞'} — ${bin.max_value ?? '+∞'}`
                                    : '—'}
                              </td>
                              <td className="px-4 py-2.5 text-right">
                                {editingBin === bin.id ? (
                                  <div className="flex items-center justify-end gap-2">
                                    <input
                                      type="number"
                                      value={editPoints}
                                      onChange={e => setEditPoints(e.target.value)}
                                      className="w-20 px-2 py-1 text-sm text-right rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                                      autoFocus
                                    />
                                  </div>
                                ) : (
                                  <span className={`font-mono font-medium ${bin.points >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                    {bin.points >= 0 ? '+' : ''}{fmt(bin.points, 1)}
                                  </span>
                                )}
                              </td>
                              <td className="px-4 py-2.5 text-right font-mono text-[var(--color-text-muted)]">
                                {fmt(bin.points * char.weight_multiplier, 1)}
                              </td>
                              <td className="px-4 py-2.5 text-center">
                                {editingBin === bin.id ? (
                                  <div className="flex items-center justify-center gap-1">
                                    <input
                                      type="text"
                                      value={editJustification}
                                      onChange={e => setEditJustification(e.target.value)}
                                      placeholder="Reason..."
                                      className="w-28 px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
                                    />
                                    <button
                                      onClick={() => handleSaveBinPoints(bin.id)}
                                      disabled={savingBin}
                                      className="p-1 rounded text-emerald-400 hover:bg-emerald-500/15 disabled:opacity-50"
                                    >
                                      <Save size={14} />
                                    </button>
                                    <button
                                      onClick={() => { setEditingBin(null); setEditPoints(''); setEditJustification(''); }}
                                      className="p-1 rounded text-[var(--color-text-muted)] hover:bg-[var(--color-bg)]"
                                    >
                                      <X size={14} />
                                    </button>
                                  </div>
                                ) : (
                                  <button
                                    onClick={() => { setEditingBin(bin.id); setEditPoints(String(bin.points)); setEditJustification(''); }}
                                    className="p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-primary)] hover:bg-[var(--color-primary)]/10 transition-colors"
                                    title="Edit points"
                                  >
                                    <Edit3 size={14} />
                                  </button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* ═══════════════════ SCRIPT TAB ═══════════════════ */}
      {activeTab === 'script' && (
        <div className="space-y-6">
          {/* ── Raw Script ── */}
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-[var(--color-text)] flex items-center gap-2">
                <FileText size={18} /> Scoring Script
                {editingScript && (
                  <Badge variant="warning">Editing</Badge>
                )}
              </h2>
              <div className="flex items-center gap-2">
                {editingScript ? (
                  <>
                    <Button variant="primary" size="sm" onClick={handleSaveScript} isLoading={savingScript}>
                      <Save size={14} className="mr-1" /> Save Script
                    </Button>
                    <Button variant="ghost" size="sm" onClick={handleCancelEditScript} disabled={savingScript}>
                      <X size={14} className="mr-1" /> Cancel
                    </Button>
                  </>
                ) : (
                  <>
                    <Button variant="secondary" size="sm" onClick={handleEditScript}>
                      <Edit3 size={14} className="mr-1" /> Edit
                    </Button>
                    <Button variant="ghost" size="sm" onClick={handleCopyScript}>
                      <Copy size={14} className="mr-1" /> {copied ? 'Copied!' : 'Copy'}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={handleDownloadScript}>
                      <Download size={14} className="mr-1" /> Download
                    </Button>
                    <Button variant="ghost" size="sm" onClick={loadScript} isLoading={loadingScript}>
                      <RefreshCw size={14} className="mr-1" /> Reload
                    </Button>
                  </>
                )}
              </div>
            </div>

            {scriptSaveError && (
              <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
                <AlertCircle size={16} /> {scriptSaveError}
              </div>
            )}

            {editingScript && (
              <div className="mb-3 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 text-sm text-blue-300 flex items-start gap-2">
                <Info size={16} className="mt-0.5 flex-shrink-0" />
                <span>
                  Edit the script below. When you save, the characteristics and bins will be
                  automatically updated to reflect your changes. Keep the comment format intact
                  (e.g. <code className="bg-blue-500/20 px-1 rounded"># Characteristic: CODE - Name (field: data_field)</code>)
                  so the parser can correctly identify each characteristic.
                </span>
              </div>
            )}

            <div className="relative rounded-lg overflow-hidden border border-[var(--color-border)]">
              {editingScript ? (
                <textarea
                  value={editedScript}
                  onChange={e => setEditedScript(e.target.value)}
                  spellCheck={false}
                  className="w-full min-h-[500px] p-4 text-sm leading-relaxed font-mono text-[var(--color-text)] bg-[var(--color-bg)] resize-y focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] border-none"
                  style={{ tabSize: 2 }}
                />
              ) : (
                <div className="overflow-auto max-h-[500px]">
                  <pre className="p-4 text-sm leading-relaxed font-mono text-[var(--color-text)] bg-[var(--color-bg)] whitespace-pre-wrap">
                    {loadingScript ? (
                      <span className="text-[var(--color-text-muted)]">Loading script...</span>
                    ) : script ? (
                      script.split('\n').map((line, i) => (
                        <div key={i} className="flex hover:bg-[var(--color-surface)] -mx-4 px-4">
                          <span className="select-none w-10 text-right mr-4 text-[var(--color-text-muted)] opacity-40 flex-shrink-0">
                            {i + 1}
                          </span>
                          <span className="flex-1">{highlightLine(line)}</span>
                        </div>
                      ))
                    ) : (
                      <span className="text-[var(--color-text-muted)]">No script available</span>
                    )}
                  </pre>
                </div>
              )}
            </div>

            {editingScript && editedScript !== script && (
              <div className="mt-3 text-xs text-[var(--color-text-muted)] flex items-center gap-1">
                <Activity size={12} /> Unsaved changes detected
              </div>
            )}
          </Card>

          {/* ── Live Calculation ── */}
          <Card>
            <h2 className="text-lg font-semibold text-[var(--color-text)] flex items-center gap-2 mb-4">
              <Play size={18} /> Live Score Calculation
            </h2>
            <p className="text-sm text-[var(--color-text-muted)] mb-4">
              Enter applicant data values for each characteristic to see a step-by-step score trace.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
              {scorecard.characteristics?.filter(c => c.is_active).map(char => (
                <Input
                  key={char.id}
                  label={`${char.name} (${char.data_field})`}
                  value={calcInputs[char.data_field] || ''}
                  onChange={e => setCalcInputs(prev => ({ ...prev, [char.data_field]: e.target.value }))}
                  placeholder={`Enter ${char.data_field}...`}
                />
              ))}
            </div>

            <div className="flex gap-2 mb-4">
              <Button onClick={handleLiveCalculate} isLoading={calculating}>
                <Zap size={14} className="mr-1" /> Calculate Score
              </Button>
              <Button variant="ghost" onClick={() => { setCalcInputs({}); setCalcResult(null); }}>
                <X size={14} className="mr-1" /> Clear
              </Button>
            </div>

            {calcResult && (
              <div className="space-y-4 mt-4 pt-4 border-t border-[var(--color-border)]">
                {/* Score result header */}
                <div className="flex items-center gap-6">
                  <div className="text-center">
                    <div className="text-4xl font-bold text-[var(--color-primary)]">{fmt(calcResult.total_score)}</div>
                    <div className="text-xs text-[var(--color-text-muted)] mt-1">Total Score</div>
                  </div>
                  <div>{decisionBadge(calcResult.decision)}</div>
                </div>

                {/* Score trace table */}
                <div className="overflow-auto rounded-lg border border-[var(--color-border)]">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-[var(--color-bg)]">
                        <th className="px-4 py-2 text-left text-xs font-medium text-[var(--color-text-muted)]">Characteristic</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-[var(--color-text-muted)]">Input Value</th>
                        <th className="px-4 py-2 text-left text-xs font-medium text-[var(--color-text-muted)]">Matched Bin</th>
                        <th className="px-4 py-2 text-right text-xs font-medium text-[var(--color-text-muted)]">Weighted Points</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--color-border)]">
                      <tr className="bg-[var(--color-bg)]/50">
                        <td className="px-4 py-2 text-[var(--color-text-muted)] italic">Base Score</td>
                        <td className="px-4 py-2">—</td>
                        <td className="px-4 py-2">—</td>
                        <td className="px-4 py-2 text-right font-mono text-[var(--color-text)]">{fmt(scorecard.base_score)}</td>
                      </tr>
                      {calcResult.characteristic_scores.map((cs, i) => (
                        <tr key={i} className="hover:bg-[var(--color-bg)] transition-colors">
                          <td className="px-4 py-2">
                            <span className="text-[var(--color-text)]">{cs.name}</span>
                            <span className="text-xs text-[var(--color-text-muted)] ml-1">({cs.code})</span>
                          </td>
                          <td className="px-4 py-2 font-mono text-[var(--color-text-muted)]">{String(cs.value)}</td>
                          <td className="px-4 py-2 text-[var(--color-text-muted)]">{cs.bin_label}</td>
                          <td className="px-4 py-2 text-right">
                            <span className={`font-mono font-medium ${cs.weighted_points >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                              {cs.weighted_points >= 0 ? '+' : ''}{fmt(cs.weighted_points, 1)}
                            </span>
                          </td>
                        </tr>
                      ))}
                      <tr className="bg-[var(--color-surface)] font-semibold">
                        <td className="px-4 py-2 text-[var(--color-text)]">Total</td>
                        <td className="px-4 py-2" colSpan={2}></td>
                        <td className="px-4 py-2 text-right font-mono text-[var(--color-primary)]">{fmt(calcResult.total_score)}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* Factors */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {calcResult.top_positive_factors?.length > 0 && (
                    <div className="p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/20">
                      <div className="text-xs font-medium text-emerald-400 mb-2 flex items-center gap-1">
                        <TrendingUp size={14} /> Top Positive Factors
                      </div>
                      <ul className="space-y-1">
                        {calcResult.top_positive_factors.map((f, i) => (
                          <li key={i} className="text-sm text-[var(--color-text)]">+ {f}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {calcResult.top_negative_factors?.length > 0 && (
                    <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/20">
                      <div className="text-xs font-medium text-red-400 mb-2 flex items-center gap-1">
                        <AlertTriangle size={14} /> Top Negative Factors
                      </div>
                      <ul className="space-y-1">
                        {calcResult.top_negative_factors.map((f, i) => (
                          <li key={i} className="text-sm text-[var(--color-text)]">- {f}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                {/* Reason codes */}
                {calcResult.reason_codes?.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    <span className="text-xs text-[var(--color-text-muted)]">Reason Codes:</span>
                    {calcResult.reason_codes.map((rc, i) => (
                      <Badge key={i} variant="info">{rc}</Badge>
                    ))}
                  </div>
                )}
              </div>
            )}
          </Card>

          {/* ── What-If Analysis ── */}
          <Card>
            <h2 className="text-lg font-semibold text-[var(--color-text)] flex items-center gap-2 mb-4">
              <GitBranch size={18} /> What-If Analysis
            </h2>
            <p className="text-sm text-[var(--color-text-muted)] mb-4">
              Select an existing application and modify characteristic values to see how the score would change.
            </p>

            <div className="space-y-4">
              <Input
                label="Application ID"
                type="number"
                value={whatIfAppId}
                onChange={e => setWhatIfAppId(e.target.value)}
                placeholder="Enter application ID..."
              />

              {scorecard.characteristics?.filter(c => c.is_active).length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-2">
                    Modifications (leave blank to keep original)
                  </label>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {scorecard.characteristics?.filter(c => c.is_active).map(char => (
                      <Input
                        key={char.id}
                        label={char.name}
                        value={whatIfMods[char.data_field] || ''}
                        onChange={e => setWhatIfMods(prev => ({ ...prev, [char.data_field]: e.target.value }))}
                        placeholder={`Modify ${char.data_field}...`}
                      />
                    ))}
                  </div>
                </div>
              )}

              <Button onClick={handleWhatIf} isLoading={whatIfLoading} disabled={!whatIfAppId}>
                <Activity size={14} className="mr-1" /> Run What-If
              </Button>
            </div>

            {whatIfResult && (
              <div className="mt-6 pt-4 border-t border-[var(--color-border)] space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                  <div className="text-center p-3 rounded-lg bg-[var(--color-bg)]">
                    <div className="text-2xl font-bold text-[var(--color-text)]">{fmt(whatIfResult.base_score)}</div>
                    <div className="text-xs text-[var(--color-text-muted)]">Base Score</div>
                    <div className="mt-1">{decisionBadge(whatIfResult.base_decision)}</div>
                  </div>
                  <div className="flex items-center justify-center text-[var(--color-text-muted)]">
                    <span className="text-2xl">&rarr;</span>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-[var(--color-bg)]">
                    <div className="text-2xl font-bold text-[var(--color-primary)]">{fmt(whatIfResult.modified_score)}</div>
                    <div className="text-xs text-[var(--color-text-muted)]">Modified Score</div>
                    <div className="mt-1">{decisionBadge(whatIfResult.modified_decision)}</div>
                  </div>
                  <div className="flex items-center justify-center text-[var(--color-text-muted)]">
                    <span className="text-2xl">=</span>
                  </div>
                  <div className="text-center p-3 rounded-lg bg-[var(--color-bg)]">
                    <div className={`text-2xl font-bold ${whatIfResult.score_change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {whatIfResult.score_change >= 0 ? '+' : ''}{fmt(whatIfResult.score_change)}
                    </div>
                    <div className="text-xs text-[var(--color-text-muted)]">Change</div>
                  </div>
                </div>

                {whatIfResult.changes?.length > 0 && (
                  <div className="overflow-auto rounded-lg border border-[var(--color-border)]">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-[var(--color-bg)]">
                          <th className="px-4 py-2 text-left text-xs font-medium text-[var(--color-text-muted)]">Characteristic</th>
                          <th className="px-4 py-2 text-center text-xs font-medium text-[var(--color-text-muted)]">Original Value</th>
                          <th className="px-4 py-2 text-center text-xs font-medium text-[var(--color-text-muted)]">Modified Value</th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-[var(--color-text-muted)]">Original Pts</th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-[var(--color-text-muted)]">Modified Pts</th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-[var(--color-text-muted)]">Change</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--color-border)]">
                        {whatIfResult.changes.map((ch, i) => (
                          <tr key={i} className="hover:bg-[var(--color-bg)] transition-colors">
                            <td className="px-4 py-2 text-[var(--color-text)]">
                              {ch.name} <span className="text-xs text-[var(--color-text-muted)]">({ch.code})</span>
                            </td>
                            <td className="px-4 py-2 text-center font-mono text-[var(--color-text-muted)]">{String(ch.original_value)}</td>
                            <td className="px-4 py-2 text-center font-mono text-[var(--color-text)]">{String(ch.modified_value)}</td>
                            <td className="px-4 py-2 text-right font-mono text-[var(--color-text-muted)]">{fmt(ch.original_points, 1)}</td>
                            <td className="px-4 py-2 text-right font-mono text-[var(--color-text)]">{fmt(ch.modified_points, 1)}</td>
                            <td className="px-4 py-2 text-right">
                              <span className={`font-mono font-medium ${ch.point_change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                                {ch.point_change >= 0 ? '+' : ''}{fmt(ch.point_change, 1)}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* ═══════════════════ PERFORMANCE TAB ═══════════════════ */}
      {activeTab === 'performance' && (
        <div className="space-y-6">
          {loadingPerf ? (
            <div className="flex items-center justify-center h-48">
              <RefreshCw className="animate-spin text-[var(--color-primary)]" size={28} />
            </div>
          ) : perfSnapshot ? (
            <>
              {/* ── KPIs ── */}
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4">
                {[
                  { label: 'Total Scored', value: fmt(perfSnapshot.total_scored), icon: <Hash size={16} />, color: 'blue' },
                  { label: 'Avg Score', value: fmt(perfSnapshot.avg_score), icon: <Target size={16} />, color: 'purple' },
                  { label: 'Gini', value: pct(perfSnapshot.gini), icon: <TrendingUp size={16} />, color: 'emerald' },
                  { label: 'KS', value: pct(perfSnapshot.ks), icon: <Activity size={16} />, color: 'cyan' },
                  { label: 'PSI', value: perfSnapshot.psi?.toFixed(4) || '—', icon: <Shield size={16} />, color: perfSnapshot.psi > 0.25 ? 'red' : perfSnapshot.psi > 0.1 ? 'amber' : 'emerald' },
                  { label: 'Approval Rate', value: pctRaw(perfSnapshot.approval_rate), icon: <CheckCircle size={16} />, color: 'emerald' },
                  { label: 'Default Rate', value: pctRaw(perfSnapshot.default_rate), icon: <AlertCircle size={16} />, color: 'red' },
                ].map((kpi, i) => (
                  <Card key={i} padding="sm">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-${kpi.color}-400`}>{kpi.icon}</span>
                      <span className="text-xs text-[var(--color-text-muted)]">{kpi.label}</span>
                    </div>
                    <div className="text-xl font-bold text-[var(--color-text)]">{kpi.value}</div>
                  </Card>
                ))}
              </div>

              {/* ── Score Distribution Histogram ── */}
              {perfSnapshot.score_distribution?.length > 0 && (
                <Card>
                  <h2 className="text-lg font-semibold text-[var(--color-text)] flex items-center gap-2 mb-4">
                    <BarChart3 size={18} /> Score Distribution
                  </h2>
                  <div className="flex items-end gap-1" style={{ height: 200 }}>
                    {(() => {
                      const maxCount = Math.max(...perfSnapshot.score_distribution.map(d => d.count), 1);
                      return perfSnapshot.score_distribution.map((d, i) => (
                        <div key={i} className="flex-1 flex flex-col items-center gap-1 group" title={`${d.band}: ${fmt(d.count)} (${pctRaw(d.pct)})`}>
                          <div className="text-[10px] text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 transition-opacity">
                            {fmt(d.count)}
                          </div>
                          <div
                            className="w-full rounded-t-md transition-all group-hover:brightness-125"
                            style={{
                              height: `${Math.max((d.count / maxCount) * 160, 2)}px`,
                              background: `linear-gradient(to top, var(--color-primary), color-mix(in srgb, var(--color-primary) 70%, white))`,
                              opacity: 0.6 + (d.count / maxCount) * 0.4,
                            }}
                          />
                          <div className="text-[10px] text-[var(--color-text-muted)] whitespace-nowrap transform -rotate-45 origin-top-left mt-1">
                            {d.band}
                          </div>
                        </div>
                      ));
                    })()}
                  </div>
                  <div className="mt-8 flex items-center justify-between text-xs text-[var(--color-text-muted)]">
                    <span>Lower scores</span>
                    <span>Higher scores</span>
                  </div>
                </Card>
              )}

              {/* ── Score Band Analysis Table ── */}
              {perfSnapshot.score_band_analysis?.length > 0 && (
                <Card>
                  <h2 className="text-lg font-semibold text-[var(--color-text)] flex items-center gap-2 mb-4">
                    <Layers size={18} /> Score Band Analysis
                  </h2>
                  <div className="overflow-auto rounded-lg border border-[var(--color-border)]">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-[var(--color-bg)]">
                          <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-muted)]">Band</th>
                          <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--color-text-muted)]">Count</th>
                          <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--color-text-muted)]">% of Total</th>
                          <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--color-text-muted)]">Approved</th>
                          <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--color-text-muted)]">Approval Rate</th>
                          <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--color-text-muted)]">Defaults</th>
                          <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--color-text-muted)]">Default Rate</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--color-border)]">
                        {perfSnapshot.score_band_analysis.map((band, i) => (
                          <tr key={i} className="hover:bg-[var(--color-bg)] transition-colors">
                            <td className="px-4 py-2.5 font-medium text-[var(--color-text)]">{band.band}</td>
                            <td className="px-4 py-2.5 text-right font-mono text-[var(--color-text)]">{fmt(band.count)}</td>
                            <td className="px-4 py-2.5 text-right text-[var(--color-text-muted)]">
                              <div className="flex items-center justify-end gap-2">
                                <div className="w-16 h-1.5 rounded-full bg-[var(--color-border)] overflow-hidden">
                                  <div
                                    className="h-full rounded-full bg-[var(--color-primary)]"
                                    style={{ width: `${Math.min(band.pct_of_total, 100)}%` }}
                                  />
                                </div>
                                {pctRaw(band.pct_of_total)}
                              </div>
                            </td>
                            <td className="px-4 py-2.5 text-right font-mono text-[var(--color-text)]">{fmt(band.approved)}</td>
                            <td className="px-4 py-2.5 text-right">
                              <span className={band.approval_rate >= 50 ? 'text-emerald-400' : 'text-amber-400'}>
                                {pctRaw(band.approval_rate)}
                              </span>
                            </td>
                            <td className="px-4 py-2.5 text-right font-mono text-[var(--color-text)]">{fmt(band.default_count)}</td>
                            <td className="px-4 py-2.5 text-right">
                              <span className={band.default_rate <= 5 ? 'text-emerald-400' : band.default_rate <= 15 ? 'text-amber-400' : 'text-red-400'}>
                                {pctRaw(band.default_rate)}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )}

              {/* ── Performance History ── */}
              {perfHistory.length > 0 && (
                <Card>
                  <h2 className="text-lg font-semibold text-[var(--color-text)] flex items-center gap-2 mb-4">
                    <TrendingUp size={18} /> Performance History
                  </h2>
                  <div className="overflow-auto rounded-lg border border-[var(--color-border)]">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="bg-[var(--color-bg)]">
                          <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-muted)]">Date</th>
                          <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--color-text-muted)]">Scored</th>
                          <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--color-text-muted)]">Approval %</th>
                          <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--color-text-muted)]">Default %</th>
                          <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--color-text-muted)]">Gini</th>
                          <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--color-text-muted)]">KS</th>
                          <th className="px-4 py-2.5 text-right text-xs font-medium text-[var(--color-text-muted)]">PSI</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--color-border)]">
                        {perfHistory.map((h, i) => (
                          <tr key={i} className="hover:bg-[var(--color-bg)] transition-colors">
                            <td className="px-4 py-2 text-[var(--color-text)]">{h.date}</td>
                            <td className="px-4 py-2 text-right font-mono text-[var(--color-text)]">{fmt(h.total_scored)}</td>
                            <td className="px-4 py-2 text-right text-[var(--color-text)]">{pctRaw(h.approval_rate)}</td>
                            <td className="px-4 py-2 text-right text-[var(--color-text)]">{pctRaw(h.default_rate)}</td>
                            <td className="px-4 py-2 text-right text-[var(--color-text)]">{pct(h.gini)}</td>
                            <td className="px-4 py-2 text-right text-[var(--color-text)]">{pct(h.ks)}</td>
                            <td className="px-4 py-2 text-right">
                              <span className={h.psi > 0.25 ? 'text-red-400' : h.psi > 0.1 ? 'text-amber-400' : 'text-emerald-400'}>
                                {h.psi?.toFixed(4) || '—'}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )}

              {/* ── Alerts ── */}
              {alerts.length > 0 && (
                <Card>
                  <h2 className="text-lg font-semibold text-[var(--color-text)] flex items-center gap-2 mb-4">
                    <AlertTriangle size={18} /> Alerts
                  </h2>
                  <div className="space-y-3">
                    {alerts.map((alert, i) => (
                      <div
                        key={i}
                        className={`p-4 rounded-lg border transition-colors ${
                          alert.is_acknowledged
                            ? 'border-[var(--color-border)] bg-[var(--color-bg)] opacity-60'
                            : alert.severity === 'critical'
                              ? 'border-red-500/30 bg-red-500/5'
                              : alert.severity === 'warning'
                                ? 'border-amber-500/30 bg-amber-500/5'
                                : 'border-sky-500/30 bg-sky-500/5'
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div className="mt-0.5">{severityIcon(alert.severity)}</div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className={`font-medium text-sm ${severityColor(alert.severity)}`}>{alert.title}</span>
                              <Badge variant={alert.severity === 'critical' ? 'danger' : alert.severity === 'warning' ? 'warning' : 'info'}>
                                {alert.severity}
                              </Badge>
                              {alert.is_acknowledged && <Badge variant="default">Acknowledged</Badge>}
                            </div>
                            <p className="text-sm text-[var(--color-text-muted)]">{alert.message}</p>
                            {alert.recommendation && (
                              <p className="text-xs text-[var(--color-text-muted)] mt-2 italic">
                                Recommendation: {alert.recommendation}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </>
          ) : (
            <Card>
              <div className="text-center py-12 text-[var(--color-text-muted)]">
                <BarChart3 size={48} className="mx-auto mb-3 opacity-30" />
                <p>No performance data available yet.</p>
                <p className="text-xs mt-1">Performance metrics are generated after applications are scored.</p>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* ═══════════════════ AUDIT TRAIL TAB ═══════════════════ */}
      {activeTab === 'audit' && (
        <div className="space-y-6">
          <Card>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-[var(--color-text)] flex items-center gap-2">
                <Clock size={18} /> Change Log
              </h2>
              <Button variant="ghost" size="sm" onClick={loadChangeLog} isLoading={loadingLog}>
                <RefreshCw size={14} className="mr-1" /> Refresh
              </Button>
            </div>

            {loadingLog ? (
              <div className="flex items-center justify-center h-32">
                <RefreshCw className="animate-spin text-[var(--color-primary)]" size={24} />
              </div>
            ) : changeLog.length === 0 ? (
              <div className="text-center py-12 text-[var(--color-text-muted)]">
                <Clock size={48} className="mx-auto mb-3 opacity-30" />
                <p>No changes recorded yet.</p>
              </div>
            ) : (
              <div className="overflow-auto rounded-lg border border-[var(--color-border)]">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-[var(--color-bg)]">
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-muted)]">Date</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-muted)]">Type</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-muted)]">Field</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-muted)]">Old Value</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-muted)]">New Value</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-muted)]">Justification</th>
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-[var(--color-text-muted)]">By</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--color-border)]">
                    {changeLog.map((entry, i) => (
                      <tr key={i} className="hover:bg-[var(--color-bg)] transition-colors">
                        <td className="px-4 py-2.5 text-[var(--color-text-muted)] whitespace-nowrap text-xs">
                          {entry.created_at ? new Date(entry.created_at).toLocaleString() : '—'}
                        </td>
                        <td className="px-4 py-2.5">
                          <Badge variant={
                            entry.change_type === 'points_edit' ? 'info'
                              : entry.change_type === 'cutoff_edit' ? 'warning'
                                : entry.change_type === 'weight_scale' ? 'purple'
                                  : entry.change_type === 'status_change' ? 'success'
                                    : 'default'
                          }>
                            {entry.change_type?.replace(/_/g, ' ')}
                          </Badge>
                        </td>
                        <td className="px-4 py-2.5 text-[var(--color-text)] font-mono text-xs">
                          {entry.field_path || '—'}
                        </td>
                        <td className="px-4 py-2.5">
                          <span className="text-red-400 font-mono text-xs bg-red-500/10 px-1.5 py-0.5 rounded">
                            {entry.old_value || '—'}
                          </span>
                        </td>
                        <td className="px-4 py-2.5">
                          <span className="text-emerald-400 font-mono text-xs bg-emerald-500/10 px-1.5 py-0.5 rounded">
                            {entry.new_value || '—'}
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-[var(--color-text-muted)] text-xs max-w-[200px] truncate" title={entry.justification}>
                          {entry.justification || '—'}
                        </td>
                        <td className="px-4 py-2.5 text-[var(--color-text)] text-xs whitespace-nowrap">
                          {entry.proposed_by_name || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════
   Simple syntax highlighting for score script
   ═══════════════════════════════════════════════════════════ */

function highlightLine(line: string): React.ReactNode {
  // Comments
  if (line.trimStart().startsWith('#') || line.trimStart().startsWith('//')) {
    return <span className="text-emerald-400/70 italic">{line}</span>;
  }

  const parts: React.ReactNode[] = [];
  const strings = /(["'])(?:(?!\1).)*\1/g;

  // Simple approach: split by tokens
  let remaining = line;
  let key = 0;

  // Check for strings first
  const stringMatches = [...line.matchAll(strings)];
  if (stringMatches.length > 0) {
    let lastIndex = 0;
    stringMatches.forEach(match => {
      if (match.index !== undefined && match.index > lastIndex) {
        parts.push(<span key={key++}>{highlightNonString(line.slice(lastIndex, match.index))}</span>);
      }
      parts.push(
        <span key={key++} className="text-amber-300">{match[0]}</span>
      );
      lastIndex = (match.index || 0) + match[0].length;
    });
    if (lastIndex < line.length) {
      parts.push(<span key={key++}>{highlightNonString(line.slice(lastIndex))}</span>);
    }
    return <>{parts}</>;
  }

  return <>{highlightNonString(remaining)}</>;
}

function highlightNonString(text: string): React.ReactNode {
  const keywords = /\b(def|if|elif|else|return|for|in|and|or|not|import|from|class|True|False|None|try|except|raise|with|as|lambda|yield|pass|break|continue|while)\b/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  let match: RegExpExecArray | null;

  while ((match = keywords.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(<span key={key++}>{highlightNumbers(text.slice(lastIndex, match.index))}</span>);
    }
    parts.push(
      <span key={key++} className="text-purple-400 font-medium">{match[0]}</span>
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(<span key={key++}>{highlightNumbers(text.slice(lastIndex))}</span>);
  }

  return parts.length > 0 ? <>{parts}</> : <>{text}</>;
}

function highlightNumbers(text: string): React.ReactNode {
  const numbers = /\b(\d+\.?\d*)\b/g;
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  let match: RegExpExecArray | null;

  while ((match = numbers.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(<span key={key++}>{text.slice(lastIndex, match.index)}</span>);
    }
    parts.push(
      <span key={key++} className="text-sky-300">{match[0]}</span>
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(<span key={key++}>{text.slice(lastIndex)}</span>);
  }

  return parts.length > 0 ? <>{parts}</> : <>{text}</>;
}
