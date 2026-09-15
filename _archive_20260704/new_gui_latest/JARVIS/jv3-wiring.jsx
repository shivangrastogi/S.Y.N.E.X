// ─── JARVIS v3.1 — Tech-Wiring System (4 nodes, X-pattern) ──────────────────

const { J, ca } = window;

// Reactor sits at (540, 390) in the 1080×820 center area.
// 4 nodes in X layout — all within safe bounds (clear of dock + chat).

const NODES_4 = [
  { id:'cpu', label:'CPU',     value:'12%',     sub:'Intel i9-13900K', detail:'8P+16E cores · 125W TDP · Boost 5.8GHz', color:J.cyan,    left:188, top:156 },
  { id:'ram', label:'RAM',     value:'4.2 GB',  sub:'16 GB DDR5-6000', detail:'Dual channel · XMP 6000MHz · 32-36-36-76', color:J.purple,  left:748, top:156 },
  { id:'bat', label:'BATTERY', value:'87%',     sub:'6h 20m remain',   detail:'68Wh · 45W fast charge · 2.1W idle drain',  color:J.magenta, left:188, top:506 },
  { id:'net', label:'NETWORK', value:'1.4 MB/s',sub:'WiFi 6 · Online', detail:'Intel AX210 · -42dBm · 867Mbps link',       color:J.green,   left:748, top:506 },
];

// Wire paths — orthogonal PCB traces forming an X through reactor
const WIRES_4 = [
  { id:'cpu', d:'M540,390 L540,278 L332,278 L332,190', color:J.cyan    },
  { id:'ram', d:'M540,390 L540,278 L748,278 L748,190', color:J.purple  },
  { id:'bat', d:'M540,390 L540,502 L332,502 L332,540', color:J.magenta },
  { id:'net', d:'M540,390 L540,502 L748,502 L748,540', color:J.green   },
];

// Junctions at bends
const JUNCTIONS_4 = [
  { x:540, y:278, color:J.cyan    },
  { x:332, y:278, color:J.cyan    },
  { x:748, y:278, color:J.purple  },
  { x:540, y:502, color:J.magenta },
  { x:332, y:502, color:J.magenta },
  { x:748, y:502, color:J.green   },
];

// ── Animated wire ─────────────────────────────────────────────────────────────
function Wire4({ def, aiState }) {
  const spd = aiState === 'PROCESSING' ? 0.9 : aiState === 'LISTENING' ? 1.4 : aiState === 'SPEAKING' ? 1.2 : 2.2;
  return (
    <g>
      {/* Base glow line */}
      <path d={def.d} stroke={def.color} strokeWidth="1.5" fill="none"
        opacity="0.15" pathLength="100" />
      {/* Brighter mid line */}
      <path d={def.d} stroke={def.color} strokeWidth="1" fill="none"
        opacity="0.35" pathLength="100" />
      {/* Packet 1 */}
      <path d={def.d} stroke={def.color} strokeWidth="2" fill="none"
        opacity="0.9" pathLength="100" strokeLinecap="round"
        style={{
          filter:`drop-shadow(0 0 3px ${def.color})`,
          strokeDasharray:'10 90',
          animation:`wire-flow ${spd}s linear 0s infinite`,
        }} />
      {/* Packet 2 — trailing */}
      <path d={def.d} stroke={def.color} strokeWidth="1.5" fill="none"
        opacity="0.5" pathLength="100" strokeLinecap="round"
        style={{
          strokeDasharray:'5 95',
          animation:`wire-flow ${spd * 1.7}s linear ${spd * 0.55}s infinite`,
        }} />
    </g>
  );
}

// ── Node box with amazing hover ───────────────────────────────────────────────
function NodeBox4({ node, liveVals }) {
  const [hov, setHov] = React.useState(false);
  const val = (liveVals && liveVals[node.id]) || node.value;

  const bars = [45,62,38,75,58,82,49,70];

  const ICON = {
    cpu: <><rect x="4" y="4" width="10" height="10" rx="1.2" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M7 4V2M11 4V2M7 16v-2M11 16v-2M4 7H2M4 11H2M16 7h-2M16 11h-2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/><circle cx="9" cy="9" r="2" stroke="currentColor" strokeWidth="1" fill="none"/></>,
    ram: <><rect x="2" y="5" width="14" height="8" rx="1.2" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M5 5V3M9 5V3M13 5V3M5 13v2M9 13v2M13 13v2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/><line x1="5" y1="9" x2="13" y2="9" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/></>,
    bat: <><rect x="2" y="5" width="12" height="8" rx="1.5" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M14 7.5v3" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/><rect x="4" y="7" width="6" height="4" rx="0.5" fill="currentColor" opacity="0.75"/></>,
    net: <><circle cx="9" cy="9" r="6.5" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M2 9h14M9 2c-2.5 2.5-3 4.8-3 7s.5 4.5 3 7M9 2c2.5 2.5 3 4.8 3 7s-.5 4.5-3 7" stroke="currentColor" strokeWidth="1.2" fill="none"/></>,
  };

  return (
    <div
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        position:'absolute', left:node.left, top:node.top,
        width:144, zIndex:15, cursor:'default',
        transition:'all 0.25s cubic-bezier(0.4,0,0.2,1)',
        transform: hov ? 'scale(1.06) translateY(-2px)' : 'scale(1)',
        transformOrigin: node.left < 400 ? 'left center' : 'right center',
      }}
    >
      {/* Main card */}
      <div style={{
        width:'100%', borderRadius:12,
        background: hov ? 'rgba(13,21,37,0.98)' : 'rgba(10,15,28,0.88)',
        backdropFilter:'blur(14px)',
        border:`1px solid ${hov ? ca(node.color,0.65) : ca(node.color,0.3)}`,
        boxShadow: hov
          ? `0 0 28px ${ca(node.color,0.35)}, 0 0 60px ${ca(node.color,0.12)}, 0 8px 32px rgba(0,0,0,0.6), inset 0 1px 0 ${ca(node.color,0.15)}`
          : `0 0 8px ${ca(node.color,0.1)}, 0 4px 16px rgba(0,0,0,0.4)`,
        padding:'10px 12px 8px',
        overflow:'hidden',
        transition:'all 0.25s ease',
      }}>
        {/* Scan line on hover */}
        {hov && (
          <div style={{ position:'absolute', left:0, right:0, height:1,
            background:`linear-gradient(90deg,transparent,${node.color},transparent)`,
            animation:'j-scan 1.5s linear infinite', opacity:0.6 }} />
        )}

        {/* Top accent bar */}
        <div style={{ position:'absolute', top:0, left:20, right:20, height:1.5, borderRadius:1,
          background:`linear-gradient(90deg,transparent,${node.color},transparent)`,
          opacity: hov ? 0.8 : 0.3, transition:'opacity 0.25s' }} />

        {/* Header row */}
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:6 }}>
          <div style={{ display:'flex', alignItems:'center', gap:6 }}>
            <div style={{ color:node.color, opacity:hov?1:0.8, transition:'opacity 0.2s' }}>
              <svg width="13" height="13" viewBox="0 0 18 18" fill="none">{ICON[node.id]}</svg>
            </div>
            <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5, fontWeight:700,
              letterSpacing:'1.5px', color:node.color }}>{node.label}</span>
          </div>
          <div style={{ width:5, height:5, borderRadius:'50%', background:node.color,
            boxShadow:`0 0 ${hov?8:4}px ${node.color}`,
            animation:'j-blink 2s ease-in-out infinite',
            transition:'box-shadow 0.2s' }} />
        </div>

        {/* Value */}
        <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:20, fontWeight:700,
          color:node.color, lineHeight:1, letterSpacing:'0.5px',
          textShadow:`0 0 ${hov?18:8}px ${ca(node.color,hov?0.7:0.4)}`,
          transition:'text-shadow 0.25s' }}>{val}</div>

        {/* Sub label */}
        <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, color:J.textMut,
          marginTop:4, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>
          {node.sub}
        </div>

        {/* Sparkline */}
        <div style={{ display:'flex', gap:2, alignItems:'flex-end', height:18, marginTop:6 }}>
          {bars.map((h,i) => (
            <div key={i} style={{ flex:1, borderRadius:1.5,
              background:`linear-gradient(180deg,${node.color},${ca(node.color,0.25)})`,
              height:`${hov ? h : h*0.7}%`, minHeight:2,
              opacity: hov ? 0.8+(i/bars.length)*0.2 : 0.45+(i/bars.length)*0.25,
              transition:`height 0.4s ${i*0.04}s ease, opacity 0.3s` }} />
          ))}
        </div>
      </div>

      {/* Hover detail card — slides down */}
      <div style={{
        marginTop:4, borderRadius:10, overflow:'hidden',
        maxHeight: hov ? 80 : 0,
        opacity: hov ? 1 : 0,
        transition:'max-height 0.3s cubic-bezier(0.4,0,0.2,1), opacity 0.25s ease',
        background:'rgba(10,15,28,0.95)',
        backdropFilter:'blur(12px)',
        border: hov ? `1px solid ${ca(node.color,0.3)}` : 'none',
        boxShadow: hov ? `0 0 16px ${ca(node.color,0.15)}` : 'none',
      }}>
        <div style={{ padding:'8px 12px' }}>
          <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, color:J.textMut,
            lineHeight:1.7, letterSpacing:'0.3px' }}>{node.detail}</div>
          {/* Mini status row */}
          <div style={{ display:'flex', gap:6, marginTop:5, alignItems:'center' }}>
            <div style={{ width:4,height:4,borderRadius:'50%', background:J.green,
              boxShadow:`0 0 4px ${J.green}` }} />
            <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:7.5,
              color:J.green, fontWeight:700 }}>NOMINAL</span>
            <div style={{ flex:1,height:1,background:`linear-gradient(90deg,${ca(node.color,0.3)},transparent)` }} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Full wiring layer ─────────────────────────────────────────────────────────
function WiringSystem({ aiState, liveVals }) {
  return (
    <div style={{ position:'absolute', inset:0, pointerEvents:'none' }}>
      {/* SVG wires + junctions */}
      <svg width="1080" height="820" viewBox="0 0 1080 820"
        style={{ position:'absolute', inset:0, overflow:'visible' }}>
        {WIRES_4.map(w => <Wire4 key={w.id} def={w} aiState={aiState} />)}
        {JUNCTIONS_4.map((j,i) => (
          <g key={i}>
            <circle cx={j.x} cy={j.y} r="4" fill={j.color} opacity="0.75"
              style={{ filter:`drop-shadow(0 0 3px ${j.color})`,
                animation:`j-blink ${1.8+i*0.25}s ease-in-out ${i*0.15}s infinite` }} />
            <circle cx={j.x} cy={j.y} r="7.5" fill={j.color} opacity="0.1" />
          </g>
        ))}
        {/* Origin pulse ring at reactor center */}
        <circle cx="540" cy="390" r="238" fill="none"
          stroke="rgba(0,212,255,0.07)" strokeWidth="1" strokeDasharray="3 8" />
      </svg>

      {/* Node boxes */}
      <div style={{ position:'absolute', inset:0, pointerEvents:'auto' }}>
        {NODES_4.map(node => (
          <NodeBox4 key={node.id} node={node} liveVals={liveVals} />
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { WiringSystem });
