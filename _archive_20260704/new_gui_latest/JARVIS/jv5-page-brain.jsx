// ─── JARVIS v5 — Brain Page (Intent + Pattern Explorer) ─────────────────────
const { J, ca } = window;

const INTENTS = [
  { name:'open_app',         category:'Action',     conf:99.2, patterns:48, last:'2m ago',  color:J.cyan    },
  { name:'weather_query',    category:'Knowledge',  conf:98.8, patterns:23, last:'8m ago',  color:J.cyan    },
  { name:'system_check',     category:'System',     conf:99.6, patterns:31, last:'12m ago', color:J.green   },
  { name:'music_control',    category:'Action',     conf:97.4, patterns:38, last:'18m ago', color:J.purple  },
  { name:'schedule_meeting', category:'Calendar',   conf:96.1, patterns:19, last:'1h ago',  color:J.amber   },
  { name:'general_query',    category:'Knowledge',  conf:94.7, patterns:82, last:'just now',color:J.cyan    },
  { name:'greeting',         category:'Social',     conf:99.8, patterns:14, last:'4h ago',  color:J.green   },
  { name:'memory_recall',    category:'Memory',     conf:98.2, patterns:27, last:'45m ago', color:J.amber   },
  { name:'volume_control',   category:'Action',     conf:99.1, patterns:11, last:'3m ago',  color:J.purple  },
];

const SAMPLE_UTTERANCES = {
  open_app:         ['"chrome kholo"', '"open VS Code"', '"launch Spotify"', '"start figma"'],
  weather_query:    ['"mausam kaisa hai"', '"weather batao"', '"will it rain today"', '"temperature kya hai"'],
  system_check:     ['"CPU status batao"', '"system health"', '"how much RAM"', '"battery level"'],
  music_control:    ['"play lo-fi"', '"gana chalao"', '"volume up"', '"next track"'],
  schedule_meeting: ['"set a meeting at 4"', '"schedule call with team"', '"remind me at 3pm"'],
  general_query:    ['"what is X"', '"explain Y"', '"tell me about Z"'],
  greeting:         ['"hey AERIS"', '"good morning"', '"hello"', '"namaste"'],
  memory_recall:    ['"what did I say earlier"', '"yesterday\'s notes"', '"last project"'],
  volume_control:   ['"volume 60"', '"awaaz badhao"', '"mute"', '"louder"'],
};

const CONF_HISTORY = Array.from({ length: 14 }, (_, i) => 92 + Math.sin(i * 0.6) * 4 + Math.random() * 3);

function BrainPage() {
  const [selected, setSelected] = React.useState(INTENTS[0]);
  const [category, setCategory] = React.useState('all');
  const cats = ['all', 'Action', 'Knowledge', 'System', 'Calendar', 'Social', 'Memory'];
  const filtered = INTENTS.filter(i => category === 'all' || i.category === category);

  return (
    <window.PageContainer>
      <window.PageHeader title="Brain"
        subtitle="The neural core of A.E.R.I.S. 21 intents, 301 patterns, learning every day."
        accent={J.cyan}
        badge={{ text:'ACTIVE', color:J.green }}
        right={<window.PillButton icon="spark" color={J.cyan} primary>Train New Intent</window.PillButton>}
      />

      <div style={{ flex:1, overflow:'hidden', padding:'18px 32px 28px',
        display:'grid', gridTemplateColumns:'1fr 1fr', gap:16, minHeight:0 }}>

        {/* LEFT column */}
        <div style={{ display:'flex', flexDirection:'column', gap:14, minHeight:0 }}>
          {/* Hero: neural network viz */}
          <window.PageCard title="NEURAL NETWORK" subtitle="Live intent recognition graph" accent={J.cyan}
            right={<window.STag text="LIVE" color={J.green} />}>
            <NeuralVisualization />
            <div style={{ display:'flex', gap:8, marginTop:12 }}>
              <MiniStat label="INTENTS"  value="21"    color={J.cyan}    />
              <MiniStat label="PATTERNS" value="301"   color={J.purple}  />
              <MiniStat label="ACCURACY" value="99.8%" color={J.green}   />
              <MiniStat label="LATENCY"  value="84ms"  color={J.amber}   />
            </div>
          </window.PageCard>

          {/* Confidence history */}
          <window.PageCard title="CONFIDENCE HISTORY" subtitle="Last 14 days · rolling average" accent={J.purple}>
            <window.LineChart values={CONF_HISTORY} color={J.purple} height={70} max={100} />
            <div style={{ display:'flex', justifyContent:'space-between', marginTop:8 }}>
              <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut }}>14d ago</span>
              <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.cyan, fontWeight:700 }}>↑ +3.2% improvement</span>
              <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut }}>now</span>
            </div>
          </window.PageCard>
        </div>

        {/* RIGHT column */}
        <div style={{ display:'flex', flexDirection:'column', gap:14, minHeight:0 }}>
          {/* Intent list */}
          <window.PageCard title="INTENT CLASSIFIER" subtitle={`${filtered.length} intents in ${category === 'all' ? 'all categories' : category}`}
            accent={J.cyan} fullHeight style={{ flex:1, minHeight:0 }}
            right={
              <div style={{ display:'flex', gap:4, flexWrap:'wrap' }}>
                {cats.map(c => (
                  <button key={c} onClick={() => setCategory(c)} style={{
                    padding:'3px 8px', borderRadius:5, cursor:'pointer',
                    fontFamily:"'JetBrains Mono',monospace", fontSize:8, fontWeight:700, letterSpacing:'0.8px',
                    background: category === c ? ca(J.cyan, 0.15) : 'transparent',
                    border:`1px solid ${category === c ? ca(J.cyan, 0.4) : 'rgba(255,255,255,0.08)'}`,
                    color: category === c ? J.cyan : J.textMut,
                  }}>{c.toUpperCase()}</button>
                ))}
              </div>
            }>
            <div style={{ overflowY:'auto', height:'100%' }}>
              {filtered.map(intent => (
                <IntentRow key={intent.name} intent={intent}
                  selected={selected?.name === intent.name}
                  onClick={() => setSelected(intent)} />
              ))}
            </div>
          </window.PageCard>

          {/* Pattern detail */}
          {selected && <PatternDetail intent={selected} />}
        </div>
      </div>
    </window.PageContainer>
  );
}

function NeuralVisualization() {
  // 3 input layer, 4 hidden, 3 output. SVG nodes with connections.
  const layers = [
    { x: 30,  count: 4, color: J.textMut },
    { x: 140, count: 6, color: J.cyan },
    { x: 250, count: 6, color: J.cyan },
    { x: 360, count: 4, color: J.green },
  ];
  const W = 400, H = 180;
  const nodes = layers.flatMap((layer, li) => {
    const spacing = H / (layer.count + 1);
    return Array.from({ length: layer.count }, (_, ni) => ({
      layer: li, x: layer.x, y: spacing * (ni + 1), color: layer.color, idx: ni,
    }));
  });

  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} style={{ display:'block' }}>
      {/* Connections */}
      {layers.slice(0, -1).map((layer, li) => {
        const next = layers[li + 1];
        return Array.from({ length: layer.count }).flatMap((_, i) =>
          Array.from({ length: next.count }, (_, j) => {
            const sp1 = H / (layer.count + 1);
            const sp2 = H / (next.count + 1);
            const active = (i + j + li) % 5 === 0;
            return (
              <line key={`${li}-${i}-${j}`}
                x1={layer.x} y1={sp1 * (i + 1)}
                x2={next.x}  y2={sp2 * (j + 1)}
                stroke={active ? ca(J.cyan, 0.4) : ca(J.cyan, 0.08)}
                strokeWidth="0.6"
                style={active ? { filter:`drop-shadow(0 0 2px ${J.cyan})` } : {}}
              />
            );
          })
        );
      })}
      {/* Nodes */}
      {nodes.map(n => (
        <g key={`${n.layer}-${n.idx}`}>
          <circle cx={n.x} cy={n.y} r="5" fill={n.color} opacity="0.85"
            style={{
              filter:`drop-shadow(0 0 4px ${n.color})`,
              animation:`j-blink ${1.5 + (n.layer + n.idx) * 0.18}s ease-in-out ${(n.layer + n.idx) * 0.12}s infinite`,
            }} />
          <circle cx={n.x} cy={n.y} r="9" fill={n.color} opacity="0.1" />
        </g>
      ))}
      {/* Layer labels */}
      {['INPUT', 'HIDDEN', 'HIDDEN', 'OUTPUT'].map((l, i) => (
        <text key={i} x={layers[i].x} y={H - 4} textAnchor="middle"
          style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:7, fontWeight:700,
            letterSpacing:'1px', fill: J.textMut }}>{l}</text>
      ))}
    </svg>
  );
}

function MiniStat({ label, value, color }) {
  return (
    <div style={{ flex:1, padding:'8px 10px', borderRadius:7,
      background:'rgba(255,255,255,0.02)', border:'1px solid rgba(255,255,255,0.04)' }}>
      <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, fontWeight:700,
        letterSpacing:'1.4px', color:J.textMut }}>{label}</div>
      <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:15, fontWeight:700,
        color, marginTop:3, letterSpacing:'0.3px',
        textShadow:`0 0 8px ${ca(color, 0.3)}` }}>{value}</div>
    </div>
  );
}

function IntentRow({ intent, selected, onClick }) {
  const [hov, setHov] = React.useState(false);
  return (
    <div onClick={onClick}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{
        display:'flex', alignItems:'center', gap:10, padding:'8px 10px', borderRadius:7,
        background: selected ? ca(intent.color, 0.08) : hov ? 'rgba(255,255,255,0.025)' : 'transparent',
        border:`1px solid ${selected ? ca(intent.color, 0.4) : 'transparent'}`,
        marginBottom:3, cursor:'pointer', transition:'all 0.15s',
        position:'relative',
      }}>
      {selected && (
        <div style={{ position:'absolute', left:-1, top:8, bottom:8, width:2,
          background:intent.color, borderRadius:'0 2px 2px 0',
          boxShadow:`0 0 5px ${intent.color}` }} />
      )}
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:11, fontWeight:600,
            color: selected ? J.textPri : J.textSec, letterSpacing:'0.2px' }}>{intent.name}</span>
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, color:J.textMut,
            letterSpacing:'1px', padding:'1px 5px', borderRadius:3,
            background:'rgba(255,255,255,0.04)' }}>{intent.category}</span>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:10, marginTop:4 }}>
          <div style={{ flex:1, height:3, borderRadius:2, background:'rgba(255,255,255,0.05)', overflow:'hidden', maxWidth:140 }}>
            <div style={{ width:`${intent.conf}%`, height:'100%',
              background:`linear-gradient(90deg, ${ca(intent.color,0.5)}, ${intent.color})`,
              boxShadow:`0 0 4px ${intent.color}` }} />
          </div>
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
            color:intent.color, minWidth:36 }}>{intent.conf}%</span>
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut,
            minWidth:46, textAlign:'right' }}>{intent.patterns} pats</span>
        </div>
      </div>
    </div>
  );
}

function PatternDetail({ intent }) {
  const samples = SAMPLE_UTTERANCES[intent.name] || ['No samples available'];
  return (
    <window.PageCard title="PATTERN EXAMPLES" subtitle={intent.name} accent={intent.color}>
      <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
        {samples.map((s, i) => (
          <div key={i} style={{
            padding:'7px 11px', borderRadius:6,
            background:ca(intent.color, 0.05),
            border:`1px solid ${ca(intent.color, 0.15)}`,
            fontFamily:"'JetBrains Mono',monospace", fontSize:10.5, color:J.textPri,
            letterSpacing:'0.2px',
          }}>{s}</div>
        ))}
      </div>
      <div style={{ display:'flex', justifyContent:'space-between', marginTop:10, padding:'8px 4px 0',
        borderTop:'1px solid rgba(255,255,255,0.04)' }}>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut }}>
          Last triggered <span style={{ color:J.textSec }}>{intent.last}</span>
        </span>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:intent.color, fontWeight:700 }}>
          {intent.patterns} learned patterns
        </span>
      </div>
    </window.PageCard>
  );
}

Object.assign(window, { BrainPage });
