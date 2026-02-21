import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Shield, Settings } from 'lucide-react';

export interface StrategyNodeData {
  label: string;
  strategyId: number | null;
  strategyName?: string;
  strategyParams?: Record<string, unknown>;
  evaluationMode?: string;
  [key: string]: unknown;
}

function StrategyNodeInner({ data, selected }: NodeProps) {
  const d = data as unknown as StrategyNodeData;
  const hasParams = d.strategyParams && Object.keys(d.strategyParams).length > 0;

  const modeColors: Record<string, string> = {
    sequential: 'emerald',
    dual_path: 'blue',
    scoring: 'purple',
    hybrid: 'amber',
  };
  const color = modeColors[d.evaluationMode || 'sequential'] || 'emerald';

  return (
    <div
      className={`relative px-4 py-3 min-w-0 sm:min-w-[180px] max-w-[260px] rounded-lg border-2 transition-shadow ${
        selected
          ? `border-${color}-500 shadow-lg shadow-${color}-500/20`
          : 'border-[var(--color-border)] shadow-sm'
      }`}
      style={{ background: 'var(--color-surface)' }}
    >
      <Handle type="target" position={Position.Top} className="!bg-emerald-500 !w-3 !h-3" />

      <div className="flex items-center gap-2 mb-1">
        <div className={`p-1 rounded bg-${color}-500/10`}>
          <Shield size={14} className={`text-${color}-500`} />
        </div>
        <span className="text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wide">
          Strategy
        </span>
      </div>

      <div className="font-semibold text-sm text-[var(--color-text)] truncate">
        {d.label || d.strategyName || 'Assign Strategy'}
      </div>

      {d.strategyName && d.strategyName !== d.label && (
        <div className="text-xs text-[var(--color-text-secondary)] mt-1 truncate">
          {d.strategyName}
        </div>
      )}

      {d.evaluationMode && (
        <div className={`text-xs mt-1 text-${color}-500`}>
          {d.evaluationMode.replace('_', '-')}
        </div>
      )}

      {hasParams && (
        <div className="flex items-center gap-1 mt-2 text-xs text-amber-500">
          <Settings size={10} />
          <span>{Object.keys(d.strategyParams!).length} override{Object.keys(d.strategyParams!).length !== 1 ? 's' : ''}</span>
        </div>
      )}
    </div>
  );
}

export const StrategyNode = memo(StrategyNodeInner);
