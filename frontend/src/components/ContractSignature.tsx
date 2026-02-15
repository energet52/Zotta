import { useRef, useState, useEffect } from 'react';
import Button from './ui/Button';
import { loanApi } from '../api/endpoints';
import HirePurchaseAgreementText from './HirePurchaseAgreementText';

interface ContractSignatureProps {
  applicationId: number;
  loanAmount: number;
  interestRate: number;
  termMonths: number;
  monthlyPayment: number;
  /** Additional props for the full contract text */
  applicantName?: string;
  applicantAddress?: string;
  referenceNumber?: string;
  downpayment?: number;
  totalFinanced?: number;
  productName?: string;
  items?: { description?: string; category_name?: string; quantity: number; price: number }[];
  onSigned: () => void;
  onCancel: () => void;
}

export default function ContractSignature({
  applicationId,
  loanAmount,
  interestRate: _interestRate,
  termMonths,
  monthlyPayment,
  applicantName,
  applicantAddress,
  referenceNumber,
  downpayment,
  totalFinanced,
  productName,
  items,
  onSigned,
  onCancel,
}: ContractSignatureProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [hasSignature, setHasSignature] = useState(false);
  const [typedName, setTypedName] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * 2;
    canvas.height = rect.height * 2;
    ctx.scale(2, 2);
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#1a202c';
    ctx.lineWidth = 2;
  }, []);

  const getCoords = (e: React.MouseEvent | React.TouchEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    if ('touches' in e) {
      return {
        x: e.touches[0].clientX - rect.left,
        y: e.touches[0].clientY - rect.top,
      };
    }
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    };
  };

  const startDrawing = (e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!ctx) return;

    setIsDrawing(true);
    const { x, y } = getCoords(e);
    ctx.beginPath();
    ctx.moveTo(x, y);
  };

  const draw = (e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    if (!isDrawing) return;
    const ctx = canvasRef.current?.getContext('2d');
    if (!ctx) return;

    const { x, y } = getCoords(e);
    ctx.lineTo(x, y);
    ctx.stroke();
    setHasSignature(true);
  };

  const stopDrawing = () => {
    setIsDrawing(false);
  };

  const clearSignature = () => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    setHasSignature(false);
  };

  const handleSubmit = async () => {
    if (!hasSignature || !typedName || !agreed) return;

    setSubmitting(true);
    setError('');

    try {
      const canvas = canvasRef.current;
      const signatureData = canvas?.toDataURL('image/png') || '';

      await loanApi.signContract(applicationId, {
        signature_data: signatureData,
        typed_name: typedName,
        agreed: true,
      });

      onSigned();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to sign contract');
    } finally {
      setSubmitting(false);
    }
  };

  const isValid = hasSignature && typedName.trim().length >= 2 && agreed;

  // Compute financial values
  const dp = downpayment || 0;
  const tf = totalFinanced || loanAmount;
  const totalRepayment = monthlyPayment > 0 ? monthlyPayment * termMonths : loanAmount;
  const interestAndFees = totalRepayment > (tf - dp) ? totalRepayment - (tf - dp) : 0;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50 overflow-y-auto">
      <div className="bg-[var(--color-surface)] rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <h2 className="text-xl font-bold mb-1 text-[var(--color-text)]">Hire Purchase Agreement</h2>
          <p className="text-sm text-[var(--color-text-muted)] mb-4">Please read the full agreement carefully and sign below to accept.</p>

          {/* Full contract text */}
          <HirePurchaseAgreementText
            applicantName={applicantName || ''}
            applicantAddress={applicantAddress || ''}
            referenceNumber={referenceNumber}
            productName={productName}
            items={items}
            cashPrice={loanAmount}
            downpayment={dp}
            totalFinanced={tf}
            interestAndFees={interestAndFees}
            termMonths={termMonths}
            monthlyPayment={monthlyPayment}
          />

          {/* Signature Pad */}
          <div className="mt-6 mb-4">
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-[var(--color-text)]">Draw Your Signature</label>
              {hasSignature && (
                <button
                  onClick={clearSignature}
                  className="text-xs text-red-500 hover:text-red-700"
                >
                  Clear
                </button>
              )}
            </div>
            <canvas
              ref={canvasRef}
              onMouseDown={startDrawing}
              onMouseMove={draw}
              onMouseUp={stopDrawing}
              onMouseLeave={stopDrawing}
              onTouchStart={startDrawing}
              onTouchMove={draw}
              onTouchEnd={stopDrawing}
              className="w-full h-32 border-2 border-dashed border-[var(--color-border)] rounded-lg cursor-crosshair bg-white touch-none"
              style={{ touchAction: 'none' }}
            />
            {!hasSignature && (
              <p className="text-xs text-[var(--color-text-muted)] mt-1">Draw your signature above using your mouse or finger</p>
            )}
          </div>

          {/* Typed Name */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-[var(--color-text)] mb-1">Full Legal Name</label>
            <input
              type="text"
              value={typedName}
              onChange={(e) => setTypedName(e.target.value)}
              placeholder="Type your full legal name"
              className="w-full px-3 py-2 border border-[var(--color-border)] rounded-lg text-sm bg-[var(--color-surface)] text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/40"
            />
          </div>

          {/* Agreement Checkbox */}
          <div className="mb-6">
            <label className="flex items-start space-x-3 cursor-pointer">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-[var(--color-border)] accent-[var(--color-primary)]"
              />
              <span className="text-sm text-[var(--color-text)]">
                I have read and agree to the Hire Purchase Agreement and Consent above. I confirm my details are accurate and authorize credit checks. I understand that this constitutes a legally binding agreement.
              </span>
            </label>
          </div>

          {error && (
            <div className="mb-4 p-2 bg-red-50 text-red-700 rounded-lg text-sm">{error}</div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <Button
              className="flex-1"
              onClick={handleSubmit}
              isLoading={submitting}
              disabled={!isValid}
            >
              Sign & Accept Contract
            </Button>
            <Button variant="secondary" onClick={onCancel}>
              Cancel
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
