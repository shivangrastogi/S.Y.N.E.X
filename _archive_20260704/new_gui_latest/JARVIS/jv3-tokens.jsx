// ─── JARVIS v3 — Design Tokens, AI States, Shared Hooks + Primitives ─────────

const J = {
  bg:      '#0A0F1C',
  bgEle:   '#0F172A',
  panel:   'rgb(13,21,37)',
  border:  'rgb(30,41,59)',
  cyan:    'rgb(0,212,255)',
  magenta: 'rgb(255,45,149)',
  purple:  'rgb(168,85,247)',
  green:   'rgb(16,185,129)',
  amber:   'rgb(251,191,36)',
  red:     'rgb(248,113,113)',
  textPri: 'rgb(234,234,234)',
  textSec: 'rgb(148,163,184)',
  textMut: 'rgb(100,116,139)',
};

const ca = (col, a) => col.replace('rgb(','rgba(').replace(')',`,${a})`);

const JSTATES = {
  IDLE:       { label:'IDLE',       col: J.cyan,    ring:{ r1:'13s',r2:'9s',r3:'6s'  }, pulse:'4s',   glowOp:0.32 },
  LISTENING:  { label:'LISTENING',  col: J.green,   ring:{ r1:'8s', r2:'5s',r3:'3.5s'}, pulse:'1.4s', glowOp:0.7  },
  PROCESSING: { label:'PROCESSING', col: J.magenta, ring:{ r1:'2s', r2:'1.4s',r3:'0.9s'}, pulse:'0.7s', glowOp:0.6 },
  SPEAKING:   { label:'SPEAKING',   col: J.purple,  ring:{ r1:'5s', r2:'3.5s',r3:'2.2s'}, pulse:'1.8s', glowOp:0.5 },
};

const JARVIS_PROMPT = `You are A.E.R.I.S (Adaptive Execution & Response Intelligence System), a next-gen desktop AI assistant — JARVIS v3.0. You are sleek, smart, fast. Rules:
- Max 2 sentences per response. Be direct, clever, confident.
- Mix English with Hinglish naturally when it fits. (e.g. "Karo na, boss")
- Personality: calm genius, slight wit, no fluff.
- After EVERY reply, add on a NEW line exactly: [META:{"intent":"snake_case_intent","conf":98.2,"act":"executed","ms":150}]
  - intent: open_app / weather_query / schedule / music / system_check / knowledge / general / joke / greet
  - conf: float 88-99.9
  - act: executed | slot_filling | knowledge | clarifying
  - ms: int 90-380
- NEVER skip the META tag. NEVER explain it.`;

// ─── HOOKS ───────────────────────────────────────────────────────────────────

function useClock() {
  const [t, setT] = React.useState(new Date());
  React.useEffect(() => { const id = setInterval(() => setT(new Date()), 1000); return () => clearInterval(id); }, []);
  return t.toTimeString().slice(0,8);
}

function useStreamText() {
  const [text, setText]       = React.useState('');
  const [active, setActive]   = React.useState(false);
  const [done, setDone]       = React.useState(true);
  const ref = React.useRef(null);

  const stream = React.useCallback((full, speed = 16) => {
    if (ref.current) clearInterval(ref.current);
    setText(''); setDone(false); setActive(true);
    let i = 0;
    ref.current = setInterval(() => {
      i++;
      setText(full.slice(0, i));
      if (i >= full.length) { clearInterval(ref.current); setActive(false); setDone(true); }
    }, speed);
  }, []);

  React.useEffect(() => () => { if (ref.current) clearInterval(ref.current); }, []);
  return { text, active, done, stream };
}

function useJarvisAPI() {
  const [busy, setBusy] = React.useState(false);
  const call = React.useCallback(async (userMsg, history = []) => {
    setBusy(true);
    try {
      const msgs = [
        ...history.slice(-8).map(m => ({ role: m.role === 'ai' ? 'assistant' : 'user', content: m.raw || m.text })),
        { role: 'user', content: userMsg },
      ];
      const raw = await window.claude.complete({ system: JARVIS_PROMPT, messages: msgs });
      const metaM = raw.match(/\[META:(\{.*?\})\]/);
      let meta = { intent:'general', conf:95, act:'executed', ms:200 };
      if (metaM) { try { meta = JSON.parse(metaM[1]); } catch(e){} }
      const text = raw.replace(/\[META:.*?\]/g,'').trim();
      return { text, meta };
    } catch(e) {
      return { text:'Neural core hiccup. Ek second...', meta:{ intent:'err', conf:0, act:'executed', ms:0 } };
    } finally { setBusy(false); }
  }, []);
  return { call, busy };
}

// ─── SHARED ATOMS ─────────────────────────────────────────────────────────────

function JTag({ text, color, pulse = false }) {
  return (
    <div style={{ display:'inline-flex', alignItems:'center', gap:5,
      padding:'2px 8px 2px 6px', borderRadius:6,
      background: ca(color, 0.1), border:`1px solid ${ca(color, 0.3)}`,
    }}>
      <div style={{ width:5, height:5, borderRadius:'50%', background:color, boxShadow:`0 0 5px ${color}`,
        animation: pulse ? 'j-blink 1.2s ease-in-out infinite' : 'none' }} />
      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700, letterSpacing:'0.8px', color }}>{text}</span>
    </div>
  );
}

function JLabel({ children, color, spacing = 1.8 }) {
  return (
    <span style={{ fontFamily:'Inter,sans-serif', fontSize:9, fontWeight:700,
      letterSpacing:`${spacing}px`, color: color || J.textMut, textTransform:'uppercase' }}>
      {children}
    </span>
  );
}

Object.assign(window, { J, ca, JSTATES, JARVIS_PROMPT, useClock, useStreamText, useJarvisAPI, JTag, JLabel });
