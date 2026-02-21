import { memo, useState } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { ClipboardCheck, Pencil, Check } from 'lucide-react';

export interface AssessmentOption {
  id: number;
  name: string;
  ruleCount: number;
}

export interface AssessmentNodeData {
  label: string;
  assessmentId: number | null;
  assessmentName?: string;
  ruleCount?: number;
  assessmentOptions?: AssessmentOption[];
  nodeKey?: string;
  onDataChange?: (nodeId: string, updates: Record<string, unknown>) => void;
  [key: string]: unknown;
}

function AssessmentNodeInner({ id, data, selected }: NodeProps) {
  const d = data as unknown as AssessmentNodeData;
  const [editing, setEditing] = useState(false);
  const [editLabel, setEditLabel] = useState(d.label || '');
  const [editAssessmentId, setEditAssessmentId] = useState<number | null>(d.assessmentId);
  const options = d.assessmentOptions || [];

  const startEditing = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditLabel(d.label || '');
    setEditAssessmentId(d.assessmentId);
    setEditing(true);
  };

  const saveEdits = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!d.onDataChange) return;
    const selected = options.find((o) => o.id === editAssessmentId);
    d.onDataChange(id, {
      label: editLabel || selected?.name || 'Assessment',
      assessmentId: editAssessmentId,
      assessmentName: selected?.name || '',
      ruleCount: selected?.ruleCount || 0,
    });
    setEditing(false);
  };

  if (editing) {
    return (
      <div
        className="relative px-3 py-3 min-w-0 sm:min-w-[220px] max-w-[280px] rounded-lg border-2 border-orange-500 shadow-lg shadow-orange-500/20 nopan nodrag nowheel"
        style={{ background: 'var(--color-surface)' }}
        onMouseDown={(e) => e.stopPropagation()}
        onPointerDown={(e) => e.stopPropagation()}
      >
        <Handle type="target" position={Position.Top} className="!bg-orange-500 !w-3 !h-3" />
        <div className="space-y-2">
          <input
            value={editLabel}
            onChange={(e) => setEditLabel(e.target.value)}
            placeholder="Label"
            className="w-full px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)]"
            autoFocus
          />
          <select
            value={editAssessmentId ?? ''}
            onChange={(e) => {
              const val = e.target.value ? Number(e.target.value) : null;
              setEditAssessmentId(val);
              const opt = options.find((o) => o.id === val);
              if (opt) setEditLabel(opt.name);
            }}
            className="w-full px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)]"
          >
            <option value="">Select assessment...</option>
            {options.map((o) => (
              <option key={o.id} value={o.id}>{o.name} ({o.ruleCount} rules)</option>
            ))}
          </select>
          <button
            onClick={saveEdits}
            className="w-full flex items-center justify-center gap-1 px-2 py-1 text-xs rounded bg-orange-500 text-white hover:bg-orange-600"
          >
            <Check size={12} /> Apply
          </button>
        </div>
      </div>
    );
  }

  const assignedName = d.assessmentName || options.find((o) => o.id === d.assessmentId)?.name;

  return (
    <div
      className={`relative px-4 py-3 min-w-0 sm:min-w-[180px] max-w-[260px] rounded-lg border-2 transition-shadow ${
        selected ? 'border-orange-500 shadow-lg shadow-orange-500/20' : 'border-[var(--color-border)] shadow-sm'
      }`}
      style={{ background: 'var(--color-surface)' }}
    >
      <Handle type="target" position={Position.Top} className="!bg-orange-500 !w-3 !h-3" />

      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <div className="p-1 rounded bg-orange-500/10">
            <ClipboardCheck size={14} className="text-orange-500" />
          </div>
          <span className="text-xs font-medium text-[var(--color-text-secondary)] uppercase tracking-wide">
            Assessment
          </span>
        </div>
        {d.onDataChange && (
          <button onClick={startEditing} className="p-0.5 rounded hover:bg-orange-500/10">
            <Pencil size={11} className="text-orange-400" />
          </button>
        )}
      </div>

      <div className="font-semibold text-sm text-[var(--color-text)] truncate">
        {d.label || assignedName || 'Assessment'}
      </div>

      {!d.assessmentId && d.onDataChange && (
        <div className="text-xs text-amber-500 mt-1">No assessment assigned</div>
      )}

      {d.assessmentId && (
        <div className="text-xs text-[var(--color-text-secondary)] mt-1">
          {d.ruleCount !== undefined ? `${d.ruleCount} rules` : assignedName || `ID: ${d.assessmentId}`}
        </div>
      )}
    </div>
  );
}

export const AssessmentNode = memo(AssessmentNodeInner);
