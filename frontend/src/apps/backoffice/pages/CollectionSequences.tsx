import { useEffect, useState, useCallback } from 'react';
import {
  Sparkles,
  Plus,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle,
  Loader2,
  X,
  Copy,
  Trash2,
  ToggleLeft,
  ToggleRight,
  Play,
  Pause,
  Brain,
  MessageSquare,
  BarChart3,
  Clock,
  Send,
  Phone,
  Mail,
  Zap,
  Shield,
  Users,
  TrendingUp,
  Eye,
  ArrowUpDown,
  Target,
  Filter,
  Pencil,
  Save,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { sequencesApi } from '../../../api/endpoints';

/* ── Types ─────────────────────────────────────────────── */

interface SequenceStep {
  id?: number;
  sequence_id?: number;
  step_number: number;
  day_offset: number;
  channel: string;
  action_type: string;
  template_id?: number | null;
  custom_message?: string | null;
  condition_json?: Record<string, unknown> | null;
  send_time?: string | null;
  is_active: boolean;
  wait_for_response_hours: number;
  ai_effectiveness_score?: number | null;
}

interface Sequence {
  id: number;
  name: string;
  description?: string;
  delinquency_stage: string;
  is_active: boolean;
  is_default: boolean;
  priority: number;
  channels?: string[];
  ai_generated: boolean;
  ai_summary?: string;
  step_count: number;
  steps: SequenceStep[];
  enrollment_count: number;
  active_enrollment_count: number;
  created_at?: string;
}

interface Template {
  id: number;
  name: string;
  channel: string;
  tone: string;
  category: string;
  body: string;
  subject?: string;
  variables?: string[];
  is_ai_generated: boolean;
  is_active: boolean;
  usage_count: number;
  response_rate?: number;
  payment_rate?: number;
  created_at?: string;
}

interface Enrollment {
  id: number;
  case_id: number;
  sequence_id: number;
  sequence_name?: string;
  current_step_number: number;
  status: string;
  paused_reason?: string;
  enrolled_at?: string;
  dpd?: number;
  total_overdue?: number;
  delinquency_stage?: string;
  borrower_name?: string;
  loan_ref?: string;
}

interface Analytics {
  total_sequences: number;
  active_enrollments: number;
  messages_sent_7d: number;
  response_rate: number;
  payment_rate: number;
  channel_stats: { channel: string; total: number; response_rate: number; payment_rate: number }[];
  sequence_summary: { id: number; name: string; stage: string; enrollments: number }[];
}

type Tab = 'sequences' | 'templates' | 'enrollments' | 'analytics';

/* ── Helpers ───────────────────────────────────────────── */

const STAGES = [
  { value: 'early_1_30', label: 'Early (1-30 DPD)', color: 'text-amber-400 bg-amber-500/10 border-amber-500/30' },
  { value: 'mid_31_60', label: 'Mid (31-60 DPD)', color: 'text-orange-400 bg-orange-500/10 border-orange-500/30' },
  { value: 'late_61_90', label: 'Late (61-90 DPD)', color: 'text-red-400 bg-red-500/10 border-red-500/30' },
  { value: 'severe_90_plus', label: 'Severe (90+ DPD)', color: 'text-rose-400 bg-rose-500/10 border-rose-500/30' },
];

const CHANNELS = [
  { value: 'whatsapp', label: 'WhatsApp', icon: MessageSquare },
  { value: 'sms', label: 'SMS', icon: Send },
  { value: 'email', label: 'Email', icon: Mail },
  { value: 'phone', label: 'Phone', icon: Phone },
];

const TONES = ['friendly', 'firm', 'urgent', 'final'];
const CATEGORIES = ['reminder', 'demand', 'follow_up', 'promise_reminder', 'broken_promise', 'payment_link', 'settlement_offer'];
const ACTION_TYPES = ['send_message', 'create_task', 'escalate', 'create_ptp_request', 'settlement_offer'];

function stageBadge(stage: string) {
  const s = STAGES.find(x => x.value === stage);
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border ${s?.color ?? 'text-gray-400 bg-gray-500/10 border-gray-500/30'}`}>
      {s?.label ?? stage}
    </span>
  );
}

function channelIcon(ch: string) {
  const C = CHANNELS.find(x => x.value === ch)?.icon ?? Send;
  return <C size={14} />;
}

function statusBadge(status: string) {
  const colors: Record<string, string> = {
    active: 'text-green-400 bg-green-500/10 border-green-500/30',
    paused: 'text-amber-400 bg-amber-500/10 border-amber-500/30',
    completed: 'text-sky-400 bg-sky-500/10 border-sky-500/30',
    cancelled: 'text-gray-400 bg-gray-500/10 border-gray-500/30',
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border ${colors[status] ?? colors.cancelled}`}>
      {status}
    </span>
  );
}

function formatDate(iso?: string): string {
  if (!iso) return '-';
  try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
}

/* ── Main Component ────────────────────────────────────── */

export default function CollectionSequences() {
  const [activeTab, setActiveTab] = useState<Tab>('sequences');
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Sequences state
  const [sequences, setSequences] = useState<Sequence[]>([]);
  const [seqLoading, setSeqLoading] = useState(true);
  const [expandedSeq, setExpandedSeq] = useState<number | null>(null);
  const [showCreateSeq, setShowCreateSeq] = useState(false);
  const [newSeq, setNewSeq] = useState({ name: '', description: '', delinquency_stage: 'early_1_30', is_default: false });
  const [aiGenPrompt, setAiGenPrompt] = useState('');
  const [aiGenStage, setAiGenStage] = useState('early_1_30');
  const [aiGenLoading, setAiGenLoading] = useState(false);
  const [aiGenResult, setAiGenResult] = useState<any>(null);

  // Sequence editing state
  const [editingSeq, setEditingSeq] = useState<Sequence | null>(null);
  const [editSeqForm, setEditSeqForm] = useState({ name: '', description: '', delinquency_stage: '', is_default: false, priority: 0 });
  const [addingStep, setAddingStep] = useState<number | null>(null);
  const [newStep, setNewStep] = useState({ day_offset: 1, channel: 'whatsapp', action_type: 'send_message', custom_message: '', send_time: '09:00', wait_for_response_hours: 0 });
  const [editingStep, setEditingStep] = useState<SequenceStep | null>(null);
  const [editStepForm, setEditStepForm] = useState({ day_offset: 0, channel: 'whatsapp', action_type: 'send_message', custom_message: '', send_time: '09:00', wait_for_response_hours: 0 });

  // Templates state
  const [templates, setTemplates] = useState<Template[]>([]);
  const [tmplLoading, setTmplLoading] = useState(false);
  const [showCreateTmpl, setShowCreateTmpl] = useState(false);
  const [newTmpl, setNewTmpl] = useState({ name: '', channel: 'whatsapp', tone: 'friendly', category: 'reminder', body: '', subject: '' });
  const [tmplPreview, setTmplPreview] = useState('');
  const [aiTmplLoading, setAiTmplLoading] = useState(false);
  const [editingTmpl, setEditingTmpl] = useState<Template | null>(null);
  const [editTmplForm, setEditTmplForm] = useState({ name: '', channel: 'whatsapp', tone: 'friendly', category: 'reminder', body: '', subject: '' });

  // Enrollments state
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [enrollTotal, setEnrollTotal] = useState(0);
  const [enrollLoading, setEnrollLoading] = useState(false);
  const [enrollFilter, setEnrollFilter] = useState('');
  const [autoEnrollLoading, setAutoEnrollLoading] = useState(false);

  // Analytics state
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  // Auto-hide success
  useEffect(() => {
    if (successMsg) { const t = setTimeout(() => setSuccessMsg(''), 3000); return () => clearTimeout(t); }
  }, [successMsg]);

  /* ── Data Loaders ──────────────────────────────── */

  const loadSequences = useCallback(async () => {
    try {
      setSeqLoading(true);
      const res = await sequencesApi.listSequences();
      setSequences(res.data);
    } catch { setError('Failed to load sequences'); }
    finally { setSeqLoading(false); }
  }, []);

  const loadTemplates = useCallback(async () => {
    try {
      setTmplLoading(true);
      const res = await sequencesApi.listTemplates();
      setTemplates(res.data);
    } catch { setError('Failed to load templates'); }
    finally { setTmplLoading(false); }
  }, []);

  const loadEnrollments = useCallback(async () => {
    try {
      setEnrollLoading(true);
      const params: Record<string, unknown> = {};
      if (enrollFilter) params.status = enrollFilter;
      const res = await sequencesApi.listEnrollments(params);
      setEnrollments(res.data.enrollments);
      setEnrollTotal(res.data.total);
    } catch { setError('Failed to load enrollments'); }
    finally { setEnrollLoading(false); }
  }, [enrollFilter]);

  const loadAnalytics = useCallback(async () => {
    try {
      setAnalyticsLoading(true);
      const res = await sequencesApi.getAnalytics();
      setAnalytics(res.data);
    } catch { setError('Failed to load analytics'); }
    finally { setAnalyticsLoading(false); }
  }, []);

  useEffect(() => { loadSequences(); }, [loadSequences]);
  useEffect(() => { if (activeTab === 'templates') loadTemplates(); }, [activeTab, loadTemplates]);
  useEffect(() => { if (activeTab === 'enrollments') loadEnrollments(); }, [activeTab, loadEnrollments, enrollFilter]);
  useEffect(() => { if (activeTab === 'analytics') loadAnalytics(); }, [activeTab, loadAnalytics]);

  /* ── Sequence Actions ──────────────────────────── */

  const handleCreateSequence = async () => {
    try {
      await sequencesApi.createSequence(newSeq);
      setSuccessMsg('Sequence created');
      setShowCreateSeq(false);
      setNewSeq({ name: '', description: '', delinquency_stage: 'early_1_30', is_default: false });
      loadSequences();
    } catch { setError('Failed to create sequence'); }
  };

  const handleToggleActive = async (seq: Sequence) => {
    try {
      await sequencesApi.updateSequence(seq.id, { is_active: !seq.is_active });
      loadSequences();
    } catch { setError('Failed to toggle sequence'); }
  };

  const handleDuplicate = async (id: number) => {
    try {
      await sequencesApi.duplicateSequence(id);
      setSuccessMsg('Sequence duplicated');
      loadSequences();
    } catch { setError('Failed to duplicate'); }
  };

  const handleDeleteSeq = async (id: number) => {
    if (!confirm('Deactivate this sequence?')) return;
    try {
      await sequencesApi.deleteSequence(id);
      setSuccessMsg('Sequence deactivated');
      loadSequences();
    } catch { setError('Failed to delete'); }
  };

  /* ── Sequence Editing ─────────────────────────── */

  const startEditSeq = (seq: Sequence) => {
    setEditingSeq(seq);
    setEditSeqForm({
      name: seq.name,
      description: seq.description || '',
      delinquency_stage: seq.delinquency_stage,
      is_default: seq.is_default,
      priority: seq.priority,
    });
    setExpandedSeq(seq.id);
  };

  const handleSaveSeq = async () => {
    if (!editingSeq) return;
    try {
      await sequencesApi.updateSequence(editingSeq.id, editSeqForm);
      setSuccessMsg('Sequence updated');
      setEditingSeq(null);
      loadSequences();
    } catch { setError('Failed to update sequence'); }
  };

  const cancelEditSeq = () => {
    setEditingSeq(null);
    setAddingStep(null);
    setEditingStep(null);
  };

  /* ── Step Management ────────────────────────────── */

  const handleAddStep = async (seqId: number) => {
    try {
      const seq = sequences.find(s => s.id === seqId);
      const nextNum = seq ? Math.max(0, ...seq.steps.map(s => s.step_number)) + 1 : 1;
      await sequencesApi.addStep(seqId, { ...newStep, step_number: nextNum, is_active: true });
      setSuccessMsg('Step added');
      setAddingStep(null);
      setNewStep({ day_offset: 1, channel: 'whatsapp', action_type: 'send_message', custom_message: '', send_time: '09:00', wait_for_response_hours: 0 });
      loadSequences();
    } catch { setError('Failed to add step'); }
  };

  const startEditStep = (step: SequenceStep) => {
    setEditingStep(step);
    setEditStepForm({
      day_offset: step.day_offset,
      channel: step.channel,
      action_type: step.action_type,
      custom_message: step.custom_message || '',
      send_time: step.send_time || '09:00',
      wait_for_response_hours: step.wait_for_response_hours,
    });
  };

  const handleSaveStep = async () => {
    if (!editingStep?.id) return;
    try {
      await sequencesApi.updateStep(editingStep.id, editStepForm);
      setSuccessMsg('Step updated');
      setEditingStep(null);
      loadSequences();
    } catch { setError('Failed to update step'); }
  };

  const handleDeleteStep = async (stepId: number) => {
    if (!confirm('Delete this step?')) return;
    try {
      await sequencesApi.deleteStep(stepId);
      setSuccessMsg('Step deleted');
      loadSequences();
    } catch { setError('Failed to delete step'); }
  };

  const handleToggleStep = async (step: SequenceStep) => {
    if (!step.id) return;
    try {
      await sequencesApi.updateStep(step.id, { is_active: !step.is_active });
      loadSequences();
    } catch { setError('Failed to toggle step'); }
  };

  /* ── AI Generate Sequence ──────────────────────── */

  const handleAiGenerate = async () => {
    if (!aiGenPrompt.trim()) return;
    try {
      setAiGenLoading(true);
      const res = await sequencesApi.generateSequence({ description: aiGenPrompt, delinquency_stage: aiGenStage });
      setAiGenResult(res.data);
    } catch { setError('AI generation failed'); }
    finally { setAiGenLoading(false); }
  };

  const handleSaveGenerated = async () => {
    if (!aiGenResult) return;
    try {
      const steps = (aiGenResult.steps || []).map((s: any, i: number) => ({
        step_number: s.step_number || i + 1,
        day_offset: s.day_offset,
        channel: s.channel || 'whatsapp',
        action_type: s.action_type || 'send_message',
        custom_message: s.message || '',
        send_time: s.send_time || '09:00',
        wait_for_response_hours: s.wait_for_response_hours || 0,
        is_active: true,
      }));
      await sequencesApi.createSequence({
        name: aiGenResult.name || 'AI Generated Sequence',
        description: aiGenResult.description || aiGenPrompt,
        delinquency_stage: aiGenStage,
        ai_generated: true,
        ai_summary: aiGenResult.summary,
        channels: [...new Set(steps.map((s: any) => s.channel))],
        steps,
      });
      setSuccessMsg('AI sequence saved');
      setAiGenResult(null);
      setAiGenPrompt('');
      loadSequences();
    } catch { setError('Failed to save generated sequence'); }
  };

  /* ── Template Actions ──────────────────────────── */

  const handleCreateTemplate = async () => {
    try {
      await sequencesApi.createTemplate(newTmpl);
      setSuccessMsg('Template created');
      setShowCreateTmpl(false);
      setNewTmpl({ name: '', channel: 'whatsapp', tone: 'friendly', category: 'reminder', body: '', subject: '' });
      loadTemplates();
    } catch { setError('Failed to create template'); }
  };

  const handleAiTemplate = async () => {
    try {
      setAiTmplLoading(true);
      const res = await sequencesApi.generateTemplate({
        channel: newTmpl.channel,
        tone: newTmpl.tone,
        category: newTmpl.category,
      });
      setNewTmpl(prev => ({
        ...prev,
        name: res.data.name || prev.name,
        body: res.data.body || prev.body,
        subject: res.data.subject || prev.subject,
      }));
      setSuccessMsg('AI template generated');
    } catch { setError('AI template generation failed'); }
    finally { setAiTmplLoading(false); }
  };

  const handlePreview = async (body: string) => {
    try {
      const res = await sequencesApi.previewMessage({ body });
      setTmplPreview(res.data.rendered);
    } catch { setTmplPreview('Preview failed'); }
  };

  const handleDeleteTemplate = async (id: number) => {
    try {
      await sequencesApi.deleteTemplate(id);
      setSuccessMsg('Template deactivated');
      loadTemplates();
    } catch { setError('Failed to delete template'); }
  };

  const startEditTmpl = (t: Template) => {
    setEditingTmpl(t);
    setEditTmplForm({
      name: t.name,
      channel: t.channel,
      tone: t.tone,
      category: t.category,
      body: t.body,
      subject: t.subject || '',
    });
    setShowCreateTmpl(false);
  };

  const handleSaveTmpl = async () => {
    if (!editingTmpl) return;
    try {
      await sequencesApi.updateTemplate(editingTmpl.id, editTmplForm);
      setSuccessMsg('Template updated');
      setEditingTmpl(null);
      loadTemplates();
    } catch { setError('Failed to update template'); }
  };

  const cancelEditTmpl = () => {
    setEditingTmpl(null);
  };

  /* ── Enrollment Actions ────────────────────────── */

  const handleEnrollmentAction = async (id: number, status: string) => {
    try {
      await sequencesApi.updateEnrollment(id, { status });
      setSuccessMsg(`Enrollment ${status}`);
      loadEnrollments();
    } catch { setError(`Failed to ${status} enrollment`); }
  };

  const handleAutoEnroll = async () => {
    try {
      setAutoEnrollLoading(true);
      const res = await sequencesApi.autoEnroll();
      setSuccessMsg(res.data.message || 'Auto-enrolled');
      loadEnrollments();
    } catch { setError('Auto-enroll failed'); }
    finally { setAutoEnrollLoading(false); }
  };

  /* ── Render ────────────────────────────────────── */

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'sequences', label: 'Sequences', icon: <Zap size={16} /> },
    { id: 'templates', label: 'Templates', icon: <MessageSquare size={16} /> },
    { id: 'enrollments', label: 'Enrollments', icon: <Users size={16} /> },
    { id: 'analytics', label: 'Analytics', icon: <BarChart3 size={16} /> },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Collection Sequences</h1>
        <p className="text-sm text-[var(--color-text-muted)] mt-1">
          AI-powered automated notification workflows for collections
        </p>
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

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--color-border)]">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-[var(--color-primary)] text-[var(--color-primary)]'
                : 'border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
            }`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {/* ═══════════ SEQUENCES TAB ═══════════ */}
      {activeTab === 'sequences' && (
        <div className="space-y-4">
          {/* Actions bar */}
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm" onClick={() => setShowCreateSeq(!showCreateSeq)}>
              <Plus size={14} className="mr-1" /> Create Sequence
            </Button>
          </div>

          {/* Create form */}
          {showCreateSeq && (
            <Card>
              <h3 className="font-medium mb-3">New Sequence</h3>
              <div className="grid grid-cols-2 gap-3">
                <input value={newSeq.name} onChange={e => setNewSeq(p => ({ ...p, name: e.target.value }))}
                  placeholder="Sequence name" className="px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                <select value={newSeq.delinquency_stage} onChange={e => setNewSeq(p => ({ ...p, delinquency_stage: e.target.value }))}
                  className="px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg">
                  {STAGES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
                <textarea value={newSeq.description} onChange={e => setNewSeq(p => ({ ...p, description: e.target.value }))}
                  placeholder="Description" rows={2} className="col-span-2 px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg resize-none" />
                <label className="col-span-2 flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={newSeq.is_default} onChange={e => setNewSeq(p => ({ ...p, is_default: e.target.checked }))} />
                  Default sequence for this stage
                </label>
              </div>
              <div className="flex gap-2 mt-3">
                <Button size="sm" onClick={handleCreateSequence} disabled={!newSeq.name.trim()}>Create</Button>
                <Button size="sm" variant="ghost" onClick={() => setShowCreateSeq(false)}>Cancel</Button>
              </div>
            </Card>
          )}

          {/* AI Generator */}
          <Card>
            <div className="flex items-center gap-2 mb-3">
              <Brain size={18} className="text-purple-400" />
              <span className="font-medium">AI Sequence Generator</span>
            </div>
            <div className="space-y-3">
              <div className="flex gap-3">
                <select value={aiGenStage} onChange={e => setAiGenStage(e.target.value)}
                  className="w-48 px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg">
                  {STAGES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
                <input value={aiGenPrompt} onChange={e => setAiGenPrompt(e.target.value)}
                  placeholder='e.g. "Gentle recovery for first-time borrowers with small balances"'
                  className="flex-1 px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                <Button size="sm" onClick={handleAiGenerate} isLoading={aiGenLoading} disabled={!aiGenPrompt.trim()}>
                  <Sparkles size={14} className="mr-1" /> Generate
                </Button>
              </div>
              {aiGenResult && (
                <div className="bg-purple-500/10 border border-purple-500/30 rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-purple-400">{aiGenResult.name}</span>
                    {aiGenResult.ai_generated && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/30">AI-Powered</span>}
                  </div>
                  <p className="text-sm text-[var(--color-text-muted)]">{aiGenResult.summary || aiGenResult.description}</p>
                  <div className="space-y-1.5">
                    {(aiGenResult.steps || []).map((s: any, i: number) => (
                      <div key={i} className="flex items-center gap-3 text-xs bg-[var(--color-bg)] rounded px-3 py-2 border border-[var(--color-border)]">
                        <span className="font-mono w-8 text-[var(--color-text-muted)]">D+{s.day_offset}</span>
                        <span className="flex items-center gap-1">{channelIcon(s.channel)} {s.channel}</span>
                        <span className="flex-1 truncate text-[var(--color-text-muted)]">{s.message?.slice(0, 80)}...</span>
                      </div>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" onClick={handleSaveGenerated}><Plus size={14} className="mr-1" /> Save Sequence</Button>
                    <Button size="sm" variant="ghost" onClick={() => setAiGenResult(null)}>Discard</Button>
                  </div>
                </div>
              )}
            </div>
          </Card>

          {/* Sequence List */}
          {seqLoading ? (
            <div className="flex items-center justify-center h-32 text-[var(--color-text-muted)]">
              <Loader2 className="animate-spin mr-2" size={20} /> Loading sequences...
            </div>
          ) : sequences.length === 0 ? (
            <Card>
              <p className="text-sm text-[var(--color-text-muted)] text-center py-8">
                No sequences yet. Create one manually or use the AI generator above.
              </p>
            </Card>
          ) : (
            <div className="space-y-2">
              {sequences.map(seq => {
                const isExpanded = expandedSeq === seq.id;
                const isEditing = editingSeq?.id === seq.id;
                return (
                  <div key={seq.id} className={`rounded-lg border ${isEditing ? 'border-[var(--color-primary)]/50 ring-1 ring-[var(--color-primary)]/20' : 'border-[var(--color-border)]'} bg-[var(--color-surface)] ${!seq.is_active ? 'opacity-60' : ''}`}>
                    {/* Header row */}
                    <div className="flex items-center gap-3 px-4 py-3">
                      <button onClick={() => setExpandedSeq(isExpanded ? null : seq.id)} className="flex-1 min-w-0 text-left flex items-center gap-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-sm">{seq.name}</span>
                            {seq.ai_generated && <span className="text-[10px] px-1 py-0 rounded bg-purple-500/10 text-purple-400">AI</span>}
                            {seq.is_default && <span className="text-[10px] px-1 py-0 rounded bg-sky-500/10 text-sky-400">Default</span>}
                          </div>
                          <div className="flex items-center gap-3 mt-0.5 text-xs text-[var(--color-text-muted)]">
                            {stageBadge(seq.delinquency_stage)}
                            <span>{seq.step_count} steps</span>
                            <span>{seq.active_enrollment_count} active</span>
                          </div>
                        </div>
                        <span className="text-[var(--color-text-muted)]">{isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}</span>
                      </button>

                      <div className="flex items-center gap-2 shrink-0">
                        <div className="flex gap-1 text-[var(--color-text-muted)]">
                          {(seq.channels || []).map(ch => <span key={ch} title={ch}>{channelIcon(ch)}</span>)}
                        </div>
                        <button onClick={() => startEditSeq(seq)} className="p-1 rounded hover:bg-[var(--color-bg)] text-[var(--color-text-muted)]" title="Edit"><Pencil size={14} /></button>
                        <button onClick={() => handleToggleActive(seq)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                          {seq.is_active ? <ToggleRight size={22} className="text-green-400" /> : <ToggleLeft size={22} className="text-gray-500" />}
                        </button>
                        <button onClick={() => handleDuplicate(seq.id)} className="p-1 rounded hover:bg-[var(--color-bg)] text-[var(--color-text-muted)]" title="Duplicate"><Copy size={14} /></button>
                        <button onClick={() => handleDeleteSeq(seq.id)} className="p-1 rounded hover:bg-red-500/10 text-red-400" title="Deactivate"><Trash2 size={14} /></button>
                      </div>
                    </div>

                    {/* Expanded: edit form + steps */}
                    {isExpanded && (
                      <div className="px-4 pb-4 border-t border-[var(--color-border)] mx-4 pt-3 space-y-3">
                        {/* Sequence edit form */}
                        {isEditing ? (
                          <div className="rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] p-3 space-y-3">
                            <div className="flex items-center gap-2 mb-1">
                              <Pencil size={14} className="text-[var(--color-primary)]" />
                              <span className="text-xs font-medium text-[var(--color-primary)]">Editing Sequence</span>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                              <input value={editSeqForm.name} onChange={e => setEditSeqForm(p => ({ ...p, name: e.target.value }))}
                                placeholder="Sequence name" className="px-3 py-2 text-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg" />
                              <select value={editSeqForm.delinquency_stage} onChange={e => setEditSeqForm(p => ({ ...p, delinquency_stage: e.target.value }))}
                                className="px-3 py-2 text-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg">
                                {STAGES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                              </select>
                              <textarea value={editSeqForm.description} onChange={e => setEditSeqForm(p => ({ ...p, description: e.target.value }))}
                                placeholder="Description" rows={2} className="col-span-2 px-3 py-2 text-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg resize-none" />
                              <div className="flex items-center gap-4">
                                <label className="flex items-center gap-2 text-sm">
                                  <input type="checkbox" checked={editSeqForm.is_default} onChange={e => setEditSeqForm(p => ({ ...p, is_default: e.target.checked }))} />
                                  Default
                                </label>
                                <label className="flex items-center gap-2 text-sm">
                                  Priority:
                                  <input type="number" value={editSeqForm.priority} onChange={e => setEditSeqForm(p => ({ ...p, priority: parseInt(e.target.value) || 0 }))}
                                    className="w-16 px-2 py-1 text-sm bg-[var(--color-surface)] border border-[var(--color-border)] rounded" />
                                </label>
                              </div>
                            </div>
                            <div className="flex gap-2">
                              <Button size="sm" onClick={handleSaveSeq} disabled={!editSeqForm.name.trim()}>
                                <Save size={14} className="mr-1" /> Save Changes
                              </Button>
                              <Button size="sm" variant="ghost" onClick={cancelEditSeq}>Cancel</Button>
                            </div>
                          </div>
                        ) : (
                          <>
                            {seq.description && <p className="text-xs text-[var(--color-text-muted)] mb-2">{seq.description}</p>}
                            {seq.ai_summary && <p className="text-xs text-purple-400/80 italic mb-2">{seq.ai_summary}</p>}
                          </>
                        )}

                        {/* Steps timeline with editing */}
                        <div className="relative">
                          {seq.steps.map((step, idx) => {
                            const isEditingThisStep = editingStep?.id === step.id;
                            return (
                              <div key={step.id || idx} className="flex items-start gap-3 mb-3 last:mb-0">
                                <div className="flex flex-col items-center pt-1">
                                  <div className={`w-3 h-3 rounded-full shrink-0 ${step.is_active ? 'bg-[var(--color-primary)]' : 'bg-gray-600'}`} />
                                  {idx < seq.steps.length - 1 && <div className="w-px flex-1 bg-[var(--color-border)] mt-1 min-h-[20px]" />}
                                </div>
                                {isEditingThisStep ? (
                                  <div className="flex-1 text-xs rounded-md px-3 py-3 border border-[var(--color-primary)]/40 bg-[var(--color-bg)] space-y-2">
                                    <div className="flex items-center gap-2 mb-2">
                                      <Pencil size={12} className="text-[var(--color-primary)]" />
                                      <span className="text-[var(--color-primary)] font-medium">Editing Step #{step.step_number}</span>
                                    </div>
                                    <div className="grid grid-cols-4 gap-2">
                                      <label className="space-y-1">
                                        <span className="text-[var(--color-text-muted)]">Day offset</span>
                                        <input type="number" value={editStepForm.day_offset} onChange={e => setEditStepForm(p => ({ ...p, day_offset: parseInt(e.target.value) || 0 }))}
                                          className="w-full px-2 py-1.5 text-xs bg-[var(--color-surface)] border border-[var(--color-border)] rounded" />
                                      </label>
                                      <label className="space-y-1">
                                        <span className="text-[var(--color-text-muted)]">Channel</span>
                                        <select value={editStepForm.channel} onChange={e => setEditStepForm(p => ({ ...p, channel: e.target.value }))}
                                          className="w-full px-2 py-1.5 text-xs bg-[var(--color-surface)] border border-[var(--color-border)] rounded">
                                          {CHANNELS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                                        </select>
                                      </label>
                                      <label className="space-y-1">
                                        <span className="text-[var(--color-text-muted)]">Action</span>
                                        <select value={editStepForm.action_type} onChange={e => setEditStepForm(p => ({ ...p, action_type: e.target.value }))}
                                          className="w-full px-2 py-1.5 text-xs bg-[var(--color-surface)] border border-[var(--color-border)] rounded">
                                          {ACTION_TYPES.map(a => <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>)}
                                        </select>
                                      </label>
                                      <label className="space-y-1">
                                        <span className="text-[var(--color-text-muted)]">Send time</span>
                                        <input value={editStepForm.send_time} onChange={e => setEditStepForm(p => ({ ...p, send_time: e.target.value }))}
                                          placeholder="HH:MM" className="w-full px-2 py-1.5 text-xs bg-[var(--color-surface)] border border-[var(--color-border)] rounded" />
                                      </label>
                                    </div>
                                    <label className="block space-y-1">
                                      <span className="text-[var(--color-text-muted)]">Message</span>
                                      <textarea value={editStepForm.custom_message} onChange={e => setEditStepForm(p => ({ ...p, custom_message: e.target.value }))}
                                        rows={2} className="w-full px-2 py-1.5 text-xs bg-[var(--color-surface)] border border-[var(--color-border)] rounded resize-none" />
                                    </label>
                                    <label className="flex items-center gap-2">
                                      <span className="text-[var(--color-text-muted)]">Wait for response (hours):</span>
                                      <input type="number" value={editStepForm.wait_for_response_hours} onChange={e => setEditStepForm(p => ({ ...p, wait_for_response_hours: parseInt(e.target.value) || 0 }))}
                                        className="w-16 px-2 py-1 text-xs bg-[var(--color-surface)] border border-[var(--color-border)] rounded" />
                                    </label>
                                    <div className="flex gap-2 pt-1">
                                      <Button size="sm" onClick={handleSaveStep}><Save size={12} className="mr-1" /> Save</Button>
                                      <Button size="sm" variant="ghost" onClick={() => setEditingStep(null)}>Cancel</Button>
                                    </div>
                                  </div>
                                ) : (
                                  <div className={`flex-1 text-xs rounded-md px-3 py-2 border group ${step.is_active ? 'bg-[var(--color-bg)] border-[var(--color-border)]' : 'bg-gray-800/30 border-gray-700/30 opacity-60'}`}>
                                    <div className="flex items-center gap-2 mb-1">
                                      <span className="font-mono text-[var(--color-text-muted)]">Day +{step.day_offset}</span>
                                      <span className="flex items-center gap-1 text-[var(--color-text)]">{channelIcon(step.channel)} {step.channel}</span>
                                      <span className="text-[var(--color-text-muted)]">{step.action_type.replace(/_/g, ' ')}</span>
                                      {step.send_time && <span className="text-[var(--color-text-muted)] flex items-center gap-0.5"><Clock size={10} /> {step.send_time}</span>}
                                      {step.ai_effectiveness_score != null && (
                                        <span className={`font-medium ${step.ai_effectiveness_score >= 70 ? 'text-green-400' : step.ai_effectiveness_score >= 40 ? 'text-amber-400' : 'text-red-400'}`}>
                                          {step.ai_effectiveness_score}%
                                        </span>
                                      )}
                                      <div className="ml-auto flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button onClick={() => startEditStep(step)} className="p-0.5 rounded hover:bg-[var(--color-surface)] text-[var(--color-text-muted)]" title="Edit step"><Pencil size={12} /></button>
                                        <button onClick={() => handleToggleStep(step)} className="p-0.5 rounded hover:bg-[var(--color-surface)] text-[var(--color-text-muted)]" title={step.is_active ? 'Disable' : 'Enable'}>
                                          {step.is_active ? <ToggleRight size={14} className="text-green-400" /> : <ToggleLeft size={14} className="text-gray-500" />}
                                        </button>
                                        <button onClick={() => step.id && handleDeleteStep(step.id)} className="p-0.5 rounded hover:bg-red-500/10 text-red-400" title="Delete step"><Trash2 size={12} /></button>
                                      </div>
                                    </div>
                                    {step.custom_message && (
                                      <p className="text-[var(--color-text-muted)] line-clamp-2">{step.custom_message}</p>
                                    )}
                                    {step.wait_for_response_hours > 0 && (
                                      <span className="text-[10px] text-amber-400/70 mt-1 inline-block">Wait {step.wait_for_response_hours}h for response</span>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>

                        {/* Add step form */}
                        {addingStep === seq.id ? (
                          <div className="rounded-lg bg-[var(--color-bg)] border border-dashed border-[var(--color-primary)]/40 p-3 space-y-2 ml-6">
                            <div className="flex items-center gap-2 mb-1">
                              <Plus size={12} className="text-[var(--color-primary)]" />
                              <span className="text-xs font-medium text-[var(--color-primary)]">New Step</span>
                            </div>
                            <div className="grid grid-cols-4 gap-2 text-xs">
                              <label className="space-y-1">
                                <span className="text-[var(--color-text-muted)]">Day offset</span>
                                <input type="number" value={newStep.day_offset} onChange={e => setNewStep(p => ({ ...p, day_offset: parseInt(e.target.value) || 0 }))}
                                  className="w-full px-2 py-1.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded" />
                              </label>
                              <label className="space-y-1">
                                <span className="text-[var(--color-text-muted)]">Channel</span>
                                <select value={newStep.channel} onChange={e => setNewStep(p => ({ ...p, channel: e.target.value }))}
                                  className="w-full px-2 py-1.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded">
                                  {CHANNELS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                                </select>
                              </label>
                              <label className="space-y-1">
                                <span className="text-[var(--color-text-muted)]">Action</span>
                                <select value={newStep.action_type} onChange={e => setNewStep(p => ({ ...p, action_type: e.target.value }))}
                                  className="w-full px-2 py-1.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded">
                                  {ACTION_TYPES.map(a => <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>)}
                                </select>
                              </label>
                              <label className="space-y-1">
                                <span className="text-[var(--color-text-muted)]">Send time</span>
                                <input value={newStep.send_time} onChange={e => setNewStep(p => ({ ...p, send_time: e.target.value }))}
                                  placeholder="HH:MM" className="w-full px-2 py-1.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded" />
                              </label>
                            </div>
                            <label className="block space-y-1 text-xs">
                              <span className="text-[var(--color-text-muted)]">Message</span>
                              <textarea value={newStep.custom_message} onChange={e => setNewStep(p => ({ ...p, custom_message: e.target.value }))}
                                rows={2} placeholder="Message content... Use {{name}}, {{amount_due}}, etc."
                                className="w-full px-2 py-1.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded resize-none" />
                            </label>
                            <label className="flex items-center gap-2 text-xs">
                              <span className="text-[var(--color-text-muted)]">Wait for response (hours):</span>
                              <input type="number" value={newStep.wait_for_response_hours} onChange={e => setNewStep(p => ({ ...p, wait_for_response_hours: parseInt(e.target.value) || 0 }))}
                                className="w-16 px-2 py-1 bg-[var(--color-surface)] border border-[var(--color-border)] rounded" />
                            </label>
                            <div className="flex gap-2 pt-1">
                              <Button size="sm" onClick={() => handleAddStep(seq.id)}><Plus size={12} className="mr-1" /> Add Step</Button>
                              <Button size="sm" variant="ghost" onClick={() => setAddingStep(null)}>Cancel</Button>
                            </div>
                          </div>
                        ) : (
                          <button onClick={() => { setAddingStep(seq.id); setEditingStep(null); }}
                            className="flex items-center gap-1.5 text-xs text-[var(--color-primary)] hover:text-[var(--color-primary)]/80 ml-6 py-1">
                            <Plus size={12} /> Add Step
                          </button>
                        )}

                        {seq.steps.length === 0 && !addingStep && (
                          <p className="text-xs text-[var(--color-text-muted)] text-center py-4">No steps configured. Click "Add Step" above to get started.</p>
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

      {/* ═══════════ TEMPLATES TAB ═══════════ */}
      {activeTab === 'templates' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Button size="sm" onClick={() => { setShowCreateTmpl(!showCreateTmpl); setEditingTmpl(null); }}>
              <Plus size={14} className="mr-1" /> Create Template
            </Button>
          </div>

          {/* Create template form */}
          {showCreateTmpl && !editingTmpl && (
            <Card>
              <h3 className="font-medium mb-3">New Message Template</h3>
              <div className="grid grid-cols-3 gap-3">
                <input value={newTmpl.name} onChange={e => setNewTmpl(p => ({ ...p, name: e.target.value }))}
                  placeholder="Template name" className="col-span-3 px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                <select value={newTmpl.channel} onChange={e => setNewTmpl(p => ({ ...p, channel: e.target.value }))}
                  className="px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg">
                  {CHANNELS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
                <select value={newTmpl.tone} onChange={e => setNewTmpl(p => ({ ...p, tone: e.target.value }))}
                  className="px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg">
                  {TONES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
                </select>
                <select value={newTmpl.category} onChange={e => setNewTmpl(p => ({ ...p, category: e.target.value }))}
                  className="px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg">
                  {CATEGORIES.map(c => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
                </select>
                {newTmpl.channel === 'email' && (
                  <input value={newTmpl.subject} onChange={e => setNewTmpl(p => ({ ...p, subject: e.target.value }))}
                    placeholder="Email subject" className="col-span-3 px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                )}
                <textarea value={newTmpl.body} onChange={e => setNewTmpl(p => ({ ...p, body: e.target.value }))}
                  placeholder="Message body... Use {{name}}, {{amount_due}}, {{ref}}, {{dpd}}, etc."
                  rows={4} className="col-span-3 px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg resize-none font-mono" />
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {['name', 'first_name', 'amount_due', 'total_overdue', 'due_date', 'dpd', 'ref', 'payment_link', 'promise_amount', 'promise_date'].map(v => (
                  <button key={v} onClick={() => setNewTmpl(p => ({ ...p, body: p.body + `{{${v}}}` }))}
                    className="text-[10px] px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/30 hover:bg-sky-500/20">
                    {`{{${v}}}`}
                  </button>
                ))}
              </div>
              {tmplPreview && (
                <div className="mt-3 p-3 rounded-lg bg-green-500/5 border border-green-500/20 text-sm">
                  <span className="text-xs text-green-400 font-medium block mb-1">Preview</span>
                  {tmplPreview}
                </div>
              )}
              <div className="flex gap-2 mt-3">
                <Button size="sm" onClick={handleCreateTemplate} disabled={!newTmpl.name.trim() || !newTmpl.body.trim()}>Create</Button>
                <Button size="sm" variant="ghost" onClick={() => handlePreview(newTmpl.body)} disabled={!newTmpl.body.trim()}>
                  <Eye size={14} className="mr-1" /> Preview
                </Button>
                <Button size="sm" variant="ghost" onClick={handleAiTemplate} isLoading={aiTmplLoading}>
                  <Sparkles size={14} className="mr-1" /> AI Generate
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setShowCreateTmpl(false)}>Cancel</Button>
              </div>
            </Card>
          )}

          {/* Edit template form */}
          {editingTmpl && (
            <Card>
              <div className="flex items-center gap-2 mb-3">
                <Pencil size={14} className="text-[var(--color-primary)]" />
                <h3 className="font-medium">Edit Template: <span className="text-[var(--color-primary)]">{editingTmpl.name}</span></h3>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <input value={editTmplForm.name} onChange={e => setEditTmplForm(p => ({ ...p, name: e.target.value }))}
                  placeholder="Template name" className="col-span-3 px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                <select value={editTmplForm.channel} onChange={e => setEditTmplForm(p => ({ ...p, channel: e.target.value }))}
                  className="px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg">
                  {CHANNELS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
                <select value={editTmplForm.tone} onChange={e => setEditTmplForm(p => ({ ...p, tone: e.target.value }))}
                  className="px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg">
                  {TONES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
                </select>
                <select value={editTmplForm.category} onChange={e => setEditTmplForm(p => ({ ...p, category: e.target.value }))}
                  className="px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg">
                  {CATEGORIES.map(c => <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>)}
                </select>
                {editTmplForm.channel === 'email' && (
                  <input value={editTmplForm.subject} onChange={e => setEditTmplForm(p => ({ ...p, subject: e.target.value }))}
                    placeholder="Email subject" className="col-span-3 px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg" />
                )}
                <textarea value={editTmplForm.body} onChange={e => setEditTmplForm(p => ({ ...p, body: e.target.value }))}
                  placeholder="Message body..."
                  rows={4} className="col-span-3 px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg resize-none font-mono" />
              </div>
              <div className="flex flex-wrap gap-1 mt-2">
                {['name', 'first_name', 'amount_due', 'total_overdue', 'due_date', 'dpd', 'ref', 'payment_link', 'promise_amount', 'promise_date'].map(v => (
                  <button key={v} onClick={() => setEditTmplForm(p => ({ ...p, body: p.body + `{{${v}}}` }))}
                    className="text-[10px] px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/30 hover:bg-sky-500/20">
                    {`{{${v}}}`}
                  </button>
                ))}
              </div>
              {tmplPreview && (
                <div className="mt-3 p-3 rounded-lg bg-green-500/5 border border-green-500/20 text-sm">
                  <span className="text-xs text-green-400 font-medium block mb-1">Preview</span>
                  {tmplPreview}
                </div>
              )}
              <div className="flex gap-2 mt-3">
                <Button size="sm" onClick={handleSaveTmpl} disabled={!editTmplForm.name.trim() || !editTmplForm.body.trim()}>
                  <Save size={14} className="mr-1" /> Save Changes
                </Button>
                <Button size="sm" variant="ghost" onClick={() => handlePreview(editTmplForm.body)} disabled={!editTmplForm.body.trim()}>
                  <Eye size={14} className="mr-1" /> Preview
                </Button>
                <Button size="sm" variant="ghost" onClick={cancelEditTmpl}>Cancel</Button>
              </div>
            </Card>
          )}

          {/* Template list */}
          {tmplLoading ? (
            <div className="flex items-center justify-center h-32 text-[var(--color-text-muted)]">
              <Loader2 className="animate-spin mr-2" size={20} /> Loading templates...
            </div>
          ) : templates.length === 0 ? (
            <Card>
              <p className="text-sm text-[var(--color-text-muted)] text-center py-8">
                No templates yet. Create one or use AI to generate templates.
              </p>
            </Card>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                    <th className="px-3 py-2">Name</th>
                    <th className="px-3 py-2">Channel</th>
                    <th className="px-3 py-2">Tone</th>
                    <th className="px-3 py-2">Category</th>
                    <th className="px-3 py-2">Uses</th>
                    <th className="px-3 py-2">Resp %</th>
                    <th className="px-3 py-2">Pay %</th>
                    <th className="px-3 py-2 w-20"></th>
                  </tr>
                </thead>
                <tbody>
                  {templates.map(t => (
                    <tr key={t.id} className={`border-b border-[var(--color-border)] hover:bg-[var(--color-surface)] ${editingTmpl?.id === t.id ? 'bg-[var(--color-primary)]/5' : ''}`}>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-1.5">
                          <span className="font-medium">{t.name}</span>
                          {t.is_ai_generated && <span className="text-[10px] text-purple-400">AI</span>}
                        </div>
                        <p className="text-xs text-[var(--color-text-muted)] line-clamp-1 mt-0.5">{t.body.slice(0, 60)}...</p>
                      </td>
                      <td className="px-3 py-2"><span className="flex items-center gap-1">{channelIcon(t.channel)} {t.channel}</span></td>
                      <td className="px-3 py-2 capitalize">{t.tone}</td>
                      <td className="px-3 py-2 text-[var(--color-text-muted)]">{t.category.replace(/_/g, ' ')}</td>
                      <td className="px-3 py-2">{t.usage_count}</td>
                      <td className="px-3 py-2">{t.response_rate != null ? `${t.response_rate}%` : '-'}</td>
                      <td className="px-3 py-2">{t.payment_rate != null ? `${t.payment_rate}%` : '-'}</td>
                      <td className="px-3 py-2">
                        <div className="flex gap-1">
                          <button onClick={() => startEditTmpl(t)} className="p-1 rounded hover:bg-[var(--color-bg)] text-[var(--color-text-muted)]" title="Edit"><Pencil size={14} /></button>
                          <button onClick={() => handleDeleteTemplate(t.id)} className="p-1 rounded hover:bg-red-500/10 text-red-400" title="Deactivate"><Trash2 size={14} /></button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ═══════════ ENROLLMENTS TAB ═══════════ */}
      {activeTab === 'enrollments' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <select value={enrollFilter} onChange={e => setEnrollFilter(e.target.value)}
              className="px-3 py-1.5 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg">
              <option value="">All statuses</option>
              <option value="active">Active</option>
              <option value="paused">Paused</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <Button size="sm" onClick={handleAutoEnroll} isLoading={autoEnrollLoading}>
              <Zap size={14} className="mr-1" /> Auto-Enroll
            </Button>
            <span className="text-xs text-[var(--color-text-muted)]">{enrollTotal} total enrollments</span>
          </div>

          {enrollLoading ? (
            <div className="flex items-center justify-center h-32 text-[var(--color-text-muted)]">
              <Loader2 className="animate-spin mr-2" size={20} /> Loading enrollments...
            </div>
          ) : enrollments.length === 0 ? (
            <Card>
              <p className="text-sm text-[var(--color-text-muted)] text-center py-8">
                No enrollments. Use Auto-Enroll to batch-enroll open collection cases.
              </p>
            </Card>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-[var(--color-text-muted)] border-b border-[var(--color-border)]">
                    <th className="px-3 py-2">Borrower</th>
                    <th className="px-3 py-2">Loan</th>
                    <th className="px-3 py-2">Sequence</th>
                    <th className="px-3 py-2">Step</th>
                    <th className="px-3 py-2">DPD</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Enrolled</th>
                    <th className="px-3 py-2 w-24">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {enrollments.map(e => (
                    <tr key={e.id} className="border-b border-[var(--color-border)] hover:bg-[var(--color-surface)]">
                      <td className="px-3 py-2 font-medium">{e.borrower_name || `Case #${e.case_id}`}</td>
                      <td className="px-3 py-2 font-mono text-xs">{e.loan_ref || '-'}</td>
                      <td className="px-3 py-2">{e.sequence_name || `Seq #${e.sequence_id}`}</td>
                      <td className="px-3 py-2 text-center">{e.current_step_number}</td>
                      <td className="px-3 py-2">{e.dpd ?? '-'}</td>
                      <td className="px-3 py-2">
                        {statusBadge(e.status)}
                        {e.paused_reason && <span className="block text-[10px] text-[var(--color-text-muted)] mt-0.5">{e.paused_reason}</span>}
                      </td>
                      <td className="px-3 py-2 text-xs text-[var(--color-text-muted)]">{formatDate(e.enrolled_at)}</td>
                      <td className="px-3 py-2">
                        <div className="flex gap-1">
                          {e.status === 'active' && (
                            <button onClick={() => handleEnrollmentAction(e.id, 'paused')} className="p-1 rounded hover:bg-amber-500/10 text-amber-400" title="Pause"><Pause size={14} /></button>
                          )}
                          {e.status === 'paused' && (
                            <button onClick={() => handleEnrollmentAction(e.id, 'active')} className="p-1 rounded hover:bg-green-500/10 text-green-400" title="Resume"><Play size={14} /></button>
                          )}
                          {(e.status === 'active' || e.status === 'paused') && (
                            <button onClick={() => handleEnrollmentAction(e.id, 'cancelled')} className="p-1 rounded hover:bg-red-500/10 text-red-400" title="Cancel"><X size={14} /></button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ═══════════ ANALYTICS TAB ═══════════ */}
      {activeTab === 'analytics' && (
        <div className="space-y-6">
          {analyticsLoading ? (
            <div className="flex items-center justify-center h-32 text-[var(--color-text-muted)]">
              <Loader2 className="animate-spin mr-2" size={20} /> Loading analytics...
            </div>
          ) : analytics ? (
            <>
              {/* KPI Cards */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                {[
                  { label: 'Active Sequences', value: analytics.total_sequences, icon: <Zap size={16} className="text-sky-400" /> },
                  { label: 'Active Enrollments', value: analytics.active_enrollments, icon: <Users size={16} className="text-green-400" /> },
                  { label: 'Messages (7d)', value: analytics.messages_sent_7d, icon: <Send size={16} className="text-purple-400" /> },
                  { label: 'Response Rate', value: `${analytics.response_rate}%`, icon: <MessageSquare size={16} className="text-amber-400" /> },
                  { label: 'Payment Rate', value: `${analytics.payment_rate}%`, icon: <TrendingUp size={16} className="text-green-400" /> },
                ].map((kpi, i) => (
                  <Card key={i}>
                    <div className="flex items-center gap-2 mb-1">{kpi.icon}<span className="text-xs text-[var(--color-text-muted)]">{kpi.label}</span></div>
                    <div className="text-xl font-bold">{kpi.value}</div>
                  </Card>
                ))}
              </div>

              {/* Channel Performance */}
              {analytics.channel_stats.length > 0 && (
                <Card>
                  <h3 className="font-medium mb-3 flex items-center gap-2">
                    <BarChart3 size={16} className="text-sky-400" /> Channel Performance (30d)
                  </h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {analytics.channel_stats.map(cs => (
                      <div key={cs.channel} className="px-3 py-2 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
                        <div className="flex items-center gap-1.5 mb-1">
                          {channelIcon(cs.channel)}
                          <span className="text-sm font-medium capitalize">{cs.channel}</span>
                        </div>
                        <div className="text-xs text-[var(--color-text-muted)] space-y-0.5">
                          <div>{cs.total} messages sent</div>
                          <div className="text-amber-400">{cs.response_rate}% response</div>
                          <div className="text-green-400">{cs.payment_rate}% payment</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {/* Sequence Summary */}
              {analytics.sequence_summary.length > 0 && (
                <Card>
                  <h3 className="font-medium mb-3 flex items-center gap-2">
                    <Target size={16} className="text-purple-400" /> Sequence Overview
                  </h3>
                  <div className="space-y-2">
                    {analytics.sequence_summary.map(ss => (
                      <div key={ss.id} className="flex items-center gap-3 px-3 py-2 rounded-md bg-[var(--color-bg)] border border-[var(--color-border)]">
                        <span className="text-sm font-medium flex-1">{ss.name}</span>
                        {stageBadge(ss.stage)}
                        <span className="text-xs text-[var(--color-text-muted)]">{ss.enrollments} enrollments</span>
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </>
          ) : (
            <Card>
              <p className="text-sm text-[var(--color-text-muted)] text-center py-8">
                No analytics data available yet. Create sequences and enroll cases to see metrics.
              </p>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
