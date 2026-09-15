// ─── A.E.R.I.S MAIN APP ──────────────────────────────────────────────────────

const BOOT_MESSAGES = [
  { id:1, role:'aeris', text:'AERIS systems online. Semantic core v3.1 initialized.', time:'--:--:--', tag:{ text:'sys_boot • 100ms', color:window.AERIS_COLORS.green } },
  { id:2, role:'aeris', text:'Kya seva kar sakta hoon aapki, sir?', time:'--:--:--', tag:null },
];

const BOOT_LOGS = [
  { id:1,  type:'SYS', text:'AERIS core initialized. Loading semantic engine…',    time:'--:--:--', highlight:false },
  { id:2,  type:'SYS', text:'Semantic engine v3.1 online. 301 patterns loaded.',    time:'--:--:--', highlight:false },
  { id:3,  type:'NLU', text:'Intent classifier ready. 21 intent classes active.',   time:'--:--:--', highlight:true  },
  { id:4,  type:'MEM', text:'Memory index loaded. 0 prior sessions found.',         time:'--:--:--', highlight:false },
  { id:5,  type:'SYS', text:'All modules nominal. Awaiting user input.',            time:'--:--:--', highlight:false },
];

let _msgId  = 100;
let _logId  = 50;
const nextMsgId  = () => ++_msgId;
const nextLogId  = () => ++_logId;
const nowTime    = () => new Date().toTimeString().slice(0,8);

function TitleBar({ time, aiState, collapsed, setCollapsed }) {
  const C = window.AERIS_COLORS;
  const S = window.AERIS_STATES;
  const s = S[aiState] || S.IDLE;

  return (
    <div style={{
      height:40, background:C.panel, borderBottom:`1px solid ${C.border}`,
      display:'flex', alignItems:'center', padding:'0 20px 0 14px',
      justifyContent:'space-between', flexShrink:0,
    }}>
      <div style={{ display:'flex', alignItems:'center', gap:10 }}>
        <div
          onClick={() => setCollapsed(v => !v)}
          style={{ width:28, height:28, borderRadius:6, cursor:'pointer', display:'flex', alignItems:'center', justifyContent:'center', transition:'background 0.2s' }}
          title="Toggle sidebar"
        >
          <svg width="16" height="12" viewBox="0 0 16 12" fill="none">
            {[0,5,10].map(y => <line key={y} x1="0" y1={y+1} x2="16" y2={y+1} stroke={C.textMut} strokeWidth="1.5" strokeLinecap="round" />)}
          </svg>
        </div>
        <div style={{ width:10, height:10, borderRadius:'50%', background:C.cyan, boxShadow:`0 0 8px ${C.cyan}` }} />
        <span style={{ fontSize:13, fontWeight:700, letterSpacing:'2px', color:C.textPri }}>A.E.R.I.S</span>
        <span style={{ fontSize:10, fontWeight:500, letterSpacing:'0.5px', color:C.textMut }}>v3.1 • Semantic Core</span>
      </div>

      <div style={{
        padding:'5px 14px 5px 12px', borderRadius:12,
        background: s.color.replace('rgb','rgba').replace(')',',0.12)'),
        border:`1px solid ${s.color.replace('rgb','rgba').replace(')',',0.45)')}`,
        display:'flex', alignItems:'center', gap:8,
        transition:'background 0.6s, border-color 0.6s',
      }}>
        <div style={{ width:6, height:6, borderRadius:'50%', background:s.color, boxShadow:`0 0 5px ${s.color}`, animation:'aeris-blink 1.5s infinite', transition:'background 0.6s' }} />
        <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:10, fontWeight:700, letterSpacing:'1.5px', color:s.color, transition:'color 0.6s' }}>
          {aiState === 'IDLE' ? 'STANDBY • IDLE' : `ONLINE • ${s.label}`}
        </span>
      </div>

      <div style={{ display:'flex', gap:18, alignItems:'center' }}>
        <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:12, fontWeight:700, letterSpacing:'1px', color:C.textSec }}>{time}</span>
        <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:10, color:C.textMut }}>CPU 12%&nbsp;&nbsp;RAM 4.2G&nbsp;&nbsp;BAT 87%</span>
        <div style={{ display:'flex', gap:6 }}>
          {['#F87171','#FBBF24','#34D399'].map(c => <div key={c} style={{ width:10, height:10, borderRadius:'50%', background:c }} />)}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, color }) {
  const C = window.AERIS_COLORS;
  return (
    <div style={{
      flex:1, borderRadius:14,
      background:'rgba(13,21,37,0.75)',
      border:`1px solid ${C.border}`,
      backdropFilter:'blur(4px)',
      padding:'16px 20px',
      display:'flex', flexDirection:'column', gap:6,
      transition:'border-color 0.2s, box-shadow 0.2s',
    }}
    onMouseEnter={e => { e.currentTarget.style.borderColor='rgba(0,212,255,0.3)'; e.currentTarget.style.boxShadow='0 0 20px rgba(0,212,255,0.12)'; }}
    onMouseLeave={e => { e.currentTarget.style.borderColor=C.border; e.currentTarget.style.boxShadow='none'; }}
    >
      <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:9, fontWeight:700, letterSpacing:'1.8px', color:C.textMut }}>{label}</span>
      <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:22, fontWeight:700, color: color||C.cyan, letterSpacing:'1px' }}>{value}</span>
    </div>
  );
}

function App() {
  const C = window.AERIS_COLORS;
  const [aiState, setAiState]     = React.useState('IDLE');
  const [messages, setMessages]   = React.useState(BOOT_MESSAGES);
  const [logs, setLogs]           = React.useState(BOOT_LOGS);
  const [logsOpen, setLogsOpen]   = React.useState(false);
  const [streamingId, setStreamId]= React.useState(null);
  const [activeTab, setActiveTab] = React.useState('Chat');
  const [collapsed, setCollapsed] = React.useState(false);
  const [lastInput, setLastInput] = React.useState('');
  const [msgCount, setMsgCount]   = React.useState(2);
  const time                      = window.useClock();
  const { stream, displayed: streamText, done: streamDone } = window.useStreamingText();
  const { ask, loading } = window.useAerisAPI();
  const speechRef = React.useRef(null);
  const stateRef  = React.useRef(aiState);
  stateRef.current = aiState;

  const addLog = React.useCallback((type, text, highlight = false) => {
    setLogs(prev => [...prev, { id:nextLogId(), type, text, time:nowTime(), highlight }]);
  }, []);

  const pushMessage = React.useCallback((role, text, tag = null, rawText = '') => {
    const id = nextMsgId();
    const msg = { id, role, text, time:nowTime(), tag, rawText: rawText || text };
    setMessages(prev => [...prev, msg]);
    setMsgCount(c => c + 1);
    return id;
  }, []);

  // ── Handle send (typed input) ──────────────────────────────────────────────
  const handleSend = React.useCallback(async (text) => {
    if (!text.trim()) return;
    setLastInput(text);

    // Add user message
    pushMessage('user', text);
    addLog('NLU', `Input received: "${text.slice(0,50)}${text.length>50?'…':''}"`, true);
    setAiState('PROCESSING');

    // Fetch from Claude
    addLog('NLU', 'Running semantic parse + intent classification…');
    const historySnapshot = messages.slice(-10);
    const { text: reply, meta } = await ask(text, historySnapshot);

    addLog('NLU', `Intent: ${meta.intent} | Confidence: ${meta.confidence}% | Action: ${meta.action}`, true);
    setAiState('SPEAKING');
    addLog('TTS', `Streaming response… latency ${meta.latency_ms}ms`);

    // Create placeholder message and stream into it
    const id = nextMsgId();
    const tag = {
      text: `${meta.intent} • ${meta.confidence}% • ${meta.latency_ms}ms`,
      color: meta.action === 'executed' || meta.action === 'knowledge_retrieved' ? C.green : meta.action === 'error' ? C.red : C.cyan,
    };
    setMessages(prev => [...prev, { id, role:'aeris', text:reply, time:nowTime(), tag, rawText:reply }]);
    setMsgCount(c => c + 1);
    setStreamId(id);
    stream(reply, 20);
  }, [messages, ask, pushMessage, addLog, stream]);

  // ── Watch stream completion ────────────────────────────────────────────────
  React.useEffect(() => {
    if (streamDone && streamingId !== null) {
      setStreamId(null);
      setAiState('IDLE');
      addLog('ACT', `Response delivered. ${msgCount} messages in session.`);
    }
  }, [streamDone]);

  // ── Mic / Speech recognition ───────────────────────────────────────────────
  const handleMic = React.useCallback(() => {
    if (aiState === 'LISTENING') {
      // Stop
      if (speechRef.current) { try { speechRef.current.stop(); } catch(e) {} }
      setAiState('IDLE');
      addLog('MIC', 'Voice capture stopped by user.');
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      const rec = new SpeechRecognition();
      speechRef.current = rec;
      rec.lang = 'en-IN';
      rec.interimResults = false;
      rec.maxAlternatives = 1;

      rec.onstart = () => {
        setAiState('LISTENING');
        addLog('MIC', 'Voice stream active. Listening for input…', true);
      };
      rec.onresult = (e) => {
        const spoken = e.results[0][0].transcript;
        addLog('MIC', `Captured: "${spoken}" | confidence ${(e.results[0][0].confidence * 100).toFixed(1)}%`, true);
        setAiState('IDLE');
        handleSend(spoken);
      };
      rec.onerror = (e) => {
        addLog('ERR', `Speech recognition error: ${e.error}`);
        setAiState('IDLE');
      };
      rec.onend = () => {
        if (stateRef.current === 'LISTENING') setAiState('IDLE');
      };
      try { rec.start(); } catch(e) { addLog('ERR', 'Could not start mic: ' + e.message); }
    } else {
      // Fallback simulation
      setAiState('LISTENING');
      addLog('MIC', 'Voice stream active (simulated — no Speech API found).', true);
      const samples = ['Kya hal hai AERIS?', 'Weather batao aaj ka', 'Mujhe remind karo kal 9 baje', 'Chrome kholo'];
      const spoken = samples[Math.floor(Math.random() * samples.length)];
      setTimeout(() => {
        addLog('MIC', `Simulated capture: "${spoken}"`, true);
        setAiState('IDLE');
        handleSend(spoken);
      }, 2200);
    }
  }, [aiState, addLog, handleSend]);

  return (
    <div style={{ width:1440, height:900, background:C.bg, display:'flex', flexDirection:'column', overflow:'hidden', position:'relative' }}>
      {/* Noise texture */}
      <div style={{ position:'absolute', inset:0, pointerEvents:'none', zIndex:99, opacity:0.025, backgroundImage:"url(\"data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E\")" }} />

      <TitleBar time={time} aiState={aiState} collapsed={collapsed} setCollapsed={setCollapsed} />

      <div style={{ flex:1, display:'flex', overflow:'hidden' }}>
        <window.Sidebar activeTab={activeTab} setActiveTab={setActiveTab} collapsed={collapsed} />

        {/* Center column */}
        <div style={{ flex:1, display:'flex', flexDirection:'column', overflow:'hidden', position:'relative' }}>
          {/* Grid bg */}
          <div style={{ position:'absolute', inset:0, pointerEvents:'none', backgroundImage:`linear-gradient(rgba(0,212,255,0.025) 1px, transparent 1px),linear-gradient(90deg,rgba(0,212,255,0.025) 1px, transparent 1px)`, backgroundSize:'40px 40px' }} />

          {/* Reactor + state + stats */}
          <div style={{ flex:1, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', padding:'40px 0 20px', overflow:'hidden' }}>
            <window.ArcReactor state={aiState} />
            <div style={{ marginTop:28 }}>
              <window.ReactorStateText state={aiState} lastInput={lastInput} />
            </div>
            <div style={{ display:'flex', gap:12, marginTop:28, width:'78%', maxWidth:700 }}>
              <StatCard label="INTENTS"  value="21"    color={C.cyan}    />
              <StatCard label="PATTERNS" value="301"   color={C.cyan}    />
              <StatCard label="ACCURACY" value="99.8%" color={C.green}   />
              <StatCard label="UPTIME"   value="2h 14m" color={C.textSec} />
            </div>

            {/* State switcher */}
            <div style={{ display:'flex', gap:8, marginTop:20 }}>
              {Object.keys(window.AERIS_STATES).filter(s => s!=='ERROR').map(s => {
                const sc = window.AERIS_STATES[s].color;
                const active = aiState === s;
                return (
                  <button key={s} onClick={() => { setAiState(s); addLog('SYS', `Manual state override → ${s}`); }} style={{
                    padding:'5px 12px', borderRadius:8, cursor:'pointer',
                    fontFamily:"'JetBrains Mono', monospace", fontSize:9, fontWeight:700, letterSpacing:'1px',
                    background: active ? sc.replace('rgb','rgba').replace(')',',0.15)') : 'rgba(255,255,255,0.04)',
                    border:`1px solid ${active ? sc.replace('rgb','rgba').replace(')',',0.5)') : 'rgba(255,255,255,0.1)'}`,
                    color: active ? sc : C.textMut,
                    transition:'all 0.2s',
                  }}>{s}</button>
                );
              })}
            </div>
          </div>

          {/* Logs panel */}
          <window.SystemLogsPanel logs={logs} expanded={logsOpen} onToggle={() => setLogsOpen(v => !v)} />
        </div>

        {/* Chat panel */}
        <window.ChatPanel
          messages={messages}
          streamingId={streamingId}
          streamText={streamText}
          aiState={aiState}
          onSend={handleSend}
          onMicClick={handleMic}
        />
      </div>
    </div>
  );
}

function ScaledApp() {
  const [scale, setScale] = React.useState(1);
  React.useEffect(() => {
    const calc = () => setScale(Math.min(window.innerWidth/1440, window.innerHeight/900));
    calc();
    window.addEventListener('resize', calc);
    return () => window.removeEventListener('resize', calc);
  }, []);
  return (
    <div style={{ width:'100vw', height:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'#000', overflow:'hidden' }}>
      <div style={{ transform:`scale(${scale})`, transformOrigin:'center center' }}>
        <App />
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<ScaledApp />);
