import { useEffect, useState } from 'react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import Input from '../../../components/ui/Input';
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

  if (loading) return <div className="text-center py-12 text-gray-400">Loading...</div>;

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">My Profile</h1>

      {message && (
        <div className={`mb-4 p-3 rounded-lg text-sm ${message.includes('success') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
          {message}
        </div>
      )}

      <Card className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Account Info</h2>
          <Badge variant={verificationStatus === 'verified' ? 'success' : verificationStatus === 'pending' ? 'warning' : 'danger'}>
            ID: {verificationStatus}
          </Badge>
        </div>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div><span className="text-gray-500">Name:</span> {user?.first_name} {user?.last_name}</div>
          <div><span className="text-gray-500">Email:</span> {user?.email}</div>
          <div><span className="text-gray-500">Phone:</span> {user?.phone || 'Not set'}</div>
        </div>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold mb-4">Personal Details</h2>
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input label="National ID" name="national_id" value={profile.national_id || ''} onChange={handleChange} />
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
            <Input label="Job Title" name="job_title" value={profile.job_title || ''} onChange={handleChange} />
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
