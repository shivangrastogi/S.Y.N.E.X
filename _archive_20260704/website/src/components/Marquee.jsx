const banks = [
  'SBI', 'HDFC', 'ICICI', 'Axis', 'Kotak', 'Paytm', 'PhonePe',
  'Google Pay', 'Amazon Pay', 'IDFC', 'BHIM', 'Mobikwik',
];

export default function Marquee() {
  const row = [...banks, ...banks];
  return (
    <section className="border-y border-mint/10 py-6 overflow-hidden">
      <div className="mx-auto max-w-7xl px-5 mb-4 text-center text-xs uppercase tracking-[0.25em] text-muted">
        Auto-detects transactions from
      </div>
      <div className="relative flex">
        <div className="marquee-track flex shrink-0 items-center gap-12 pr-12">
          {row.map((b, i) => (
            <span
              key={i}
              className="font-display text-2xl font-medium text-muted/70 whitespace-nowrap"
            >
              {b}
            </span>
          ))}
        </div>
        <div className="marquee-track flex shrink-0 items-center gap-12 pr-12" aria-hidden>
          {row.map((b, i) => (
            <span
              key={`b${i}`}
              className="font-display text-2xl font-medium text-muted/70 whitespace-nowrap"
            >
              {b}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
