import { memo, useState } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { GitBranch, Pencil, Check, Plus, Trash2 } from 'lucide-react';

const ROUTING_ATTRIBUTES: {
  value: string;
  label: string;
  type: 'binary' | 'categorical' | 'numeric_range';
  trueLabel?: string;
  falseLabel?: string;
  categories?: string[];
  unit?: string;
}[] = [
  { value: 'is_existing_customer', label: 'Customer Relationship', type: 'binary', trueLabel: 'Existing Customer', falseLabel: 'New Customer' },
  { value: 'is_pre_approved', label: 'Pre-Approved', type: 'binary', trueLabel: 'Pre-Approved', falseLabel: 'Not Pre-Approved' },
  { value: 'has_adverse_records', label: 'Adverse Records', type: 'binary', trueLabel: 'Has Adverse', falseLabel: 'No Adverse' },
  { value: 'is_income_verified', label: 'Income Verified', type: 'binary', trueLabel: 'Verified', falseLabel: 'Not Verified' },
  { value: 'is_approved_merchant', label: 'Approved Merchant', type: 'binary', trueLabel: 'Approved', falseLabel: 'Not Approved' },
  { value: 'employment_type', label: 'Employment Type', type: 'categorical', categories: ['employed', 'self_employed', 'contract', 'unemployed', 'retired'] },
  { value: 'bureau_file_status', label: 'Bureau Data', type: 'categorical', categories: ['none', 'thin', 'standard', 'thick'] },
  { value: 'income_band', label: 'Income Band', type: 'categorical', categories: ['below_5000', '5000_15000', '15000_30000', 'above_30000'] },
  { value: 'merchant_name', label: 'Merchant', type: 'categorical' },
  { value: 'channel', label: 'Channel', type: 'categorical', categories: ['branch', 'online', 'mobile', 'agent', 'api', 'pos'] },
  { value: 'product_family', label: 'Product Family', type: 'categorical' },
  { value: 'geographic_region', label: 'Region', type: 'categorical' },
  { value: 'risk_band', label: 'Risk Band', type: 'categorical', categories: ['A', 'B', 'C', 'D', 'E'] },
  { value: 'monthly_income', label: 'Monthly Income', type: 'numeric_range', unit: 'TTD' },
  { value: 'loan_amount', label: 'Loan Amount', type: 'numeric_range', unit: 'TTD' },
  { value: 'age', label: 'Applicant Age', type: 'numeric_range', unit: 'years' },
  { value: 'dti_ratio', label: 'DTI Ratio', type: 'numeric_range', unit: '' },
  { value: 'ltv_ratio', label: 'LTV Ratio', type: 'numeric_range', unit: '' },
  { value: 'application_score', label: 'Application Score', type: 'numeric_range', unit: 'pts' },
  { value: 'loan_tenure_months', label: 'Loan Tenure', type: 'numeric_range', unit: 'months' },
  { value: 'net_disposable_income', label: 'Net Disposable Income', type: 'numeric_range', unit: 'TTD' },
  { value: 'total_exposure', label: 'Total Exposure', type: 'numeric_range', unit: 'TTD' },
];

interface BranchDef {
  label: string;
  values?: string[];
  value?: boolean;
  min?: number;
  max?: number;
  operator?: string;
  threshold?: number;
}

export interface ConditionNodeData {
  label: string;
  attribute: string;
  conditionType: 'binary' | 'categorical' | 'numeric_range' | 'compound';
  operator?: string;
  branches: Record<string, unknown>;
  nullBranch?: string;
  nodeKey?: string;
  onDataChange?: (nodeId: string, updates: Record<string, unknown>) => void;
  [key: string]: unknown;
}

function ConditionNodeInner({ id, data, selected }: NodeProps) {
  const d = data as unknown as ConditionNodeData;
  const [editing, setEditing] = useState(false);
  const branchEntries = Object.entries(d.branches || {}) as [string, BranchDef][];
  const branchCount = branchEntries.length;
  const attrDef = ROUTING_ATTRIBUTES.find((a) => a.value === d.attribute);

  const typeLabel =
    d.conditionType === 'binary' ? 'Binary'
    : d.conditionType === 'categorical' ? 'Categorical'
    : d.conditionType === 'numeric_range' ? 'Numeric'
    : 'Compound';

  const startEditing = (e: React.MouseEvent) => {
    e.stopPropagation();
    setEditing(true);
  };

  if (editing && d.onDataChange) {
    return (
      <ConditionEditor
        id={id}
        data={d}
        onSave={(updates) => { d.onDataChange!(id, updates); setEditing(false); }}
        onCancel={() => setEditing(false)}
      />
    );
  }

  return (
    <div
      className={`relative px-4 py-3 min-w-[200px] max-w-[280px] rounded-lg border-2 transition-shadow ${
        selected ? 'border-blue-500 shadow-lg shadow-blue-500/20' : 'border-[var(--color-border)] shadow-sm'
      }`}
      style={{ background: 'var(--color-surface)' }}
    >
      <Handle type="target" position={Position.Top} className="!bg-blue-500 !w-3 !h-3" />

      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <div className="p-1 rounded bg-blue-500/10">
            <GitBranch size={14} className="text-blue-500" />
          </div>
          <span className="text-[10px] font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">
            {typeLabel}
          </span>
        </div>
        {d.onDataChange && (
          <button onClick={startEditing} className="p-0.5 rounded hover:bg-blue-500/10">
            <Pencil size={11} className="text-blue-400" />
          </button>
        )}
      </div>

      <div className="font-semibold text-sm text-[var(--color-text)] truncate">
        {d.label || attrDef?.label || d.attribute || 'Condition'}
      </div>

      {d.attribute && (
        <div className="text-[11px] text-[var(--color-text-secondary)] mt-0.5 font-mono truncate">
          {d.attribute}
        </div>
      )}

      {branchCount > 0 && (
        <div className="mt-2 space-y-0.5">
          {branchEntries.map(([name, def]) => (
            <div key={name} className="flex items-center gap-1.5 text-[11px]">
              <div className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0" />
              <span className="text-blue-400 font-medium truncate">{name}</span>
              {def.operator && def.threshold !== undefined && (
                <span className="text-[var(--color-text-secondary)]">
                  {def.operator} {def.threshold}{attrDef?.unit ? ` ${attrDef.unit}` : ''}
                </span>
              )}
              {def.values && def.values.length > 0 && (
                <span className="text-[var(--color-text-secondary)] truncate">
                  [{def.values.join(', ')}]
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-blue-500 !w-3 !h-3" />
    </div>
  );
}

function ConditionEditor({
  id,
  data,
  onSave,
  onCancel,
}: {
  id: string;
  data: ConditionNodeData;
  onSave: (updates: Record<string, unknown>) => void;
  onCancel: () => void;
}) {
  const [label, setLabel] = useState(data.label || '');
  const [attribute, setAttribute] = useState(data.attribute || '');

  const attrDef = ROUTING_ATTRIBUTES.find((a) => a.value === attribute);
  const condType = attrDef?.type || 'binary';

  const existingBranches = Object.entries(data.branches || {}) as [string, BranchDef][];

  const getDefaultBranches = (attr: typeof ROUTING_ATTRIBUTES[0] | undefined): [string, BranchDef][] => {
    if (!attr) return [['Yes', { value: true }], ['No', { value: false }]];
    if (attr.type === 'binary') {
      return [
        [attr.trueLabel || 'Yes', { value: true }],
        [attr.falseLabel || 'No', { value: false }],
      ];
    }
    if (attr.type === 'categorical') {
      if (attr.categories && attr.categories.length > 0) {
        return attr.categories.slice(0, 3).map((c) => [c, { values: [c] }]);
      }
      return [['Group 1', { values: [] }], ['Other', { values: [] }]];
    }
    return [
      ['High', { operator: '>=', threshold: 0 }],
      ['Low', { operator: '<', threshold: 0 }],
    ];
  };

  const [branches, setBranches] = useState<[string, BranchDef][]>(
    existingBranches.length > 0 ? existingBranches : getDefaultBranches(attrDef),
  );

  const handleAttrChange = (val: string) => {
    setAttribute(val);
    const newAttr = ROUTING_ATTRIBUTES.find((a) => a.value === val);
    setLabel(newAttr?.label || val);
    setBranches(getDefaultBranches(newAttr));
  };

  const updateBranch = (idx: number, field: string, val: unknown) => {
    const updated = [...branches];
    if (field === 'name') {
      updated[idx] = [val as string, updated[idx][1]];
    } else {
      updated[idx] = [updated[idx][0], { ...updated[idx][1], [field]: val }];
    }
    setBranches(updated);
  };

  const addBranch = () => {
    if (condType === 'categorical') {
      setBranches([...branches, [`Branch ${branches.length + 1}`, { values: [] }]]);
    } else if (condType === 'numeric_range') {
      setBranches([...branches, [`Range ${branches.length + 1}`, { operator: '>=', threshold: 0 }]]);
    } else {
      setBranches([...branches, [`Branch ${branches.length + 1}`, { value: true }]]);
    }
  };

  const removeBranch = (idx: number) => {
    if (branches.length <= 2) return;
    setBranches(branches.filter((_, i) => i !== idx));
  };

  const handleSave = (e: React.MouseEvent) => {
    e.stopPropagation();
    const branchObj: Record<string, unknown> = {};
    branches.forEach(([name, def]) => { branchObj[name] = def; });
    onSave({
      label: label || attrDef?.label || attribute,
      attribute,
      conditionType: condType,
      branches: branchObj,
    });
  };

  return (
    <div
      className="relative px-3 py-3 min-w-[260px] max-w-[320px] rounded-lg border-2 border-blue-500 shadow-lg shadow-blue-500/20"
      style={{ background: 'var(--color-surface)' }}
      onClick={(e) => e.stopPropagation()}
    >
      <Handle type="target" position={Position.Top} className="!bg-blue-500 !w-3 !h-3" />
      <div className="space-y-2">
        <div className="text-[10px] font-semibold text-blue-400 uppercase tracking-wider">Edit Condition</div>

        <input
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Label (e.g. Customer Type)"
          className="w-full px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)]"
          autoFocus
        />

        <select
          value={attribute}
          onChange={(e) => handleAttrChange(e.target.value)}
          className="w-full px-2 py-1 text-xs rounded border border-[var(--color-border)] bg-[var(--color-bg)] text-[var(--color-text)]"
        >
          <option value="">Select attribute...</option>
          <optgroup label="Binary (Yes/No)">
            {ROUTING_ATTRIBUTES.filter((a) => a.type === 'binary').map((a) => (
              <option key={a.value} value={a.value}>{a.label}</option>
            ))}
          </optgroup>
          <optgroup label="Categorical">
            {ROUTING_ATTRIBUTES.filter((a) => a.type === 'categorical').map((a) => (
              <option key={a.value} value={a.value}>{a.label}</option>
            ))}
          </optgroup>
          <optgroup label="Numeric Range">
            {ROUTING_ATTRIBUTES.filter((a) => a.type === 'numeric_range').map((a) => (
              <option key={a.value} value={a.value}>{a.label}{a.unit ? ` (${a.unit})` : ''}</option>
            ))}
          </optgroup>
        </select>

        <div className="border-t pt-2" style={{ borderColor: 'var(--color-border)' }}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] font-semibold text-[var(--color-text-secondary)] uppercase">Branches</span>
            <button onClick={addBranch} className="p-0.5 rounded hover:bg-blue-500/10">
              <Plus size={11} className="text-blue-400" />
            </button>
          </div>

          {branches.map(([name, def], idx) => (
            <div key={idx} className="mb-1.5 p-1.5 rounded bg-[var(--color-bg)] space-y-1">
              <div className="flex items-center gap-1">
                <div className="w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0" />
                <input
                  value={name}
                  onChange={(e) => updateBranch(idx, 'name', e.target.value)}
                  className="flex-1 px-1.5 py-0.5 text-xs rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] font-medium"
                  placeholder="Branch name"
                />
                {branches.length > 2 && (
                  <button onClick={() => removeBranch(idx)} className="p-0.5 text-red-400 hover:text-red-500">
                    <Trash2 size={10} />
                  </button>
                )}
              </div>

              {condType === 'binary' && (
                <select
                  value={String(def.value ?? true)}
                  onChange={(e) => updateBranch(idx, 'value', e.target.value === 'true')}
                  className="w-full px-1.5 py-0.5 text-[11px] rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
                >
                  <option value="true">True (Yes)</option>
                  <option value="false">False (No)</option>
                </select>
              )}

              {condType === 'categorical' && (
                <input
                  value={(def.values || []).join(', ')}
                  onChange={(e) => updateBranch(idx, 'values', e.target.value.split(',').map((v) => v.trim()).filter(Boolean))}
                  placeholder={attrDef?.categories ? `e.g. ${attrDef.categories.slice(0, 2).join(', ')}` : 'Values (comma-separated)'}
                  className="w-full px-1.5 py-0.5 text-[11px] rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
                />
              )}

              {condType === 'numeric_range' && (
                <div className="flex items-center gap-1">
                  <select
                    value={def.operator || '>='}
                    onChange={(e) => updateBranch(idx, 'operator', e.target.value)}
                    className="w-14 px-1 py-0.5 text-[11px] rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
                  >
                    <option value=">=">{'≥'}</option>
                    <option value=">">{'>'}</option>
                    <option value="<">{'<'}</option>
                    <option value="<=">{'≤'}</option>
                    <option value="==">{'='}</option>
                  </select>
                  <input
                    type="number"
                    value={def.threshold ?? ''}
                    onChange={(e) => updateBranch(idx, 'threshold', Number(e.target.value))}
                    placeholder="Value"
                    className="flex-1 px-1.5 py-0.5 text-[11px] rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
                  />
                  {attrDef?.unit && (
                    <span className="text-[10px] text-[var(--color-text-secondary)]">{attrDef.unit}</span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="flex gap-1">
          <button
            onClick={handleSave}
            className="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-xs rounded bg-blue-500 text-white hover:bg-blue-600"
          >
            <Check size={12} /> Apply
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onCancel(); }}
            className="px-2 py-1 text-xs rounded border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
          >
            Cancel
          </button>
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-blue-500 !w-3 !h-3" />
    </div>
  );
}

export const ConditionNode = memo(ConditionNodeInner);
