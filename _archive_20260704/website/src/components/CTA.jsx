import { motion } from 'framer-motion';
import { Apple, Smartphone } from 'lucide-react';

const ease = [0.16, 1, 0.3, 1];

export default function CTA() {
  return (
    <section id="cta" className="py-28">
      <div className="mx-auto max-w-5xl px-5">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.8, ease }}
          className="relative glass rounded-[2.5rem] px-8 py-16 sm:px-16 text-center overflow-hidden glow-ring"
        >
          <div
            className="pointer-events-none absolute inset-0 opacity-60 spin-slow"
            style={{
              background:
                'conic-gradient(from 90deg at 50% 50%, transparent, rgba(94,234,212,0.18), transparent 50%)',
            }}
          />
          <div className="relative z-10">
            <h2 className="font-display text-4xl sm:text-6xl font-semibold leading-tight">
              Take back control of <br className="hidden sm:block" />
              <span className="text-gradient">your money.</span>
            </h2>
            <p className="mt-5 text-muted text-lg max-w-md mx-auto">
              Free, private, and automatic. Your bank already texts you —
              let AERIS do the rest.
            </p>
            <div className="mt-9 flex flex-wrap justify-center gap-4">
              <a
                href="#"
                className="inline-flex items-center gap-2.5 rounded-2xl bg-mint text-[#042521] font-semibold px-6 py-3.5 hover:shadow-[0_0_36px_rgba(94,234,212,0.55)] transition-shadow"
              >
                <Smartphone size={18} /> Get it on Android
              </a>
              <a
                href="#"
                className="inline-flex items-center gap-2.5 rounded-2xl glass px-6 py-3.5 hover:border-mint/40 transition-colors"
              >
                <Apple size={18} className="text-mint" /> iOS — coming soon
              </a>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
