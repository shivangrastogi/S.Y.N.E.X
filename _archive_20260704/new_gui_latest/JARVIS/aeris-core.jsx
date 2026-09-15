// ─── A.E.R.I.S CORE — constants, hooks, shared primitives ────────────────────

const AERIS_COLORS = {
  bg:      'rgb(10,15,28)',
  panel:   'rgb(15,23,42)',
  card:    'rgb(13,21,37)',
  border:  'rgb(30,41,59)',
  cyan:    'rgb(0,212,255)',
  green:   'rgb(16,185,129)',
  red:     'rgb(248,113,113)',
  purple:  'rgb(168,85,247)',
  amber:   'rgb(251,191,36)',
  textPri: 'rgb(234,234,234)',
  textSec: 'rgb(148,163,184)',
  textMut: 'rgb(100,116,139)',
};

const AERIS_STATES = {
  IDLE:       { label: 'IDLE',       color: AERIS_COLORS.cyan,   ring: { r1:'14s', r2:'10s', r3:'7s' },  pulse:'4s',   glowOp:0.35 },
  LISTENING:  { label: 'LISTENING',  color: AERIS_COLORS.green,  ring: { r1:'9s',  r2:'6s',  r3:'4s' },  pulse:'1.5s', glowOp:0.7  },
  PROCESSING: { label: 'PROCESSING', color: AERIS_COLORS.cyan,   ring: { r1:'3s',  r2:'2s',  r3:'1.2s'},  pulse:'0.8s', glowOp:0.55 },
  SPEAKING:   { label: 'SPEAKING',   color: AERIS_COLORS.purple, ring: { r1:'6s',  r2:'4s',  r3:'2.5s'}, pulse:'2s',   glowOp:0.5  },
  ERROR:      { label: 'ERROR',      color: AERIS_COLORS.red,    ring: { r1:'8s',  r2:'5s',  r3:'3s' },  pulse:'0.5s', glowOp:0.6  },
};

const AERIS_SYSTEM_PROMPT = `You are A.E.R.I.S — Adaptive Execution & Response Intelligence System, v3.1. You are a desktop AI assistant. Rules:
- Respond concisely in 1-2 sentences maximum.
- Speak in a calm, precise, slightly formal tone. Occasional Hinglish (Hindi-English mix) is welcome.
- After EVERY response, on a new line, add a metadata tag exactly like this (valid JSON): [AERIS_META:{"intent":"detected_intent","confidence":99.2,"action":"action_taken","latency_ms":180}]
- intent: short snake_case string like open_app, weather_query, schedule_meeting, general_query, system_check, knowledge_query
- confidence: float 85-99.9
- action: one of executed, slot_filling, knowledge_retrieved, clarification_needed
- latency_ms: integer 80-400
- Never explain the metadata. Never skip it.`;

// ─── HOOKS ────────────────────────────────────────────────────────────────────

function useClock() {
  const [time, setTime] = React.useState(new Date());
  React.useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return time.toTimeString().slice(0, 8);
}

function useStreamingText() {
  const [displayed, setDisplayed] = React.useState('');
  const [streaming, setStreaming]  = React.useState(false);
  const [done, setDone]            = React.useState(true);
  const timerRef = React.useRef(null);

  const stream = React.useCallback((text, speed = 18) => {
    if (timerRef.current) clearInterval(timerRef.current);
    setDisplayed('');
    setDone(false);
    setStreaming(true);
    let i = 0;
    timerRef.current = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(timerRef.current);
        setStreaming(false);
        setDone(true);
      }
    }, speed);
  }, []);

  const cancel = React.useCallback(() => {
    if (timerRef.current) clearInterval(timerRef.current);
    setStreaming(false);
    setDone(true);
  }, []);

  React.useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);
  return { displayed, streaming, done, stream, cancel };
}

function useAerisAPI() {
  const [loading, setLoading] = React.useState(false);
  const [error, setError]     = React.useState(null);

  const ask = React.useCallback(async (userText, history = []) => {
    setLoading(true);
    setError(null);
    try {
      const messages = [
        ...history.slice(-8).map(m => ({ role: m.role === 'aeris' ? 'assistant' : 'user', content: m.rawText || m.text })),
        { role: 'user', content: userText },
      ];
      const raw = await window.claude.complete({
        system: AERIS_SYSTEM_PROMPT,
        messages,
      });
      // Parse metadata from response
      const metaMatch = raw.match(/\[AERIS_META:(\{.*?\})\]/);
      let meta = { intent: 'general_query', confidence: 95.0, action: 'executed', latency_ms: 200 };
      if (metaMatch) {
        try { meta = JSON.parse(metaMatch[1]); } catch(e) {}
      }
      const text = raw.replace(/\[AERIS_META:.*?\]/g, '').trim();
      return { text, meta };
    } catch (err) {
      setError(err.message);
      return { text: 'System error. Reconnecting to semantic core...', meta: { intent: 'sys_error', confidence: 0, action: 'error', latency_ms: 0 } };
    } finally {
      setLoading(false);
    }
  }, []);

  return { ask, loading, error };
}

// ─── SHARED PRIMITIVES ────────────────────────────────────────────────────────

function Pill({ text, color, dot = true, blink = false }) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '3px 10px 3px 8px', borderRadius: 8,
      background: color.replace('rgb','rgba').replace(')',',0.1)'),
      border: `1px solid ${color.replace('rgb','rgba').replace(')',',0.35)')}`,
    }}>
      {dot && <div style={{
        width: 5, height: 5, borderRadius: '50%', background: color,
        boxShadow: `0 0 4px ${color}`,
        animation: blink ? 'aeris-blink 1.2s ease-in-out infinite' : 'none',
      }} />}
      <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 9, fontWeight: 700, letterSpacing: '0.8px', color }}>{text}</span>
    </div>
  );
}

function MonoText({ children, size = 12, color, weight = 400, spacing = 0, style = {} }) {
  return (
    <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: size, fontWeight: weight, color: color || AERIS_COLORS.textPri, letterSpacing: `${spacing}px`, ...style }}>
      {children}
    </span>
  );
}

// Export to window so other scripts can use them
Object.assign(window, {
  AERIS_COLORS,
  AERIS_STATES,
  AERIS_SYSTEM_PROMPT,
  useClock,
  useStreamingText,
  useAerisAPI,
  Pill,
  MonoText,
});
