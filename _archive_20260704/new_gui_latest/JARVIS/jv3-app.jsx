// ─── JARVIS v3 — Main App ─────────────────────────────────────────────────────

const BOOT_MSGS = [
  { id:1, role:'ai', text:'JARVIS v3.0 online. Neural core initialized. Kya karein aaj, boss?', time:'--:--', tag:{ text:'sys_boot · 100ms', color:window.J.green }, raw:'JARVIS v3.0 online. Neural core initialized. Kya karein aaj, boss?' },
];
const BOOT_LOGS = [
  { id:1, type:'SYS', text:'Core initialized · semantic engine v3.1 loaded', time:'--:--:--', col: window.J.green },
  { id:2, type:'NLU', text:'301 intent patterns active · 21 intent classes',   time:'--:--:--', col: window.J.cyan  },
  { id:3, type:'SYS', text:'All modules nominal · awaiting input',             time:'--:--:--', col: window.J.textMut },
];

let _mid = 10, _lid = 10;
const nid  = () => ++_mid;
const nlid = () => ++_lid;
const now  = () => new Date().toTimeString().slice(0,5);
const nowS = () => new Date().toTimeString().slice(0,8);

function TitleBar({ time, state, onCollapse }) {
  const J = window.J;
  const s = window.JSTATES[state] || window.JSTATES.IDLE;
  return (
    <div style={{ height:40, background:'rgba(13,21,37,0.95)', backdropFilter:'blur(12px)',
      borderBottom:`1px solid rgba(30,41,59,0.7)`,
      display:'flex', alignItems:'center', padding:'0 20px 0 14px',
      justifyContent:'space-between', flexShrink:0, zIndex:60, position:'relative' }}>

      {/* Left */}
      <div style={{ display:'flex', alignItems:'center', gap:10 }}>
        <div style={{ width:10,height:10,borderRadius:'50%', background:J.cyan, boxShadow:`0 0 8px ${J.cyan}` }} />
        <span style={{ fontSize:13, fontWeight:700, letterSpacing:'2px', color:J.textPri }}>A.E.R.I.S</span>
        <span style={{ fontSize:10, color:J.textMut, letterSpacing:'0.5px' }}>JARVIS v3.0</span>
        <div style={{ width:1, height:14, background:'rgba(30,41,59,0.8)' }} />
        <span style={{ fontSize:10, color:J.textMut }}>› Shivang's Machine</span>
      </div>

      {/* Status pill */}
      <div style={{ padding:'4px 14px 4px 10px', borderRadius:12,
        background: ca(s.col,0.1), border:`1px solid ${ca(s.col,0.4)}`,
        display:'flex', alignItems:'center', gap:8, transition:'all 0.6s' }}>
        <div style={{ width:6,height:6,borderRadius:'50%', background:s.col,
          boxShadow:`0 0 5px ${s.col}`, animation:'j-blink 1.5s infinite',
          transition:'background 0.6s' }} />
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, fontWeight:700,
          letterSpacing:'1.5px', color:s.col, transition:'color 0.6s' }}>
          {state==='IDLE'?'STANDBY · IDLE':`ONLINE · ${s.label}`}
        </span>
      </div>

      {/* Right */}
      <div style={{ display:'flex', gap:16, alignItems:'center' }}>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:12, fontWeight:700, color:J.textSec }}>{time}</span>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:J.textMut }}>CPU 12% · RAM 4.2G</span>
        <div style={{ display:'flex', gap:6 }}>
          {['#F87171','#FBBF24','#34D399'].map(c=><div key={c} style={{ width:10,height:10,borderRadius:'50%', background:c }} />)}
        </div>
      </div>
    </div>
  );
}

function LogsBar({ logs, open, onToggle }) {
  const J = window.J;
  const ref = React.useRef(null);
  const TYPE_COLORS = { SYS:J.textMut, NLU:J.cyan, ACT:J.green, MIC:J.green, TTS:J.purple, ERR:J.red };

  React.useEffect(()=>{
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  },[logs.length]);

  return (
    <div style={{ borderTop:`1px solid rgba(30,41,59,0.7)`,
      background:'rgba(10,15,28,0.9)', backdropFilter:'blur(8px)',
      height: open ? 160 : 38, transition:'height 0.3s cubic-bezier(0.4,0,0.2,1)',
      overflow:'hidden', flexShrink:0 }}>
      {/* Header row */}
      <div onClick={onToggle} style={{ height:38, display:'flex', alignItems:'center',
        justifyContent:'space-between', padding:'0 16px', cursor:'pointer',
        borderBottom: open ? `1px solid rgba(30,41,59,0.5)` : 'none' }}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <div style={{ width:5,height:5,borderRadius:'50%', background:J.green,
            boxShadow:`0 0 5px ${J.green}`, animation:'j-blink 1.5s infinite' }} />
          <window.JLabel color={J.textSec}>SYSTEM LOGS</window.JLabel>
          <div style={{ padding:'1px 6px', borderRadius:4, background:ca(J.cyan,0.1),
            border:`1px solid ${ca(J.cyan,0.2)}` }}>
            <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, fontWeight:700, color:J.cyan }}>{logs.length}</span>
          </div>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:10 }}>
          {!open && logs.length > 0 && (
            <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut,
              maxWidth:400, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
              {logs[logs.length-1].text}
            </span>
          )}
          <svg width="10" height="7" viewBox="0 0 10 7" fill="none"
            style={{ transform:open?'rotate(180deg)':'none', transition:'transform 0.3s' }}>
            <path d="M1 1l4 4 4-4" stroke={J.textMut} strokeWidth="1.4" strokeLinecap="round"/>
          </svg>
        </div>
      </div>

      {/* Log lines */}
      <div ref={ref} style={{ height:120, overflowY:'auto', padding:'4px 16px' }}>
        {logs.map((log,i)=>(
          <div key={log.id} style={{ display:'flex', gap:8, padding:'2.5px 0',
            borderBottom:`1px solid rgba(30,41,59,0.2)`,
            animation: i===logs.length-1 ? 'j-fadein 0.25s ease' : 'none' }}>
            <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5, color:J.textMut, flexShrink:0 }}>{log.time}</span>
            <div style={{ padding:'0px 5px', borderRadius:3, flexShrink:0,
              background:ca(TYPE_COLORS[log.type]||J.textMut,0.12),
              border:`1px solid ${ca(TYPE_COLORS[log.type]||J.textMut,0.2)}` }}>
              <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:7.5, fontWeight:700, color:TYPE_COLORS[log.type]||J.textMut }}>{log.type}</span>
            </div>
            <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5, color: log.highlight?log.col:J.textSec, flex:1 }}>{log.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── MAIN APP ─────────────────────────────────────────────────────────────────
function JarvisApp() {
  const J = window.J;
  const [booted, setBooted]     = React.useState(false);
  const [aiState, setAiState]   = React.useState('IDLE');
  const [messages, setMessages] = React.useState(BOOT_MSGS);
  const [logs, setLogs]         = React.useState(BOOT_LOGS);
  const [logsOpen, setLogsOpen] = React.useState(false);
  const [streamId, setStreamId] = React.useState(null);
  const [activeNav, setActiveNav]= React.useState('chat');
  const [lastInput, setLastInput]= React.useState('');
  const time = window.useClock();
  const { text:streamText, done:streamDone, stream } = window.useStreamText();
  const { call } = window.useJarvisAPI();
  const speechRef = React.useRef(null);
  const stateRef  = React.useRef('IDLE');
  stateRef.current = aiState;

  const addLog = React.useCallback((type, text, highlight=false, col=null)=>{
    const c = col || { SYS:J.textMut,NLU:J.cyan,ACT:J.green,MIC:J.green,TTS:J.purple,ERR:J.red }[type] || J.textMut;
    setLogs(prev=>[...prev,{ id:nlid(), type, text, time:nowS(), highlight, col:c }]);
  },[]);

  const pushMsg = React.useCallback((role,text,tag=null,raw='')=>{
    const id=nid();
    setMessages(prev=>[...prev,{ id, role, text, time:now(), tag, raw:raw||text }]);
    return id;
  },[]);

  const handleSend = React.useCallback(async(text)=>{
    if(!text.trim()) return;
    setLastInput(text);
    pushMsg('user', text);
    addLog('NLU',`Input: "${text.slice(0,48)}${text.length>48?'…':''}"`,true);
    setAiState('PROCESSING');
    addLog('NLU','Semantic parse + intent classification running…');

    const snap = messages.slice(-10);
    const { text:reply, meta } = await call(text, snap);

    addLog('NLU',`Intent: ${meta.intent} · ${meta.conf}% · ${meta.act}`,true);
    setAiState('SPEAKING');
    addLog('TTS',`Streaming response… ${meta.ms}ms latency`);

    const tagColor = meta.act==='executed'||meta.act==='knowledge' ? J.green : meta.act==='error' ? J.red : J.cyan;
    const id = nid();
    setMessages(prev=>[...prev,{
      id, role:'ai', text:reply, time:now(),
      tag:{ text:`${meta.intent} · ${meta.conf}% · ${meta.ms}ms`, color:tagColor },
      raw:reply,
    }]);
    setStreamId(id);
    stream(reply, 18);
  },[messages, call, pushMsg, addLog, stream]);

  React.useEffect(()=>{
    if(streamDone && streamId!==null){
      setStreamId(null);
      setAiState('IDLE');
      addLog('ACT','Response delivered. System ready.');
    }
  },[streamDone]);

  const handleMic = React.useCallback(()=>{
    if(aiState==='LISTENING'){
      if(speechRef.current){ try{speechRef.current.stop();}catch(e){} }
      setAiState('IDLE'); addLog('MIC','Voice capture stopped.'); return;
    }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if(SR){
      const r = new SR(); speechRef.current=r;
      r.lang='en-IN'; r.interimResults=false; r.maxAlternatives=1;
      r.onstart=()=>{ setAiState('LISTENING'); addLog('MIC','Voice stream active…',true); };
      r.onresult=e=>{ const s=e.results[0][0].transcript; addLog('MIC',`Captured: "${s}" · ${(e.results[0][0].confidence*100).toFixed(1)}%`,true); setAiState('IDLE'); handleSend(s); };
      r.onerror=e=>{ addLog('ERR',`Speech error: ${e.error}`); setAiState('IDLE'); };
      r.onend=()=>{ if(stateRef.current==='LISTENING') setAiState('IDLE'); };
      try{ r.start(); }catch(e){ addLog('ERR','Mic unavailable: '+e.message); }
    } else {
      setAiState('LISTENING'); addLog('MIC','Simulated voice capture…',true);
      const samples=['Kya haal hai?','Chrome kholo','Weather batao','Volume badhao','Kal 9 baje remind karo'];
      const spoken=samples[Math.floor(Math.random()*samples.length)];
      setTimeout(()=>{ addLog('MIC',`Simulated: "${spoken}"`,true); setAiState('IDLE'); handleSend(spoken); },2200);
    }
  },[aiState,addLog,handleSend]);

  const handleCommand = React.useCallback((label)=>{
    const map={ 'Open Apps':'App launcher kholo', 'Clean System':'System clean karo', 'Weather':'Aaj ka weather batao', 'Music':'Koi achha gana chalao', 'Screenshot':'Screenshot lo', 'Search':'Kuch search karna hai' };
    handleSend(map[label]||label);
  },[handleSend]);

  if(!booted) return <window.BootScreen onComplete={()=>setBooted(true)} />;

  return (
    <div style={{ width:1440, height:900, background:J.bg, display:'flex', flexDirection:'column', overflow:'hidden', position:'relative' }}>

      {/* Noise */}
      <div style={{ position:'absolute',inset:0,pointerEvents:'none',zIndex:99,opacity:0.025,
        backgroundImage:"url(\"data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")" }} />

      <TitleBar time={time} state={aiState} />

      {/* Body */}
      <div style={{ flex:1, display:'flex', overflow:'hidden', position:'relative' }}>
        {/* Grid bg */}
        <div style={{ position:'absolute',inset:0,pointerEvents:'none',
          backgroundImage:`linear-gradient(rgba(0,212,255,0.022) 1px,transparent 1px),linear-gradient(90deg,rgba(0,212,255,0.022) 1px,transparent 1px)`,
          backgroundSize:'48px 48px' }} />

        {/* Floating dock */}
        <window.FloatingDock active={activeNav} setActive={setActiveNav} />

        {/* System cards */}
        <window.SystemCards />

        {/* Center — reactor + text + stats */}
        <div style={{ flex:1, display:'flex', flexDirection:'column', overflow:'hidden', position:'relative' }}>
          <window.ParticleField count={28} />

          <div style={{ flex:1, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', padding:'30px 0 80px' }}>
            <window.ReactorRings state={aiState} />
            <div style={{ marginTop:24 }}>
              <window.ReactorStateText state={aiState} lastInput={lastInput} />
            </div>
            {/* Stats */}
            <div style={{ display:'flex', gap:10, marginTop:24, width:'72%', maxWidth:680 }}>
              <window.StatPill label="INTENTS"  value="21"     color={J.cyan}    />
              <window.StatPill label="PATTERNS" value="301"    color={J.cyan}    />
              <window.StatPill label="ACCURACY" value="99.8%"  color={J.green}   />
              <window.StatPill label="UPTIME"   value="2h 14m" color={J.textSec} />
            </div>
            {/* State manual switcher */}
            <div style={{ display:'flex', gap:8, marginTop:18 }}>
              {Object.keys(window.JSTATES).map(s=>{
                const sc=window.JSTATES[s].col, active=aiState===s;
                return(
                  <button key={s} onClick={()=>{ setAiState(s); addLog('SYS',`Manual → ${s}`); }} style={{
                    padding:'5px 11px', borderRadius:8, cursor:'pointer',
                    fontFamily:"'JetBrains Mono',monospace", fontSize:8.5, fontWeight:700, letterSpacing:'0.9px',
                    background:active?ca(sc,0.14):'rgba(255,255,255,0.04)',
                    border:`1px solid ${active?ca(sc,0.5):'rgba(255,255,255,0.08)'}`,
                    color:active?sc:J.textMut, transition:'all 0.2s',
                  }}>{s}</button>
                );
              })}
            </div>
          </div>

          {/* Logs */}
          <LogsBar logs={logs} open={logsOpen} onToggle={()=>setLogsOpen(v=>!v)} />
        </div>

        {/* Chat panel */}
        <window.GlassChatPanel
          messages={messages} streamId={streamId} streamText={streamText}
          aiState={aiState} onSend={handleSend} onMic={handleMic} />
      </div>

      {/* Command capsules */}
      <window.CommandBar onCommand={handleCommand} />
    </div>
  );
}

function ScaledJarvis() {
  const [scale, setScale] = React.useState(1);
  React.useEffect(()=>{
    const calc=()=>setScale(Math.min(window.innerWidth/1440,window.innerHeight/900));
    calc(); window.addEventListener('resize',calc); return()=>window.removeEventListener('resize',calc);
  },[]);
  return(
    <div style={{ width:'100vw',height:'100vh',display:'flex',alignItems:'center',justifyContent:'center',background:'#000',overflow:'hidden' }}>
      <div style={{ transform:`scale(${scale})`, transformOrigin:'center center' }}>
        <JarvisApp />
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<ScaledJarvis />);
