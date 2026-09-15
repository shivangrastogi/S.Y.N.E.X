// ─── JARVIS v5 — Automations Page ───────────────────────────────────────────
const { J, ca } = window;

const WORKFLOWS = [
  { id:'coding',  name:'Coding Mode',  desc:'Full dev environment, hands-free.',
    color:J.cyan, icon:'code',
    steps:['Open VS Code · last project','Launch Chrome with docs tabs','Start Spotify · Focus playlist','Set Focus theme · DND on'],
    triggers:['voice', 'morning 9am'], runs: 142, avgMs: 1840 },
  { id:'study',   name:'Study Mode',   desc:'Distraction-free deep work.',
    color:J.purple, icon:'brain',
    steps:['Open Notion · current notes','Calendar widget','Block social media','Pomodoro timer 25min'],
    triggers:['voice'], runs: 38, avgMs: 920 },
  { id:'edit',    name:'Editing Mode', desc:'Design + reference layout.',
    color:J.magenta, icon:'edit',
    steps:['Open Figma · last file','Reference images sidebar','Lo-fi playlist','Hide all notifications'],
    triggers:['voice', 'evening 6pm'], runs: 21, avgMs: 1240 },
  { id:'wind',    name:'Wind Down',    desc:'Close work, save state.',
    color:J.amber, icon:'moon',
    steps:['Save all open documents','Close work apps gracefully','Switch to Night theme','Set Do Not Disturb · 8h'],
    triggers:['voice', 'nightly 11pm'], runs: 67, avgMs: 720 },
  { id:'meeting', name:'Meeting Ready', desc:'Pre-meeting workspace.',
    color:J.green, icon:'check',
    steps:['Open Zoom · current meeting','Notes doc · meeting template','Mic check · level 65%','Mute background apps'],
    triggers:['calendar'], runs: 19, avgMs: 580 },
  { id:'morning', name:'Morning Brief', desc:'Daily intelligence summary.',
    color:J.cyan, icon:'sun',
    steps:['Weather + commute check','Calendar overview · top 3','Unread Slack messages','Read top news headlines'],
    triggers:['daily 7:30am'], runs: 89, avgMs: 1120 },
];

const RECENT_RUNS = [
  { workflow:'Coding Mode',  time:'14:32', status:'success', ms:1820, color:J.green  },
  { workflow:'Morning Brief',time:'07:30', status:'success', ms:1090, color:J.green  },
  { workflow:'Meeting Ready',time:'10:00', status:'success', ms:540,  color:J.green  },
  { workflow:'Coding Mode',  time:'09:14', status:'partial', ms:2010, color:J.amber  },
  { workflow:'Wind Down',    time:'yesterday 23:00', status:'success', ms:710,  color:J.green  },
];

function AutomationsPage({ onAction }) {
  const [query, setQuery] = React.useState('');
  const [selected, setSelected] = React.useState(WORKFLOWS[0]);
  const filtered = WORKFLOWS.filter(w =>
    !query || w.name.toLowerCase().includes(query.toLowerCase()) || w.desc.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <window.PageContainer>
      <window.PageHeader title="Automations"
        subtitle="Saved routines. Run them by voice, click, schedule, or trigger. JARVIS executes the steps for you."
        accent={J.amber}
        right={
          <div style={{ display:'flex', gap:8 }}>
            <window.SearchBar value={query} onChange={setQuery} placeholder="Search workflows…" width={240} />
            <window.PillButton icon="plus" color={J.amber} primary>New Workflow</window.PillButton>
          </div>
        } />

      <div style={{ flex:1, overflow:'hidden', padding:'18px 32px 28px', display:'flex', gap:16 }}>

        {/* Left — workflow list */}
        <div style={{ flex:1, display:'flex', flexDirection:'column', gap:16, minWidth:0 }}>
          {/* Stats */}
          <div style={{ display:'flex', gap:10 }}>
            <window.StatTile label="ACTIVE"      value="6"      sub="6 workflows" color={J.amber}  icon={<window.PageIcon name="bolt"/>} />
            <window.StatTile label="RUNS · 7d"   value="376"    sub="↑ 22% vs prior" color={J.green} icon={<window.PageIcon name="trend"/>} />
            <window.StatTile label="TIME SAVED"  value="14h"    sub="this week" color={J.cyan}   icon={<window.PageIcon name="clock"/>} />
            <window.StatTile label="AVG LATENCY" value="1.2s"   sub="98.4% success" color={J.purple} icon={<window.PageIcon name="spark"/>} />
          </div>

          {/* Workflow cards grid */}
          <window.PageCard title="WORKFLOW LIBRARY" subtitle={`${filtered.length} of ${WORKFLOWS.length} workflows`} accent={J.amber} fullHeight
            style={{ flex:1, minHeight:0 }}>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, overflowY:'auto', paddingRight:4 }}>
              {filtered.map(w => (
                <WorkflowCard key={w.id} w={w}
                  selected={selected?.id === w.id}
                  onClick={() => setSelected(w)}
                  onRun={() => onAction(`Run ${w.name}`)} />
              ))}
            </div>
          </window.PageCard>
        </div>

        {/* Right — detail + recent runs */}
        <div style={{ width:340, flexShrink:0, display:'flex', flexDirection:'column', gap:16 }}>
          {selected && <WorkflowDetail w={selected} onRun={() => onAction(`Run ${selected.name}`)} />}

          <window.PageCard title="RECENT RUNS" subtitle="Last 5 executions" accent={J.green}>
            {RECENT_RUNS.map((r, i) => (
              <div key={i} style={{ display:'flex', alignItems:'center', gap:10, padding:'8px 4px',
                borderBottom: i === RECENT_RUNS.length-1 ? 'none' : '1px solid rgba(255,255,255,0.04)' }}>
                <div style={{ width:5, height:5, borderRadius:'50%', background:r.color,
                  boxShadow:`0 0 4px ${r.color}` }} />
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ fontSize:11, color:J.textPri, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                    {r.workflow}
                  </div>
                  <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut,
                    marginTop:2, letterSpacing:'0.3px' }}>{r.time} · {r.ms}ms</div>
                </div>
                <window.STag text={r.status.toUpperCase()} color={r.color} />
              </div>
            ))}
          </window.PageCard>
        </div>
      </div>
    </window.PageContainer>
  );
}

function WorkflowCard({ w, selected, onClick, onRun }) {
  const [hov, setHov] = React.useState(false);
  return (
    <div onClick={onClick}
      onMouseEnter={()=>setHov(true)} onMouseLeave={()=>setHov(false)}
      style={{
        padding:'14px 14px', borderRadius:10, cursor:'pointer', position:'relative',
        background: selected ? ca(w.color, 0.08) : hov ? 'rgba(255,255,255,0.025)' : 'rgba(13,21,37,0.5)',
        border:`1px solid ${selected ? ca(w.color, 0.5) : hov ? ca(w.color, 0.2) : 'rgba(30,41,59,0.6)'}`,
        boxShadow: selected ? `0 0 18px ${ca(w.color, 0.18)}` : 'none',
        transition:'all 0.2s', overflow:'hidden',
      }}>
      <div style={{ position:'absolute', top:0, left:14, right:14, height:1.5, borderRadius:1,
        background:`linear-gradient(90deg, transparent, ${w.color}, transparent)`,
        opacity: selected ? 0.7 : 0.25, transition:'opacity 0.2s' }} />

      <div style={{ display:'flex', alignItems:'flex-start', gap:11, marginBottom:8 }}>
        <div style={{ width:34, height:34, borderRadius:8, flexShrink:0,
          background:ca(w.color, 0.12), border:`1px solid ${ca(w.color, 0.3)}`,
          display:'flex', alignItems:'center', justifyContent:'center', color:w.color,
        }}><window.PageIcon name={w.icon} size={15}/></div>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontSize:13, fontWeight:600, color:J.textPri, letterSpacing:'0.1px' }}>{w.name}</div>
          <div style={{ fontSize:10, color:J.textMut, marginTop:2, lineHeight:1.4 }}>{w.desc}</div>
        </div>
      </div>

      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginTop:10 }}>
        <div style={{ display:'flex', gap:5 }}>
          {w.triggers.map(t => (
            <span key={t} style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, fontWeight:700,
              letterSpacing:'0.5px', color:J.textMut,
              padding:'2px 6px', borderRadius:4, background:'rgba(255,255,255,0.04)',
              border:'1px solid rgba(255,255,255,0.06)' }}>{t}</span>
          ))}
        </div>
        <button onClick={e => { e.stopPropagation(); onRun(); }} style={{
          padding:'4px 10px', borderRadius:6, cursor:'pointer',
          background: ca(w.color, 0.14), border:`1px solid ${ca(w.color, 0.4)}`,
          fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
          letterSpacing:'1.2px', color:w.color, transition:'all 0.15s',
        }}>▶ RUN</button>
      </div>
    </div>
  );
}

function WorkflowDetail({ w, onRun }) {
  return (
    <window.PageCard title={w.name.toUpperCase()} subtitle={w.desc} accent={w.color}
      right={<window.PillButton icon="play" color={w.color} primary onClick={onRun}>Execute</window.PillButton>}>

      {/* Stats */}
      <div style={{ display:'flex', gap:8, marginBottom:12 }}>
        <MiniMetric label="RUNS"     value={w.runs} color={w.color} />
        <MiniMetric label="AVG TIME" value={`${w.avgMs}ms`} color={w.color} />
        <MiniMetric label="SUCCESS"  value="99%" color={J.green} />
      </div>

      {/* Steps */}
      <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
        letterSpacing:'1.5px', color:J.textMut, marginBottom:8 }}>STEPS</div>
      <div>
        {w.steps.map((s, i) => (
          <div key={i} style={{ display:'flex', gap:10, alignItems:'flex-start',
            padding:'6px 0', borderBottom: i === w.steps.length-1 ? 'none' : '1px solid rgba(255,255,255,0.04)' }}>
            <div style={{ width:18, height:18, borderRadius:'50%', flexShrink:0,
              background:ca(w.color, 0.12), border:`1px solid ${ca(w.color, 0.35)}`,
              display:'flex', alignItems:'center', justifyContent:'center',
              fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700, color:w.color }}>
              {i+1}
            </div>
            <div style={{ flex:1, fontSize:11, color:J.textPri, lineHeight:1.5, letterSpacing:'0.1px' }}>
              {s}
            </div>
          </div>
        ))}
      </div>
    </window.PageCard>
  );
}

function MiniMetric({ label, value, color }) {
  return (
    <div style={{ flex:1, padding:'8px 10px', borderRadius:7,
      background:'rgba(255,255,255,0.02)', border:'1px solid rgba(255,255,255,0.04)' }}>
      <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, fontWeight:700,
        letterSpacing:'1.4px', color:J.textMut }}>{label}</div>
      <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:14, fontWeight:700,
        color, marginTop:3, letterSpacing:'0.3px' }}>{value}</div>
    </div>
  );
}

Object.assign(window, { AutomationsPage });
