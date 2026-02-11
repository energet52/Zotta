import { useEffect, useState } from 'react';
import { ChevronDown, ChevronUp, Plus, Trash2 } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { adminApi } from '../../../api/endpoints';

type Merchant = { id: number; name: string; is_active: boolean };
type Branch = { id: number; merchant_id: number; name: string; address?: string; is_online: boolean; is_active: boolean };

export default function MerchantManagement() {
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [branchesByMerchant, setBranchesByMerchant] = useState<Record<number, Branch[]>>({});
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [newMerchant, setNewMerchant] = useState('');
  const [newBranch, setNewBranch] = useState<Record<number, { name: string; address: string; is_online: boolean }>>({});

  const loadMerchants = async () => {
    const res = await adminApi.getMerchants();
    setMerchants(res.data || []);
  };

  const loadBranches = async (merchantId: number) => {
    const res = await adminApi.getBranches(merchantId);
    setBranchesByMerchant((prev) => ({ ...prev, [merchantId]: res.data || [] }));
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
                    {m.is_active ? 'Active' : 'Inactive'} • {branches.length} branches
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
                      if (next) await loadBranches(m.id);
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
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
