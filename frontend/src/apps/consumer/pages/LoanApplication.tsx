import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, ChevronRight, Check } from 'lucide-react';
import Card from '../../../components/ui/Card';
import Button from '../../../components/ui/Button';
import Input from '../../../components/ui/Input';
import Select from '../../../components/ui/Select';
import { loanApi } from '../../../api/endpoints';

const STEPS = ['Personal Info', 'Employment', 'Loan Details', 'Documents', 'Review'];

const PURPOSE_OPTIONS = [
  { value: 'debt_consolidation', label: 'Debt Consolidation' },
  { value: 'home_improvement', label: 'Home Improvement' },
  { value: 'medical', label: 'Medical Expenses' },
  { value: 'education', label: 'Education' },
  { value: 'vehicle', label: 'Vehicle Purchase' },
  { value: 'personal', label: 'Personal' },
  { value: 'business', label: 'Business' },
  { value: 'other', label: 'Other' },
];

const TERM_OPTIONS = [
  { value: '12', label: '12 months (1 year)' },
  { value: '24', label: '24 months (2 years)' },
  { value: '36', label: '36 months (3 years)' },
  { value: '48', label: '48 months (4 years)' },
  { value: '60', label: '60 months (5 years)' },
  { value: '72', label: '72 months (6 years)' },
  { value: '84', label: '84 months (7 years)' },
];

export default function LoanApplication() {
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const [profile, setProfile] = useState({
    date_of_birth: '', national_id: '', gender: '', marital_status: '',
    address_line1: '', address_line2: '', city: '', parish: '',
  });
  const [employment, setEmployment] = useState({
    employer_name: '', job_title: '', employment_type: '', years_employed: '',
    monthly_income: '', other_income: '', monthly_expenses: '', existing_debt: '', dependents: '',
  });
  const [loan, setLoan] = useState({
    amount_requested: '', term_months: '', purpose: '', purpose_description: '',
  });
  const [files, setFiles] = useState<{ type: string; file: File }[]>([]);

  const updateProfile = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setProfile({ ...profile, [e.target.name]: e.target.value });
  const updateEmployment = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setEmployment({ ...employment, [e.target.name]: e.target.value });
  const updateLoan = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
    setLoan({ ...loan, [e.target.name]: e.target.value });

  const handleFileAdd = (type: string, file: File) => {
    setFiles((prev) => [...prev.filter((f) => f.type !== type), { type, file }]);
  };

  /** Convert empty strings to undefined so Pydantic receives null instead of "". */
  const emptyToUndef = (v: string) => (v === '' ? undefined : v);

  const handleSubmit = async () => {
    setLoading(true);
    setError('');
    try {
      // 1. Update profile
      await loanApi.updateProfile({
        date_of_birth: emptyToUndef(profile.date_of_birth),
        national_id: emptyToUndef(profile.national_id),
        gender: emptyToUndef(profile.gender),
        marital_status: emptyToUndef(profile.marital_status),
        address_line1: emptyToUndef(profile.address_line1),
        address_line2: emptyToUndef(profile.address_line2),
        city: emptyToUndef(profile.city),
        parish: emptyToUndef(profile.parish),
        years_employed: employment.years_employed ? parseInt(employment.years_employed) : undefined,
        monthly_income: employment.monthly_income ? parseFloat(employment.monthly_income) : undefined,
        other_income: employment.other_income ? parseFloat(employment.other_income) : undefined,
        monthly_expenses: employment.monthly_expenses ? parseFloat(employment.monthly_expenses) : undefined,
        existing_debt: employment.existing_debt ? parseFloat(employment.existing_debt) : undefined,
        dependents: employment.dependents ? parseInt(employment.dependents) : undefined,
        employer_name: emptyToUndef(employment.employer_name),
        job_title: emptyToUndef(employment.job_title),
        employment_type: emptyToUndef(employment.employment_type),
      });

      // 2. Create loan application
      const loanRes = await loanApi.create({
        amount_requested: parseFloat(loan.amount_requested),
        term_months: parseInt(loan.term_months),
        purpose: loan.purpose,
        purpose_description: loan.purpose_description || undefined,
      });

      const appId = loanRes.data.id;

      // 3. Upload documents
      for (const { type, file } of files) {
        const formData = new FormData();
        formData.append('document_type', type);
        formData.append('file', file);
        await loanApi.uploadDocument(appId, formData);
      }

      // 4. Submit application
      await loanApi.submit(appId);

      navigate(`/applications/${appId}`);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'string') {
        setError(detail);
      } else if (Array.isArray(detail)) {
        // Pydantic validation errors — extract human-readable messages
        setError(detail.map((e: any) => e.msg || String(e)).join('; '));
      } else {
        setError('Failed to submit application');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Loan Application</h1>

      {/* Step indicator */}
      <div className="flex items-center mb-8">
        {STEPS.map((label, i) => (
          <div key={label} className="flex items-center flex-1">
            <div className="flex items-center">
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium
                ${i < step ? 'bg-green-500 text-white' : i === step ? 'bg-[var(--color-primary)] text-white' : 'bg-gray-200 text-gray-500'}`}>
                {i < step ? <Check size={16} /> : i + 1}
              </div>
              <span className={`ml-2 text-sm hidden sm:inline ${i === step ? 'font-medium text-gray-900' : 'text-gray-500'}`}>
                {label}
              </span>
            </div>
            {i < STEPS.length - 1 && <div className="flex-1 h-px bg-gray-200 mx-3" />}
          </div>
        ))}
      </div>

      {error && <div className="mb-4 p-3 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>}

      <Card padding="lg">
        {/* Step 1: Personal Info */}
        {step === 0 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold mb-4">Personal Information</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input label="Date of Birth" name="date_of_birth" type="date" value={profile.date_of_birth} onChange={updateProfile} required />
              <Input label="National ID" name="national_id" value={profile.national_id} onChange={updateProfile} placeholder="e.g. 19880315001" required />
              <Select label="Gender" name="gender" value={profile.gender} onChange={updateProfile}
                options={[{ value: 'male', label: 'Male' }, { value: 'female', label: 'Female' }, { value: 'other', label: 'Other' }]} />
              <Select label="Marital Status" name="marital_status" value={profile.marital_status} onChange={updateProfile}
                options={[{ value: 'single', label: 'Single' }, { value: 'married', label: 'Married' }, { value: 'divorced', label: 'Divorced' }, { value: 'widowed', label: 'Widowed' }]} />
            </div>
            <Input label="Address Line 1" name="address_line1" value={profile.address_line1} onChange={updateProfile} required />
            <Input label="Address Line 2 (optional)" name="address_line2" value={profile.address_line2} onChange={updateProfile} />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input label="City/Town" name="city" value={profile.city} onChange={updateProfile} required />
              <Input label="Parish/Region" name="parish" value={profile.parish} onChange={updateProfile} />
            </div>
          </div>
        )}

        {/* Step 2: Employment */}
        {step === 1 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold mb-4">Employment & Income</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input label="Employer Name" name="employer_name" value={employment.employer_name} onChange={updateEmployment} required />
              <Input label="Job Title" name="job_title" value={employment.job_title} onChange={updateEmployment} required />
              <Select label="Employment Type" name="employment_type" value={employment.employment_type} onChange={updateEmployment}
                options={[{ value: 'employed', label: 'Employed' }, { value: 'self_employed', label: 'Self-Employed' }, { value: 'contract', label: 'Contract' }]} />
              <Input label="Years at Current Job" name="years_employed" type="number" value={employment.years_employed} onChange={updateEmployment} min="0" />
              <Input label="Monthly Income (TTD)" name="monthly_income" type="number" value={employment.monthly_income} onChange={updateEmployment} required />
              <Input label="Other Income (TTD)" name="other_income" type="number" value={employment.other_income} onChange={updateEmployment} />
              <Input label="Monthly Expenses (TTD)" name="monthly_expenses" type="number" value={employment.monthly_expenses} onChange={updateEmployment} required />
              <Input label="Existing Debt (TTD)" name="existing_debt" type="number" value={employment.existing_debt} onChange={updateEmployment} />
            </div>
            <Input label="Number of Dependents" name="dependents" type="number" value={employment.dependents} onChange={updateEmployment} min="0" />
          </div>
        )}

        {/* Step 3: Loan Details */}
        {step === 2 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold mb-4">Loan Details</h2>
            <Input label="Loan Amount (TTD)" name="amount_requested" type="number" value={loan.amount_requested} onChange={updateLoan}
              placeholder="e.g. 50000" min="5000" max="500000" required helperText="TTD 5,000 - TTD 500,000" />
            <Select label="Loan Term" name="term_months" value={loan.term_months} onChange={updateLoan} options={TERM_OPTIONS} />
            <Select label="Loan Purpose" name="purpose" value={loan.purpose} onChange={updateLoan} options={PURPOSE_OPTIONS} />
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Additional Details (optional)</label>
              <textarea
                name="purpose_description"
                value={loan.purpose_description}
                onChange={updateLoan}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
                placeholder="Describe how you plan to use the loan..."
              />
            </div>

            {/* Loan estimate */}
            {loan.amount_requested && loan.term_months && (
              <div className="bg-blue-50 p-4 rounded-lg mt-4">
                <h3 className="font-medium text-blue-900 mb-2">Estimated Monthly Payment</h3>
                <p className="text-2xl font-bold text-blue-700">
                  TTD {(
                    (() => {
                      const r = 0.12 / 12; // avg rate estimate
                      const n = parseInt(loan.term_months);
                      const p = parseFloat(loan.amount_requested);
                      return (p * (r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1)).toFixed(2);
                    })()
                  )}
                </p>
                <p className="text-xs text-blue-600 mt-1">* Estimate based on average 12% rate. Actual rate depends on your credit profile.</p>
              </div>
            )}
          </div>
        )}

        {/* Step 4: Documents */}
        {step === 3 && (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold mb-4">Upload Documents</h2>
            <p className="text-sm text-gray-500 mb-4">Please upload clear, legible copies of the following documents.</p>

            {[
              { type: 'national_id', label: 'National ID / Passport', desc: 'A valid government-issued photo ID' },
              { type: 'proof_of_income', label: 'Proof of Income', desc: 'Recent pay slip or employment letter' },
              { type: 'utility_bill', label: 'Utility Bill', desc: 'Proof of address, less than 3 months old' },
            ].map(({ type, label, desc }) => (
              <div key={type} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <p className="font-medium text-sm">{label}</p>
                    <p className="text-xs text-gray-500">{desc}</p>
                  </div>
                  {files.find((f) => f.type === type) && (
                    <span className="text-green-600 text-xs font-medium flex items-center">
                      <Check size={14} className="mr-1" /> Uploaded
                    </span>
                  )}
                </div>
                <input
                  type="file"
                  accept="image/*,.pdf"
                  onChange={(e) => e.target.files?.[0] && handleFileAdd(type, e.target.files[0])}
                  className="text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                />
              </div>
            ))}
          </div>
        )}

        {/* Step 5: Review */}
        {step === 4 && (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold mb-4">Review Your Application</h2>

            <div className="space-y-4">
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-medium mb-2">Personal Information</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <span className="text-gray-500">National ID:</span><span>{profile.national_id}</span>
                  <span className="text-gray-500">Date of Birth:</span><span>{profile.date_of_birth}</span>
                  <span className="text-gray-500">Address:</span><span>{profile.address_line1}, {profile.city}</span>
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-medium mb-2">Employment</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <span className="text-gray-500">Employer:</span><span>{employment.employer_name}</span>
                  <span className="text-gray-500">Monthly Income:</span><span>TTD {parseFloat(employment.monthly_income || '0').toLocaleString()}</span>
                  <span className="text-gray-500">Years Employed:</span><span>{employment.years_employed}</span>
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-medium mb-2">Loan Details</h3>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <span className="text-gray-500">Amount:</span><span>TTD {parseFloat(loan.amount_requested || '0').toLocaleString()}</span>
                  <span className="text-gray-500">Term:</span><span>{loan.term_months} months</span>
                  <span className="text-gray-500">Purpose:</span><span className="capitalize">{loan.purpose.replace('_', ' ')}</span>
                </div>
              </div>

              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-medium mb-2">Documents</h3>
                <ul className="text-sm space-y-1">
                  {files.map((f) => (
                    <li key={f.type} className="flex items-center text-green-700">
                      <Check size={14} className="mr-2" />
                      {f.type.replace('_', ' ')} - {f.file.name}
                    </li>
                  ))}
                  {files.length === 0 && <li className="text-yellow-600">No documents uploaded</li>}
                </ul>
              </div>
            </div>

            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm text-yellow-800">
              By submitting this application, you confirm that all information provided is accurate and you authorize Zotta to perform a credit check.
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex justify-between mt-8 pt-4 border-t border-gray-100">
          <Button variant="ghost" onClick={() => setStep(Math.max(0, step - 1))} disabled={step === 0}>
            <ChevronLeft size={16} className="mr-1" /> Previous
          </Button>
          {step < STEPS.length - 1 ? (
            <Button onClick={() => setStep(step + 1)}>
              Next <ChevronRight size={16} className="ml-1" />
            </Button>
          ) : (
            <Button onClick={handleSubmit} isLoading={loading}>
              Submit Application
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
