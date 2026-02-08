import { useRef, useState, useEffect } from 'react';
import Card from './ui/Card';
import Button from './ui/Button';
import { loanApi } from '../api/endpoints';

interface ContractSignatureProps {
  applicationId: number;
  loanAmount: number;
  interestRate: number;
  termMonths: number;
  monthlyPayment: number;
  onSigned: () => void;
  onCancel: () => void;
}

export default function ContractSignature({
  applicationId,
  loanAmount,
  interestRate,
  termMonths,
  monthlyPayment,
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

  // Calculate total payment
  const totalPayment = monthlyPayment > 0 ? monthlyPayment * termMonths : loanAmount;
  const totalInterest = totalPayment - loanAmount;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50 overflow-y-auto">
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <h2 className="text-xl font-bold mb-1">Loan Agreement</h2>
          <p className="text-sm text-gray-500 mb-6">Please review the terms and sign below to accept.</p>

          {/* Contract Terms */}
          <div className="bg-gray-50 rounded-lg p-4 mb-6 text-sm">
            <h3 className="font-semibold text-gray-800 mb-3">Loan Terms Summary</h3>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <span className="text-gray-500">Loan Amount</span>
                <p className="font-bold">TTD {loanAmount.toLocaleString()}</p>
              </div>
              <div>
                <span className="text-gray-500">Interest Rate</span>
                <p className="font-bold">{interestRate}% per annum</p>
              </div>
              <div>
                <span className="text-gray-500">Term</span>
                <p className="font-bold">{termMonths} months</p>
              </div>
              <div>
                <span className="text-gray-500">Monthly Payment</span>
                <p className="font-bold">TTD {monthlyPayment > 0 ? monthlyPayment.toLocaleString() : 'TBD'}</p>
              </div>
              {totalInterest > 0 && (
                <>
                  <div>
                    <span className="text-gray-500">Total Interest</span>
                    <p className="font-bold text-orange-600">TTD {totalInterest.toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>
                  </div>
                  <div>
                    <span className="text-gray-500">Total Repayment</span>
                    <p className="font-bold">TTD {totalPayment.toLocaleString(undefined, { maximumFractionDigits: 2 })}</p>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Terms and Conditions Text */}
          <div className="bg-gray-50 rounded-lg p-4 mb-6 text-xs text-gray-600 max-h-40 overflow-y-auto">
            <h4 className="font-semibold text-gray-700 mb-2">Terms and Conditions</h4>
            <p className="mb-2">
              By signing this agreement, I ("Borrower") acknowledge and agree to the following:
            </p>
            <ol className="list-decimal list-inside space-y-1">
              <li>The Borrower agrees to repay the loan amount plus interest as outlined above, in equal monthly installments.</li>
              <li>Payments are due on the same date each month. Late payments may incur additional fees as per Zotta's fee schedule.</li>
              <li>The Borrower may prepay the loan in full at any time without penalty.</li>
              <li>Failure to make payments for 90 or more consecutive days may result in the loan being classified as delinquent and reported to credit bureaus.</li>
              <li>All information provided in the loan application is true and accurate to the best of the Borrower's knowledge.</li>
              <li>The Borrower agrees to notify Zotta of any material changes to their financial situation.</li>
              <li>This agreement shall be governed by the laws of the Republic of Trinidad and Tobago.</li>
              <li>Zotta reserves the right to transfer or assign this loan agreement to third parties.</li>
            </ol>
          </div>

          {/* Signature Pad */}
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <label className="text-sm font-medium text-gray-700">Draw Your Signature</label>
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
              className="w-full h-32 border-2 border-dashed border-gray-300 rounded-lg cursor-crosshair bg-white touch-none"
              style={{ touchAction: 'none' }}
            />
            {!hasSignature && (
              <p className="text-xs text-gray-400 mt-1">Draw your signature above using your mouse or finger</p>
            )}
          </div>

          {/* Typed Name */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">Full Legal Name</label>
            <input
              type="text"
              value={typedName}
              onChange={(e) => setTypedName(e.target.value)}
              placeholder="Type your full legal name"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            />
          </div>

          {/* Agreement Checkbox */}
          <div className="mb-6">
            <label className="flex items-start space-x-3">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-gray-300 text-[var(--color-primary)] focus:ring-[var(--color-primary)]"
              />
              <span className="text-sm text-gray-700">
                I have read and agree to the terms and conditions outlined above. I understand that this constitutes a legally binding agreement.
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
