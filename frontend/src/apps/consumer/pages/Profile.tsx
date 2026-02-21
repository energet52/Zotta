import { useEffect, useState } from 'react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import Input from '../../../components/ui/Input';
import SearchableSelect from '../../../components/ui/SearchableSelect';
import { OCCUPATION_OPTIONS } from '../../../constants/occupations';
import { loanApi, verificationApi } from '../../../api/endpoints';
import { useAuthStore } from '../../../store/authStore';
import Badge from '../../../components/ui/Badge';

export default function Profile() {
  const { user } = useAuthStore();
  const [profile, setProfile] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [verificationStatus, setVerificationStatus] = useState('pending');

  useEffect(() => {
    Promise.all([
      loanApi.getProfile(),
      verificationApi.getStatus(),
    ]).then(([profRes, verRes]) => {
      setProfile(profRes.data);
      setVerificationStatus(verRes.data.status);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setProfile({ ...profile, [e.target.name]: e.target.value });
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage('');
    try {
      await loanApi.updateProfile(profile);
      setMessage('Profile saved successfully');
    } catch {
      setMessage('Failed to save profile');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="text-center py-12 text-[var(--color-text-muted)]">Loading...</div>;

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6 text-[var(--color-text)]">My Profile</h1>

      {message && (
        <div className={`mb-4 p-3 rounded-lg text-sm border ${message.includes('success') ? 'bg-[var(--color-success)]/20 text-[var(--color-success)] border-[var(--color-success)]/30' : 'bg-red-500/20 text-red-400 border-red-500/30'}`}>
          {message}
        </div>
      )}

      <Card className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-[var(--color-text)]">Account Info</h2>
          <Badge variant={verificationStatus === 'verified' ? 'success' : verificationStatus === 'pending' ? 'warning' : 'danger'}>
            ID: {verificationStatus}
          </Badge>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
          <div><span className="text-[var(--color-text-muted)]">Name:</span> <span className="text-[var(--color-text)]">{user?.first_name} {user?.last_name}</span></div>
          <div><span className="text-[var(--color-text-muted)]">Email:</span> <span className="text-[var(--color-text)]">{user?.email}</span></div>
          <div><span className="text-[var(--color-text-muted)]">Phone:</span> <span className="text-[var(--color-text)]">{user?.phone || 'Not set'}</span></div>
        </div>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold mb-4 text-[var(--color-text)]">Personal Details</h2>
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[var(--color-text-muted)] mb-1">ID Type</label>
              <select
                name="id_type"
                value={profile.id_type || ''}
                onChange={(e) => setProfile({ ...profile, id_type: e.target.value })}
                className="w-full px-3 py-2 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg text-sm text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50 focus:border-[var(--color-primary)]"
              >
                <option value="">Select ID type</option>
                <option value="national_id">National ID</option>
                <option value="passport">Passport</option>
                <option value="drivers_license">Driver&apos;s License</option>
                <option value="tax_number">Tax Number</option>
              </select>
            </div>
            <Input label="ID Number" name="national_id" value={profile.national_id || ''} onChange={handleChange} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="Date of Birth" name="date_of_birth" type="date" value={profile.date_of_birth || ''} onChange={handleChange} />
          </div>
          <Input label="Address" name="address_line1" value={profile.address_line1 || ''} onChange={handleChange} />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="City" name="city" value={profile.city || ''} onChange={handleChange} />
            <Input label="Parish" name="parish" value={profile.parish || ''} onChange={handleChange} />
          </div>

          <h3 className="text-md font-semibold mt-6 pt-4 border-t">Employment</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="Employer" name="employer_name" value={profile.employer_name || ''} onChange={handleChange} />
            <SearchableSelect
              label="Employment Sector"
              value={profile.employer_sector || ''}
              onChange={(v) => setProfile({ ...profile, employer_sector: v })}
              options={[
                'Banking & Financial Services','Insurance','Hospitality & Tourism','Agriculture & Agro-processing','Oil & Gas / Energy','Mining & Extractives','Telecommunications','Retail & Distribution','Real Estate & Construction','Manufacturing','Transportation & Logistics','Healthcare & Pharmaceuticals','Education','Government & Public Sector','Utilities (Water & Electricity)','Creative Industries & Entertainment','Maritime & Shipping','Professional Services (Legal, Accounting, Consulting)','Information Technology','Microfinance & Credit Unions','Other','Not Applicable',
              ].map(s => ({ value: s, label: s }))}
              placeholder="Search or select sector..."
            />
            <SearchableSelect
              label="Occupation / Job Title"
              value={profile.job_title || ''}
              onChange={(v) => setProfile({ ...profile, job_title: v })}
              options={OCCUPATION_OPTIONS.map(s => ({ value: s, label: s }))}
              placeholder="Search or select occupation..."
              allowOther
              otherPlaceholder="Enter your occupation..."
            />
            <Input label="Monthly Income (TTD)" name="monthly_income" type="number" value={profile.monthly_income || ''} onChange={handleChange} />
            <Input label="Years Employed" name="years_employed" type="number" value={profile.years_employed || ''} onChange={handleChange} />
          </div>

          <div className="flex justify-end mt-4">
            <Button onClick={handleSave} isLoading={saving}>Save Profile</Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
