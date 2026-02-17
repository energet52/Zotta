import { useState, useEffect, useCallback } from 'react';
import {
  Shield, Search, RefreshCw, ChevronLeft, ChevronRight,
  User, LogIn, LogOut, FileText, AlertTriangle, Settings,
  CreditCard, Target, Users, MessageSquare, Clock, Filter,
  X, ChevronDown,
} from 'lucide-react';
import { adminApi } from '../../../api/endpoints';

interface AuditEntry {
  id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  user_id: number | null;
  user_name: string | null;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  details: string | null;
  ip_address: string | null;
  created_at: string;
}

interface AuditResponse {
  entries: AuditEntry[];
  total: number;
  limit: number;
  offset: number;
  filters: {
    entity_types: string[];
    actions: string[];
  };
}

const ACTION_CONFIG: Record<string, { icon: typeof Shield; color: string; label: string }> = {
  login: { icon: LogIn, color: '#34d399', label: 'Login' },
  login_failed: { icon: LogIn, color: '#fbbf24', label: 'Failed Login' },
  login_failed_locked: { icon: AlertTriangle, color: '#f87171', label: 'Account Locked' },
  logout: { icon: LogOut, color: '#94a3b8', label: 'Logout' },
  register: { icon: User, color: '#60a5fa', label: 'Registration' },
  mfa_verified: { icon: Shield, color: '#34d399', label: 'MFA Verified' },
  password_changed: { icon: Settings, color: '#fbbf24', label: 'Password Changed' },
  password_reset: { icon: Settings, color: '#fbbf24', label: 'Password Reset' },
  create: { icon: FileText, color: '#60a5fa', label: 'Created' },
  update: { icon: Settings, color: '#a78bfa', label: 'Updated' },
  delete: { icon: AlertTriangle, color: '#f87171', label: 'Deleted' },
  suspend: { icon: AlertTriangle, color: '#f87171', label: 'Suspended' },
  reactivate: { icon: User, color: '#34d399', label: 'Reactivated' },
  deactivate: { icon: AlertTriangle, color: '#f87171', label: 'Deactivated' },
  unlock: { icon: Shield, color: '#34d399', label: 'Unlocked' },
  roles_assigned: { icon: Users, color: '#a78bfa', label: 'Roles Assigned' },
  sessions_revoked: { icon: LogOut, color: '#fbbf24', label: 'Sessions Revoked' },
  consent_signed_and_submitted: { icon: FileText, color: '#34d399', label: 'Consent Signed' },
  contract_signed: { icon: FileText, color: '#34d399', label: 'Contract Signed' },
  counterproposal: { icon: CreditCard, color: '#fbbf24', label: 'Counterproposal' },
  counterproposal_accepted: { icon: CreditCard, color: '#34d399', label: 'Counterproposal Accepted' },
  counterproposal_rejected: { icon: CreditCard, color: '#f87171', label: 'Counterproposal Rejected' },
  offer_accepted: { icon: CreditCard, color: '#34d399', label: 'Offer Accepted' },
  offer_declined: { icon: CreditCard, color: '#f87171', label: 'Offer Declined' },
  document_uploaded: { icon: FileText, color: '#60a5fa', label: 'Document Uploaded' },
  document_deleted: { icon: FileText, color: '#f87171', label: 'Document Deleted' },
  assigned: { icon: User, color: '#a78bfa', label: 'Assigned' },
  underwriter_edit: { icon: Settings, color: '#a78bfa', label: 'Underwriter Edit' },
  underwriter_approve: { icon: Shield, color: '#34d399', label: 'Approved' },
  underwriter_decline: { icon: AlertTriangle, color: '#f87171', label: 'Declined' },
  underwriter_request_info: { icon: MessageSquare, color: '#fbbf24', label: 'Info Requested' },
  disbursed: { icon: CreditCard, color: '#34d399', label: 'Disbursed' },
  staff_created: { icon: FileText, color: '#60a5fa', label: 'Staff Created App' },
  payment_recorded: { icon: CreditCard, color: '#34d399', label: 'Payment Recorded' },
  online_payment: { icon: CreditCard, color: '#34d399', label: 'Online Payment' },
  collection_record_added: { icon: AlertTriangle, color: '#fbbf24', label: 'Collection Record' },
  created: { icon: Target, color: '#60a5fa', label: 'Created' },
  promoted_to_champion: { icon: Target, color: '#34d399', label: 'Promoted to Champion' },
  kill_switch: { icon: AlertTriangle, color: '#f87171', label: 'Kill Switch' },
  retired: { icon: Settings, color: '#94a3b8', label: 'Retired' },
  traffic_allocation_updated: { icon: Target, color: '#a78bfa', label: 'Traffic Updated' },
  ask_ai: { icon: MessageSquare, color: '#a78bfa', label: 'AI Query' },
  contact_info_updated: { icon: User, color: '#a78bfa', label: 'Contact Updated' },
  staff_initiated_conversation: { icon: MessageSquare, color: '#60a5fa', label: 'Conversation Started' },
};

const ENTITY_LABELS: Record<string, string> = {
  auth: 'Authentication',
  user: 'User',
  role: 'Role',
  loan_application: 'Loan Application',
  scorecard: 'Scorecard',
  collection: 'Collection',
  credit_bureau_alert: 'Bureau Alert',
  conversation: 'Conversation',
  pending_action: 'Pending Action',
};

function getActionConfig(action: string) {
  return ACTION_CONFIG[action] || { icon: FileText, color: '#94a3b8', label: action.replace(/_/g, ' ') };
}

function formatDate(iso: string) {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return d.toLocaleDateString('en-TT', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatFullDate(iso: string) {
  return new Date(iso).toLocaleString('en-TT', {
    year: 'numeric', month: 'short', day: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  });
}


export default function AuditTrail() {
  const [data, setData] = useState<AuditResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(0);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const pageSize = 50;

  // Filters
  const [entityType, setEntityType] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [searchText, setSearchText] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number | undefined> = {
        limit: pageSize,
        offset: page * pageSize,
      };
      if (entityType) params.entity_type = entityType;
      if (actionFilter) params.action = actionFilter;
      if (searchText) params.search = searchText;

      const res = await adminApi.getAuditTrail(params);
      setData(res.data);
    } catch (err) {
      console.error('Failed to load audit trail', err);
    } finally {
      setLoading(false);
    }
  }, [page, entityType, actionFilter, searchText]);

  useEffect(() => { load(); }, [load]);

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

  const handleSearch = () => {
    setSearchText(searchInput);
    setPage(0);
  };

  const clearFilters = () => {
    setEntityType('');
    setActionFilter('');
    setSearchText('');
    setSearchInput('');
    setPage(0);
  };

  const hasActiveFilters = entityType || actionFilter || searchText;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[var(--color-text)] flex items-center gap-2">
            <Shield size={22} className="text-[var(--color-primary)]" />
            Audit Trail
          </h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Complete activity log across the system
            {data && <span className="ml-1">— {data.total.toLocaleString()} entries</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm transition-colors ${
              hasActiveFilters
                ? 'border-[var(--color-primary)] text-[var(--color-primary)] bg-[var(--color-primary)]/10'
                : 'border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
            }`}
          >
            <Filter size={14} />
            Filters
            {hasActiveFilters && (
              <span className="w-5 h-5 rounded-full bg-[var(--color-primary)] text-white text-[10px] flex items-center justify-center">
                {[entityType, actionFilter, searchText].filter(Boolean).length}
              </span>
            )}
          </button>
          <button
            onClick={load}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-[var(--color-border)] text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      {/* Filter Panel */}
      {showFilters && (
        <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-[var(--color-text)]">Filters</h3>
            {hasActiveFilters && (
              <button onClick={clearFilters} className="text-xs text-[var(--color-primary)] hover:underline flex items-center gap-1">
                <X size={12} /> Clear all
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Entity Type</label>
              <select
                value={entityType}
                onChange={e => { setEntityType(e.target.value); setPage(0); }}
                className="w-full h-9 px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)]"
              >
                <option value="">All types</option>
                {data?.filters.entity_types.map(t => (
                  <option key={t} value={t}>{ENTITY_LABELS[t] || t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Action</label>
              <select
                value={actionFilter}
                onChange={e => { setActionFilter(e.target.value); setPage(0); }}
                className="w-full h-9 px-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)]"
              >
                <option value="">All actions</option>
                {data?.filters.actions.map(a => (
                  <option key={a} value={a}>{getActionConfig(a).label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Search details</label>
              <form onSubmit={e => { e.preventDefault(); handleSearch(); }} className="flex gap-2">
                <div className="relative flex-1">
                  <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
                  <input
                    value={searchInput}
                    onChange={e => setSearchInput(e.target.value)}
                    placeholder="Search..."
                    className="w-full h-9 pl-8 pr-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-sm text-[var(--color-text)]"
                  />
                </div>
                <button type="submit" className="h-9 px-3 rounded-lg bg-[var(--color-primary)] text-white text-sm">Go</button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Timeline */}
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl overflow-hidden">
        {loading && !data ? (
          <div className="flex items-center justify-center py-20 text-[var(--color-text-muted)]">
            <RefreshCw size={20} className="animate-spin mr-2" />
            Loading audit trail...
          </div>
        ) : !data?.entries.length ? (
          <div className="flex flex-col items-center justify-center py-20 text-[var(--color-text-muted)]">
            <Shield size={32} className="mb-3 opacity-40" />
            <p className="text-sm">No audit entries found</p>
            {hasActiveFilters && (
              <button onClick={clearFilters} className="mt-2 text-xs text-[var(--color-primary)] hover:underline">
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <div className="divide-y divide-[var(--color-border)]">
            {data.entries.map(entry => {
              const config = getActionConfig(entry.action);
              const Icon = config.icon;
              const isExpanded = expandedId === entry.id;
              const hasPayload = entry.old_values || entry.new_values || entry.ip_address;

              return (
                <div key={entry.id}>
                  <button
                    onClick={() => setExpandedId(isExpanded ? null : entry.id)}
                    className="w-full flex items-center gap-4 px-5 py-3.5 text-left hover:bg-[var(--color-surface-hover)] transition-colors"
                  >
                    {/* Icon */}
                    <div
                      className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: `${config.color}20` }}
                    >
                      <Icon size={14} style={{ color: config.color }} />
                    </div>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-sm font-medium text-[var(--color-text)]">
                          {config.label}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-bg)] text-[var(--color-text-muted)]">
                          {ENTITY_LABELS[entry.entity_type] || entry.entity_type}
                        </span>
                        {entry.entity_id > 0 && (
                          <span className="text-[10px] text-[var(--color-text-muted)] font-mono">
                            #{entry.entity_id}
                          </span>
                        )}
                      </div>
                      {entry.details && (
                        <p className="text-xs text-[var(--color-text-muted)] truncate max-w-xl">
                          {entry.details}
                        </p>
                      )}
                    </div>

                    {/* User */}
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {entry.user_name && (
                        <span className="text-xs text-[var(--color-text-muted)]">
                          {entry.user_name}
                        </span>
                      )}
                    </div>

                    {/* Time */}
                    <div className="flex items-center gap-2 flex-shrink-0 w-20 justify-end">
                      <Clock size={12} className="text-[var(--color-text-muted)]" />
                      <span className="text-xs text-[var(--color-text-muted)]" title={formatFullDate(entry.created_at)}>
                        {formatDate(entry.created_at)}
                      </span>
                    </div>

                    {/* Expand indicator */}
                    {hasPayload && (
                      <ChevronDown
                        size={14}
                        className={`text-[var(--color-text-muted)] transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                      />
                    )}
                  </button>

                  {/* Expanded Details */}
                  {isExpanded && hasPayload && (
                    <div className="px-5 pb-4 pl-[4.25rem]">
                      <div className="bg-[var(--color-bg)] rounded-lg p-4 space-y-3 text-xs">
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                          <div>
                            <span className="text-[var(--color-text-muted)] block mb-0.5">Timestamp</span>
                            <span className="text-[var(--color-text)] font-mono">{formatFullDate(entry.created_at)}</span>
                          </div>
                          <div>
                            <span className="text-[var(--color-text-muted)] block mb-0.5">User</span>
                            <span className="text-[var(--color-text)]">{entry.user_name || '—'} (#{entry.user_id})</span>
                          </div>
                          <div>
                            <span className="text-[var(--color-text-muted)] block mb-0.5">IP Address</span>
                            <span className="text-[var(--color-text)] font-mono">{entry.ip_address || '—'}</span>
                          </div>
                          <div>
                            <span className="text-[var(--color-text-muted)] block mb-0.5">Entity</span>
                            <span className="text-[var(--color-text)]">{entry.entity_type} #{entry.entity_id}</span>
                          </div>
                        </div>

                        {entry.old_values && Object.keys(entry.old_values).length > 0 && (
                          <div>
                            <span className="text-[var(--color-text-muted)] block mb-1">Previous Values</span>
                            <pre className="bg-[var(--color-surface)] rounded p-2 overflow-x-auto text-[var(--color-text)] font-mono text-[11px]">
                              {JSON.stringify(entry.old_values, null, 2)}
                            </pre>
                          </div>
                        )}

                        {entry.new_values && Object.keys(entry.new_values).length > 0 && (
                          <div>
                            <span className="text-[var(--color-text-muted)] block mb-1">New Values</span>
                            <pre className="bg-[var(--color-surface)] rounded p-2 overflow-x-auto text-[var(--color-text)] font-mono text-[11px]">
                              {JSON.stringify(entry.new_values, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {data && totalPages > 1 && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-[var(--color-border)]">
            <span className="text-xs text-[var(--color-text-muted)]">
              Showing {data.offset + 1}–{Math.min(data.offset + data.limit, data.total)} of {data.total}
            </span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                className="p-1.5 rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] disabled:opacity-30"
              >
                <ChevronLeft size={14} />
              </button>
              <span className="text-xs text-[var(--color-text-muted)] px-3">
                Page {page + 1} of {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="p-1.5 rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] disabled:opacity-30"
              >
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
