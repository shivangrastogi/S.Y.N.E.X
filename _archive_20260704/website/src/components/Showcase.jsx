import { motion } from 'framer-motion';
import { Lock, KeyRound, EyeOff, Fingerprint } from 'lucide-react';

const ease = [0.16, 1, 0.3, 1];

const points = [
  { icon: KeyRound, t: 'Your key, your data', b: 'A 256-bit key is derived from your password + a recovery key — wrapped, never stored in the clear.' },
  { icon: EyeOff, t: 'We see only ciphertext', b: 'Transactions, amounts and SMS land in the cloud already encrypted. Useless without your device.' },
  { icon: Fingerprint, t: 'On-device intelligence', b: 'Forecasts, categorisation and the assistant all run locally. Nothing is sent off to analyse.' },
];

function PhoneMock() {
  return (
    <div className="relative mx-auto w-[300px]">
      <div className="relative rounded-[2.6rem] border border-mint/20 bg-vault p-3 glow-ring">
        <div className="rounded-[2rem] overflow-hidden bg-obsidian">
          {/* status bar */}
          <div className="flex justify-between items-center px-5 pt-3 pb-1 text-[10px] text-muted">
            <span>9:41</span>
            <span>AERIS</span>
          </div>
          {/* hero spent card */}
          <div className="px-4 pt-2">
            <div className="rounded-3xl p-4 bg-gradient-to-br from-teal to-[#0f766e] text-white shadow-lg">
              <div className="text-[11px] text-white/70">Spent · This month</div>
              <div className="font-display text-3xl font-bold mt-1">₹12,450</div>
              <div className="mt-3 flex gap-2">
                <div className="flex-1 rounded-xl bg-white/15 px-2.5 py-1.5">
                  <div className="text-[9px] text-white/70">Income</div>
                  <div className="text-xs font-bold">₹48k</div>
                </div>
                <div className="flex-1 rounded-xl bg-white/15 px-2.5 py-1.5">
                  <div className="text-[9px] text-white/70">Saved</div>
                  <div className="text-xs font-bold">₹35.5k</div>
                </div>
              </div>
            </div>
          </div>
          {/* budget ring */}
          <div className="px-4 mt-3">
            <div className="rounded-3xl glass p-4 flex items-center gap-4">
              <div
                className="h-16 w-16 rounded-full grid place-items-center"
                style={{
                  background:
                    'conic-gradient(#5eead4 0% 62%, rgba(255,255,255,0.08) 62% 100%)',
                }}
              >
                <div className="h-12 w-12 rounded-full bg-obsidian grid place-items-center text-xs font-bold">
                  62%
                </div>
              </div>
              <div className="text-[11px] leading-relaxed">
                <div className="font-semibold text-ink">Monthly budget</div>
                <div className="text-muted">₹12,450 of ₹20,000</div>
                <div className="text-mint">₹7,550 left</div>
              </div>
            </div>
          </div>
          {/* mini bars */}
          <div className="px-4 mt-3 pb-5">
            <div className="rounded-3xl glass p-4">
              <div className="text-[11px] text-muted mb-2">Daily spend</div>
              <div className="flex items-end gap-1.5 h-16">
                {[30, 55, 22, 70, 40, 88, 50, 64, 35, 78, 46, 60].map((h, i) => (
                  <div
                    key={i}
                    className="flex-1 rounded-t bg-gradient-to-t from-teal to-mint"
                    style={{ height: `${h}%` }}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
      {/* floating chip */}
      <motion.div
        animate={{ y: [0, -10, 0] }}
        transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
        className="absolute -right-6 top-24 glass rounded-2xl px-3 py-2 text-xs glow-ring"
      >
        <div className="flex items-center gap-1.5 text-mint font-semibold">
          <Lock size={12} /> Encrypted
        </div>
      </motion.div>
    </div>
  );
}

export default function Showcase() {
  return (
    <section id="security" className="py-28">
      <div className="mx-auto max-w-7xl px-5 grid lg:grid-cols-2 gap-16 items-center">
        <motion.div
          initial={{ opacity: 0, x: -30 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.8, ease }}
        >
          <PhoneMock />
        </motion.div>

        <div>
          <motion.h2
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, ease }}
            className="font-display text-4xl sm:text-5xl font-semibold"
          >
            Private by architecture, not by promise.
          </motion.h2>
          <p className="mt-4 text-muted text-lg max-w-md">
            Most finance apps ask you to trust them. AERIS makes trust
            unnecessary — your data is unreadable to everyone but you.
          </p>

          <div className="mt-10 space-y-5">
            {points.map((p, i) => (
              <motion.div
                key={p.t}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-50px' }}
                transition={{ duration: 0.5, ease, delay: i * 0.1 }}
                className="flex gap-4"
              >
                <span className="shrink-0 grid place-items-center h-11 w-11 rounded-xl bg-teal/15 border border-mint/25">
                  <p.icon size={20} className="text-mint" />
                </span>
                <div>
                  <div className="font-semibold text-ink">{p.t}</div>
                  <div className="text-muted text-sm leading-relaxed">{p.b}</div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
