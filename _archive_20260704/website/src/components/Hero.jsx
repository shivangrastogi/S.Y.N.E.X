import { motion } from 'framer-motion';
import { Lock, ArrowRight, Sparkle } from 'lucide-react';
import HeroPreview from './HeroPreview.jsx';

const ease = [0.16, 1, 0.3, 1];

export default function Hero() {
  return (
    <section className="relative min-h-screen flex items-center pt-28 pb-16">
      <div className="mx-auto max-w-7xl px-5 grid lg:grid-cols-2 gap-10 items-center w-full">
        {/* Copy */}
        <div className="relative z-10">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease }}
            className="inline-flex items-center gap-2 glass rounded-full px-3 py-1.5 text-xs text-muted mb-6"
          >
            <Lock size={13} className="text-mint" />
            End-to-end encrypted · reads your bank SMS for you
          </motion.div>

          <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl font-semibold leading-[0.95]">
            <motion.span
              initial={{ opacity: 0, y: 28 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, ease, delay: 0.05 }}
              className="block"
            >
              Money that
            </motion.span>
            <motion.span
              initial={{ opacity: 0, y: 28 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, ease, delay: 0.18 }}
              className="block text-gradient"
            >
              reads itself.
            </motion.span>
          </h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease, delay: 0.32 }}
            className="mt-6 max-w-md text-lg text-muted leading-relaxed"
          >
            AERIS turns your bank &amp; UPI alerts into clean, private
            transactions — then forecasts, charts and nudges you toward your
            goals. No typing. No one watching.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease, delay: 0.44 }}
            className="mt-9 flex flex-wrap items-center gap-4"
          >
            <a
              href="#cta"
              className="group inline-flex items-center gap-2 rounded-2xl bg-mint text-[#042521] font-semibold px-6 py-3.5 hover:shadow-[0_0_36px_rgba(94,234,212,0.55)] transition-shadow"
            >
              Start tracking free
              <ArrowRight
                size={18}
                className="group-hover:translate-x-1 transition-transform"
              />
            </a>
            <a
              href="#features"
              className="inline-flex items-center gap-2 rounded-2xl glass px-6 py-3.5 text-ink hover:border-mint/40 transition-colors"
            >
              <Sparkle size={16} className="text-mint" />
              See what it does
            </a>
          </motion.div>

          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1, delay: 0.7 }}
            className="mt-10 flex items-center gap-6 text-sm text-muted"
          >
            <div>
              <div className="font-display text-2xl text-ink">256-bit</div>
              <div>AES encryption</div>
            </div>
            <div className="h-8 w-px bg-mint/20" />
            <div>
              <div className="font-display text-2xl text-ink">0</div>
              <div>data we can read</div>
            </div>
            <div className="h-8 w-px bg-mint/20" />
            <div>
              <div className="font-display text-2xl text-ink">7+</div>
              <div>chart types</div>
            </div>
          </motion.div>
        </div>

        {/* Product preview (replaces the oversized 3D orb) */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 1.1, ease, delay: 0.2 }}
          className="relative"
        >
          <HeroPreview />
        </motion.div>
      </div>

      <div className="pointer-events-none absolute bottom-6 left-1/2 -translate-x-1/2 text-muted text-xs tracking-widest uppercase">
        scroll
      </div>
    </section>
  );
}
