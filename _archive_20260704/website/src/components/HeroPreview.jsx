import { motion } from 'framer-motion';
import { Lock, TrendingUp, Sparkle } from 'lucide-react';

const ease = [0.16, 1, 0.3, 1];

/* A compact, premium "snapshot" of the app — replaces the oversized 3D orb.
   Gentle float + parallax chips, fully contained within its column. */
export default function HeroPreview() {
  return (
    <div className="relative mx-auto w-full max-w-md aspect-square grid place-items-center">
      {/* soft glow, contained */}
      <div
        className="pointer-events-none absolute h-[78%] w-[78%] rounded-full blur-3xl opacity-40"
        style={{ background: 'radial-gradient(circle, #5eead4, transparent 68%)' }}
      />

      {/* main card */}
      <motion.div
        initial={{ opacity: 0, y: 24, rotateX: 8 }}
        animate={{ opacity: 1, y: [0, -10, 0], rotateX: 0 }}
        transition={{
          opacity: { duration: 0.8, ease },
          rotateX: { duration: 0.8, ease },
          y: { duration: 6, repeat: Infinity, ease: 'easeInOut' },
        }}
        style={{ transformPerspective: 1000 }}
        className="relative z-10 w-[78%] glass rounded-[2rem] p-6 glow-ring"
      >
        <div className="text-xs text-muted">Spent · This month</div>
        <div className="font-display text-4xl font-bold mt-1">₹12,450</div>

        <div className="mt-5 flex items-center gap-4">
          <div
            className="h-20 w-20 rounded-full grid place-items-center shrink-0"
            style={{
              background:
                'conic-gradient(#5eead4 0% 62%, rgba(255,255,255,0.08) 62% 100%)',
            }}
          >
            <div className="h-14 w-14 rounded-full bg-obsidian grid place-items-center font-display font-bold">
              62%
            </div>
          </div>
          <div className="text-sm leading-relaxed">
            <div className="font-semibold">Monthly budget</div>
            <div className="text-muted">₹12,450 of ₹20,000</div>
            <div className="text-mint">₹7,550 left</div>
          </div>
        </div>

        {/* mini bars */}
        <div className="mt-5 flex items-end gap-1.5 h-14">
          {[34, 58, 26, 72, 44, 90, 52, 66, 38, 80].map((h, i) => (
            <div
              key={i}
              className="flex-1 rounded-t bg-gradient-to-t from-teal to-mint"
              style={{ height: `${h}%` }}
            />
          ))}
        </div>
      </motion.div>

      {/* floating chips */}
      <motion.div
        animate={{ y: [0, -12, 0] }}
        transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
        className="absolute z-20 left-2 top-10 glass rounded-2xl px-3 py-2 text-xs glow-ring"
      >
        <div className="flex items-center gap-1.5 text-mint font-semibold">
          <Lock size={12} /> Encrypted
        </div>
      </motion.div>

      <motion.div
        animate={{ y: [0, 12, 0] }}
        transition={{ duration: 6.5, repeat: Infinity, ease: 'easeInOut' }}
        className="absolute z-20 right-1 bottom-12 glass rounded-2xl px-3 py-2 text-xs glow-ring"
      >
        <div className="flex items-center gap-1.5 text-mint font-semibold">
          <TrendingUp size={12} /> +28% saved
        </div>
      </motion.div>

      <motion.div
        animate={{ y: [0, -9, 0] }}
        transition={{ duration: 5.5, repeat: Infinity, ease: 'easeInOut', delay: 0.5 }}
        className="absolute z-20 right-6 top-4 glass rounded-full h-10 w-10 grid place-items-center glow-ring"
      >
        <Sparkle size={16} className="text-mint" />
      </motion.div>
    </div>
  );
}
