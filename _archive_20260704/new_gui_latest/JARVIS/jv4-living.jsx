// ─── JARVIS v4 — Living Intelligence Panel ──────────────────────────────────
// Replaces the empty space below the reactor with a state-aware "living" panel.
// IDLE → Proactive greeting + actions
// LISTENING → Voice waveform + transcript
// PROCESSING → AI thought stream (live thinking steps)
// SPEAKING → Output waveform + streaming indicator

const { J, ca } = window;

// ─── TIME-AWARE HELPERS ─────────────────────────────────────────────────────
function getTimePeriod() {
  const h = new Date().getHours();
  if (h < 5)  return { label: 'LATE NIGHT',     greeting: 'Still up late' };
  if (h < 12) return { label: 'GOOD MORNING',   greeting: 'Morning' };
  if (h < 17) return { label: 'GOOD AFTERNOON', greeting: 'Afternoon' };
  if (h < 21) return { label: 'GOOD EVENING',   greeting: 'Evening' };
  return { label: 'GOOD NIGHT', greeting: 'Late evening' };
}

// Mock memory context — would come from real desktop awareness in PyQt
const MEMORY_CONTEXT = {
  activeTask:  'SehatUP redesign',
  recentApps:  ['VS Code', 'Figma', 'Spotify'],
  focusTime:   '3h 42m',
  lastSession: 'React component refactor · 14:08',
};

const ACTION_CHIPS = [
  { label: 'Resume coding',   cmd: 'Resume my last coding session', icon: 'code' },
  { label: 'Today\'s summary', cmd: 'Summarize what I did today',   icon: 'log'  },
  { label: 'Open workspace',  cmd: 'Open my dev workspace',         icon: 'grid' },
  { label: 'Quick break',     cmd: 'Suggest a 5 minute break',      icon: 'pause' },
];

const CHIP_ICONS = {
  code:  <><path d="M5 4L2 7l3 3M9 4l3 3-3 3" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
  log:   <><path d="M3 3h8M3 7h8M3 11h5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/></>,
  grid:  <><rect x="2" y="2" width="4" height="4" rx="0.5" stroke="currentColor" strokeWidth="1.3" fill="none"/><rect x="8" y="2" width="4" height="4" rx="0.5" stroke="currentColor" strokeWidth="1.3" fill="none"/><rect x="2" y="8" width="4" height="4" rx="0.5" stroke="currentColor" strokeWidth="1.3" fill="none"/><rect x="8" y="8" width="4" height="4" rx="0.5" stroke="currentColor" strokeWidth="1.3" fill="none"/></>,
  pause: <><rect x="3" y="3" width="3" height="8" rx="0.5" stroke="currentColor" strokeWidth="1.3" fill="none"/><rect x="8" y="3" width="3" height="8" rx="0.5" stroke="currentColor" strokeWidth="1.3" fill="none"/></>,
};

function ActionChip({ chip, onClick }) {
  const [hov, setHov] = React.useState(false);
  return (
    <button
      onClick={() => onClick(chip.cmd)}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display:'flex', alignItems:'center', gap:7,
        padding:'7px 13px', borderRadius:8, cursor:'pointer',
        background: hov ? 'rgba(0,212,255,0.1)' : 'rgba(255,255,255,0.025)',
        border:`1px solid ${hov ? 'rgba(0,212,255,0.4)' : 'rgba(255,255,255,0.08)'}`,
        color: hov ? J.cyan : J.textSec,
        fontSize:11, fontWeight:500, fontFamily:'Inter,sans-serif',
        transition:'all 0.2s ease',
        transform: hov ? 'translateY(-1px)' : 'none',
        boxShadow: hov ? '0 4px 12px rgba(0,212,255,0.12)' : 'none',
      }}
    >
      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">{CHIP_ICONS[chip.icon]}</svg>
      <span>{chip.label}</span>
    </button>
  );
}

// ─── PROACTIVE GREETING ─────────────────────────────────────────────────────
function ProactiveGreeting({ time, onAction }) {
  const period = getTimePeriod();
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
      {/* Header row */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'baseline' }}>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
          letterSpacing:'2.5px', color:ca(J.cyan,0.85) }}>
          {period.label}
        </span>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut, letterSpacing:'0.5px' }}>
          {time}
        </span>
      </div>

      {/* Greeting body */}
      <div>
        <div style={{ fontSize:20, fontWeight:600, color:J.textPri, letterSpacing:'-0.2px', lineHeight:1.3 }}>
          {period.greeting}, Shivang.
        </div>
        <div style={{ fontSize:13, color:J.textSec, marginTop:5, lineHeight:1.55, letterSpacing:'0.1px' }}>
          You've been in flow for <span style={{ color:J.cyan, fontWeight:600 }}>{MEMORY_CONTEXT.focusTime}</span> today.
          {' '}<span style={{ color:J.textPri }}>{MEMORY_CONTEXT.activeTask}</span> awaits your touch.
        </div>
      </div>

      {/* Action chips */}
      <div style={{ display:'flex', gap:7, flexWrap:'wrap' }}>
        {ACTION_CHIPS.map(chip => (
          <ActionChip key={chip.label} chip={chip} onClick={onAction} />
        ))}
      </div>
    </div>
  );
}

// ─── THOUGHT STREAM (Processing state) ──────────────────────────────────────
const THOUGHT_STEPS = [
  { text:'Parsing input',              icon:'parse' },
  { text:'Identifying intent',         icon:'intent' },
  { text:'Checking automation layer',  icon:'auto' },
  { text:'Querying knowledge base',    icon:'know' },
  { text:'Generating response',        icon:'gen' },
];

function ThoughtStream({ input, elapsed }) {
  const [step, setStep] = React.useState(0);
  const [timings, setTimings] = React.useState({});

  React.useEffect(() => {
    setStep(0);
    setTimings({});
    let cur = 0;
    const start = Date.now();
    const iv = setInterval(() => {
      cur++;
      setTimings(prev => ({ ...prev, [cur-1]: Date.now() - start }));
      if (cur >= THOUGHT_STEPS.length - 1) {
        // Stay on last step (don't auto-complete — let API response trigger transition)
        clearInterval(iv);
      }
      setStep(cur);
    }, 420);
    return () => clearInterval(iv);
  }, []);

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
      {/* Header */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <div style={{ width:8, height:8, borderRadius:'50%', background:J.magenta,
            boxShadow:`0 0 8px ${J.magenta}`, animation:'j-blink 0.7s ease-in-out infinite' }} />
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
            letterSpacing:'2.5px', color:J.magenta }}>THINKING</span>
        </div>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut }}>
          {elapsed ? `${elapsed}s elapsed` : 'live'}
        </span>
      </div>

      {/* Input echo */}
      {input && (
        <div style={{ padding:'8px 12px', borderRadius:8,
          background:ca(J.magenta,0.06), border:`1px solid ${ca(J.magenta,0.18)}` }}>
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:J.textMut }}>INPUT</span>
          <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:12, color:J.textPri, marginTop:2,
            overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
            "{input}"
          </div>
        </div>
      )}

      {/* Steps */}
      <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
        {THOUGHT_STEPS.map((s, i) => {
          const isDone    = i < step;
          const isActive  = i === step;
          const isPending = i > step;
          const color = isDone ? J.green : isActive ? J.cyan : J.textMut;
          return (
            <div key={i} style={{
              display:'flex', alignItems:'center', gap:10,
              opacity: isPending ? 0.4 : 1, transition:'opacity 0.3s',
              animation: isActive ? 'j-fadein 0.3s ease' : 'none',
            }}>
              {/* Status icon */}
              <div style={{ width:14, height:14, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                {isDone && (
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <path d="M3 6l2 2 4-4" stroke={J.green} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                )}
                {isActive && (
                  <div style={{ width:10, height:10, borderRadius:'50%',
                    border:`1.5px solid ${ca(J.cyan,0.3)}`,
                    borderTopColor: J.cyan,
                    animation:'j-spin 0.7s linear infinite' }} />
                )}
                {isPending && (
                  <div style={{ width:6, height:6, borderRadius:'50%',
                    border:`1px solid ${J.textMut}`, opacity:0.5 }} />
                )}
              </div>
              {/* Step text */}
              <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:11.5,
                color, letterSpacing:'0.2px', flex:1 }}>
                {s.text}{isActive ? '…' : ''}
              </span>
              {/* Timing */}
              {isDone && timings[i] !== undefined && (
                <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut }}>
                  {timings[i]}ms
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── LISTENING PANEL ────────────────────────────────────────────────────────
function ListeningPanel({ transcript }) {
  // Static-ish bar heights, animated by CSS
  const bars = React.useMemo(() =>
    Array.from({ length: 32 }, (_, i) => 8 + Math.abs(Math.sin(i * 0.8)) * 22)
  , []);

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <div style={{ width:8, height:8, borderRadius:'50%', background:J.green,
            boxShadow:`0 0 8px ${J.green}`, animation:'j-blink 1.2s ease-in-out infinite' }} />
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
            letterSpacing:'2.5px', color:J.green }}>LISTENING</span>
        </div>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut }}>en-IN · 96% clarity</span>
      </div>

      {/* Big waveform */}
      <div style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:3, height:44 }}>
        {bars.map((h, i) => (
          <div key={i} style={{
            width:3, borderRadius:1.5,
            background:`linear-gradient(180deg,${J.green},${ca(J.green,0.4)})`,
            height: `${h}px`,
            animation:`j-wave ${0.55 + (i%7)*0.08}s ease-in-out ${(i%5)*0.07}s infinite`,
            transformOrigin:'center',
            opacity:0.85,
          }} />
        ))}
      </div>

      {/* Transcript */}
      <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:12, color:J.textPri,
        textAlign:'center', minHeight:18 }}>
        {transcript ? `"${transcript}"` : <span style={{ color:J.textMut }}>Awaiting voice input…</span>}
      </div>
    </div>
  );
}

// ─── SPEAKING PANEL ─────────────────────────────────────────────────────────
function SpeakingPanel() {
  const bars = Array.from({ length: 28 });
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <div style={{ width:8, height:8, borderRadius:'50%', background:J.purple,
            boxShadow:`0 0 8px ${J.purple}`, animation:'j-blink 1.2s ease-in-out infinite' }} />
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
            letterSpacing:'2.5px', color:J.purple }}>RESPONDING</span>
        </div>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut }}>TTS stream active</span>
      </div>

      {/* Output waveform */}
      <div style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:3, height:44 }}>
        {bars.map((_, i) => (
          <div key={i} style={{
            width:3, borderRadius:1.5,
            background:`linear-gradient(180deg,${J.purple},${ca(J.purple,0.3)})`,
            height: `${10 + Math.sin(i * 0.7) * 14}px`,
            animation:`j-wave ${0.45 + (i%6)*0.09}s ease-in-out ${(i%4)*0.08}s infinite`,
            transformOrigin:'center',
            opacity:0.8,
          }} />
        ))}
      </div>

      <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:12, color:J.textSec, textAlign:'center' }}>
        Streaming response to terminal…
      </div>
    </div>
  );
}

// ─── MAIN LIVING PANEL ──────────────────────────────────────────────────────
function LivingIntelligencePanel({ aiState, time, lastInput, transcript, onAction }) {
  let content;
  if (aiState === 'IDLE')            content = <ProactiveGreeting time={time} onAction={onAction} />;
  else if (aiState === 'LISTENING')  content = <ListeningPanel transcript={transcript} />;
  else if (aiState === 'PROCESSING') content = <ThoughtStream input={lastInput} />;
  else if (aiState === 'SPEAKING')   content = <SpeakingPanel />;

  return (
    <div style={{
      width:540, padding:'18px 22px',
      borderRadius:14,
      background:'rgba(13,21,37,0.7)',
      backdropFilter:'blur(20px)',
      border:`1px solid rgba(30,41,59,0.7)`,
      boxShadow:'0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04)',
      transition:'all 0.3s ease',
      position:'relative',
      overflow:'hidden',
    }}>
      {/* Subtle accent stripe */}
      <div style={{ position:'absolute', left:0, top:18, bottom:18, width:2,
        background: aiState==='IDLE' ? ca(J.cyan,0.5)
                  : aiState==='LISTENING' ? ca(J.green,0.6)
                  : aiState==='PROCESSING' ? ca(J.magenta,0.6)
                  : ca(J.purple,0.6),
        borderRadius:'0 2px 2px 0',
        transition:'background 0.4s ease',
      }} />
      {content}
    </div>
  );
}

// ─── MEMORY CHIPS (compact context strip) ───────────────────────────────────
function MemoryChips() {
  const items = [
    { icon:'•', label:`Active: ${MEMORY_CONTEXT.activeTask}`,  color: J.cyan   },
    { icon:'·', label:`Recent: ${MEMORY_CONTEXT.recentApps.join(' · ')}`, color: J.textSec },
    { icon:'⏱', label:`Focus ${MEMORY_CONTEXT.focusTime}`,      color: J.purple },
  ];
  return (
    <div style={{ display:'flex', gap:8, alignItems:'center', justifyContent:'center' }}>
      {items.map((it, i) => (
        <React.Fragment key={i}>
          <div style={{ display:'inline-flex', alignItems:'center', gap:6,
            fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:J.textMut, letterSpacing:'0.3px' }}>
            <span style={{ color:it.color, fontSize:8 }}>{it.icon}</span>
            <span>{it.label}</span>
          </div>
          {i < items.length - 1 && (
            <div style={{ width:3, height:3, borderRadius:'50%', background:'rgba(255,255,255,0.12)' }} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

// ─── ENHANCED CONTEXT BAR (top bar, more dense) ──────────────────────────────
function EnhancedContextBar({ time, state }) {
  const s = window.JSTATES[state] || window.JSTATES.IDLE;

  return (
    <div style={{ height:40, background:'rgba(8,12,22,0.96)', backdropFilter:'blur(18px)',
      borderBottom:`1px solid rgba(30,41,59,0.7)`,
      display:'flex', alignItems:'center', padding:'0 16px',
      justifyContent:'space-between', flexShrink:0, zIndex:60, position:'relative',
      fontFamily:"'JetBrains Mono',monospace", fontSize:10,
    }}>
      {/* Left — brand + breadcrumb */}
      <div style={{ display:'flex', alignItems:'center', gap:10 }}>
        <div style={{ width:8, height:8, borderRadius:'50%', background:J.cyan, boxShadow:`0 0 8px ${J.cyan}` }} />
        <span style={{ fontSize:12, fontWeight:700, letterSpacing:'2px', color:J.textPri }}>A.E.R.I.S</span>
        <span style={{ color:J.textMut, letterSpacing:'0.4px' }}>v3.2</span>
        <div style={{ width:1, height:14, background:'rgba(30,41,59,0.8)', margin:'0 4px' }} />
        <span style={{ color:J.textSec, letterSpacing:'0.3px' }}>Shivang's Machine</span>
      </div>

      {/* Center — system telemetry */}
      <div style={{ display:'flex', alignItems:'center', gap:14, position:'absolute', left:'50%', transform:'translateX(-50%)' }}>
        <SystemPill label="MODEL"  value="Haiku 4.5"  color={J.cyan}   pulse />
        <Divider />
        <SystemPill label="GPU"    value="18%"        color={J.purple} />
        <Divider />
        <SystemPill label="MEM"    value="4.2/16G"    color={J.cyan}   />
        <Divider />
        <SystemPill label="NET"    value="↓1.4 ↑0.3"  color={J.green}  />
        <Divider />
        <SystemPill label="WAKE"   value="ARMED"      color={J.amber}  pulse />
      </div>

      {/* Right — state + time */}
      <div style={{ display:'flex', alignItems:'center', gap:12 }}>
        <div style={{
          padding:'3px 10px 3px 8px', borderRadius:10,
          background: ca(s.col,0.1), border:`1px solid ${ca(s.col,0.4)}`,
          display:'flex', alignItems:'center', gap:6,
          transition:'all 0.5s',
        }}>
          <div style={{ width:5, height:5, borderRadius:'50%', background:s.col,
            boxShadow:`0 0 4px ${s.col}`, animation:'j-blink 1.5s infinite' }} />
          <span style={{ fontSize:9, fontWeight:700, letterSpacing:'1.5px', color:s.col, transition:'color 0.5s' }}>
            {state === 'IDLE' ? 'STANDBY' : s.label}
          </span>
        </div>
        <span style={{ fontSize:11, fontWeight:700, color:J.textSec, letterSpacing:'1px' }}>{time}</span>
      </div>
    </div>
  );
}

function SystemPill({ label, value, color, pulse }) {
  return (
    <div style={{ display:'flex', alignItems:'center', gap:5 }}>
      <div style={{ width:4, height:4, borderRadius:'50%', background:color,
        boxShadow:`0 0 4px ${color}`,
        animation: pulse ? 'j-blink 2s ease-in-out infinite' : 'none' }} />
      <span style={{ fontSize:9, fontWeight:700, letterSpacing:'1.2px', color:J.textMut }}>{label}</span>
      <span style={{ fontSize:10, fontWeight:600, color:J.textSec, marginLeft:2 }}>{value}</span>
    </div>
  );
}

function Divider() {
  return <div style={{ width:1, height:10, background:'rgba(255,255,255,0.06)' }} />;
}

Object.assign(window, {
  LivingIntelligencePanel,
  MemoryChips,
  EnhancedContextBar,
  ACTION_CHIPS,
  MEMORY_CONTEXT,
  getTimePeriod,
});
