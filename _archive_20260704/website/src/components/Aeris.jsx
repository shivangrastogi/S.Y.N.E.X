import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';

const lines = [
  'You’re saving 28% this month — nice! 🎉',
  'Food’s your biggest spend. Trim 15%?',
  'Rent usually hits on the 3rd — heads up.',
  '3-day streak! Open me tomorrow to keep it.',
];

function MascotSVG() {
  return (
    <svg viewBox="0 0 200 220" className="w-44 h-48">
      <defs>
        <linearGradient id="body" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#5eead4" />
          <stop offset="1" stopColor="#0ea5a4" />
        </linearGradient>
      </defs>
      {/* antenna */}
      <line x1="100" y1="34" x2="100" y2="14" stroke="#5eead4" strokeWidth="5" strokeLinecap="round" />
      <circle cx="100" cy="10" r="7" fill="#5eead4" />
      {/* body */}
      <rect x="40" y="34" width="120" height="150" rx="46" fill="url(#body)" />
      {/* face plate */}
      <rect x="56" y="58" width="88" height="92" rx="34" fill="#eafff8" />
      {/* eyes */}
      <circle cx="84" cy="98" r="9" fill="#0b1416" />
      <circle cx="116" cy="98" r="9" fill="#0b1416" />
      <circle cx="81" cy="95" r="3" fill="#fff" />
      <circle cx="113" cy="95" r="3" fill="#fff" />
      {/* cheeks */}
      <circle cx="70" cy="116" r="6" fill="#fb7185" opacity="0.5" />
      <circle cx="130" cy="116" r="6" fill="#fb7185" opacity="0.5" />
      {/* smile */}
      <path d="M82 120 Q100 138 118 120" stroke="#0b1416" strokeWidth="5" fill="none" strokeLinecap="round" />
    </svg>
  );
}

export default function Aeris() {
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI((p) => (p + 1) % lines.length), 3200);
    return () => clearInterval(t);
  }, []);

  return (
    <section id="aeris" className="py-28">
      <div className="mx-auto max-w-7xl px-5">
        <div className="glass rounded-[2.5rem] p-10 sm:p-16 grid lg:grid-cols-2 gap-12 items-center overflow-hidden relative">
          <div
            className="pointer-events-none absolute -top-20 -right-20 h-72 w-72 rounded-full blur-3xl opacity-40"
            style={{ background: 'radial-gradient(circle, #5eead4, transparent 70%)' }}
          />
          <div className="relative z-10">
            <p className="text-mint text-sm font-semibold tracking-widest uppercase">
              Your finance buddy
            </p>
            <h2 className="font-display text-4xl sm:text-5xl font-semibold mt-3">
              Say hi to Aeris.
            </h2>
            <p className="mt-4 text-muted text-lg max-w-md">
              Aeris reacts to how you’re doing — celebrating savings, warning
              about overspend — and answers questions about your money, all on
              your device. Ask “how much on food this month?” and get a real
              answer.
            </p>
            <a
              href="#cta"
              className="mt-8 inline-flex rounded-2xl bg-mint text-[#042521] font-semibold px-6 py-3.5 hover:shadow-[0_0_30px_rgba(94,234,212,0.5)] transition-shadow"
            >
              Chat with Aeris
            </a>
          </div>

          <div className="relative z-10 flex flex-col items-center gap-6">
            <motion.div
              animate={{ y: [0, -14, 0] }}
              transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
            >
              <MascotSVG />
            </motion.div>
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 8, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.4 }}
              className="glass rounded-2xl rounded-tl-sm px-5 py-3 max-w-xs text-center"
            >
              <span className="text-mint text-xs font-bold">Aeris</span>
              <p className="text-sm mt-1">{lines[i]}</p>
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}
