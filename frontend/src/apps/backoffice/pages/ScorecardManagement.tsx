import { useEffect, useState, useCallback, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Upload, Plus, Copy, Search, RefreshCw, X,
  Trophy, Swords, Eye, FileText, Zap,
  AlertTriangle, Archive, ChevronRight,
  BarChart3, Shield, ArrowUpDown, ArrowUp, ArrowDown,
  Percent, CheckCircle2,
} from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import Input from '../../../components/ui/Input';
import Badge from '../../../components/ui/Badge';
import { scorecardsApi } from '../../../api/endpoints';

/* ─────────────────────────── Types ─────────────────────────── */

interface Scorecard {
  id: number;
  name: string;
  version: number;
  description: string;
  status: string;
  base_score: number;
  min_score: number;
  max_score: number;
  auto_approve_threshold: number;
  manual_review_threshold: number;
  auto_decline_threshold: number;
  traffic_pct: number;
  target_products: string[] | null;
  created_at: string;
}

interface ChampionChallengerEntry {
  id: number;
  name: string;
  version: number;
  status: string;
  traffic_pct: number;
  role?: string;
  base_score?: number;
  auto_approve_threshold?: number;
  auto_decline_threshold?: number;
}

/* ─────────────────────── Status config ────────────────────── */

const STATUS_CONFIG: Record<string, { variant: 'success' | 'info' | 'purple' | 'default' | 'warning' | 'danger'; label: string; icon: typeof Trophy }> = {
  champion:  { variant: 'success', label: 'Champion',   icon: Trophy },
  challenger:{ variant: 'info',    label: 'Challenger',  icon: Swords },
  shadow:    { variant: 'purple',  label: 'Shadow',      icon: Eye },
  draft:     { variant: 'default', label: 'Draft',       icon: FileText },
  validated: { variant: 'warning', label: 'Validated',   icon: CheckCircle2 },
  retired:   { variant: 'danger',  label: 'Retired',     icon: Archive },
};

const STATUS_COLORS: Record<string, string> = {
  champion:  '#22c55e',
  challenger:'#3b82f6',
  shadow:    '#a855f7',
  draft:     '#6b7280',
  validated: '#f59e0b',
  retired:   '#ef4444',
};

/* ─────────────────────── Helpers ──────────────────────────── */

const dateFmt = (iso: string | null) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

/* ═══════════════════════ MAIN COMPONENT ═════════════════════ */

export default function ScorecardManagement() {
  const navigate = useNavigate();

  /* ── State ──────────────────────────────────────────────────── */
  const [scorecards, setScorecards] = useState<Scorecard[]>([]);
  const [champStatus, setChampStatus] = useState<ChampionChallengerEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [champLoading, setChampLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sortBy, setSortBy] = useState<'name' | 'version' | 'created_at' | 'traffic_pct'>('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  /* ── Import modal ───────────────────────────────────────────── */
  const [showImport, setShowImport] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importName, setImportName] = useState('');
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /* ── Clone modal ────────────────────────────────────────────── */
  const [cloneTarget, setCloneTarget] = useState<Scorecard | null>(null);
  const [cloneName, setCloneName] = useState('');
  const [cloning, setCloning] = useState(false);

  /* ── Promote modal ──────────────────────────────────────────── */
  const [promoteTarget, setPromoteTarget] = useState<ChampionChallengerEntry | null>(null);
  const [promoteJustification, setPromoteJustification] = useState('');
  const [promoting, setPromoting] = useState(false);

  /* ── Traffic allocation ─────────────────────────────────────── */
  const [trafficEditing, setTrafficEditing] = useState(false);
  const [trafficAllocations, setTrafficAllocations] = useState<Record<number, number>>({});
  const [savingTraffic, setSavingTraffic] = useState(false);

  /* ── Action loading states ──────────────────────────────────── */
  const [actionLoading, setActionLoading] = useState<Record<number, string>>({});

  /* ── Load data ──────────────────────────────────────────────── */
  const loadScorecards = useCallback(async () => {
    setLoading(true);
    try {
      const res = await scorecardsApi.list();
      const data = Array.isArray(res.data) ? res.data : res.data?.items ?? [];
      setScorecards(data);
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  const loadChampionChallenger = useCallback(async () => {
    setChampLoading(true);
    try {
      const res = await scorecardsApi.getChampionChallengerStatus();
      const data = Array.isArray(res.data) ? res.data : res.data?.items ?? res.data?.scorecards ?? [];
      setChampStatus(data);
      const allocs: Record<number, number> = {};
      data.forEach((s: ChampionChallengerEntry) => { allocs[s.id] = s.traffic_pct; });
      setTrafficAllocations(allocs);
    } catch { /* ignore */ }
    setChampLoading(false);
  }, []);

  useEffect(() => { loadScorecards(); loadChampionChallenger(); }, [loadScorecards, loadChampionChallenger]);

  /* ── Handlers ───────────────────────────────────────────────── */
  const handleImport = async () => {
    if (!importFile || !importName.trim()) return;
    setImporting(true);
    try {
      const formData = new FormData();
      formData.append('file', importFile);
      await scorecardsApi.importCsv(formData, {
        name: importName.trim(),
      });
      setShowImport(false);
      setImportFile(null);
      setImportName('');
      await loadScorecards();
    } catch { /* ignore */ }
    setImporting(false);
  };

  const handleClone = async () => {
    if (!cloneTarget || !cloneName.trim()) return;
    setCloning(true);
    try {
      await scorecardsApi.clone(cloneTarget.id, cloneName.trim());
      setCloneTarget(null);
      setCloneName('');
      await loadScorecards();
    } catch { /* ignore */ }
    setCloning(false);
  };

  const handlePromote = async () => {
    if (!promoteTarget || !promoteJustification.trim()) return;
    setPromoting(true);
    try {
      await scorecardsApi.promoteToChampion(promoteTarget.id, { justification: promoteJustification.trim() });
      setPromoteTarget(null);
      setPromoteJustification('');
      await Promise.all([loadScorecards(), loadChampionChallenger()]);
    } catch { /* ignore */ }
    setPromoting(false);
  };

  const handleKillSwitch = async (id: number) => {
    setActionLoading(prev => ({ ...prev, [id]: 'kill' }));
    try {
      await scorecardsApi.killSwitch(id);
      await Promise.all([loadScorecards(), loadChampionChallenger()]);
    } catch { /* ignore */ }
    setActionLoading(prev => { const n = { ...prev }; delete n[id]; return n; });
  };

  const handleRetire = async (id: number) => {
    setActionLoading(prev => ({ ...prev, [id]: 'retire' }));
    try {
      await scorecardsApi.retire(id);
      await Promise.all([loadScorecards(), loadChampionChallenger()]);
    } catch { /* ignore */ }
    setActionLoading(prev => { const n = { ...prev }; delete n[id]; return n; });
  };

  const handleActivateShadow = async (id: number) => {
    setActionLoading(prev => ({ ...prev, [id]: 'shadow' }));
    try {
      await scorecardsApi.activateShadow(id);
      await Promise.all([loadScorecards(), loadChampionChallenger()]);
    } catch { /* ignore */ }
    setActionLoading(prev => { const n = { ...prev }; delete n[id]; return n; });
  };

  const handleActivateChallenger = async (id: number, trafficPct: number) => {
    setActionLoading(prev => ({ ...prev, [id]: 'challenger' }));
    try {
      await scorecardsApi.activateChallenger(id, trafficPct);
      await Promise.all([loadScorecards(), loadChampionChallenger()]);
    } catch { /* ignore */ }
    setActionLoading(prev => { const n = { ...prev }; delete n[id]; return n; });
  };

  const handleSaveTraffic = async () => {
    setSavingTraffic(true);
    try {
      const allocations = Object.entries(trafficAllocations).map(([id, pct]) => ({
        scorecard_id: Number(id),
        traffic_pct: pct,
      }));
      await scorecardsApi.updateTrafficAllocation(allocations);
      await loadChampionChallenger();
      setTrafficEditing(false);
    } catch { /* ignore */ }
    setSavingTraffic(false);
  };

  /* ── Filtering & sorting ────────────────────────────────────── */
  const filtered = scorecards
    .filter(s => {
      if (statusFilter && s.status !== statusFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        return s.name.toLowerCase().includes(q) || s.description?.toLowerCase().includes(q);
      }
      return true;
    })
    .sort((a, b) => {
      let cmp = 0;
      if (sortBy === 'name') cmp = a.name.localeCompare(b.name);
      else if (sortBy === 'version') cmp = a.version - b.version;
      else if (sortBy === 'traffic_pct') cmp = a.traffic_pct - b.traffic_pct;
      else cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      return sortDir === 'asc' ? cmp : -cmp;
    });

  /* ── Traffic totals ─────────────────────────────────────────── */
  const totalTraffic = Object.values(trafficAllocations).reduce((s, v) => s + v, 0);

  /* ═══════════════════════════ RENDER ═══════════════════════════ */
  return (
    <div className="space-y-5">

      {/* ───────── HEADER ───────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">Scorecard Management</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-1">
            Build, test, and deploy credit scorecards with champion-challenger workflows
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" size="sm" onClick={() => setShowImport(true)}>
            <Upload size={14} className="mr-1.5" /> Import CSV
          </Button>
          <Button size="sm" onClick={() => navigate('/backoffice/scorecards/new')}>
            <Plus size={14} className="mr-1.5" /> Create New
          </Button>
        </div>
      </div>

      {/* ───────── CHAMPION-CHALLENGER PANEL ───────── */}
      <Card padding="none">
        <div className="px-5 py-4 border-b border-[var(--color-border)] flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center"
              style={{ background: 'rgba(34,197,94,0.12)' }}
            >
              <Shield size={16} className="text-emerald-400" />
            </div>
            <div>
              <h2 className="font-semibold text-sm">Champion-Challenger Status</h2>
              <span className="text-xs text-[var(--color-text-muted)]">
                {champStatus.length} active model{champStatus.length !== 1 ? 's' : ''}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {trafficEditing ? (
              <>
                <Button variant="ghost" size="sm" onClick={() => {
                  setTrafficEditing(false);
                  const allocs: Record<number, number> = {};
                  champStatus.forEach(s => { allocs[s.id] = s.traffic_pct; });
                  setTrafficAllocations(allocs);
                }}>
                  Cancel
                </Button>
                <Button size="sm" onClick={handleSaveTraffic} isLoading={savingTraffic} disabled={savingTraffic}>
                  Save Allocation
                </Button>
              </>
            ) : (
              <Button variant="ghost" size="sm" onClick={() => setTrafficEditing(true)} disabled={champStatus.length === 0}>
                <Percent size={14} className="mr-1" /> Edit Traffic
              </Button>
            )}
            <Button variant="ghost" size="sm" onClick={loadChampionChallenger} disabled={champLoading}>
              <RefreshCw size={14} className={champLoading ? 'animate-spin' : ''} />
            </Button>
          </div>
        </div>

        {/* Traffic allocation bar */}
        {champStatus.length > 0 && (
          <div className="px-5 py-3 border-b border-[var(--color-border)]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                Traffic Distribution
              </span>
              <span className={`text-xs font-bold ${totalTraffic === 100 ? 'text-emerald-400' : 'text-amber-400'}`}>
                {totalTraffic}% allocated
              </span>
            </div>
            <div className="h-3 rounded-full overflow-hidden flex" style={{ background: 'var(--color-bg)' }}>
              {champStatus.map((s, i) => {
                const pct = trafficAllocations[s.id] ?? s.traffic_pct;
                if (pct <= 0) return null;
                return (
                  <div
                    key={s.id}
                    className="h-full transition-all duration-300 first:rounded-l-full last:rounded-r-full relative group"
                    style={{
                      width: `${pct}%`,
                      backgroundColor: STATUS_COLORS[s.status] || '#6b7280',
                      marginLeft: i > 0 ? '1px' : 0,
                    }}
                    title={`${s.name} — ${pct}%`}
                  >
                    {pct >= 10 && (
                      <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white/90">
                        {pct}%
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="flex items-center gap-4 mt-2">
              {champStatus.map(s => (
                <div key={s.id} className="flex items-center gap-1.5 text-xs">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: STATUS_COLORS[s.status] || '#6b7280' }}
                  />
                  <span className="text-[var(--color-text-muted)]">{s.name}</span>
                  <span className="font-medium">{trafficAllocations[s.id] ?? s.traffic_pct}%</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Model cards */}
        <div className="p-5">
          {champLoading ? (
            <div className="flex items-center justify-center gap-2 py-8 text-sm text-[var(--color-text-muted)]">
              <RefreshCw size={14} className="animate-spin" /> Loading champion-challenger status...
            </div>
          ) : champStatus.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-[var(--color-text-muted)]">
              <Shield size={32} className="mb-2 opacity-30" />
              <p className="text-sm">No active models deployed</p>
              <p className="text-xs mt-1">Activate a scorecard as shadow or challenger to begin testing</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {champStatus.map(entry => {
                const cfg = STATUS_CONFIG[entry.status] || STATUS_CONFIG.draft;
                const Icon = cfg.icon;
                const isActioning = !!actionLoading[entry.id];

                return (
                  <div
                    key={entry.id}
                    className="rounded-xl border transition-all hover:border-[var(--color-primary)]/40 cursor-pointer group"
                    style={{
                      background: 'var(--color-bg)',
                      borderColor: `${STATUS_COLORS[entry.status] || '#374151'}30`,
                    }}
                    onClick={() => navigate(`/backoffice/scorecards/${entry.id}`)}
                  >
                    {/* Card header */}
                    <div className="px-4 py-3 border-b border-[var(--color-border)]/50 flex items-start justify-between">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div
                          className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                          style={{ background: `${STATUS_COLORS[entry.status]}18` }}
                        >
                          <Icon size={16} style={{ color: STATUS_COLORS[entry.status] }} />
                        </div>
                        <div className="min-w-0">
                          <h3 className="font-semibold text-sm truncate group-hover:text-[var(--color-primary)] transition-colors">
                            {entry.name}
                          </h3>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-xs text-[var(--color-text-muted)]">v{entry.version}</span>
                            <Badge variant={cfg.variant}>{cfg.label}</Badge>
                          </div>
                        </div>
                      </div>
                      <ChevronRight size={14} className="text-[var(--color-text-muted)] mt-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>

                    {/* Traffic bar inside card */}
                    <div className="px-4 py-3">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs text-[var(--color-text-muted)]">Traffic allocation</span>
                        {trafficEditing ? (
                          <span className="text-xs font-bold" style={{ color: STATUS_COLORS[entry.status] }}>
                            {trafficAllocations[entry.id] ?? entry.traffic_pct}%
                          </span>
                        ) : (
                          <span className="text-xs font-bold" style={{ color: STATUS_COLORS[entry.status] }}>
                            {entry.traffic_pct}%
                          </span>
                        )}
                      </div>

                      {trafficEditing ? (
                        <input
                          type="range"
                          min={0}
                          max={100}
                          value={trafficAllocations[entry.id] ?? entry.traffic_pct}
                          onChange={e => {
                            e.stopPropagation();
                            const newVal = Number(e.target.value);
                            setTrafficAllocations(prev => {
                              const otherIds = champStatus.filter(s => s.id !== entry.id).map(s => s.id);
                              const remaining = 100 - newVal;
                              if (otherIds.length === 1) {
                                return { ...prev, [entry.id]: newVal, [otherIds[0]]: Math.max(0, remaining) };
                              }
                              const otherTotal = otherIds.reduce((sum, id) => sum + (prev[id] ?? 0), 0);
                              const next: Record<number, number> = { ...prev, [entry.id]: newVal };
                              otherIds.forEach(id => {
                                const share = otherTotal > 0 ? (prev[id] ?? 0) / otherTotal : 1 / otherIds.length;
                                next[id] = Math.max(0, Math.round(remaining * share));
                              });
                              return next;
                            });
                          }}
                          onClick={e => e.stopPropagation()}
                          className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
                          style={{
                            background: `linear-gradient(to right, ${STATUS_COLORS[entry.status]} ${trafficAllocations[entry.id] ?? entry.traffic_pct}%, var(--color-border) ${trafficAllocations[entry.id] ?? entry.traffic_pct}%)`,
                          }}
                        />
                      ) : (
                        <div className="h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--color-border)' }}>
                          <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{
                              width: `${entry.traffic_pct}%`,
                              backgroundColor: STATUS_COLORS[entry.status],
                            }}
                          />
                        </div>
                      )}
                    </div>

                    {/* Action buttons */}
                    <div
                      className="px-4 py-2.5 border-t border-[var(--color-border)]/50 flex items-center gap-1.5 flex-wrap"
                      onClick={e => e.stopPropagation()}
                    >
                      {entry.status === 'challenger' && (
                        <Button
                          variant="success"
                          size="sm"
                          onClick={() => { setPromoteTarget(entry); setPromoteJustification(''); }}
                          disabled={isActioning}
                        >
                          <Trophy size={12} className="mr-1" /> Promote
                        </Button>
                      )}
                      {entry.status === 'shadow' && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleActivateChallenger(entry.id, 10)}
                          disabled={isActioning}
                          isLoading={actionLoading[entry.id] === 'challenger'}
                        >
                          <Swords size={12} className="mr-1" /> To Challenger
                        </Button>
                      )}
                      {(entry.status === 'champion' || entry.status === 'challenger') && (
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => handleKillSwitch(entry.id)}
                          disabled={isActioning}
                          isLoading={actionLoading[entry.id] === 'kill'}
                        >
                          <Zap size={12} className="mr-1" /> Kill Switch
                        </Button>
                      )}
                      {entry.status !== 'retired' && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRetire(entry.id)}
                          disabled={isActioning}
                          isLoading={actionLoading[entry.id] === 'retire'}
                        >
                          <Archive size={12} className="mr-1" /> Retire
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Card>

      {/* ───────── SCORECARD TABLE ───────── */}
      <Card padding="none">
        {/* Filters */}
        <div className="px-5 py-4 border-b border-[var(--color-border)] flex items-center gap-3 flex-wrap">
          <div className="relative flex-1 min-w-[220px]">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
            <input
              type="text"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search scorecards..."
              className="w-full h-[36px] pl-9 pr-8 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:border-transparent placeholder:text-[var(--color-text-muted)]"
            />
            {search && (
              <button
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                onClick={() => setSearch('')}
              >
                <X size={14} />
              </button>
            )}
          </div>

          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="h-[36px] px-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] cursor-pointer"
          >
            <option value="">All Statuses</option>
            {Object.entries(STATUS_CONFIG).map(([key, cfg]) => (
              <option key={key} value={key}>{cfg.label}</option>
            ))}
          </select>

          <div className="ml-auto flex items-center gap-2">
            <span className="text-xs text-[var(--color-text-muted)]">{filtered.length} scorecard{filtered.length !== 1 ? 's' : ''}</span>
            <Button variant="ghost" size="sm" onClick={loadScorecards} disabled={loading}>
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </Button>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm" style={{ minWidth: '1000px' }}>
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)] text-xs uppercase tracking-wider">
                <SortHeader field="name" label="Name" current={sortBy} dir={sortDir} onClick={f => { setSortBy(f as typeof sortBy); setSortDir(d => sortBy === f ? (d === 'asc' ? 'desc' : 'asc') : 'asc'); }} />
                <SortHeader field="version" label="Version" current={sortBy} dir={sortDir} onClick={f => { setSortBy(f as typeof sortBy); setSortDir(d => sortBy === f ? (d === 'asc' ? 'desc' : 'asc') : 'desc'); }} />
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Base Score</th>
                <SortHeader field="traffic_pct" label="Traffic %" current={sortBy} dir={sortDir} onClick={f => { setSortBy(f as typeof sortBy); setSortDir(d => sortBy === f ? (d === 'asc' ? 'desc' : 'asc') : 'desc'); }} />
                <SortHeader field="created_at" label="Created" current={sortBy} dir={sortDir} onClick={f => { setSortBy(f as typeof sortBy); setSortDir(d => sortBy === f ? (d === 'asc' ? 'desc' : 'asc') : 'desc'); }} />
                <th className="px-4 py-3 text-left w-[120px]">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-16 text-center text-[var(--color-text-muted)]">
                    <RefreshCw className="animate-spin mx-auto mb-2" size={20} />
                    <p className="text-sm">Loading scorecards...</p>
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-16 text-center text-[var(--color-text-muted)]">
                    <BarChart3 className="mx-auto mb-2 opacity-30" size={28} />
                    <p className="text-sm">No scorecards found</p>
                    {(search || statusFilter) && (
                      <button
                        onClick={() => { setSearch(''); setStatusFilter(''); }}
                        className="mt-2 text-xs text-[var(--color-primary)] hover:underline"
                      >
                        Clear filters
                      </button>
                    )}
                  </td>
                </tr>
              ) : filtered.map(sc => {
                const cfg = STATUS_CONFIG[sc.status] || STATUS_CONFIG.draft;
                const StatusIcon = cfg.icon;
                const isActioning = !!actionLoading[sc.id];

                return (
                  <tr
                    key={sc.id}
                    className="border-b border-[var(--color-border)] hover:bg-[var(--color-bg)]/40 transition-colors cursor-pointer group"
                    onClick={() => navigate(`/backoffice/scorecards/${sc.id}`)}
                  >
                    {/* Name */}
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div
                          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                          style={{ background: `${STATUS_COLORS[sc.status]}12` }}
                        >
                          <StatusIcon size={14} style={{ color: STATUS_COLORS[sc.status] }} />
                        </div>
                        <div className="min-w-0">
                          <Link
                            to={`/backoffice/scorecards/${sc.id}`}
                            className="font-medium text-sm hover:text-[var(--color-primary)] transition-colors block truncate"
                            onClick={e => e.stopPropagation()}
                          >
                            {sc.name}
                          </Link>
                          {sc.description && (
                            <span className="text-xs text-[var(--color-text-muted)] truncate block max-w-[240px]">
                              {sc.description}
                            </span>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Version */}
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-[var(--color-bg)] border border-[var(--color-border)]">
                        v{sc.version}
                      </span>
                    </td>

                    {/* Status */}
                    <td className="px-4 py-3">
                      <Badge variant={cfg.variant}>{cfg.label}</Badge>
                    </td>

                    {/* Base Score */}
                    <td className="px-4 py-3 text-xs font-mono font-medium">
                      {sc.base_score}
                      <span className="text-[var(--color-text-muted)] ml-1">
                        ({sc.min_score}–{sc.max_score})
                      </span>
                    </td>

                    {/* Traffic */}
                    <td className="px-4 py-3">
                      {sc.traffic_pct > 0 ? (
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--color-border)' }}>
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${sc.traffic_pct}%`,
                                backgroundColor: STATUS_COLORS[sc.status],
                              }}
                            />
                          </div>
                          <span className="text-xs font-bold" style={{ color: STATUS_COLORS[sc.status] }}>
                            {sc.traffic_pct}%
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-[var(--color-text-muted)]">—</span>
                      )}
                    </td>

                    {/* Created */}
                    <td className="px-4 py-3 text-xs text-[var(--color-text-muted)] whitespace-nowrap">
                      {dateFmt(sc.created_at)}
                    </td>

                    {/* Actions */}
                    <td className="px-4 py-3" onClick={e => e.stopPropagation()}>
                      <div className="flex items-center gap-1">
                        <button
                          title="Clone"
                          className="p-1.5 rounded-md hover:bg-[var(--color-bg)] transition-colors opacity-0 group-hover:opacity-100"
                          onClick={() => { setCloneTarget(sc); setCloneName(`${sc.name} (copy)`); }}
                        >
                          <Copy size={13} className="text-[var(--color-text-muted)]" />
                        </button>
                        {(sc.status === 'draft' || sc.status === 'validated') && (
                          <button
                            title="Activate as Shadow"
                            className="p-1.5 rounded-md hover:bg-[var(--color-bg)] transition-colors opacity-0 group-hover:opacity-100"
                            onClick={() => handleActivateShadow(sc.id)}
                            disabled={isActioning}
                          >
                            <Eye size={13} className="text-purple-400" />
                          </button>
                        )}
                        {sc.status !== 'retired' && (
                          <button
                            title="Retire"
                            className="p-1.5 rounded-md hover:bg-[var(--color-bg)] transition-colors opacity-0 group-hover:opacity-100"
                            onClick={() => handleRetire(sc.id)}
                            disabled={isActioning}
                          >
                            <Archive size={13} className="text-[var(--color-text-muted)]" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ═══════════════════ IMPORT CSV MODAL ═══════════════════ */}
      {showImport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowImport(false)}>
          <div
            className="w-full max-w-lg rounded-xl border shadow-2xl mx-4"
            style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: 'rgba(59,130,246,0.12)' }}>
                  <Upload size={16} className="text-blue-400" />
                </div>
                <div>
                  <h3 className="font-semibold text-sm">Import Scorecard from CSV</h3>
                  <p className="text-xs text-[var(--color-text-muted)]">Upload a CSV with characteristic bins and points</p>
                </div>
              </div>
              <button onClick={() => setShowImport(false)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors">
                <X size={18} />
              </button>
            </div>

            {/* Body */}
            <div className="px-6 py-5 space-y-4">
              {/* File upload area */}
              <div
                className="border-2 border-dashed rounded-xl p-6 text-center cursor-pointer hover:border-[var(--color-primary)]/50 transition-colors"
                style={{ borderColor: importFile ? 'var(--color-primary)' : 'var(--color-border)', background: 'var(--color-bg)' }}
                onClick={() => fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={e => setImportFile(e.target.files?.[0] || null)}
                />
                {importFile ? (
                  <div className="flex items-center justify-center gap-2">
                    <FileText size={20} className="text-[var(--color-primary)]" />
                    <div>
                      <p className="text-sm font-medium">{importFile.name}</p>
                      <p className="text-xs text-[var(--color-text-muted)]">
                        {(importFile.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                    <button
                      className="ml-2 p-1 rounded hover:bg-[var(--color-surface)] transition-colors"
                      onClick={e => { e.stopPropagation(); setImportFile(null); }}
                    >
                      <X size={14} className="text-[var(--color-text-muted)]" />
                    </button>
                  </div>
                ) : (
                  <>
                    <Upload size={28} className="mx-auto mb-2 text-[var(--color-text-muted)] opacity-50" />
                    <p className="text-sm text-[var(--color-text-muted)]">
                      Click to upload or drag & drop a CSV file
                    </p>
                    <p className="text-xs text-[var(--color-text-muted)] mt-1 opacity-60">
                      Required columns: characteristic, attribute, min_value, max_value, points
                    </p>
                  </>
                )}
              </div>

              {/* Scorecard name */}
              <Input
                label="Scorecard Name"
                value={importName}
                onChange={e => setImportName(e.target.value)}
                placeholder="e.g. Application Scorecard v2.1"
              />

              {/* Decision cutoffs are managed via Rules Management (R21: Scorecard Score) */}
              <p className="text-xs text-[var(--color-text-muted)] bg-[var(--color-bg)] rounded-lg p-3 border border-[var(--color-border)]">
                Score decision thresholds (auto-approve / manual review / auto-decline) are configured in <strong>Rules Management</strong> under rule R21.
              </p>
            </div>

            {/* Footer */}
            <div className="flex justify-end gap-2 px-6 py-4 border-t border-[var(--color-border)]">
              <Button variant="ghost" size="sm" onClick={() => setShowImport(false)}>
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleImport}
                disabled={!importFile || !importName.trim() || importing}
                isLoading={importing}
              >
                <Upload size={14} className="mr-1.5" /> Import Scorecard
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════ CLONE MODAL ═══════════════════════ */}
      {cloneTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setCloneTarget(null)}>
          <div
            className="w-full max-w-md rounded-xl border shadow-2xl mx-4"
            style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
              <div className="flex items-center gap-2">
                <Copy size={16} className="text-[var(--color-primary)]" />
                <h3 className="font-semibold text-sm">Clone Scorecard</h3>
              </div>
              <button onClick={() => setCloneTarget(null)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                <X size={18} />
              </button>
            </div>
            <div className="px-6 py-5 space-y-4">
              <p className="text-sm text-[var(--color-text-muted)]">
                Create a copy of <strong className="text-[var(--color-text)]">{cloneTarget.name}</strong> (v{cloneTarget.version}) with a new name.
              </p>
              <Input
                label="New Scorecard Name"
                value={cloneName}
                onChange={e => setCloneName(e.target.value)}
                placeholder="Enter a name for the clone"
              />
            </div>
            <div className="flex justify-end gap-2 px-6 py-4 border-t border-[var(--color-border)]">
              <Button variant="ghost" size="sm" onClick={() => setCloneTarget(null)}>Cancel</Button>
              <Button
                size="sm"
                onClick={handleClone}
                disabled={!cloneName.trim() || cloning}
                isLoading={cloning}
              >
                <Copy size={14} className="mr-1.5" /> Clone
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════ PROMOTE MODAL ═════════════════════ */}
      {promoteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setPromoteTarget(null)}>
          <div
            className="w-full max-w-md rounded-xl border shadow-2xl mx-4"
            style={{ background: 'var(--color-surface)', borderColor: 'var(--color-border)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
              <div className="flex items-center gap-2">
                <Trophy size={16} className="text-emerald-400" />
                <h3 className="font-semibold text-sm">Promote to Champion</h3>
              </div>
              <button onClick={() => setPromoteTarget(null)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                <X size={18} />
              </button>
            </div>
            <div className="px-6 py-5 space-y-4">
              <div
                className="flex items-center gap-3 p-3 rounded-lg"
                style={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)' }}
              >
                <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ background: 'rgba(34,197,94,0.12)' }}>
                  <Trophy size={18} className="text-emerald-400" />
                </div>
                <div>
                  <p className="font-medium text-sm">{promoteTarget.name}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">v{promoteTarget.version} — will replace current champion</p>
                </div>
              </div>

              <div className="p-3 rounded-lg border border-amber-500/20" style={{ background: 'rgba(245,158,11,0.06)' }}>
                <div className="flex items-start gap-2">
                  <AlertTriangle size={14} className="text-amber-400 mt-0.5 flex-shrink-0" />
                  <p className="text-xs text-amber-300/80">
                    This action will promote this scorecard to champion and demote the current champion.
                    All live traffic will shift to the new model. This action is audited.
                  </p>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">
                  Justification <span className="text-red-400">*</span>
                </label>
                <textarea
                  value={promoteJustification}
                  onChange={e => setPromoteJustification(e.target.value)}
                  rows={3}
                  className="w-full p-3 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] resize-none placeholder:text-[var(--color-text-muted)]"
                  placeholder="Describe why this scorecard should become champion (e.g., improved Gini, lower default rates)..."
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 px-6 py-4 border-t border-[var(--color-border)]">
              <Button variant="ghost" size="sm" onClick={() => setPromoteTarget(null)}>Cancel</Button>
              <Button
                variant="success"
                size="sm"
                onClick={handlePromote}
                disabled={!promoteJustification.trim() || promoting}
                isLoading={promoting}
              >
                <Trophy size={14} className="mr-1.5" /> Confirm Promotion
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════ SUB-COMPONENTS ═══════════════════════════ */

function SortHeader({
  field, label, current, dir, onClick,
}: {
  field: string;
  label: string;
  current: string;
  dir: 'asc' | 'desc';
  onClick: (field: string) => void;
}) {
  const active = current === field;
  return (
    <th
      className="px-4 py-3 text-left cursor-pointer select-none hover:text-[var(--color-text)] transition-colors"
      onClick={() => onClick(field)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {active ? (
          dir === 'asc' ? <ArrowUp size={12} /> : <ArrowDown size={12} />
        ) : (
          <ArrowUpDown size={10} className="opacity-40" />
        )}
      </span>
    </th>
  );
}
