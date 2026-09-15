import { ShieldCheck } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="border-t border-mint/10 py-12">
      <div className="mx-auto max-w-7xl px-5 flex flex-col sm:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-2">
          <span className="grid place-items-center h-8 w-8 rounded-lg bg-teal/20 border border-mint/30">
            <ShieldCheck size={15} className="text-mint" />
          </span>
          <span className="font-display text-lg font-semibold">AERIS</span>
          <span className="text-muted text-sm ml-2">Money that reads itself.</span>
        </div>
        <div className="flex items-center gap-6 text-sm text-muted">
          <a href="#features" className="hover:text-ink transition-colors">Features</a>
          <a href="#security" className="hover:text-ink transition-colors">Security</a>
          <a href="#aeris" className="hover:text-ink transition-colors">Aeris</a>
          <span className="text-muted/50">© {new Date().getFullYear()}</span>
        </div>
      </div>
    </footer>
  );
}
