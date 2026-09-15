import { motion } from 'framer-motion';
import { ShieldCheck } from 'lucide-react';

const links = [
  ['Features', '#features'],
  ['How it works', '#how'],
  ['Security', '#security'],
  ['Aeris', '#aeris'],
];

export default function Nav() {
  return (
    <motion.header
      initial={{ y: -40, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      className="fixed top-0 inset-x-0 z-50"
    >
      <div className="mx-auto max-w-7xl px-5 mt-4">
        <div className="glass rounded-2xl px-5 py-3 flex items-center justify-between">
          <a href="#" className="flex items-center gap-2">
            <span className="grid place-items-center h-9 w-9 rounded-xl bg-teal/20 border border-mint/30">
              <ShieldCheck size={18} className="text-mint" />
            </span>
            <span className="font-display text-xl font-semibold tracking-tight">
              AERIS
            </span>
          </a>
          <nav className="hidden md:flex items-center gap-8 text-sm text-muted">
            {links.map(([label, href]) => (
              <a
                key={href}
                href={href}
                className="hover:text-ink transition-colors"
              >
                {label}
              </a>
            ))}
          </nav>
          <a
            href="#cta"
            className="rounded-xl bg-mint text-[#042521] font-semibold text-sm px-4 py-2 hover:shadow-[0_0_24px_rgba(94,234,212,0.5)] transition-shadow"
          >
            Get the app
          </a>
        </div>
      </div>
    </motion.header>
  );
}
