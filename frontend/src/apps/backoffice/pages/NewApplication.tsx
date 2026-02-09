import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserPlus, ArrowLeft, Send } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import { underwriterApi } from '../../../api/endpoints';

const PURPOSES = [
  { value: 'debt_consolidation', label: 'Debt Consolidation' },
  { value: 'home_improvement', label: 'Home Improvement' },
  { value: 'medical', label: 'Medical' },
  { value: 'education', label: 'Education' },
  { value: 'vehicle', label: 'Vehicle' },
  { value: 'personal', label: 'Personal' },
  { value: 'business', label: 'Business' },
  { value: 'other', label: 'Other' },
];

const EMPLOYMENT_TYPES = [
  { value: 'employed', label: 'Employed' },
  { value: 'self_employed', label: 'Self-Employed' },
  { value: 'contract', label: 'Contract' },
  { value: 'part_time', label: 'Part-Time' },
  { value: 'not_employed', label: 'Not Employed' },
];

const PARISHES = [
  'Port of Spain', 'San Fernando', 'Arima', 'Chaguanas', 'Point Fortin',
  'Diego Martin', 'Tunapuna/Piarco', 'San Juan/Laventille', 'Sangre Grande',
  'Penal/Debe', 'Couva/Tabaquite/Talparo', 'Siparia', 'Mayaro/Rio Claro',
  'Princes Town', 'Tobago',
];

export default function NewApplication() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [form, setForm] = useState({
    // Personal
    email: '',
    first_name: '',
    last_name: '',
    phone: '',
    date_of_birth: '',
    national_id: '',
    gender: '',
    address_line1: '',
    city: '',
    parish: '',
    // Employment
    employer_name: '',
    job_title: '',
    employment_type: 'employed',
    years_employed: '',
    monthly_income: '',
    monthly_expenses: '',
    existing_debt: '',
    // Loan
    amount_requested: '',
    term_months: '12',
    purpose: 'personal',
    purpose_description: '',
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      const payload: Record<string, unknown> = {
        email: form.email,
        first_name: form.first_name,
        last_name: form.last_name,
        phone: form.phone || undefined,
        date_of_birth: form.date_of_birth || undefined,
        national_id: form.national_id || undefined,
        gender: form.gender || undefined,
        address_line1: form.address_line1 || undefined,
        city: form.city || undefined,
        parish: form.parish || undefined,
        employer_name: form.employer_name || undefined,
        job_title: form.job_title || undefined,
        employment_type: form.employment_type,
        years_employed: form.years_employed ? parseInt(form.years_employed) : undefined,
        monthly_income: form.monthly_income ? parseFloat(form.monthly_income) : undefined,
        monthly_expenses: form.monthly_expenses ? parseFloat(form.monthly_expenses) : undefined,
        existing_debt: form.existing_debt ? parseFloat(form.existing_debt) : undefined,
        amount_requested: parseFloat(form.amount_requested),
        term_months: parseInt(form.term_months),
        purpose: form.purpose,
        purpose_description: form.purpose_description || undefined,
      };

      const res = await underwriterApi.createOnBehalf(payload);
      setSuccess(`Application created successfully! Reference: ${res.data.reference_number}`);
      setTimeout(() => navigate(`/backoffice/review/${res.data.id}`), 2000);
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(detail.map((e: any) => e.msg || e.message || JSON.stringify(e)).join('; '));
      } else {
        setError(typeof detail === 'string' ? detail : 'Failed to create application');
      }
    }
    setLoading(false);
  };

  const inputClass = "w-full px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:border-[var(--color-primary)]";
  const labelClass = "block text-sm font-medium text-[var(--color-text-muted)] mb-1";

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <button onClick={() => navigate('/backoffice/queue')} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            <ArrowLeft size={20} />
          </button>
          <div className="p-2 bg-[var(--color-primary)]/15 rounded-lg">
            <UserPlus className="text-[var(--color-primary)]" size={24} />
          </div>
          <div>
            <h1 className="text-2xl font-bold">New Walk-in Application</h1>
            <p className="text-sm text-[var(--color-text-muted)]">Create application on behalf of a customer</p>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">{error}</div>
      )}
      {success && (
        <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4 text-emerald-400 text-sm">{success}</div>
      )}

      <form onSubmit={handleSubmit}>
        {/* Personal Information */}
        <Card className="mb-6">
          <h2 className="text-lg font-semibold mb-4 text-[var(--color-primary)]">Personal Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className={labelClass}>Email *</label>
              <input type="email" name="email" value={form.email} onChange={handleChange} className={inputClass} required />
            </div>
            <div>
              <label className={labelClass}>First Name *</label>
              <input type="text" name="first_name" value={form.first_name} onChange={handleChange} className={inputClass} required />
            </div>
            <div>
              <label className={labelClass}>Last Name *</label>
              <input type="text" name="last_name" value={form.last_name} onChange={handleChange} className={inputClass} required />
            </div>
            <div>
              <label className={labelClass}>Phone</label>
              <input type="tel" name="phone" value={form.phone} onChange={handleChange} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Date of Birth</label>
              <input type="date" name="date_of_birth" value={form.date_of_birth} onChange={handleChange} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>National ID</label>
              <input type="text" name="national_id" value={form.national_id} onChange={handleChange} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Gender</label>
              <select name="gender" value={form.gender} onChange={handleChange} className={inputClass}>
                <option value="">Select...</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className={labelClass}>Address</label>
              <input type="text" name="address_line1" value={form.address_line1} onChange={handleChange} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>City</label>
              <input type="text" name="city" value={form.city} onChange={handleChange} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Parish</label>
              <select name="parish" value={form.parish} onChange={handleChange} className={inputClass}>
                <option value="">Select...</option>
                {PARISHES.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
          </div>
        </Card>

        {/* Employment */}
        <Card className="mb-6">
          <h2 className="text-lg font-semibold mb-4 text-[var(--color-primary)]">Employment & Financial</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className={labelClass}>Employer Name</label>
              <input type="text" name="employer_name" value={form.employer_name} onChange={handleChange} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Job Title</label>
              <input type="text" name="job_title" value={form.job_title} onChange={handleChange} className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>Employment Type</label>
              <select name="employment_type" value={form.employment_type} onChange={handleChange} className={inputClass}>
                {EMPLOYMENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div>
              <label className={labelClass}>Years Employed</label>
              <input type="number" name="years_employed" value={form.years_employed} onChange={handleChange} className={inputClass} min="0" />
            </div>
            <div>
              <label className={labelClass}>Monthly Income (TTD)</label>
              <input type="number" name="monthly_income" value={form.monthly_income} onChange={handleChange} className={inputClass} min="0" step="0.01" />
            </div>
            <div>
              <label className={labelClass}>Monthly Expenses (TTD)</label>
              <input type="number" name="monthly_expenses" value={form.monthly_expenses} onChange={handleChange} className={inputClass} min="0" step="0.01" />
            </div>
            <div>
              <label className={labelClass}>Existing Debt (TTD)</label>
              <input type="number" name="existing_debt" value={form.existing_debt} onChange={handleChange} className={inputClass} min="0" step="0.01" />
            </div>
          </div>
        </Card>

        {/* Loan Details */}
        <Card className="mb-6">
          <h2 className="text-lg font-semibold mb-4 text-[var(--color-primary)]">Loan Details</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className={labelClass}>Amount Requested (TTD) *</label>
              <input type="number" name="amount_requested" value={form.amount_requested} onChange={handleChange} className={inputClass} required min="1" max="500000" step="0.01" />
            </div>
            <div>
              <label className={labelClass}>Term (months) *</label>
              <input type="number" name="term_months" value={form.term_months} onChange={handleChange} className={inputClass} required min="3" max="84" />
            </div>
            <div>
              <label className={labelClass}>Purpose *</label>
              <select name="purpose" value={form.purpose} onChange={handleChange} className={inputClass} required>
                {PURPOSES.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div className="md:col-span-3">
              <label className={labelClass}>Purpose Description</label>
              <textarea name="purpose_description" value={form.purpose_description} onChange={handleChange} className={inputClass} rows={2} />
            </div>
          </div>
        </Card>

        <div className="flex justify-end">
          <Button type="submit" disabled={loading}>
            <Send size={16} className="mr-2" />
            {loading ? 'Creating...' : 'Create & Submit Application'}
          </Button>
        </div>
      </form>
    </div>
  );
}
