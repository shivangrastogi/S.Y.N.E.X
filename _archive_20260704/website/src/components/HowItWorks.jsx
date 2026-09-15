import { motion } from 'framer-motion';

const steps = [
  {
    n: '01',
    title: 'Grant SMS once',
    body: 'AERIS reads only bank/UPI alerts — opt-in, on-device. Spam and OTPs are filtered out.',
  },
  {
    n: '02',
    title: 'It builds your ledger',
    body: 'Each alert is parsed, categorised, encrypted and saved. Wrong category? Fix it once — it learns.',
  },
  {
    n: '03',
    title: 'You get clarity',
    body: 'Charts, forecasts, budgets and Aeris’ nudges turn raw spending into decisions.',
  },
];

const ease = [0.16, 1, 0.3, 1];

export default function HowItWorks() {
  return (
    <section id="how" className="py-28">
      <div className="mx-auto max-w-7xl px-5">
        <motion.h2
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7, ease }}
          className="font-display text-4xl sm:text-5xl font-semibold max-w-xl"
        >
          From a buzzing SMS to a smarter you — in three quiet steps.
        </motion.h2>

        <div className="mt-16 grid md:grid-cols-3 gap-6">
          {steps.map((s, i) => (
            <motion.div
              key={s.n}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-60px' }}
              transition={{ duration: 0.6, ease, delay: i * 0.12 }}
              className="relative"
            >
              <div className="font-display text-7xl font-semibold text-mint/15">
                {s.n}
              </div>
              <h3 className="font-display text-2xl font-semibold -mt-6 mb-3">
                {s.title}
              </h3>
              <p className="text-muted leading-relaxed">{s.body}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
