// ─── JARVIS v5 — Main App with Page Router + Window Controls ────────────────

const BOOT_MSGS_V5 = [
  { id:1, role:'ai',
    text:'Hey Shivang. JARVIS v3.2 online — neural core synced, all 4 nodes wired. Ready when you are.',
    time:'--:--',
    meta:{ intent:'sys_boot', conf:99.9, act:'executed', ms:100 },
    raw:'Hey Shivang. JARVIS online.' },
];

const BOOT_LOGS_V5 = [
  { id:1, type:'SYS', text:'Neural core online · wiring grid initialized',     time:'--:--:--', highlight:false },
  { id:2, type:'NLU', text:'301 intent patterns loaded · 21 intent classes',   time:'--:--:--', highlight:true  },
  { id:3, type:'MEM', text:'Recent context restored · 4 active automations',   time:'--:--:--', highlight:false },
  { id:4, type:'SYS', text:'4/4 system nodes wired · all telemetry nominal',   time:'--:--:--', highlight:false },
  { id:5, type:'SYS', text:'JARVIS v3.2 ready · awaiting instructions',        time:'--:--:--', highlight:false },
];

let _M5 = 30, _L5 = 30;
const nM5   = () => ++_M5;
const nL5   = () => ++_L5;
const NOW5  = () => new Date().toTimeString().slice(0,5);
const NOWS5 = () => new Date().toTimeString().slice(0,8);

// ─── NEW TITLEBAR — with window controls + dense telemetry ──────────────────
function AppTitleBar({ time, state, onMinimize, onMaximize, onClose }) {
  const { J, ca } = window;
  const s = window.JSTATES[state] || window.JSTATES.IDLE;

  function Pill({ label, value, color, pulse }) {
    return (
      <div style={{ display:'flex', alignItems:'center', gap:5 }}>
        <div style={{ width:4, height:4, borderRadius:'50%', background:color,
          boxShadow:`0 0 4px ${color}`, animation: pulse ? 'j-blink 2s infinite' : 'none' }} />
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
          letterSpacing:'1.2px', color:J.textMut }}>{label}</span>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, fontWeight:600, color:J.textSec, marginLeft:2 }}>{value}</span>
      </div>
    );
  }
  function Sep() { return <div style={{ width:1, height:10, background:'rgba(255,255,255,0.06)' }} />; }

  return (
    <div style={{ height:40, background:'rgba(8,12,22,0.96)', backdropFilter:'blur(18px)',
      borderBottom:`1px solid rgba(30,41,59,0.7)`,
      display:'flex', alignItems:'center', padding:'0 16px',
      justifyContent:'space-between', flexShrink:0, zIndex:60, position:'relative',
      fontFamily:"'JetBrains Mono',monospace", fontSize:10,
    }}>
      {/* Left — brand */}
      <div style={{ display:'flex', alignItems:'center', gap:10 }}>
        <div style={{ width:8, height:8, borderRadius:'50%', background:J.cyan, boxShadow:`0 0 8px ${J.cyan}` }} />
        <span style={{ fontSize:12, fontWeight:700, letterSpacing:'2px', color:J.textPri }}>A.E.R.I.S</span>
        <span style={{ color:J.textMut, letterSpacing:'0.4px' }}>v3.2</span>
        <div style={{ width:1, height:14, background:'rgba(30,41,59,0.8)', margin:'0 4px' }} />
        <span style={{ color:J.textSec, letterSpacing:'0.3px' }}>Shivang's Machine</span>
      </div>

      {/* Center — system telemetry */}
      <div style={{ display:'flex', alignItems:'center', gap:14, position:'absolute', left:'50%', transform:'translateX(-50%)' }}>
        <Pill label="MODEL"  value="Haiku 4.5"  color={J.cyan}   pulse />
        <Sep/>
        <Pill label="GPU"    value="18%"        color={J.purple} />
        <Sep/>
        <Pill label="MEM"    value="4.2/16G"    color={J.cyan}   />
        <Sep/>
        <Pill label="NET"    value="↓1.4 ↑0.3"  color={J.green}  />
        <Sep/>
        <Pill label="WAKE"   value="ARMED"      color={J.amber}  pulse />
      </div>

      {/* Right — state pill + time + window controls */}
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
        <div style={{ width:1, height:14, background:'rgba(30,41,59,0.8)' }} />
        <window.WindowControls onMinimize={onMinimize} onMaximize={onMaximize} onClose={onClose} />
      </div>
    </div>
  );
}

// ─── CHAT VIEW — the default conversation surface ───────────────────────────
function ChatView({ aiState, setAiState, lastInput, transcript, messages, streamId, streamText,
                   handleSend, handleMic, logs, logsOpen, setLogsOpen, addLog, liveVals }) {
  const { J, ca } = window;
  return (
    <>
      <div style={{ flex:1, display:'flex', flexDirection:'column', overflow:'hidden', position:'relative' }}>
        <div style={{ position:'absolute', inset:0, pointerEvents:'none',
          backgroundImage:`linear-gradient(rgba(0,212,255,0.015) 1px,transparent 1px),linear-gradient(90deg,rgba(0,212,255,0.015) 1px,transparent 1px)`,
          backgroundSize:'48px 48px' }} />
        <div style={{ position:'absolute', inset:0, pointerEvents:'none',
          background:`radial-gradient(ellipse 70% 50% at 50% 40%, rgba(0,212,255,0.04), transparent 70%)` }} />

        <div style={{ flex:1, position:'relative', overflow:'hidden' }}>
          <window.ParticleField count={14} />
          <window.WiringSystem aiState={aiState} liveVals={liveVals} />

          <div style={{ position:'absolute', left: 540 - 230, top: 390 - 230, width:460, height:460, zIndex:10 }}>
            <window.ReactorRings state={aiState} />
          </div>

          <div style={{ position:'absolute', left:'50%', top: 390 + 230 + 30,
            transform:'translateX(-50%)', zIndex:12 }}>
            <window.LivingIntelligencePanel aiState={aiState}
              time={window.useClock()} lastInput={lastInput}
              transcript={transcript} onAction={handleSend} />
          </div>

          <div style={{ position:'absolute', bottom:14, left:'50%',
            transform:'translateX(-50%)', zIndex:11 }}>
            <window.MemoryChips />
          </div>

          <div style={{ position:'absolute', bottom:14, right:18, zIndex:13, display:'flex', gap:4 }}>
            {Object.keys(window.JSTATES).map(s => {
              const sc = window.JSTATES[s].col, active = aiState === s;
              return (
                <button key={s}
                  onClick={() => { setAiState(s); addLog('SYS', `Manual → ${s}`); }}
                  style={{
                    padding:'3px 7px', borderRadius:5,
                    fontFamily:"'JetBrains Mono',monospace", fontSize:7.5, fontWeight:700, letterSpacing:'0.8px',
                    background: active ? ca(sc, 0.14) : 'rgba(255,255,255,0.03)',
                    border:`1px solid ${active ? ca(sc, 0.45) : 'rgba(255,255,255,0.06)'}`,
                    color: active ? sc : J.textMut, transition:'all 0.2s', cursor:'pointer',
                  }}>{s.slice(0,3)}</button>
              );
            })}
          </div>
        </div>

        <LogsBar logs={logs} open={logsOpen} onToggle={() => setLogsOpen(v => !v)} />
      </div>

      <window.MissionControlChatPanel
        messages={messages} streamId={streamId} streamText={streamText}
        aiState={aiState} onSend={handleSend} onMic={handleMic} />
    </>
  );
}

// ─── LOGS BAR ────────────────────────────────────────────────────────────────
function LogsBar({ logs, open, onToggle }) {
  const { J, ca } = window;
  const ref = React.useRef(null);
  const TC = { SYS:J.textMut, NLU:J.cyan, ACT:J.green, MIC:J.green, TTS:J.purple, ERR:J.red, MEM:J.amber };
  React.useEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight; }, [logs.length]);

  return (
    <div style={{
      borderTop:`1px solid rgba(30,41,59,0.6)`,
      background:'rgba(6,10,18,0.92)', backdropFilter:'blur(8px)',
      height: open ? 158 : 32, transition:'height 0.3s cubic-bezier(0.4,0,0.2,1)',
      overflow:'hidden', flexShrink:0,
    }}>
      <div onClick={onToggle} style={{
        height:32, display:'flex', alignItems:'center', justifyContent:'space-between',
        padding:'0 14px', cursor:'pointer',
        borderBottom: open ? `1px solid rgba(30,41,59,0.4)` : 'none',
      }}>
        <div style={{ display:'flex', alignItems:'center', gap:7 }}>
          <div style={{ width:4, height:4, borderRadius:'50%', background:J.green,
            opacity:0.7, animation:'j-blink 1.8s infinite' }} />
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
            letterSpacing:'1.8px', color:J.textMut }}>SYSTEM LOG</span>
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5, color:J.textMut, opacity:0.6 }}>{logs.length}</span>
        </div>
        <div style={{ display:'flex', gap:10, alignItems:'center' }}>
          {!open && logs.length > 0 && (
            <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5, color:J.textMut,
              maxWidth:400, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
              {logs[logs.length-1].text}
            </span>
          )}
          <svg width="9" height="6" viewBox="0 0 10 7" fill="none"
            style={{ transform: open ? 'rotate(180deg)' : 'none', transition:'transform 0.3s' }}>
            <path d="M1 1l4 4 4-4" stroke={J.textMut} strokeWidth="1.4" strokeLinecap="round"/>
          </svg>
        </div>
      </div>
      <div ref={ref} style={{ height:126, overflowY:'auto', padding:'4px 14px' }}>
        {logs.map((log, i) => (
          <div key={log.id} style={{ display:'flex', gap:8, padding:'2.5px 0',
            borderBottom:`1px solid rgba(30,41,59,0.15)`,
            animation: i === logs.length-1 ? 'j-fadein 0.25s ease' : 'none' }}>
            <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5, color:J.textMut, flexShrink:0 }}>{log.time}</span>
            <div style={{ padding:'0 5px', borderRadius:3, flexShrink:0,
              background: ca(TC[log.type]||J.textMut, 0.1),
              border:`1px solid ${ca(TC[log.type]||J.textMut, 0.18)}` }}>
              <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:7.5, fontWeight:700, color:TC[log.type]||J.textMut }}>{log.type}</span>
            </div>
            <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5,
              color: log.highlight ? TC[log.type]||J.cyan : J.textSec, flex:1 }}>{log.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── MAIN APP ─────────────────────────────────────────────────────────────────
function JarvisV5App() {
  const { J, ca } = window;
  const [booted, setBooted]       = React.useState(false);
  const [aiState, setAiState]     = React.useState('IDLE');
  const [messages, setMessages]   = React.useState(BOOT_MSGS_V5);
  const [logs, setLogs]           = React.useState(BOOT_LOGS_V5);
  const [logsOpen, setLogsOpen]   = React.useState(false);
  const [streamId, setStreamId]   = React.useState(null);
  const [activeNav, setActiveNav] = React.useState('chat');
  const [prevNav, setPrevNav]     = React.useState('chat');
  const [lastInput, setLastInput] = React.useState('');
  const [transcript, setTranscript] = React.useState('');
  const [minimized, setMinimized] = React.useState(false);
  const [maximized, setMaximized] = React.useState(false);

  const time = window.useClock();
  const { text:streamText, done:streamDone, stream } = window.useStreamText();
  const { call } = window.useJarvisAPI();
  const speechRef = React.useRef(null);
  const stateRef  = React.useRef('IDLE');
  stateRef.current = aiState;

  const handleNavChange = React.useCallback((key) => {
    if (key !== 'settings') setPrevNav(key);
    setActiveNav(key);
  }, []);

  // Live node values
  const [liveVals, setLiveVals] = React.useState({});
  React.useEffect(() => {
    const iv = setInterval(() => {
      setLiveVals({
        cpu: `${Math.max(4, Math.min(95, 12 + (Math.random()-0.5)*14 | 0))}%`,
        ram: `${(4.2 + (Math.random()-0.48)*0.2).toFixed(1)} GB`,
        bat: `${87 - (Math.random() > 0.95 ? 1 : 0)}%`,
        net: `${(Math.random() * 3).toFixed(1)} MB/s`,
      });
    }, 2800);
    return () => clearInterval(iv);
  }, []);

  const addLog = React.useCallback((type, text, highlight=false) => {
    setLogs(prev => [...prev, { id:nL5(), type, text, time:NOWS5(), highlight }]);
  }, []);

  const handleSend = React.useCallback(async (text) => {
    if (!text.trim()) return;
    setLastInput(text);
    // Switch back to chat view if we're on a different page when sending
    if (activeNav !== 'chat') handleNavChange('chat');
    const uid = nM5();
    setMessages(prev => [...prev, { id:uid, role:'user', text, time:NOW5(), raw:text }]);
    addLog('NLU', `Input: "${text.slice(0,48)}${text.length>48?'…':''}"`, true);
    setAiState('PROCESSING');
    addLog('NLU', 'Semantic parse + intent classification running…');
    const snap = messages.slice(-10);
    const { text:reply, meta } = await call(text, snap);
    addLog('NLU', `Intent: ${meta.intent} · ${meta.conf}% · ${meta.act}`, true);
    setAiState('SPEAKING');
    addLog('TTS', `Streaming response… ${meta.ms}ms`);
    const id = nM5();
    setMessages(prev => [...prev, { id, role:'ai', text:reply, time:NOW5(), meta, raw:reply }]);
    setStreamId(id);
    stream(reply, 18);
  }, [messages, call, addLog, stream, activeNav, handleNavChange]);

  React.useEffect(() => {
    if (streamDone && streamId !== null) {
      setStreamId(null);
      setAiState('IDLE');
      addLog('ACT', 'Response delivered · system nominal');
    }
  }, [streamDone]);

  const handleMic = React.useCallback(() => {
    if (aiState === 'LISTENING') {
      if (speechRef.current) { try { speechRef.current.stop(); } catch(e){} }
      setAiState('IDLE'); addLog('MIC', 'Voice capture stopped');
      return;
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SR) {
      const r = new SR();
      speechRef.current = r;
      r.lang = 'en-IN'; r.interimResults = true; r.maxAlternatives = 1;
      r.onstart = () => { setAiState('LISTENING'); setTranscript(''); addLog('MIC', 'Voice stream active…', true); };
      r.onresult = e => {
        const t = e.results[e.results.length - 1][0].transcript;
        setTranscript(t);
        if (e.results[e.results.length - 1].isFinal) {
          addLog('MIC', `Captured: "${t}"`, true);
          setAiState('IDLE');
          handleSend(t);
        }
      };
      r.onerror = e => { addLog('ERR', `Speech error: ${e.error}`); setAiState('IDLE'); };
      r.onend = () => { if (stateRef.current === 'LISTENING') setAiState('IDLE'); };
      try { r.start(); } catch(e) { addLog('ERR', 'Mic unavailable'); }
    } else {
      setAiState('LISTENING');
      setTranscript('');
      addLog('MIC', 'Simulated voice capture…', true);
      const samples = ['Kya haal hai?', 'CPU status batao', 'Weather check karo', 'Chrome kholo', 'Volume 70 percent karo'];
      const s = samples[Math.floor(Math.random() * samples.length)];
      const words = s.split(' ');
      let cur = '';
      words.forEach((w, i) => {
        setTimeout(() => { cur = cur ? `${cur} ${w}` : w; setTranscript(cur); }, 400 + i * 380);
      });
      setTimeout(() => {
        addLog('MIC', `Simulated: "${s}"`, true);
        setAiState('IDLE');
        handleSend(s);
      }, 400 + words.length * 380 + 500);
    }
  }, [aiState, addLog, handleSend]);

  // Window control handlers
  const handleMinimize = () => setMinimized(true);
  const handleMaximize = () => setMaximized(m => !m);
  const handleClose    = () => { addLog('SYS', 'Close requested · close blocked (demo)'); };

  if (!booted) return <window.BootScreen onComplete={() => setBooted(true)} />;

  // Minimized state
  if (minimized) {
    return (
      <div style={{
        width:1440, height:900, background:J.bg,
        display:'flex', alignItems:'center', justifyContent:'center',
      }}>
        <button onClick={() => setMinimized(false)} style={{
          padding:'14px 28px', borderRadius:14, cursor:'pointer',
          background:'rgba(13,21,37,0.95)', backdropFilter:'blur(20px)',
          border:`1px solid ${ca(J.cyan, 0.4)}`,
          boxShadow:`0 0 28px ${ca(J.cyan, 0.25)}`,
          display:'flex', alignItems:'center', gap:14,
        }}>
          <window.MiniReactor variant="orbital" size={36} />
          <div style={{ textAlign:'left' }}>
            <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, fontWeight:700,
              letterSpacing:'2px', color:J.cyan }}>A.E.R.I.S MINIMIZED</div>
            <div style={{ fontSize:11, color:J.textSec, marginTop:3 }}>Click to restore</div>
          </div>
        </button>
      </div>
    );
  }

  // Route to active page (or default chat view)
  const renderActivePage = () => {
    switch (activeNav) {
      case 'home':     return <window.HomePage aiState={aiState} onAction={handleSend} lastInput={lastInput} transcript={transcript} />;
      case 'auto':     return <window.AutomationsPage onAction={handleSend} />;
      case 'brain':    return <window.BrainPage />;
      case 'memory':   return <window.MemoryPage />;
      case 'system':   return <window.SystemPage />;
      case 'settings': return <window.SettingsView onClose={() => handleNavChange(prevNav)} />;
      case 'chat':
      default:
        return <ChatView
          aiState={aiState} setAiState={setAiState}
          lastInput={lastInput} transcript={transcript}
          messages={messages} streamId={streamId} streamText={streamText}
          handleSend={handleSend} handleMic={handleMic}
          logs={logs} logsOpen={logsOpen} setLogsOpen={setLogsOpen}
          addLog={addLog} liveVals={liveVals} />;
    }
  };

  return (
    <div style={{ width:1440, height:900, background:J.bg, display:'flex',
      flexDirection:'column', overflow:'hidden', position:'relative' }}>

      {/* Noise texture */}
      <div style={{ position:'absolute', inset:0, pointerEvents:'none', zIndex:99, opacity:0.022,
        backgroundImage:"url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")" }} />

      <AppTitleBar time={time} state={aiState}
        onMinimize={handleMinimize}
        onMaximize={handleMaximize}
        onClose={handleClose} />

      <div style={{ flex:1, display:'flex', overflow:'hidden' }}>
        <window.FloatingDock active={activeNav} setActive={handleNavChange} />
        {renderActivePage()}
      </div>
    </div>
  );
}

function ScaledJarvisV5() {
  const [scale, setScale] = React.useState(1);
  React.useEffect(() => {
    const calc = () => setScale(Math.min(window.innerWidth/1440, window.innerHeight/900));
    calc();
    window.addEventListener('resize', calc);
    return () => window.removeEventListener('resize', calc);
  }, []);
  return (
    <div style={{ width:'100vw', height:'100vh', display:'flex', alignItems:'center',
      justifyContent:'center', background:'#000', overflow:'hidden' }}>
      <div style={{ transform:`scale(${scale})`, transformOrigin:'center center' }}>
        <JarvisV5App />
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<ScaledJarvisV5 />);
