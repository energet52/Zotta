import { useState } from 'react';
import { Plus, Pencil, Trash2, MapPin, Save, X } from 'lucide-react';
import Button from './ui/Button';
import Card from './ui/Card';

export interface Reference {
  id?: number;
  name: string;
  relationship_type: string;
  phone: string;
  address: string;
  directions?: string;
}

interface ReferencesEditorProps {
  references: Reference[];
  onAdd: (ref: Omit<Reference, 'id'>) => Promise<void>;
  onUpdate: (id: number, ref: Omit<Reference, 'id'>) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  readOnly?: boolean;
}

const RELATIONSHIP_OPTIONS = [
  'Friend', 'Aunt', 'Uncle', 'Cousin', 'Sibling', 'Parent', 'Grandparent',
  'Neighbour', 'Coworker', 'Employer', 'Pastor', 'Community Leader', 'Other',
];

const emptyForm: Omit<Reference, 'id'> = {
  name: '', relationship_type: '', phone: '', address: '', directions: '',
};

export default function ReferencesEditor({ references, onAdd, onUpdate, onDelete, readOnly = false }: ReferencesEditorProps) {
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);

  const openAdd = () => {
    setForm(emptyForm);
    setEditId(null);
    setShowForm(true);
  };

  const openEdit = (ref: Reference) => {
    setForm({
      name: ref.name,
      relationship_type: ref.relationship_type,
      phone: ref.phone,
      address: ref.address,
      directions: ref.directions || '',
    });
    setEditId(ref.id ?? null);
    setShowForm(true);
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.relationship_type || !form.phone.trim() || !form.address.trim()) return;
    setSaving(true);
    try {
      if (editId != null) {
        await onUpdate(editId, form);
      } else {
        await onAdd(form);
      }
      setShowForm(false);
      setForm(emptyForm);
      setEditId(null);
    } catch { /* ignore */ }
    setSaving(false);
  };

  const handleDelete = async (id: number) => {
    setDeleting(id);
    try {
      await onDelete(id);
    } catch { /* ignore */ }
    setDeleting(null);
  };

  const canSave = form.name.trim() && form.relationship_type && form.phone.trim() && form.address.trim();

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-[var(--color-text)]">References</h3>
          <p className="text-xs text-[var(--color-text-muted)]">
            People who can vouch for your address and employment
          </p>
        </div>
        {!readOnly && !showForm && (
          <Button size="sm" onClick={openAdd}>
            <Plus size={14} className="mr-1" /> Add Reference
          </Button>
        )}
      </div>

      {/* Form (add / edit) */}
      {showForm && (
        <Card className="border-[var(--color-primary)]/30">
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Full Name *</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="e.g. Shaquille Guischard"
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Relationship *</label>
                <select
                  value={form.relationship_type}
                  onChange={(e) => setForm({ ...form, relationship_type: e.target.value })}
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
                >
                  <option value="">Select relationship...</option>
                  {RELATIONSHIP_OPTIONS.map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Phone *</label>
                <input
                  type="tel"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  placeholder="(868) 123-4567"
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">Address *</label>
                <input
                  type="text"
                  value={form.address}
                  onChange={(e) => setForm({ ...form, address: e.target.value })}
                  placeholder="e.g. La Puerta Diego Martin"
                  className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-[var(--color-text-muted)] mb-1">
                <MapPin size={12} className="inline mr-1" />
                Directions to House (optional — for deliveries)
              </label>
              <textarea
                value={form.directions || ''}
                onChange={(e) => setForm({ ...form, directions: e.target.value })}
                placeholder="e.g. Entering Simeon Road, passing the International Church on the left, 3rd house on the right with blue gate"
                rows={2}
                className="w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)] resize-none"
              />
            </div>

            <div className="flex items-center justify-end space-x-2 pt-1">
              <Button size="sm" variant="ghost" onClick={() => { setShowForm(false); setEditId(null); }}>
                <X size={14} className="mr-1" /> Cancel
              </Button>
              <Button size="sm" onClick={handleSave} isLoading={saving} disabled={!canSave}>
                <Save size={14} className="mr-1" /> {editId != null ? 'Update' : 'Add'}
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* Table */}
      {references.length > 0 ? (
        <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]">
                <th className="text-left px-4 py-2.5 font-medium">Address</th>
                <th className="text-left px-4 py-2.5 font-medium">Name</th>
                <th className="text-left px-4 py-2.5 font-medium">Phone</th>
                {!readOnly && <th className="text-right px-4 py-2.5 font-medium w-28">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {references.map((ref) => (
                <tr key={ref.id} className="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-hover)]/50 transition-colors">
                  <td className="px-4 py-2.5">
                    <span className="text-[var(--color-text)]">{ref.address}</span>
                    {ref.directions && (
                      <p className="text-xs text-[var(--color-text-muted)] mt-0.5 italic flex items-start">
                        <MapPin size={10} className="mr-1 mt-0.5 shrink-0" />
                        {ref.directions}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="text-[var(--color-text)]">{ref.name}</span>
                    <span className="text-[var(--color-text-muted)]"> ({ref.relationship_type})</span>
                  </td>
                  <td className="px-4 py-2.5 text-[var(--color-text)]">{ref.phone}</td>
                  {!readOnly && (
                    <td className="px-4 py-2.5 text-right">
                      <div className="flex items-center justify-end space-x-1">
                        <button
                          onClick={() => openEdit(ref)}
                          className="px-2.5 py-1 text-xs border border-[var(--color-border)] rounded hover:bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
                        >
                          <Pencil size={12} className="inline mr-1" />Edit
                        </button>
                        <button
                          onClick={() => ref.id != null && handleDelete(ref.id)}
                          disabled={deleting === ref.id}
                          className="px-2.5 py-1 text-xs border border-red-300 dark:border-red-800 rounded hover:bg-red-50 dark:hover:bg-red-950/30 text-red-500 transition-colors disabled:opacity-50"
                        >
                          <Trash2 size={12} className="inline mr-1" />{deleting === ref.id ? '...' : 'Delete'}
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : !showForm ? (
        <div className="text-center py-8 border border-dashed border-[var(--color-border)] rounded-lg">
          <p className="text-sm text-[var(--color-text-muted)]">No references added yet</p>
          {!readOnly && (
            <Button size="sm" variant="ghost" onClick={openAdd} className="mt-2">
              <Plus size={14} className="mr-1" /> Add your first reference
            </Button>
          )}
        </div>
      ) : null}
    </div>
  );
}
