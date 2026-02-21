import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Inbox } from 'lucide-react';

function StartNodeInner({ selected }: NodeProps) {
  return (
    <div
      className={`relative px-5 py-4 min-w-0 sm:min-w-[200px] rounded-lg border-2 transition-shadow text-center ${
        selected ? 'border-gray-400 shadow-lg shadow-gray-400/20' : 'border-[var(--color-border)] shadow-sm'
      }`}
      style={{ background: 'var(--color-surface)' }}
    >
      <Inbox size={20} className="mx-auto mb-1.5 text-[var(--color-text-secondary)]" />
      <div className="font-semibold text-sm text-[var(--color-text)]">Application Received</div>
      <div className="text-[11px] text-[var(--color-text-secondary)] mt-0.5">All incoming applications start here</div>
      <Handle type="source" position={Position.Bottom} className="!bg-gray-400 !w-3 !h-3" />
    </div>
  );
}

export const StartNode = memo(StartNodeInner);
