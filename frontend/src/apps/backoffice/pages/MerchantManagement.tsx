import { useEffect, useState, useRef } from 'react';
import { ChevronDown, ChevronUp, Plus, Trash2, Upload, Tags } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { adminApi } from '../../../api/endpoints';

type Merchant = { id: number; name: string; is_active: boolean };
type Branch = { id: number; merchant_id: number; name: string; address?: string; is_online: boolean; is_active: boolean };
type Category = { id: number; name: string };

function parseCategoriesFromCsv(text: string): string[] {
  const names = new Set<string>();
  const lines = text.split(/\r?\n/);
  for (const line of lines) {
    const parts = line.split(';').map((p) => p.trim()).filter(Boolean);
    parts.forEach((p) => names.add(p));
  }
  return Array.from(names);
}

export default function MerchantManagement() {
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [branchesByMerchant, setBranchesByMerchant] = useState<Record<number, Branch[]>>({});
  const [categoriesByMerchant, setCategoriesByMerchant] = useState<Record<number, Category[]>>({});
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [newMerchant, setNewMerchant] = useState('');
  const [newBranch, setNewBranch] = useState<Record<number, { name: string; address: string; is_online: boolean }>>({});
  const [newCategory, setNewCategory] = useState<Record<number, string>>({});
  const [categoryEditing, setCategoryEditing] = useState<Record<number, string>>({});
  const [importStatus, setImportStatus] = useState<Record<number, { success?: number; error?: string }>>({});
  const fileInputRefs = useRef<Record<number, HTMLInputElement | null>>({});

  const loadMerchants = async () => {
    const res = await adminApi.getMerchants();
    setMerchants(res.data || []);
  };

  const loadBranches = async (merchantId: number) => {
    const res = await adminApi.getBranches(merchantId);
    setBranchesByMerchant((prev) => ({ ...prev, [merchantId]: res.data || [] }));
  };

  const loadCategories = async (merchantId: number) => {
    const res = await adminApi.getCategories(merchantId);
    setCategoriesByMerchant((prev) => ({ ...prev, [merchantId]: res.data || [] }));
  };

  useEffect(() => {
    loadMerchants();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Merchant & Branch Management</h1>
        <p className="text-sm text-[var(--color-text-muted)]">Manage lenders' merchant list and branch directory</p>
      </div>

      <Card>
        <div className="flex items-center gap-2">
          <input
            value={newMerchant}
            onChange={(e) => setNewMerchant(e.target.value)}
            placeholder="Add new merchant..."
            className="flex-1 px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg"
          />
          <Button
            onClick={async () => {
              if (!newMerchant.trim()) return;
              await adminApi.createMerchant({ name: newMerchant.trim(), is_active: true });
              setNewMerchant('');
              await loadMerchants();
            }}
          >
            <Plus size={14} className="mr-1" /> Add Merchant
          </Button>
        </div>
      </Card>

      <div className="space-y-3">
        {merchants.map((m) => {
          const isOpen = !!expanded[m.id];
          const branches = branchesByMerchant[m.id] || [];
          return (
            <Card key={m.id}>
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold">{m.name}</div>
                  <div className="text-xs text-[var(--color-text-muted)]">
                    {m.is_active ? 'Active' : 'Inactive'} • {branches.length} branches • {(categoriesByMerchant[m.id] || []).length} categories
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={async () => {
                      await adminApi.updateMerchant(m.id, { is_active: !m.is_active });
                      await loadMerchants();
                    }}
                  >
                    {m.is_active ? 'Deactivate' : 'Activate'}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={async () => {
                      const next = !isOpen;
                      setExpanded((prev) => ({ ...prev, [m.id]: next }));
                      if (next) {
                        await Promise.all([loadBranches(m.id), loadCategories(m.id)]);
                      }
                    }}
                  >
                    {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </Button>
                </div>
              </div>

              {isOpen && (
                <div className="mt-4 space-y-3">
                  <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                          <th className="px-3 py-2 text-left">Branch</th>
                          <th className="px-3 py-2 text-left">Address</th>
                          <th className="px-3 py-2 text-left">Online</th>
                          <th className="px-3 py-2 text-left">Active</th>
                          <th className="px-3 py-2 text-left">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {branches.map((b) => (
                          <tr key={b.id} className="border-b border-[var(--color-border)]">
                            <td className="px-3 py-2">{b.name}</td>
                            <td className="px-3 py-2 text-[var(--color-text-muted)]">{b.address || '—'}</td>
                            <td className="px-3 py-2">{b.is_online ? 'Yes' : 'No'}</td>
                            <td className="px-3 py-2">{b.is_active ? 'Yes' : 'No'}</td>
                            <td className="px-3 py-2">
                              <div className="flex items-center gap-2">
                                <button
                                  className="text-[var(--color-primary)]"
                                  onClick={async () => {
                                    await adminApi.updateBranch(b.id, { is_active: !b.is_active });
                                    await loadBranches(m.id);
                                  }}
                                >
                                  {b.is_active ? 'Deactivate' : 'Activate'}
                                </button>
                                {!b.is_online && (
                                  <button
                                    className="text-red-400 inline-flex items-center gap-1"
                                    onClick={async () => {
                                      await adminApi.deleteBranch(b.id);
                                      await loadBranches(m.id);
                                    }}
                                  >
                                    <Trash2 size={14} /> Delete
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                    <input
                      placeholder="Branch name"
                      value={newBranch[m.id]?.name || ''}
                      onChange={(e) => setNewBranch((prev) => ({ ...prev, [m.id]: { ...(prev[m.id] || { address: '', is_online: false }), name: e.target.value } }))}
                      className="px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg"
                    />
                    <input
                      placeholder="Address"
                      value={newBranch[m.id]?.address || ''}
                      onChange={(e) => setNewBranch((prev) => ({ ...prev, [m.id]: { ...(prev[m.id] || { name: '', is_online: false }), address: e.target.value } }))}
                      className="px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg"
                    />
                    <label className="inline-flex items-center gap-2 px-3 py-2 border border-[var(--color-border)] rounded-lg">
                      <input
                        type="checkbox"
                        checked={!!newBranch[m.id]?.is_online}
                        onChange={(e) => setNewBranch((prev) => ({ ...prev, [m.id]: { ...(prev[m.id] || { name: '', address: '' }), is_online: e.target.checked } }))}
                      />
                      Online Branch
                    </label>
                    <Button
                      onClick={async () => {
                        const payload = newBranch[m.id];
                        if (!payload?.name?.trim()) return;
                        await adminApi.createBranch(m.id, {
                          name: payload.name.trim(),
                          address: payload.address || undefined,
                          is_online: !!payload.is_online,
                          is_active: true,
                        });
                        setNewBranch((prev) => ({ ...prev, [m.id]: { name: '', address: '', is_online: false } }));
                        await loadBranches(m.id);
                      }}
                    >
                      <Plus size={14} className="mr-1" /> Add Branch
                    </Button>
                  </div>

                  <div className="mt-6 pt-4 border-t border-[var(--color-border)]">
                    <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                      <Tags size={16} /> Product Categories
                    </h3>
                    <div className="flex flex-wrap items-center gap-2 mb-3">
                      <input
                        placeholder="Add category..."
                        value={newCategory[m.id] || ''}
                        onChange={(e) => setNewCategory((prev) => ({ ...prev, [m.id]: e.target.value }))}
                        className="flex-1 min-w-0 sm:min-w-[160px] px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg"
                      />
                      <Button
                        size="sm"
                        onClick={async () => {
                          const name = (newCategory[m.id] || '').trim();
                          if (!name) return;
                          await adminApi.createCategory(m.id, { name });
                          setNewCategory((prev) => ({ ...prev, [m.id]: '' }));
                          await loadCategories(m.id);
                        }}
                      >
                        <Plus size={14} className="mr-1" /> Add
                      </Button>
                      <input
                        ref={(el) => { fileInputRefs.current[m.id] = el; }}
                        type="file"
                        accept=".csv,.txt"
                        className="hidden"
                        onChange={async (e) => {
                          const file = e.target.files?.[0];
                          if (!file) return;
                          e.target.value = '';
                          setImportStatus((prev) => ({ ...prev, [m.id]: {} }));
                          try {
                            const text = await file.text();
                            const names = parseCategoriesFromCsv(text);
                            if (names.length === 0) {
                              setImportStatus((prev) => ({ ...prev, [m.id]: { error: 'No valid names in file' } }));
                              return;
                            }
                            let created = 0;
                            for (const n of names) {
                              try {
                                await adminApi.createCategory(m.id, { name: n });
                                created++;
                              } catch { /* skip */ }
                            }
                            await loadCategories(m.id);
                            setImportStatus((prev) => ({ ...prev, [m.id]: { success: created } }));
                          } catch {
                            setImportStatus((prev) => ({ ...prev, [m.id]: { error: 'Failed to read file' } }));
                          }
                        }}
                      />
                      <Button variant="outline" size="sm" onClick={() => fileInputRefs.current[m.id]?.click()}>
                        <Upload size={14} className="mr-1" /> Import CSV
                      </Button>
                    </div>
                    {importStatus[m.id] && (
                      <div className={`mb-2 text-sm ${importStatus[m.id].error ? 'text-red-400' : 'text-emerald-400'}`}>
                        {importStatus[m.id].error ?? `Imported ${importStatus[m.id].success} categories`}
                      </div>
                    )}
                    <div className="border border-[var(--color-border)] rounded-lg overflow-hidden">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                            <th className="px-3 py-2 text-left">Category Name</th>
                            <th className="px-3 py-2 text-left">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(categoriesByMerchant[m.id] || []).map((c) => (
                            <tr key={c.id} className="border-b border-[var(--color-border)]">
                              <td className="px-3 py-2">
                                <input
                                  value={categoryEditing[c.id] ?? c.name}
                                  onChange={(e) => setCategoryEditing((prev) => ({ ...prev, [c.id]: e.target.value }))}
                                  className="w-full px-2 py-1 bg-[var(--color-bg)] border border-[var(--color-border)] rounded"
                                />
                              </td>
                              <td className="px-3 py-2">
                                <div className="flex items-center gap-2">
                                  <button
                                    className="text-[var(--color-primary)]"
                                    onClick={async () => {
                                      const name = (categoryEditing[c.id] ?? c.name).trim();
                                      if (!name) return;
                                      await adminApi.updateCategory(c.id, { name });
                                      await loadCategories(m.id);
                                    }}
                                  >
                                    Save
                                  </button>
                                  <button
                                    className="text-red-400 inline-flex items-center gap-1"
                                    onClick={async () => {
                                      await adminApi.deleteCategory(c.id);
                                      await loadCategories(m.id);
                                    }}
                                  >
                                    <Trash2 size={14} /> Delete
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                          {(!categoriesByMerchant[m.id] || categoriesByMerchant[m.id].length === 0) && (
                            <tr>
                              <td colSpan={2} className="px-3 py-4 sm:py-6 text-center text-[var(--color-text-muted)]">
                                No categories. Add one or import from CSV (semicolon delimiter).
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
