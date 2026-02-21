import { useEffect, useState, useCallback } from 'react';
import {
  Settings,
  Save,
  Loader2,
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  Plus,
  Trash2,
  GripVertical,
  Clock,
  Shield,
  Brain,
  Zap,
  X,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { queueApi } from '../../../api/endpoints';

/* ── Types ─────────────────────────────────────────── */

interface Config {
  id: number;
  assignment_mode: string;
  stages_enabled: boolean;
  sla_mode: string;
  authority_limits_enabled: boolean;
  skills_routing_enabled: boolean;
  exceptions_formal: boolean;
  segregation_of_duties: boolean;
  target_turnaround_hours?: number;
  business_hours_start: string;
  business_hours_end: string;
  business_days: number[];
  holidays: string[];
  timezone: string;
  auto_expire_days: number;
  follow_up_days: number[];
  ai_config?: Record<string, any>;
}

interface Stage {
  id: number;
  name: string;
  slug: string;
  description?: string;
  sort_order: number;
  is_active: boolean;
  is_mandatory: boolean;
  assignment_mode?: string;
  allowed_roles?: string[];
  sla_target_hours?: number;
  sla_warning_hours?: number;
}

/* ── Component ─────────────────────────────────────── */

export default function QueueConfigPage() {
  const [config, setConfig] = useState<Config | null>(null);
  const [stages, setStages] = useState<Stage[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Section visibility
  const [showProcess, setShowProcess] = useState(false);
  const [showControls, setShowControls] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // New stage form
  const [newStage, setNewStage] = useState({ name: '', slug: '', description: '', sla_target_hours: '' });
  const [showNewStage, setShowNewStage] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [configRes, stagesRes] = await Promise.all([
        queueApi.getConfig(),
        queueApi.listStages(),
      ]);
      setConfig(configRes.data);
      setStages(stagesRes.data);
    } catch {
      setError('Failed to load configuration');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => { if (success) { const t = setTimeout(() => setSuccess(''), 3000); return () => clearTimeout(t); } }, [success]);

  const saveConfig = async () => {
    if (!config) return;
    try {
      setSaving(true);
      await queueApi.updateConfig(config as unknown as Record<string, unknown>);
      setSuccess('Configuration saved');
    } catch {
      setError('Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const updateField = (field: keyof Config, value: any) => {
    if (!config) return;
    setConfig({ ...config, [field]: value });
  };

  const addStage = async () => {
    if (!newStage.name || !newStage.slug) return;
    try {
      const payload: Record<string, any> = {
        name: newStage.name,
        slug: newStage.slug,
        description: newStage.description || undefined,
        sort_order: stages.length,
      };
      if (newStage.sla_target_hours) payload.sla_target_hours = parseInt(newStage.sla_target_hours);
      await queueApi.createStage(payload);
      setNewStage({ name: '', slug: '', description: '', sla_target_hours: '' });
      setShowNewStage(false);
      loadData();
      setSuccess('Stage created');
    } catch { setError('Failed to create stage'); }
  };

  const deleteStage = async (id: number) => {
    try {
      await queueApi.deleteStage(id);
      loadData();
      setSuccess('Stage deactivated');
    } catch { setError('Failed to deactivate'); }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-[var(--color-text-muted)]">
      <Loader2 className="animate-spin mr-2" /> Loading configuration...
    </div>
  );

  if (!config) return null;

  const SectionHeader = ({ title, icon, expanded, onToggle, description }: { title: string; icon: React.ReactNode; expanded: boolean; onToggle: () => void; description: string }) => (
    <button onClick={onToggle} className="w-full flex items-center gap-3 py-3 px-1 hover:bg-[var(--color-surface)]/50 rounded transition-colors">
      {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
      {icon}
      <div className="text-left flex-1">
        <div className="text-sm font-medium">{title}</div>
        <div className="text-xs text-[var(--color-text-muted)]">{description}</div>
      </div>
    </button>
  );

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2"><Settings size={24} /> Queue Configuration</h1>
        <Button onClick={saveConfig} disabled={saving}>
          {saving ? <Loader2 size={14} className="animate-spin mr-1" /> : <Save size={14} className="mr-1" />}
          Save Changes
        </Button>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-2 rounded-lg text-sm flex items-center gap-2">
          <AlertTriangle size={14} /> {error}
          <button onClick={() => setError('')} className="ml-auto"><X size={12} /></button>
        </div>
      )}
      {success && (
        <div className="bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-2 rounded-lg text-sm flex items-center gap-2">
          <CheckCircle size={14} /> {success}
        </div>
      )}

      {/* ═══ BASICS ═══ */}
      <Card>
        <h2 className="text-lg font-semibold mb-4">Basics</h2>
        <div className="space-y-4">
          {/* Assignment mode */}
          <div>
            <label className="block text-sm font-medium mb-1">Assignment Mode</label>
            <select
              value={config.assignment_mode}
              onChange={e => updateField('assignment_mode', e.target.value)}
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text)] text-sm"
            >
              <option value="pull">Pull (everyone grabs from shared queue)</option>
              <option value="auto">Auto (AI assigns to best-fit person)</option>
              <option value="hybrid">Hybrid (AI suggests, person accepts/defers)</option>
              <option value="manager">Manager (team lead distributes manually)</option>
            </select>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">
              {config.assignment_mode === 'pull' && 'Simple and effective for teams up to ~10 people. Everyone sees the same prioritized queue.'}
              {config.assignment_mode === 'auto' && 'AI assigns applications directly considering workload, skills, authority. Best for teams 10+.'}
              {config.assignment_mode === 'hybrid' && 'AI suggests but doesn\'t force. Team members accept or defer suggestions. Good for transitioning.'}
              {config.assignment_mode === 'manager' && 'A team lead distributes work manually. AI provides recommendations to assist.'}
            </p>
          </div>

          {/* Target turnaround */}
          <div>
            <label className="block text-sm font-medium mb-1">Target Turnaround (hours)</label>
            <input
              type="number"
              value={config.target_turnaround_hours ?? ''}
              onChange={e => updateField('target_turnaround_hours', e.target.value ? parseInt(e.target.value) : null)}
              placeholder="Optional - e.g. 48"
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text)] text-sm"
            />
            <p className="text-xs text-[var(--color-text-muted)] mt-1">Leave empty for no target. The system will still track actual turnaround.</p>
          </div>

          {/* Business hours */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Business Hours Start</label>
              <input type="time" value={config.business_hours_start.substring(0, 5)} onChange={e => updateField('business_hours_start', e.target.value)}
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text)] text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Business Hours End</label>
              <input type="time" value={config.business_hours_end.substring(0, 5)} onChange={e => updateField('business_hours_end', e.target.value)}
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text)] text-sm" />
            </div>
          </div>

          {/* Timezone */}
          <div>
            <label className="block text-sm font-medium mb-1">Timezone</label>
            <input type="text" value={config.timezone} onChange={e => updateField('timezone', e.target.value)}
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text)] text-sm" />
          </div>
        </div>
      </Card>

      {/* ═══ PROCESS ═══ */}
      <Card>
        <SectionHeader title="Process" icon={<Zap size={16} className="text-sky-400" />} expanded={showProcess} onToggle={() => setShowProcess(!showProcess)}
          description="Pipeline stages, roles, and routing configuration" />
        {showProcess && (
          <div className="mt-4 space-y-4 border-t border-[var(--color-border)] pt-4">
            {/* Stages toggle */}
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={config.stages_enabled} onChange={e => updateField('stages_enabled', e.target.checked)}
                className="rounded" />
              Enable Pipeline Stages
            </label>

            {config.stages_enabled && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Stages</span>
                  <Button size="sm" variant="secondary" onClick={() => setShowNewStage(!showNewStage)}>
                    <Plus size={14} className="mr-1" /> Add Stage
                  </Button>
                </div>

                {showNewStage && (
                  <div className="p-3 rounded-lg border border-dashed border-[var(--color-border)] space-y-2 bg-[var(--color-surface)]">
                    <div className="grid grid-cols-2 gap-2">
                      <input placeholder="Stage name" value={newStage.name} onChange={e => setNewStage({ ...newStage, name: e.target.value, slug: e.target.value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '') })}
                        className="px-3 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text)] text-sm" />
                      <input placeholder="Slug" value={newStage.slug} onChange={e => setNewStage({ ...newStage, slug: e.target.value })}
                        className="px-3 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text)] text-sm" />
                    </div>
                    <input placeholder="Description (optional)" value={newStage.description} onChange={e => setNewStage({ ...newStage, description: e.target.value })}
                      className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text)] text-sm" />
                    <input type="number" placeholder="SLA target hours (optional)" value={newStage.sla_target_hours} onChange={e => setNewStage({ ...newStage, sla_target_hours: e.target.value })}
                      className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text)] text-sm" />
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="ghost" onClick={() => setShowNewStage(false)}>Cancel</Button>
                      <Button size="sm" onClick={addStage}><Plus size={14} className="mr-1" /> Create</Button>
                    </div>
                  </div>
                )}

                {stages.filter(s => s.is_active).length === 0 ? (
                  <p className="text-xs text-[var(--color-text-muted)] text-center py-4">No stages defined yet. Add stages to build your pipeline.</p>
                ) : (
                  <div className="space-y-1">
                    {stages.filter(s => s.is_active).sort((a, b) => a.sort_order - b.sort_order).map((stage) => (
                      <div key={stage.id} className="flex items-center gap-2 px-3 py-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
                        <GripVertical size={14} className="text-[var(--color-text-muted)]" />
                        <div className="flex-1">
                          <span className="text-sm font-medium">{stage.name}</span>
                          <span className="text-xs text-[var(--color-text-muted)] ml-2">({stage.slug})</span>
                          {stage.sla_target_hours && <span className="text-xs text-amber-400 ml-2"><Clock size={10} className="inline" /> {stage.sla_target_hours}h SLA</span>}
                        </div>
                        {stage.is_mandatory && <span className="text-[10px] px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400">Required</span>}
                        <button onClick={() => deleteStage(stage.id)} className="p-1 hover:bg-red-500/10 text-red-400 rounded"><Trash2 size={14} /></button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </Card>

      {/* ═══ CONTROLS ═══ */}
      <Card>
        <SectionHeader title="Controls" icon={<Shield size={16} className="text-amber-400" />} expanded={showControls} onToggle={() => setShowControls(!showControls)}
          description="SLA targets, authority limits, exceptions, compliance" />
        {showControls && (
          <div className="mt-4 space-y-4 border-t border-[var(--color-border)] pt-4">
            {/* SLA Mode */}
            <div>
              <label className="block text-sm font-medium mb-1">SLA Mode</label>
              <select value={config.sla_mode} onChange={e => updateField('sla_mode', e.target.value)}
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text)] text-sm">
                <option value="none">None (no SLA tracking)</option>
                <option value="soft">Soft (visual indicators only, no actions)</option>
                <option value="active">Active (warnings, escalation, auto-reassign)</option>
              </select>
            </div>

            {/* Authority limits */}
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={config.authority_limits_enabled} onChange={e => updateField('authority_limits_enabled', e.target.checked)} className="rounded" />
              Enable Authority Limits
            </label>
            <p className="text-xs text-[var(--color-text-muted)] -mt-2 ml-6">Require approval when applications exceed a person's authorized amount or risk grade.</p>

            {/* Skills routing */}
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={config.skills_routing_enabled} onChange={e => updateField('skills_routing_enabled', e.target.checked)} className="rounded" />
              Enable Skills-Based Routing
            </label>

            {/* Formal exceptions */}
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={config.exceptions_formal} onChange={e => updateField('exceptions_formal', e.target.checked)} className="rounded" />
              Enable Formal Exception Workflow
            </label>

            {/* Segregation */}
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={config.segregation_of_duties} onChange={e => updateField('segregation_of_duties', e.target.checked)} className="rounded" />
              Segregation of Duties
            </label>
            <p className="text-xs text-[var(--color-text-muted)] -mt-2 ml-6">Prevent the same person from performing consecutive critical stages on the same application.</p>
          </div>
        )}
      </Card>

      {/* ═══ ADVANCED ═══ */}
      <Card>
        <SectionHeader title="Advanced" icon={<Brain size={16} className="text-purple-400" />} expanded={showAdvanced} onToggle={() => setShowAdvanced(!showAdvanced)}
          description="AI tuning, auto-expire, holidays" />
        {showAdvanced && (
          <div className="mt-4 space-y-4 border-t border-[var(--color-border)] pt-4">
            {/* Auto-expire */}
            <div>
              <label className="block text-sm font-medium mb-1">Auto-Expire Inactive Applications (days)</label>
              <input type="number" value={config.auto_expire_days} onChange={e => updateField('auto_expire_days', parseInt(e.target.value) || 14)}
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text)] text-sm" />
              <p className="text-xs text-[var(--color-text-muted)] mt-1">Applications waiting for borrower response will auto-expire after this many days.</p>
            </div>

            {/* Follow-up days */}
            <div>
              <label className="block text-sm font-medium mb-1">Follow-Up Schedule (days)</label>
              <input
                type="text"
                value={(config.follow_up_days || []).join(', ')}
                onChange={e => updateField('follow_up_days', e.target.value.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n)))}
                placeholder="1, 3, 7"
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text)] text-sm"
              />
            </div>

            {/* Holidays */}
            <div>
              <label className="block text-sm font-medium mb-1">Holidays (one date per line, YYYY-MM-DD)</label>
              <textarea
                rows={4}
                value={(config.holidays || []).join('\n')}
                onChange={e => updateField('holidays', e.target.value.split('\n').filter(s => s.trim()))}
                placeholder="2026-12-25&#10;2026-01-01"
                className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg bg-[var(--color-surface)] text-[var(--color-text)] text-sm font-mono"
              />
            </div>

            {/* Business days */}
            <div>
              <label className="block text-sm font-medium mb-1">Business Days</label>
              <div className="flex gap-2">
                {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, idx) => {
                  const dayNum = idx + 1;
                  const active = (config.business_days || []).includes(dayNum);
                  return (
                    <button key={day} onClick={() => {
                      const days = config.business_days || [];
                      updateField('business_days', active ? days.filter(d => d !== dayNum) : [...days, dayNum].sort());
                    }} className={`px-2 py-1 rounded text-xs font-medium border ${
                      active ? 'bg-[var(--color-primary)] text-white border-[var(--color-primary)]' : 'border-[var(--color-border)] text-[var(--color-text-muted)]'
                    }`}>
                      {day}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
