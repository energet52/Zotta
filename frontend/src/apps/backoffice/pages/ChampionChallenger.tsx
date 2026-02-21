import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Swords,
  CheckCircle,
  XCircle,
  Trophy,
  Trash2,
  Plus,
  Clock,
  Target,
} from 'lucide-react';
import api from '../../../api/client';

interface ChallengerTest {
  id: number;
  champion_strategy_id: number;
  challenger_strategy_id: number;
  traffic_pct: number;
  min_volume: number;
  min_duration_days: number;
  status: string;
  total_evaluated: number;
  agreement_count: number;
  disagreement_count: number;
  started_at: string;
  completed_at: string | null;
}

interface TestComparison {
  test_id: number;
  champion_strategy_id: number;
  challenger_strategy_id: number;
  status: string;
  total_evaluated: number;
  agreement_count: number;
  disagreement_count: number;
  agreement_rate: number;
  disagreement_rate: number;
  traffic_pct: number;
  min_volume_met: boolean;
  min_duration_met: boolean;
  ready_for_decision: boolean;
  days_running: number;
}

interface Strategy {
  id: number;
  name: string;
  evaluation_mode: string;
  status: string;
}

export default function ChampionChallenger() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [selectedTest, setSelectedTest] = useState<number | null>(null);
  const [form, setForm] = useState({
    champion_strategy_id: 0,
    challenger_strategy_id: 0,
    traffic_pct: 10,
    min_volume: 500,
    min_duration_days: 90,
  });

  const { data: strategies = [] } = useQuery({
    queryKey: ['strategies'],
    queryFn: async () => {
      const res = await api.get('/strategies');
      return res.data as Strategy[];
    },
  });

  const { data: tests = [] } = useQuery({
    queryKey: ['challenger-tests'],
    queryFn: async () => {
      const res = await api.get('/champion-challenger');
      return res.data as ChallengerTest[];
    },
  });

  const { data: comparison } = useQuery({
    queryKey: ['challenger-comparison', selectedTest],
    queryFn: async () => {
      if (!selectedTest) return null;
      const res = await api.get(`/champion-challenger/${selectedTest}`);
      return res.data as TestComparison;
    },
    enabled: !!selectedTest,
  });

  const createMutation = useMutation({
    mutationFn: async () => {
      const res = await api.post('/champion-challenger', form);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['challenger-tests'] });
      setShowCreate(false);
    },
  });

  const promoteMutation = useMutation({
    mutationFn: async (testId: number) => {
      await api.post(`/champion-challenger/${testId}/promote`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['challenger-tests'] });
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      setSelectedTest(null);
    },
  });

  const discardMutation = useMutation({
    mutationFn: async (testId: number) => {
      await api.delete(`/champion-challenger/${testId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['challenger-tests'] });
      setSelectedTest(null);
    },
  });

  const activeStrategies = strategies.filter((s) => s.status === 'active' || s.status === 'approved');

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[var(--color-text)]">Champion-Challenger</h1>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">
            Test strategy changes safely against production decisions
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 px-4 py-2 text-sm rounded-lg bg-blue-500 text-white hover:bg-blue-600 transition-colors"
        >
          <Plus size={16} /> New Test
        </button>
      </div>

      {showCreate && (
        <div
          className="mb-6 p-4 rounded-lg border"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}
        >
          <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">Configure Test</h3>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div>
              <label className="text-xs text-[var(--color-text-secondary)] block mb-1">Champion</label>
              <select
                value={form.champion_strategy_id}
                onChange={(e) =>
                  setForm({ ...form, champion_strategy_id: Number(e.target.value) })
                }
                className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)]"
              >
                <option value={0}>Select champion...</option>
                {strategies.filter((s) => s.status !== 'archived').map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.status})
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-[var(--color-text-secondary)] block mb-1">
                Challenger
              </label>
              <select
                value={form.challenger_strategy_id}
                onChange={(e) =>
                  setForm({ ...form, challenger_strategy_id: Number(e.target.value) })
                }
                className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)]"
              >
                <option value={0}>Select challenger...</option>
                {strategies
                  .filter((s) => s.id !== form.champion_strategy_id && s.status !== 'archived')
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.status})
                    </option>
                  ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-3">
            <div>
              <label className="text-xs text-[var(--color-text-secondary)] block mb-1">
                Traffic %
              </label>
              <input
                type="number"
                min={5}
                max={50}
                value={form.traffic_pct}
                onChange={(e) => setForm({ ...form, traffic_pct: Number(e.target.value) })}
                className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)]"
              />
            </div>
            <div>
              <label className="text-xs text-[var(--color-text-secondary)] block mb-1">
                Min Volume
              </label>
              <input
                type="number"
                value={form.min_volume}
                onChange={(e) => setForm({ ...form, min_volume: Number(e.target.value) })}
                className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)]"
              />
            </div>
            <div>
              <label className="text-xs text-[var(--color-text-secondary)] block mb-1">
                Min Duration (days)
              </label>
              <input
                type="number"
                value={form.min_duration_days}
                onChange={(e) => setForm({ ...form, min_duration_days: Number(e.target.value) })}
                className="w-full px-3 py-2 text-sm rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)]"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => createMutation.mutate()}
              disabled={!form.champion_strategy_id || !form.challenger_strategy_id}
              className="px-3 py-1.5 text-sm rounded bg-blue-500 text-white hover:bg-blue-600 disabled:opacity-50"
            >
              Start Test
            </button>
            <button
              onClick={() => setShowCreate(false)}
              className="px-3 py-1.5 text-sm rounded border border-[var(--color-border)] text-[var(--color-text)]"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Comparison Dashboard */}
      {comparison && (
        <div
          className="mb-6 p-4 rounded-lg border"
          style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}
        >
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-[var(--color-text)]">Test Results</h3>
            <div className="flex items-center gap-2">
              {comparison.ready_for_decision && (
                <button
                  onClick={() => promoteMutation.mutate(comparison.test_id)}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm rounded bg-emerald-500 text-white hover:bg-emerald-600"
                >
                  <Trophy size={14} /> Promote Challenger
                </button>
              )}
              <button
                onClick={() => discardMutation.mutate(comparison.test_id)}
                className="flex items-center gap-1 px-3 py-1.5 text-sm rounded bg-red-500 text-white hover:bg-red-600"
              >
                <Trash2 size={14} /> Discard
              </button>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-4">
            <MetricCard
              icon={<Target size={18} />}
              label="Total Evaluated"
              value={comparison.total_evaluated.toLocaleString()}
            />
            <MetricCard
              icon={<CheckCircle size={18} className="text-emerald-500" />}
              label="Agreement Rate"
              value={`${comparison.agreement_rate}%`}
            />
            <MetricCard
              icon={<XCircle size={18} className="text-red-500" />}
              label="Disagreement Rate"
              value={`${comparison.disagreement_rate}%`}
            />
            <MetricCard
              icon={<Clock size={18} />}
              label="Days Running"
              value={String(comparison.days_running)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3 mt-4">
            <div
              className={`px-3 py-2 rounded text-sm ${
                comparison.min_volume_met ? 'bg-emerald-500/10 text-emerald-600' : 'bg-amber-500/10 text-amber-600'
              }`}
            >
              {comparison.min_volume_met
                ? 'Minimum volume reached'
                : `${comparison.total_evaluated} / ${comparison.min_volume_met} volume needed`}
            </div>
            <div
              className={`px-3 py-2 rounded text-sm ${
                comparison.min_duration_met ? 'bg-emerald-500/10 text-emerald-600' : 'bg-amber-500/10 text-amber-600'
              }`}
            >
              {comparison.min_duration_met
                ? 'Minimum duration reached'
                : `${comparison.days_running} days running`}
            </div>
          </div>
        </div>
      )}

      {/* Tests list */}
      {tests.length > 0 && (
        <div className="space-y-2 mb-6">
          <h3 className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider mb-2">
            Tests ({tests.length})
          </h3>
          {tests.map((t) => {
            const champion = strategies.find((s) => s.id === t.champion_strategy_id);
            const challenger = strategies.find((s) => s.id === t.challenger_strategy_id);
            const isSelected = selectedTest === t.id;
            return (
              <div
                key={t.id}
                onClick={() => setSelectedTest(isSelected ? null : t.id)}
                className={`flex items-center gap-4 px-4 py-3 rounded-lg border cursor-pointer transition-colors ${
                  isSelected ? 'border-blue-500/50 bg-blue-500/5' : 'hover:border-blue-500/30'
                }`}
                style={isSelected ? {} : { borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}
              >
                <div className="p-2 rounded-lg bg-[var(--color-bg)]">
                  <Swords size={18} className="text-blue-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-[var(--color-text)]">
                      {champion?.name || `#${t.champion_strategy_id}`}
                    </span>
                    <span className="text-xs text-[var(--color-text-secondary)]">vs</span>
                    <span className="font-medium text-sm text-[var(--color-text)]">
                      {challenger?.name || `#${t.challenger_strategy_id}`}
                    </span>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      t.status === 'active' ? 'text-emerald-500 bg-emerald-500/10' :
                      t.status === 'completed' ? 'text-blue-500 bg-blue-500/10' :
                      'text-gray-400 bg-gray-400/10'
                    }`}>
                      {t.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-[var(--color-text-secondary)]">
                    <span>{t.traffic_pct}% traffic</span>
                    <span>{t.total_evaluated} evaluated</span>
                    <span>{t.agreement_count} agreed</span>
                    <span>{t.disagreement_count} disagreed</span>
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); discardMutation.mutate(t.id); }}
                  className="p-1.5 rounded text-red-400 hover:bg-red-400/10"
                  title="Discard test"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {/* Empty state */}
      {tests.length === 0 && !showCreate && (
        <div className="text-center py-16">
          <Swords size={48} className="mx-auto mb-4 text-[var(--color-text-secondary)]" />
          <h2 className="text-lg font-semibold text-[var(--color-text)]">No Active Tests</h2>
          <p className="text-sm text-[var(--color-text-secondary)] mt-2 max-w-md mx-auto">
            Champion-Challenger testing lets you evaluate a new strategy silently alongside your
            production strategy. The champion always makes the real decision.
          </p>
        </div>
      )}
    </div>
  );
}

function MetricCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div
      className="px-4 py-3 rounded-lg border"
      style={{ borderColor: 'var(--color-border)', background: 'var(--color-bg)' }}
    >
      <div className="flex items-center gap-2 mb-1 text-[var(--color-text-secondary)]">
        {icon}
        <span className="text-xs">{label}</span>
      </div>
      <div className="text-lg font-bold text-[var(--color-text)]">{value}</div>
    </div>
  );
}
