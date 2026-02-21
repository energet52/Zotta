import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { BarChart3, ChevronDown } from 'lucide-react';

export interface ScorecardGateNodeData {
  label: string;
  scorecardId?: number;
  scorecardName?: string;
  branches: Record<string, unknown>;
  nullBranch?: string;
  [key: string]: unknown;
}

function ScorecardGateNodeInner({ data, selected }: NodeProps) {
  const d = data as unknown as ScorecardGateNodeData;
  const branchCount = d.branches ? Object.keys(d.branches).length : 0;

  return (
    <div
      className={`relative px-4 py-3 min-w-0 sm:min-w-[180px] max-w-[260px] border-2 transition-shadow ${
        selected
          ? 'border-purple-500 shadow-lg shadow-purple-500/20'
          : 'border-[var(--color-border)] shadow-sm'
      }`}
      style={{
        background: 'var(--color-surface)',
        clipPath: 'polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%)',
        padding: '24px 16px',
      }}
    >
      <Handle type="target" position={Position.Top} className="!bg-purple-500 !w-3 !h-3" />

      <div className="flex items-center gap-2 mb-1 justify-center">
        <div className="p-1 rounded bg-purple-500/10">
          <BarChart3 size={14} className="text-purple-500" />
        </div>
        <span className="text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wide">
          Scorecard Gate
        </span>
      </div>

      <div className="font-semibold text-sm text-[var(--color-text)] text-center truncate">
        {d.label || d.scorecardName || 'Score Gate'}
      </div>

      <div className="flex items-center gap-1 mt-2 text-xs text-[var(--color-text-secondary)] justify-center">
        <ChevronDown size={12} />
        <span>{branchCount} band{branchCount !== 1 ? 's' : ''}</span>
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-purple-500 !w-3 !h-3" />
    </div>
  );
}

export const ScorecardGateNode = memo(ScorecardGateNodeInner);
