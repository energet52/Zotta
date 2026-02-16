/**
 * Shared component rendering the full Hire Purchase Agreement text,
 * matching the exact wording from the contract template (contract_template.docx).
 */
interface HirePurchaseAgreementTextProps {
  applicantName: string;
  applicantAddress: string;
  contactDetails?: string;
  referenceNumber?: string;
  items?: { description?: string; category_name?: string; quantity: number; price: number }[];
  productName?: string;
  cashPrice: number;
  downpayment: number;
  totalFinanced: number;
  interestAndFees: number;
  termMonths: number;
  monthlyPayment: number;
  signedDate?: Date;
}

const fmt = (n: number) => `TTD ${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const ordSuffix = (d: number) => {
  if (d >= 11 && d <= 13) return 'th';
  switch (d % 10) { case 1: return 'st'; case 2: return 'nd'; case 3: return 'rd'; default: return 'th'; }
};

export default function HirePurchaseAgreementText({
  applicantName,
  applicantAddress,
  contactDetails,
  referenceNumber: _referenceNumber,
  items,
  productName,
  cashPrice,
  downpayment,
  totalFinanced,
  interestAndFees,
  termMonths,
  monthlyPayment,
  signedDate,
}: HirePurchaseAgreementTextProps) {
  const now = signedDate || new Date();
  const day = now.getDate();
  const daySuffix = ordSuffix(day);
  const monthName = now.toLocaleDateString('en-US', { month: 'long' });
  const year = now.getFullYear();
  const dateStr = `${String(day).padStart(2, '0')}/${String(now.getMonth() + 1).padStart(2, '0')}/${year}`;
  const repaymentDay = `${day}${daySuffix}`;

  // Compute expiry
  const expiry = new Date(now);
  expiry.setMonth(expiry.getMonth() + termMonths);
  const expiryStr = `${String(expiry.getDate()).padStart(2, '0')}/${String(expiry.getMonth() + 1).padStart(2, '0')}/${expiry.getFullYear()}`;

  const hirePrice = monthlyPayment > 0 ? monthlyPayment * termMonths : totalFinanced;
  const ownerName = 'Effortless Consulting Limited';
  const ownerAddress = 'No.3 The Summit, St. Andrews Wynd Road, Moka, Maraval, in the Island of Trinidad, in the Republic of Trinidad and Tobago';

  const sectionClass = 'text-[var(--color-text)] text-xs leading-relaxed';
  const headingClass = 'font-bold text-sm mt-4 mb-1';
  const subHeadingClass = 'font-semibold text-xs mt-3 mb-1';

  return (
    <div className="space-y-4">
      {/* ─── HIRE PURCHASE AGREEMENT ─── */}
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg p-5 space-y-3 text-sm text-[var(--color-text)] max-h-[60vh] overflow-y-auto">
        <p className="text-center text-[10px] font-semibold tracking-wider text-[var(--color-text-muted)] uppercase">Republic of Trinidad and Tobago</p>
        <p className="text-center text-[10px] text-[var(--color-text-muted)] italic">This Agreement is subject to verification of the Hirer&apos;s information and final credit approval</p>

        <h3 className="font-bold text-center text-base mt-2">Hire Purchase Agreement</h3>

        <p className={sectionClass}>
          This Hire Purchase Agreement (&ldquo;Agreement&rdquo;) is made and entered into on this {day}<sup>{daySuffix}</sup> day of {monthName}, {year}, by and between:
        </p>

        <p className={sectionClass}>
          <span className="font-semibold">Owner:</span> {ownerName}, a company incorporated under the laws of Trinidad and Tobago, having its principal place of business at {ownerAddress} (hereinafter referred to as the &ldquo;Owner&rdquo; which expression will include their successors and assigns);
        </p>
        <p className={`${sectionClass} text-center font-semibold`}>AND</p>
        <p className={sectionClass}>
          <span className="font-semibold">Hirer:</span> {applicantName || '________________________'}, residing at {applicantAddress || '________________________'} (hereinafter referred to as the &ldquo;Hirer&rdquo;).{contactDetails ? <> Contact Details {contactDetails}</> : null}
        </p>

        <p className={sectionClass}>The Owner and Hirer are hereinafter individually referred to as a &ldquo;Party&rdquo; or collectively as &ldquo;Parties.&rdquo;</p>

        <p className={`${sectionClass} font-semibold`}>WHEREAS:</p>
        <ol className={`${sectionClass} list-[upper-alpha] list-inside space-y-1 pl-2`}>
          <li>The Owner is the legal owner of the goods described in Schedule 1 hereto (the &ldquo;Goods&rdquo;) and has agreed to let the Goods on hire to the Hirer, with an option to purchase upon completion of the payments specified in this Agreement;</li>
          <li>The Parties intend this Agreement to be governed by and construed in accordance with the Laws of Trinidad and Tobago, including the Hire Purchase Act, Chapter 82:33. (the &ldquo;Act&rdquo;), where applicable, and acknowledge that nothing in this Agreement will:
            <ol className="list-[lower-roman] list-inside pl-4 mt-1 space-y-0.5">
              <li>prejudice the Owner&apos;s obligation to comply with the provisions of the Act, including, where applicable, the requirement to give not less than twenty-one (21) days&apos; notice before enforcing any right to recover possession of the Goods;</li>
              <li>restrict or exclude the Hirer&apos;s statutory right to terminate this Agreement at any time prior to the final Instalment falling due under this Agreement; or</li>
              <li>impose on the Hirer any liability in addition to that permitted by the Act because of such termination under sub-clause(ii).</li>
            </ol>
          </li>
        </ol>

        <p className={sectionClass}>NOW, THEREFORE, in consideration of the mutual covenants and promises herein contained and for other good and valuable consideration, the receipt and sufficiency of which are hereby acknowledged, the Parties hereto agree as follows:</p>

        {/* Clause 1 */}
        <h4 className={headingClass}>1. Period of Hire</h4>
        <p className={sectionClass}>The period of hire will be for the term specified in the First Schedule hereto commencing on the date therein mentioned and ending, subject to the provisions of Clauses 2 (Payment Terms), 3(b) (Early Purchase Option) and 8 (Termination for Breach) hereof, on the date therein mentioned or in the event of the sooner determination of this Agreement for any reason whatever, on the date of such termination.</p>
        <p className={sectionClass}>So long as the Hirer is neither in default in the payment of any sum of money payable hereunder, nor is in breach of any of the covenants on its part to perform in this Agreement, it may peaceably hold and enjoy quiet possession of the Goods for the period of hire.</p>
        <p className={sectionClass}>The Goods during the period of hire will remain the property of the Owner and the Hirer will be a mere bailee thereof and nothing contained in this Agreement will be deemed to confer on the Hirer any interest in the Goods.</p>

        {/* Clause 2 */}
        <h4 className={headingClass}>2. Payment Terms</h4>
        <p className={sectionClass}>The total hire purchase price for the Goods is {fmt(hirePrice)} (&ldquo;Hire Purchase Price&rdquo;), which includes the cash price plus any applicable charges.</p>
        <p className={sectionClass}>The Hirer acknowledges having been informed of the cash price of the goods before entering into this Agreement and understands the contents of this Agreement and of the accompanying Schedule of goods and credit charges (Schedule 1).</p>
        <p className={sectionClass}>The Hirer agrees to pay punctually and without demand, deduction, counterclaim or set-off to the Owner, the downpayment and the Hire Purchase Price in {termMonths} equal monthly instalments of {fmt(monthlyPayment)} each (&ldquo;Instalment&rdquo;) as set out in Schedule 1 and all other sums due from the Hirer to the Owner, at the times specified for payment in this Agreement.</p>
        <p className={sectionClass}>Payment of the Hirer&apos;s monthly Instalments commences one (1) month after the Hirer receives or takes delivery of the Goods.</p>
        <p className={sectionClass}>All payments will be made to the Owner: (a) at place of purchase; or (b) by way of telegraphic transfer; or (c) such other place or method as the Owner may direct and designate in writing. Any payments sent by post are at the Hirer&apos;s own risk and responsibility.</p>

        <p className={subHeadingClass}>Late Payment of Instalments:</p>
        <p className={sectionClass}><span className="font-semibold">Arrears:</span> It is hereby mutually agreed and understood between Owner and the Hirer that: the Hirer will pay interest on all overdue Instalments at the same rate used to calculate the total credit charges under this Agreement. Interest will accrue daily on the outstanding balance of the cash price (less any downpayment) from the due date until full payment and be payable before and after judgment, if applicable.</p>
        <p className={sectionClass}>If the Hirer fails to make timely payments, then upon termination of the Agreement or upon exercising the option to purchase the Goods, the Hirer will pay all outstanding sums, including accrued interest and any other amounts due under this Agreement.</p>
        <p className={sectionClass}><span className="font-semibold">Late Fee:</span> If the Hirer fails to pay any Instalment or other amount due on its due date, the Owner may, at its discretion and without prejudice to other rights, impose a late payment fee not exceeding the greater of 2% of the overdue amount or TT$50 per overdue instalment, per month or part thereof the amount remains unpaid.</p>

        {/* Clause 3 */}
        <h4 className={headingClass}>3. Ownership of the Goods</h4>
        <p className={sectionClass}>The Owner retains ownership of the Goods until the Hirer has paid all Instalments of the Hire Purchase Price and any other amounts due under the obligations of this Agreement.</p>
        <p className={subHeadingClass}>Early Purchase Option:</p>
        <p className={sectionClass}>Subject to this Agreement and the Hirer&apos;s statutory right to terminate under section 6 of the Act, the Hirer will not be entitled to complete payment of the full Hire Purchase Price and acquire title to the Goods until at least three (3) months (the &ldquo;Minimum Period&rdquo;) from the Commencement Date stated in Schedule 1 herein.</p>

        {/* Clause 4 */}
        <h4 className={headingClass}>4. Obligations of the Hirer</h4>
        <p className={sectionClass}>The Hirer, throughout the term of this Agreement and the period of hire, will:</p>
        <ol className={`${sectionClass} list-[lower-alpha] list-inside pl-2 space-y-0.5`}>
          <li>punctually pay to the Owner, on or before each due date, all Instalments specified in Schedule 1, together with any other sums payable under this Agreement;</li>
          <li>not sell, assign, mortgage, pledge, charge, lease, sublet, lend, or otherwise dispose of or encumber the Goods or any interest therein;</li>
          <li>not allow the Goods to be seized, levied, or subjected to any legal process;</li>
          <li>keep the Goods in the Hirer&apos;s possession and control at the above-named address;</li>
          <li>permit the Owner at all reasonable times to inspect the Goods at any time on demand;</li>
          <li>maintain the Goods in good condition;</li>
          <li>not make any alterations or modifications to the Goods without the Owner&apos;s prior written consent;</li>
          <li>promptly notify the Owner of any change in the Hirer&apos;s address or the location of the Goods;</li>
          <li>keep the Goods properly insured against loss or damage;</li>
          <li>promptly notify the Owner of any damage to or loss of the Goods.</li>
        </ol>

        {/* Clause 5 */}
        <h4 className={headingClass}>5. Rights of the Hirer</h4>
        <p className={subHeadingClass}>a. Right to Terminate:</p>
        <p className={sectionClass}>The Hirer has the right to terminate this Agreement pursuant to the terms in Part A of Schedule 2 herein. (section 6(1) of the Act).</p>
        <p className={subHeadingClass}>b. Right to Information:</p>
        <p className={sectionClass}>The Hirer will have access to the Owner&apos;s online platform (&ldquo;Customer Portal&rdquo;) to see details of the payments made, amounts due, and the remaining term of the Agreement.</p>

        {/* Clause 6 */}
        <h4 className={headingClass}>6. Rights of the Owner</h4>
        <p className={subHeadingClass}>a. Right to Recover Possession:</p>
        <p className={sectionClass}>Where the Hire Purchase Price does not exceed TT$15,000.00, the Owner has the right to recover possession of the Goods pursuant to the terms in Parts B and C of Schedule 2 herein.</p>
        <p className={sectionClass}>Where the total Hire Purchase Price exceeds TT$15,000.00, the Parties acknowledge that the statutory rights and obligations under the Act do not apply to this Agreement, and that the rights and remedies of the Owner and Hirer will be governed solely by the terms of this Agreement and applicable law.</p>

        {/* Clause 7 */}
        <h4 className={headingClass}>7. Implied Conditions and Warranties</h4>
        <p className={sectionClass}>The Owner warrants that it has the right to sell the Goods and that the Goods are free from any charge or encumbrance at the time when the property is to pass.</p>
        <p className={sectionClass}>The Goods are supplied subject only to the conditions and warranties implied under section 10 of the Act, and no other express or implied condition or warranty will apply, except as expressly stated in this Agreement.</p>
        <p className={subHeadingClass}>Product Warranties:</p>
        <p className={sectionClass}>The Owner partners with selected merchants to provide the services under this Agreement. The Hirer selects the Goods at the merchant&apos;s place of business and enters into this Agreement with the Owner. The merchant supplies and delivers the Goods to the Hirer. The Hirer enjoys all product warranties and consumer rights regarding the product as would apply had the Hirer purchased the Goods directly from the merchant.</p>

        {/* Clause 8 */}
        <h4 className={headingClass}>8. Termination for Breach</h4>
        <p className={sectionClass}>a. If the Hirer fails to pay any Instalment or other sum due under this Agreement within ten (10) days of the due date or commits any other material breach, the Owner may terminate this Agreement and retake possession of the Goods, subject to the provisions of the Act. Where the Hirer has paid less than seventy percent (70%) of the total Hire Purchase Price, the Owner will not recover possession unless it has first given the Hirer not less than twenty-one (21) days&apos; written notice specifying the breach and requiring it to be remedied.</p>
        <p className={sectionClass}>b. In the event of the Hirer&apos;s death or the Hirer becoming permanently disabled, or the Goods being destroyed by fire at the Hirer&apos;s home address, all outstanding payments at the date of the event, less any arrears and applied insurance policy proceeds (if any), will be cancelled and no further amounts will be owing on the outstanding payments under this Agreement.</p>

        {/* Clause 9 */}
        <h4 className={headingClass}>9. Other Matters</h4>
        <p className={subHeadingClass}>a. Commencement and Acceptance:</p>
        <p className={sectionClass}>This Agreement will take effect only upon approval by a Director or any person designated by a Director or Manager of the Owner, which will be deemed given upon the Hirer&apos;s receipt and acceptance of delivery of the Goods.</p>
        <p className={subHeadingClass}>b. Entire Agreement and Variation:</p>
        <p className={sectionClass}>The Owner is bound only by the terms of this Agreement, notwithstanding any prior representation, proposal, or communication, whether oral or written. No variation of this Agreement will be binding unless made in writing and signed by a Director or Manager of the Owner and the Hirer.</p>
        <p className={subHeadingClass}>c. No Waiver:</p>
        <p className={sectionClass}>No relaxation, forbearance, indulgence, or extension of time granted by the Owner will affect or limit its rights, powers, or remedies.</p>
        <p className={subHeadingClass}>d. Assignment:</p>
        <p className={sectionClass}>All rights of the Owner hereunder are assignable.</p>
        <p className={subHeadingClass}>e. Notices:</p>
        <p className={sectionClass}>All notices under this Agreement will be in writing and may be delivered by hand, registered post or courier to the recipient&apos;s address stated herein, by email to the designated address, or by SMS or secure messaging platforms (e.g., WhatsApp) to the designated mobile number.</p>
        <p className={subHeadingClass}>f. Use of Information:</p>
        <p className={sectionClass}>The Hirer authorises the Owner to obtain information about the Hirer&apos;s creditworthiness and employment history from any relevant source. The Owner may use information obtained from the Hirer, credit reference agencies, and fraud prevention agencies to assess the application, manage this Agreement, recover debts, prevent fraud and money laundering, and for market research, credit scoring, service improvement, and automated decision-making.</p>
        <p className={sectionClass}>The Owner may disclose details of this Agreement and any default to credit bureaus, fraud prevention agencies, and other authorised credit providers. The Hirer agrees to jointly and severally indemnify the Owner against any claims, losses, or damages arising from the lawful disclosure of such information.</p>
        <p className={subHeadingClass}>g. Joint and Several Liability:</p>
        <p className={sectionClass}>Where two or more persons are named as Hirers, all references to &ldquo;the Hirer&rdquo; will include each of them, and their obligations will be joint and several.</p>
        <p className={subHeadingClass}>h. Interpretation:</p>
        <p className={sectionClass}>In this Agreement, unless the context otherwise requires: Words importing the singular include the plural and vice versa; words importing any gender include all genders. Clause and schedule headings are for convenience only and do not affect interpretation.</p>

        <p className={`${sectionClass} font-semibold mt-4`}>IN WITNESS WHEREOF, the Parties hereto have executed this Hire Purchase Agreement as of the day and year first above written.</p>

        {/* ─── SCHEDULE 1 ─── */}
        <h4 className="font-bold text-sm mt-6 mb-2 text-center border-t border-[var(--color-border)] pt-4">SCHEDULE 1: DESCRIPTION OF GOODS</h4>

        <p className={sectionClass}>The Hirer agrees that the Owner has handed me a complete copy of this Agreement. I have been informed of the cash price of the goods before entering into this Agreement, and I understand the contents of this Agreement and of this Schedule.</p>

        {/* Items table */}
        <div className="overflow-x-auto border border-[var(--color-border)] rounded-lg mt-2">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]">
                <th className="px-3 py-1.5 text-left">Item No.</th>
                <th className="px-3 py-1.5 text-left">Description</th>
                <th className="px-3 py-1.5 text-right">Qty</th>
                <th className="px-3 py-1.5 text-right">Value</th>
              </tr>
            </thead>
            <tbody>
              {(items && items.length > 0 ? items : [{ description: productName || 'Hire Purchase', category_name: '', quantity: 1, price: cashPrice }]).map((it, i) => (
                <tr key={i} className="border-t border-[var(--color-border)]/50">
                  <td className="px-3 py-1.5">{i + 1}</td>
                  <td className="px-3 py-1.5">{it.description || it.category_name || `Item ${i + 1}`}</td>
                  <td className="px-3 py-1.5 text-right">{it.quantity}</td>
                  <td className="px-3 py-1.5 text-right">{fmt(it.price)}</td>
                </tr>
              ))}
              <tr className="border-t-2 border-[var(--color-border)] font-semibold">
                <td className="px-3 py-1.5" colSpan={3}>TOTAL</td>
                <td className="px-3 py-1.5 text-right">{fmt(cashPrice)}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Financial summary */}
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs mt-3 pl-2">
          <span className="text-[var(--color-text-muted)]">Downpayment / Deposit:</span><span className="text-right font-medium">{fmt(downpayment)}</span>
          <span className="text-[var(--color-text-muted)]">Credit Charges:</span><span className="text-right font-medium">{fmt(interestAndFees)}</span>
          <span className="text-[var(--color-text-muted)]">Hire Purchase Price:</span><span className="text-right font-bold">{fmt(hirePrice)}</span>
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs mt-2 pl-2 pt-2 border-t border-[var(--color-border)]">
          <span className="text-[var(--color-text-muted)]">Period of Hire:</span><span className="text-right">{termMonths} Months</span>
          <span className="text-[var(--color-text-muted)]">Commencement Date:</span><span className="text-right">{dateStr}</span>
          <span className="text-[var(--color-text-muted)]">Expiry Date:</span><span className="text-right">{expiryStr}</span>
          <span className="text-[var(--color-text-muted)]">Monthly Instalment:</span><span className="text-right font-bold text-[var(--color-primary)]">{fmt(monthlyPayment)}</span>
          <span className="text-[var(--color-text-muted)]">Total No. of Instalments:</span><span className="text-right">{termMonths}</span>
          <span className="text-[var(--color-text-muted)]">Date each Instalment is payable:</span><span className="text-right">the {repaymentDay} day of every month</span>
        </div>

        <p className={`${sectionClass} mt-3`}>The monthly Instalment payment is due one (1) month after the Hirer receives or takes delivery of the Goods.</p>

        {/* ─── SCHEDULE 2 ─── */}
        <h4 className="font-bold text-sm mt-6 mb-2 text-center border-t border-[var(--color-border)] pt-4">SCHEDULE 2: STATUTORY NOTICES</h4>
        <p className="text-center text-[10px] text-[var(--color-text-muted)]">Pursuant to the Hire Purchase Act, Chapter 82:33 — Section 4(2)(c) of the Act</p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-3 text-[10px] leading-snug">
          <div className="border border-[var(--color-border)] rounded p-2">
            <p className="font-bold mb-1">PART A — Right of Hirer to Terminate Agreement</p>
            <p>1. The Hirer may put an end to this Agreement by giving notice of termination in writing and at the same time delivering the Goods to the Owner.</p>
            <p>2. The Hirer must then pay any instalments which are in arrear.</p>
            <p>3. If the Hirer does not deliver the Goods, the notice of termination will be ineffective.</p>
            <p>4. If the Goods have been damaged owing to the Hirer failing to take reasonable care, the Owner may sue for the amount of the damage.</p>
          </div>
          <div className="border border-[var(--color-border)] rounded p-2">
            <p className="font-bold mb-1">PART B — 70%+ of Hire Purchase Price Paid</p>
            <p>After 70% of the Hire Purchase Price has been paid, the Owner cannot take back the Goods without the Hirer&apos;s consent unless the Owner obtains an order of the Court.</p>
          </div>
          <div className="border border-[var(--color-border)] rounded p-2">
            <p className="font-bold mb-1">PART C — Less than 70% of Hire Purchase Price Paid</p>
            <p>Where less than 70% has been paid, the Owner cannot take back the Goods without first giving twenty-one (21) clear days&apos; written notice. If within that period the Hirer pays all overdue Instalments, the Agreement will continue in force.</p>
          </div>
        </div>

        <p className={`${sectionClass} mt-3`}>The Hirer agrees that the Owner has handed me a complete copy of this Agreement and I understand the contents of this Agreement and of this Schedule.</p>
      </div>
    </div>
  );
}
