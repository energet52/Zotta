import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  GitBranch,
  Search,
  ChevronRight,
  CheckCircle,
  Clock,
  Archive,
  FileEdit,
  Layers,
} from 'lucide-react';
import api from '../../../api/client';

interface TreeNode {
  id: number;
  node_key: string;
  node_type: string;
}

interface DecisionTree {
  id: number;
  product_id: number;
  name: string;
  description: string | null;
  version: number;
  status: string;
  default_strategy_id: number | null;
  nodes: TreeNode[];
  created_at: string;
  updated_at: string;
}

interface Product {
  id: number;
  name: string;
}

const statusConfig: Record<string, { icon: typeof CheckCircle; color: string; label: string }> = {
  active: { icon: CheckCircle, color: 'text-green-500 bg-green-500/10', label: 'Active' },
  draft: { icon: FileEdit, color: 'text-gray-400 bg-gray-400/10', label: 'Draft' },
  archived: { icon: Archive, color: 'text-gray-500 bg-gray-500/10', label: 'Archived' },
};

export default function DecisionTreeList() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const { data: trees = [], isLoading } = useQuery({
    queryKey: ['decision-trees-all', statusFilter],
    queryFn: async () => {
      const params = statusFilter ? `?status=${statusFilter}` : '';
      const res = await api.get(`/decision-trees${params}`);
      return res.data as DecisionTree[];
    },
  });

  const { data: products = [] } = useQuery({
    queryKey: ['products-lookup'],
    queryFn: async () => {
      const res = await api.get('/admin/products');
      return res.data as Product[];
    },
  });

  const productMap = new Map(products.map((p) => [p.id, p.name]));

  const filtered = trees.filter((t) => {
    const productName = productMap.get(t.product_id) || '';
    return (
      t.name.toLowerCase().includes(search.toLowerCase()) ||
      (t.description || '').toLowerCase().includes(search.toLowerCase()) ||
      productName.toLowerCase().includes(search.toLowerCase())
    );
  });

  const grouped = new Map<number, DecisionTree[]>();
  for (const tree of filtered) {
    const list = grouped.get(tree.product_id) || [];
    list.push(tree);
    grouped.set(tree.product_id, list);
  }

  return (
    <div className="p-4 sm:p-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[var(--color-text)]">Decision Trees</h1>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">
            Visual routing logic that assigns strategies to applications
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <div className="relative flex-1 max-w-md">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-secondary)]"
          />
          <input
            type="text"
            placeholder="Search by tree name or product..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-blue-500/30"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 text-sm rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="draft">Draft</option>
          <option value="archived">Archived</option>
        </select>
      </div>

      {/* Tree list */}
      <div className="space-y-4">
        {isLoading && (
          <div className="text-center py-8 text-sm text-[var(--color-text-secondary)]">Loading...</div>
        )}
        {!isLoading && filtered.length === 0 && (
          <div className="text-center py-12">
            <GitBranch size={40} className="mx-auto mb-3 text-[var(--color-text-secondary)]" />
            <p className="text-sm text-[var(--color-text)]">No decision trees found</p>
            <p className="text-xs text-[var(--color-text-secondary)] mt-1">
              Decision trees are created from product settings
            </p>
          </div>
        )}

        {Array.from(grouped.entries()).map(([productId, productTrees]) => {
          const productName = productMap.get(productId) || `Product #${productId}`;
          return (
            <div key={productId}>
              <div className="flex items-center gap-2 mb-2">
                <Layers size={14} className="text-[var(--color-text-secondary)]" />
                <span className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">
                  {productName}
                </span>
              </div>
              <div className="space-y-1.5">
                {productTrees.map((tree) => {
                  const cfg = statusConfig[tree.status] || statusConfig.draft;
                  const StatusIcon = cfg.icon;
                  const nodeCount = tree.nodes?.length || 0;
                  const conditionCount = tree.nodes?.filter((n) => n.node_type === 'condition').length || 0;
                  const strategyCount = tree.nodes?.filter((n) => n.node_type === 'strategy').length || 0;

                  return (
                    <div
                      key={tree.id}
                      onClick={() => navigate(`/backoffice/decision-trees/${tree.id}`)}
                      className="flex items-center gap-4 px-4 py-3 rounded-lg border cursor-pointer hover:border-blue-500/30 transition-colors"
                      style={{ borderColor: 'var(--color-border)', background: 'var(--color-surface)' }}
                    >
                      <div className="p-2 rounded-lg bg-[var(--color-bg)]">
                        <GitBranch size={20} className="text-blue-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm text-[var(--color-text)] truncate">
                            {tree.name}
                          </span>
                          <span className="text-xs text-[var(--color-text-secondary)]">v{tree.version}</span>
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.color}`}>
                            <StatusIcon size={10} /> {cfg.label}
                          </span>
                        </div>
                        {tree.description && (
                          <p className="text-xs text-[var(--color-text-secondary)] mt-0.5 truncate">
                            {tree.description}
                          </p>
                        )}
                        <div className="flex items-center gap-3 mt-1 text-xs text-[var(--color-text-secondary)]">
                          <span>{nodeCount} nodes</span>
                          <span>{conditionCount} conditions</span>
                          <span>{strategyCount} strategy endpoints</span>
                          <span className="flex items-center gap-1">
                            <Clock size={10} />
                            {new Date(tree.updated_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                      <ChevronRight size={16} className="text-[var(--color-text-secondary)]" />
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
