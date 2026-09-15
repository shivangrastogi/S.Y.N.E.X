// ─── JARVIS v5 — Home Page (Dashboard) ──────────────────────────────────────
const { J, ca } = window;

const QUICK_ACTIONS = [
  { id:'coding',   label:'Coding Mode',      sub:'VS Code · Chrome · Spotify',  color:J.cyan,    icon:'code'  },
  { id:'study',    label:'Study Mode',       sub:'Notion · Calendar · DND',      color:J.purple,  icon:'brain' },
  { id:'music',    label:'Play Focus Music', sub:'Lo-fi · Volume 60%',           color:J.magenta, icon:'music' },
  { id:'wind',     label:'Wind Down',        sub:'Save state · Night theme',     color:J.amber,   icon:'moon'  },
];

const TIMELINE_EVENTS = [
  { time:'just now', text:'Resumed SehatUP redesign workspace',         type:'auto', color:J.cyan    },
  { time:'12 min',   text:'Opened VS Code with last project state',     type:'auto', color:J.cyan    },
  { time:'24 min',   text:'You said "Open my dev workspace"',           type:'chat', color:J.purple  },
  { time:'1h 12m',   text:'Spotify playlist auto-resumed · Night Coding',type:'auto',color:J.cyan    },
  { time:'2h 04m',   text:'Reminder triggered: "Review PR #482"',       type:'notif',color:J.amber   },
  { time:'3h 18m',   text:'Generated 4 image variations for SehatUP',   type:'task', color:J.magenta },
];

const AGENDA_ITEMS = [
  { time:'16:30', text:'Standup with the team',          color:J.cyan,    done:false },
  { time:'18:00', text:'Push SehatUP v2 to staging',     color:J.purple,  done:false },
  { time:'20:00', text:'Review React hooks tutorial',    color:J.amber,   done:false },
];

function GreetingHero({ time }) {
  const p = window.getTimePeriod();
  return (
    <div style={{
      padding:'28px 32px 28px',
      borderRadius:14, position:'relative', overflow:'hidden',
      background:'linear-gradient(135deg, rgba(13,21,37,0.7) 0%, rgba(13,21,37,0.4) 60%, rgba(0,212,255,0.05) 100%)',
      border:'1px solid rgba(30,41,59,0.6)',
      marginBottom:16,
    }}>
      {/* Ambient glow */}
      <div style={{ position:'absolute', top:-80, right:-80, width:240, height:240, borderRadius:'50%',
        background:`radial-gradient(circle, ${ca(J.cyan, 0.12)}, transparent 70%)` }} />
      <div style={{ position:'absolute', bottom:-60, left:'30%', width:180, height:180, borderRadius:'50%',
        background:`radial-gradient(circle, ${ca(J.purple, 0.08)}, transparent 70%)` }} />

      <div style={{ position:'relative', display:'flex', justifyContent:'space-between', alignItems:'flex-end', gap:24 }}>
        <div>
          <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, fontWeight:700,
            letterSpacing:'3px', color:ca(J.cyan, 0.85) }}>{p.label}</div>
          <div style={{ fontSize:36, fontWeight:600, color:J.textPri, letterSpacing:'-0.5px', marginTop:10, lineHeight:1.1 }}>
            {p.greeting}, Shivang.
          </div>
          <div style={{ fontSize:14, color:J.textSec, marginTop:10, lineHeight:1.6, maxWidth:560 }}>
            You've been in flow for <span style={{ color:J.cyan, fontWeight:600 }}>3h 42m</span> today —
            longest stretch this week. <span style={{ color:J.textPri }}>SehatUP redesign</span> is waiting where you left it.
          </div>
        </div>

        {/* Live time + mini orbital */}
        <div style={{ display:'flex', alignItems:'center', gap:18 }}>
          <div style={{ textAlign:'right' }}>
            <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:30, fontWeight:700,
              color:J.textPri, letterSpacing:'1.5px', lineHeight:1 }}>{time}</div>
            <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:J.textMut,
              marginTop:6, letterSpacing:'1px' }}>{new Date().toDateString().toUpperCase()}</div>
          </div>
          <window.MiniReactor variant="orbital" size={64} />
        </div>
      </div>
    </div>
  );
}

function HomePage({ aiState, onAction, lastInput, transcript }) {
  const time = window.useClock();
  const [tick, setTick] = React.useState(0);
  React.useEffect(() => { const i = setInterval(()=>setTick(t=>t+1), 4000); return ()=>clearInterval(i); }, []);

  return (
    <window.PageContainer>
      <window.PageHeader title="Home"
        subtitle="Your AI-curated command surface. Pick up where you left off, or start something new."
        accent={J.cyan}
        right={
          <div style={{ display:'flex', gap:8 }}>
            <window.PillButton icon="spark" onClick={() => onAction('Tell me what I worked on today')}>Daily Summary</window.PillButton>
            <window.PillButton icon="plus" color={J.cyan} primary onClick={() => onAction('Start focus mode')}>Focus Mode</window.PillButton>
          </div>
        } />

      <div style={{ flex:1, overflowY:'auto', padding:'18px 32px 32px' }}>
        <GreetingHero time={time} />

        {/* Stats row */}
        <div style={{ display:'flex', gap:12, marginBottom:16 }}>
          <window.StatTile label="FOCUS TIME"     value="3h 42m" sub="↑ 18% vs yesterday" color={J.cyan}    icon={<window.PageIcon name="clock"/>} />
          <window.StatTile label="TASKS DONE"     value="8 / 12" sub="4 remaining today"   color={J.green}   icon={<window.PageIcon name="check"/>} />
          <window.StatTile label="CONVERSATIONS"  value="24"     sub="11 commands executed" color={J.purple} icon={<window.PageIcon name="chat"/>} />
          <window.StatTile label="AUTOMATIONS"    value="47"     sub="ran in last 24h"      color={J.amber}  icon={<window.PageIcon name="bolt"/>} />
        </div>

        {/* 2-col layout */}
        <div style={{ display:'grid', gridTemplateColumns:'1.4fr 1fr', gap:16, alignItems:'start' }}>

          {/* LEFT */}
          <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
            {/* Quick Actions */}
            <window.PageCard title="QUICK ACTIONS" subtitle="One-shot workflows · voice or click" accent={J.cyan}>
              <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8 }}>
                {QUICK_ACTIONS.map(a => (
                  <QuickActionCard key={a.id} action={a} onClick={() => onAction(a.label)} />
                ))}
              </div>
            </window.PageCard>

            {/* Recent activity timeline */}
            <window.PageCard title="RECENT ACTIVITY" subtitle="What happened across your workspace" accent={J.purple}
              right={<window.JLabel color={J.textMut}>LAST 4 HOURS</window.JLabel>}>
              <ActivityTimeline events={TIMELINE_EVENTS} />
            </window.PageCard>
          </div>

          {/* RIGHT */}
          <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
            {/* AI Status mini */}
            <window.PageCard title="A.E.R.I.S STATUS" subtitle="Neural core · live state" accent={J.cyan}>
              <AIStatusMini aiState={aiState} lastInput={lastInput} transcript={transcript} />
            </window.PageCard>

            {/* Today's agenda */}
            <window.PageCard title="TODAY'S AGENDA" subtitle="3 items remaining" accent={J.amber}
              right={<window.PillButton icon="plus" color={J.amber}>Add</window.PillButton>}>
              {AGENDA_ITEMS.map((a, i) => (
                <AgendaRow key={i} item={a} onToggle={()=>{}} />
              ))}
            </window.PageCard>

            {/* System pulse */}
            <window.PageCard title="SYSTEM PULSE" subtitle="All nodes nominal" accent={J.green}>
              <SystemPulseMini tick={tick} />
            </window.PageCard>
          </div>
        </div>
      </div>
    </window.PageContainer>
  );
}

function QuickActionCard({ action, onClick }) {
  const [hov, setHov] = React.useState(false);
  return (
    <button onClick={onClick}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{
        textAlign:'left', padding:'14px 14px', borderRadius:10, cursor:'pointer',
        background: hov ? ca(action.color, 0.1) : 'rgba(13,21,37,0.5)',
        border:`1px solid ${hov ? ca(action.color, 0.45) : 'rgba(30,41,59,0.65)'}`,
        boxShadow: hov ? `0 0 18px ${ca(action.color, 0.18)}` : 'none',
        transition:'all 0.2s',
        display:'flex', alignItems:'center', gap:12,
        transform: hov ? 'translateY(-1px)' : 'none',
      }}>
      <div style={{ width:38, height:38, borderRadius:10, flexShrink:0,
        background:ca(action.color, hov ? 0.18 : 0.12),
        border:`1px solid ${ca(action.color, hov ? 0.5 : 0.3)}`,
        boxShadow: hov ? `0 0 12px ${ca(action.color, 0.25)}` : 'none',
        display:'flex', alignItems:'center', justifyContent:'center',
        color:action.color, transition:'all 0.2s',
      }}>
        <window.PageIcon name={action.icon} size={16} />
      </div>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:13, fontWeight:600, color:J.textPri, letterSpacing:'0.1px' }}>{action.label}</div>
        <div style={{ fontSize:10, color:J.textMut, marginTop:2, letterSpacing:'0.2px' }}>{action.sub}</div>
      </div>
      <div style={{ color: hov ? action.color : J.textMut, transition:'color 0.2s', opacity: hov ? 1 : 0.6 }}>
        <svg width="10" height="10" viewBox="0 0 10 10"><path d="M3 1l4 4-4 4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/></svg>
      </div>
    </button>
  );
}

function ActivityTimeline({ events }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:0 }}>
      {events.map((e, i) => (
        <div key={i} style={{ display:'flex', gap:14, padding:'9px 4px',
          borderBottom: i === events.length-1 ? 'none' : '1px solid rgba(255,255,255,0.04)' }}>
          <div style={{ display:'flex', flexDirection:'column', alignItems:'center', flexShrink:0 }}>
            <div style={{ width:8, height:8, borderRadius:'50%', background:e.color,
              boxShadow:`0 0 6px ${e.color}`,
              animation: i === 0 ? 'j-blink 1.5s infinite' : 'none' }} />
            {i < events.length-1 && (
              <div style={{ width:1, flex:1, marginTop:4, background:'rgba(255,255,255,0.06)' }} />
            )}
          </div>
          <div style={{ flex:1, minWidth:0, paddingBottom: i === events.length-1 ? 0 : 4 }}>
            <div style={{ fontSize:11.5, color:J.textPri, letterSpacing:'0.1px', lineHeight:1.5 }}>{e.text}</div>
            <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut,
              marginTop:2, letterSpacing:'0.4px' }}>{e.time} · {e.type}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function AIStatusMini({ aiState, lastInput, transcript }) {
  const s = window.JSTATES[aiState] || window.JSTATES.IDLE;
  return (
    <div style={{ display:'flex', alignItems:'center', gap:14 }}>
      <window.MiniReactor variant="orbital" size={56} />
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
          <div style={{ width:6, height:6, borderRadius:'50%', background:s.col,
            boxShadow:`0 0 5px ${s.col}`, animation:'j-blink 1.5s infinite' }} />
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, fontWeight:700,
            letterSpacing:'1.8px', color:s.col }}>{s.label}</span>
        </div>
        <div style={{ fontSize:11, color:J.textSec, marginTop:6, lineHeight:1.5 }}>
          {aiState==='IDLE' && 'Ready for your command. All systems nominal.'}
          {aiState==='LISTENING' && (transcript ? `"${transcript}"` : 'Voice capture active…')}
          {aiState==='PROCESSING' && `Analyzing "${(lastInput||'').slice(0,40)}…"`}
          {aiState==='SPEAKING' && 'Generating response…'}
        </div>
      </div>
    </div>
  );
}

function AgendaRow({ item }) {
  const [done, setDone] = React.useState(item.done);
  return (
    <div style={{ display:'flex', alignItems:'center', gap:12, padding:'8px 4px',
      borderBottom:'1px solid rgba(255,255,255,0.04)' }}>
      <button onClick={() => setDone(d=>!d)} style={{
        width:18, height:18, borderRadius:5, cursor:'pointer', flexShrink:0,
        background: done ? ca(item.color, 0.25) : 'transparent',
        border:`1.5px solid ${done ? item.color : 'rgba(255,255,255,0.15)'}`,
        boxShadow: done ? `0 0 8px ${ca(item.color, 0.4)}` : 'none',
        display:'flex', alignItems:'center', justifyContent:'center',
        transition:'all 0.18s',
      }}>
        {done && <window.PageIcon name="check" size={10} color={item.color} />}
      </button>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:11.5, color: done ? J.textMut : J.textPri,
          textDecoration: done ? 'line-through' : 'none',
          opacity: done ? 0.6 : 1, transition:'all 0.2s', letterSpacing:'0.1px' }}>
          {item.text}
        </div>
      </div>
      <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:J.textMut, letterSpacing:'0.5px' }}>
        {item.time}
      </div>
    </div>
  );
}

function SystemPulseMini({ tick }) {
  // Live-ish values
  const cpu  = 8  + (Math.sin(tick * 0.7) * 6  + Math.random()*4 | 0);
  const ram  = 42 + (Math.sin(tick * 0.5) * 4  + Math.random()*2 | 0);
  const bat  = 87;
  const gpu  = 16 + (Math.sin(tick * 0.6) * 8  + Math.random()*5 | 0);

  return (
    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr 1fr', gap:12 }}>
      <PulseStat label="CPU"  value={cpu}  color={J.cyan}    />
      <PulseStat label="GPU"  value={gpu}  color={J.magenta} />
      <PulseStat label="RAM"  value={ram}  color={J.purple}  />
      <PulseStat label="BAT"  value={bat}  color={J.green}   />
    </div>
  );
}

function PulseStat({ label, value, color }) {
  return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:6 }}>
      <window.RingProgress value={value} color={color} size={52} />
      <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
        letterSpacing:'1.2px', color:J.textMut }}>{label}</div>
    </div>
  );
}

Object.assign(window, { HomePage });
