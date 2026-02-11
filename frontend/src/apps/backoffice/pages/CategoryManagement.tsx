import { useEffect, useState } from 'react';
import { Plus, Trash2 } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { adminApi } from '../../../api/endpoints';

type Category = { id: number; name: string };

export default function CategoryManagement() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [newName, setNewName] = useState('');
  const [editing, setEditing] = useState<Record<number, string>>({});

  const load = async () => {
    const res = await adminApi.getCategories();
    setCategories(res.data || []);
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Product Category Management</h1>
        <p className="text-sm text-[var(--color-text-muted)]">Define high-level shopping categories shown to consumers</p>
      </div>

      <Card>
        <div className="flex items-center gap-2">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Add new category..."
            className="flex-1 px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg"
          />
          <Button
            onClick={async () => {
              if (!newName.trim()) return;
              await adminApi.createCategory({ name: newName.trim() });
              setNewName('');
              await load();
            }}
          >
            <Plus size={14} className="mr-1" /> Add Category
          </Button>
        </div>
      </Card>

      <Card padding="none">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--color-border)] text-[var(--color-text-muted)]">
                <th className="px-4 py-3 text-left">Category Name</th>
                <th className="px-4 py-3 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {categories.map((c) => (
                <tr key={c.id} className="border-b border-[var(--color-border)]">
                  <td className="px-4 py-2">
                    <input
                      value={editing[c.id] ?? c.name}
                      onChange={(e) => setEditing((prev) => ({ ...prev, [c.id]: e.target.value }))}
                      className="w-full px-2 py-1 bg-[var(--color-bg)] border border-[var(--color-border)] rounded"
                    />
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-3">
                      <button
                        className="text-[var(--color-primary)]"
                        onClick={async () => {
                          const name = (editing[c.id] ?? c.name).trim();
                          if (!name) return;
                          await adminApi.updateCategory(c.id, { name });
                          await load();
                        }}
                      >
                        Save
                      </button>
                      <button
                        className="text-red-400 inline-flex items-center gap-1"
                        onClick={async () => {
                          await adminApi.deleteCategory(c.id);
                          await load();
                        }}
                      >
                        <Trash2 size={14} /> Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {categories.length === 0 && (
                <tr>
                  <td colSpan={2} className="px-4 py-8 text-center text-[var(--color-text-muted)]">
                    No categories found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
