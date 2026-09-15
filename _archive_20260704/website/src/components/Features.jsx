import { motion } from 'framer-motion';
import {
  MessageSquareText,
  ShieldCheck,
  Sparkles,
  PieChart,
  Target,
  Bot,
} from 'lucide-react';

const features = [
  {
    icon: MessageSquareText,
    title: 'Reads your SMS',
    body: 'Bank & UPI alerts become clean transactions automatically — even when the app is closed. Zero manual entry.',
    span: 'lg:col-span-2',
  },
  {
    icon: ShieldCheck,
    title: 'End-to-end encrypted',
    body: 'Amounts, merchants and SMS are AES-256 encrypted on-device. Not even we can read them.',
  },
  {
    icon: Sparkles,
    title: 'AI insights & forecasts',
    body: 'Burn-rate forecasts, anomaly flags and recurring-payment detection — all computed privately on your phone.',
  },
  {
    icon: PieChart,
    title: 'Charts that move',
    body: 'Interactive donut, zoom-and-pan trend, daily bars and more — your money, finally legible.',
    span: 'lg:col-span-2',
  },
  {
    icon: Target,
    title: 'Goals & streaks',
    body: 'Save toward something, build a daily streak, earn badges — with confetti when you win.',
  },
  {
    icon: Bot,
    title: 'Meet Aeris',
    body: 'A finance buddy that reacts to your spending and answers questions about your money on-device.',
  },
];

const ease = [0.16, 1, 0.3, 1];

export default function Features() {
  return (
    <section id="features" className="py-28">
      <div className="mx-auto max-w-7xl px-5">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-80px' }}
          transition={{ duration: 0.7, ease }}
          className="max-w-2xl"
        >
          <p className="text-mint text-sm font-semibold tracking-widest uppercase">
            Everything, handled
          </p>
          <h2 className="font-display text-4xl sm:text-5xl font-semibold mt-3">
            A finance app that does the boring part for you.
          </h2>
        </motion.div>

        <div className="mt-14 grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {features.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.6, ease, delay: (i % 3) * 0.08 }}
              whileHover={{ y: -6 }}
              className={`glass rounded-3xl p-7 ${f.span ?? ''}`}
            >
              <span className="grid place-items-center h-12 w-12 rounded-2xl bg-teal/15 border border-mint/25 mb-5">
                <f.icon size={22} className="text-mint" />
              </span>
              <h3 className="font-display text-2xl font-semibold mb-2">
                {f.title}
              </h3>
              <p className="text-muted leading-relaxed">{f.body}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
