// ─── JARVIS v5 — Window Controls + Page Primitives ───────────────────────────
const { J, ca } = window;

// ─── WINDOW CONTROLS (min/max/close) ────────────────────────────────────────
function WindowControls({ onMinimize, onMaximize, onClose }) {
  const [hovered, setHovered] = React.useState(null);
  const buttons = [
    { id:'min',   color:'#FBBF24', tip:'Minimize',  onClick:onMinimize,
      icon: <line x1="2" y1="5" x2="8" y2="5" stroke="rgba(0,0,0,0.65)" strokeWidth="1.5" strokeLinecap="round"/> },
    { id:'max',   color:'#34D399', tip:'Maximize',  onClick:onMaximize,
      icon: <rect x="2" y="2" width="6" height="6" rx="0.5" fill="none" stroke="rgba(0,0,0,0.65)" strokeWidth="1.4"/> },
    { id:'close', color:'#F87171', tip:'Close',     onClick:onClose,
      icon: <><line x1="2.5" y1="2.5" x2="7.5" y2="7.5" stroke="rgba(0,0,0,0.7)" strokeWidth="1.6" strokeLinecap="round"/><line x1="7.5" y1="2.5" x2="2.5" y2="7.5" stroke="rgba(0,0,0,0.7)" strokeWidth="1.6" strokeLinecap="round"/></> },
  ];
  return (
    <div
      onMouseEnter={() => setHovered('group')}
      onMouseLeave={() => setHovered(null)}
      style={{ display:'flex', gap:8 }}
    >
      {buttons.map(b => (
        <button key={b.id} onClick={b.onClick} title={b.tip}
          style={{
            width:13, height:13, borderRadius:'50%',
            background: b.color, border:`1px solid rgba(0,0,0,0.2)`,
            display:'flex', alignItems:'center', justifyContent:'center',
            cursor:'pointer', padding:0, transition:'transform 0.15s, box-shadow 0.15s',
            boxShadow: hovered === 'group' ? `0 0 6px ${b.color}` : 'none',
          }}>
          <svg width="10" height="10" viewBox="0 0 10 10" style={{
            opacity: hovered === 'group' ? 1 : 0,
            transition: 'opacity 0.15s',
          }}>{b.icon}</svg>
        </button>
      ))}
    </div>
  );
}

// ─── PAGE WRAPPER + HEADER ──────────────────────────────────────────────────
function PageHeader({ title, subtitle, accent = J.cyan, badge = null, right = null }) {
  return (
    <div style={{
      padding:'24px 32px 18px',
      borderBottom:'1px solid rgba(30,41,59,0.5)',
      background:'linear-gradient(180deg, rgba(13,21,37,0.4), transparent)',
      display:'flex', justifyContent:'space-between', alignItems:'flex-end', gap:24,
      flexShrink:0,
    }}>
      <div>
        <div style={{
          fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
          letterSpacing:'2.5px', color:accent, marginBottom:8,
        }}>WORKSPACE · {title.toUpperCase()}</div>
        <div style={{ display:'flex', alignItems:'center', gap:10 }}>
          <span style={{ fontSize:24, fontWeight:600, color:J.textPri, letterSpacing:'-0.3px' }}>{title}</span>
          {badge && <window.STag {...badge} />}
        </div>
        {subtitle && (
          <div style={{ fontSize:12, color:J.textSec, marginTop:6, lineHeight:1.5, maxWidth:600 }}>
            {subtitle}
          </div>
        )}
      </div>
      {right}
    </div>
  );
}

// Animated page container — reserves left space for the floating dock (56px + 12px gutter)
function PageContainer({ children }) {
  return (
    <div style={{
      width:'100%', height:'100%', display:'flex', flexDirection:'column',
      overflow:'hidden', animation:'j-fadein 0.35s ease',
      position:'relative',
      paddingLeft: 80,
    }}>
      {/* Subtle grid background */}
      <div style={{ position:'absolute', inset:0, pointerEvents:'none',
        backgroundImage:`linear-gradient(rgba(0,212,255,0.012) 1px, transparent 1px),linear-gradient(90deg, rgba(0,212,255,0.012) 1px, transparent 1px)`,
        backgroundSize:'48px 48px' }} />
      <div style={{ position:'relative', height:'100%', display:'flex', flexDirection:'column', minWidth:0 }}>
        {children}
      </div>
    </div>
  );
}

// Section card for page content
function PageCard({ title, subtitle, accent = J.cyan, children, right = null, fullHeight = false, style = {} }) {
  return (
    <div style={{
      borderRadius:12, position:'relative',
      background:'rgba(13,21,37,0.55)', backdropFilter:'blur(10px)',
      border:'1px solid rgba(30,41,59,0.65)',
      padding:'16px 18px',
      display:'flex', flexDirection:'column',
      height: fullHeight ? '100%' : 'auto',
      ...style,
    }}>
      {accent && (
        <div style={{ position:'absolute', left:0, top:14, bottom:14, width:2,
          background:accent, borderRadius:'0 2px 2px 0',
          boxShadow:`0 0 5px ${ca(accent,0.6)}` }} />
      )}
      {title && (
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:12 }}>
          <div>
            <div style={{
              fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
              letterSpacing:'1.8px', color:accent, marginBottom:3,
            }}>{title}</div>
            {subtitle && <div style={{ fontSize:11, color:J.textMut, letterSpacing:'0.2px' }}>{subtitle}</div>}
          </div>
          {right}
        </div>
      )}
      <div style={{ flex: fullHeight ? 1 : 'unset', minHeight:0 }}>
        {children}
      </div>
    </div>
  );
}

// Big stat tile
function StatTile({ label, value, sub, color = J.cyan, icon = null }) {
  return (
    <div style={{
      flex:1, padding:'18px 20px', borderRadius:12, position:'relative',
      background:'rgba(13,21,37,0.6)', border:`1px solid rgba(30,41,59,0.7)`,
      transition:'all 0.2s', overflow:'hidden',
    }}
    onMouseEnter={e => { e.currentTarget.style.borderColor=ca(color,0.35); e.currentTarget.style.boxShadow=`0 0 18px ${ca(color,0.12)}`; }}
    onMouseLeave={e => { e.currentTarget.style.borderColor='rgba(30,41,59,0.7)'; e.currentTarget.style.boxShadow='none'; }}
    >
      <div style={{ position:'absolute', top:0, left:14, right:14, height:1.5,
        background:`linear-gradient(90deg, transparent, ${color}, transparent)`, opacity:0.5 }} />

      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
          letterSpacing:'1.8px', color:J.textMut }}>{label}</div>
        {icon && <div style={{ color, opacity:0.85 }}>{icon}</div>}
      </div>
      <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:28, fontWeight:700,
        color, marginTop:8, lineHeight:1,
        textShadow:`0 0 14px ${ca(color,0.35)}` }}>{value}</div>
      {sub && (
        <div style={{ fontSize:10, color:J.textMut, marginTop:6, letterSpacing:'0.2px' }}>{sub}</div>
      )}
    </div>
  );
}

// Compact list row used in many pages
function ListRow({ icon, title, sub, right, color, onClick }) {
  const [hov, setHov] = React.useState(false);
  const isClickable = !!onClick;
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display:'flex', alignItems:'center', gap:12,
        padding:'10px 14px', borderRadius:8,
        background: hov && isClickable ? 'rgba(0,212,255,0.05)' : 'rgba(255,255,255,0.02)',
        border:`1px solid ${hov && isClickable ? ca(color || J.cyan, 0.2) : 'rgba(255,255,255,0.04)'}`,
        marginBottom:5, cursor: isClickable ? 'pointer' : 'default',
        transition:'all 0.18s',
      }}>
      {icon && (
        <div style={{ width:32, height:32, borderRadius:8, flexShrink:0,
          background: ca(color || J.cyan, 0.1),
          border:`1px solid ${ca(color || J.cyan, 0.25)}`,
          display:'flex', alignItems:'center', justifyContent:'center',
          color: color || J.cyan,
        }}>{icon}</div>
      )}
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:12, fontWeight:600, color:J.textPri, letterSpacing:'0.1px',
          overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{title}</div>
        {sub && (
          <div style={{ fontSize:10, color:J.textMut, marginTop:2, letterSpacing:'0.2px',
            overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{sub}</div>
        )}
      </div>
      {right && <div style={{ flexShrink:0 }}>{right}</div>}
    </div>
  );
}

// Bar chart
function BarChart({ data, color = J.cyan, height = 80 }) {
  const max = Math.max(...data.map(d => d.value), 1);
  return (
    <div style={{ display:'flex', alignItems:'flex-end', gap:6, height, padding:'4px 0' }}>
      {data.map((d, i) => {
        const h = (d.value / max) * (height - 16);
        return (
          <div key={i} style={{ flex:1, display:'flex', flexDirection:'column', alignItems:'center', gap:4 }}>
            <div style={{
              width:'100%', height:h, borderRadius:'3px 3px 1px 1px',
              background:`linear-gradient(180deg, ${color}, ${ca(color,0.3)})`,
              boxShadow:`0 0 6px ${ca(color,0.3)}`,
              animation:`j-fadein 0.4s ${i*0.05}s both ease`,
            }} />
            {d.label && (
              <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8,
                color:J.textMut, letterSpacing:'0.4px' }}>{d.label}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

// Realtime line chart (animated)
function LineChart({ values, color = J.cyan, height = 60, max = 100 }) {
  const w = 280;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = height - ((v / max) * (height - 8)) - 4;
    return `${x},${y}`;
  }).join(' ');
  const area = `0,${height} ${pts} ${w},${height}`;
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id={`grad-${color}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.4" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#grad-${color})`} />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5"
        style={{ filter:`drop-shadow(0 0 3px ${color})` }} />
      <circle cx={w} cy={height - ((values[values.length-1] / max) * (height - 8)) - 4}
        r="2.5" fill={color} style={{ filter:`drop-shadow(0 0 4px ${color})` }} />
    </svg>
  );
}

// Donut/ring progress
function RingProgress({ value, max = 100, color = J.cyan, size = 64, label }) {
  const r = (size - 12) / 2;
  const c = 2 * Math.PI * r;
  const off = c * (1 - value / max);
  return (
    <div style={{ position:'relative', width:size, height:size, display:'flex',
      alignItems:'center', justifyContent:'center' }}>
      <svg width={size} height={size} style={{ transform:'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none"
          stroke="rgba(255,255,255,0.06)" strokeWidth="4" />
        <circle cx={size/2} cy={size/2} r={r} fill="none"
          stroke={color} strokeWidth="4" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={off}
          style={{ filter:`drop-shadow(0 0 4px ${color})`, transition:'stroke-dashoffset 0.6s' }} />
      </svg>
      <div style={{ position:'absolute', textAlign:'center' }}>
        <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:13, fontWeight:700, color }}>{value}{label || '%'}</div>
      </div>
    </div>
  );
}

// Inline icon set used across pages
const PageIcons = {
  code:    <path d="M5 4L2 7l3 3M9 4l3 3-3 3" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinecap="round" strokeLinejoin="round"/>,
  chat:    <path d="M2 3h10v7H4l-2 2V3z" stroke="currentColor" strokeWidth="1.4" fill="none" strokeLinejoin="round"/>,
  bolt:    <path d="M8 1L3 8h4l-1 5 5-7H7l1-5z" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinejoin="round"/>,
  brain:   <><ellipse cx="7" cy="6" rx="3.5" ry="4.5" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M5 6h4M5 4h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></>,
  memory:  <><rect x="2" y="4" width="10" height="6" rx="1" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M5 4V2M9 4V2M5 10v2M9 10v2" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/></>,
  cpu:     <><rect x="3" y="3" width="8" height="8" rx="0.8" stroke="currentColor" strokeWidth="1.3" fill="none"/><rect x="5" y="5" width="4" height="4" stroke="currentColor" strokeWidth="1" fill="none"/></>,
  play:    <path d="M4 2l7 5-7 5V2z" stroke="currentColor" strokeWidth="1.3" fill="currentColor" strokeLinejoin="round"/>,
  pause:   <><rect x="3" y="2" width="3" height="10" rx="0.5" fill="currentColor"/><rect x="8" y="2" width="3" height="10" rx="0.5" fill="currentColor"/></>,
  clock:   <><circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M7 4v3l2 2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></>,
  spark:   <path d="M7 1v3M7 10v3M1 7h3M10 7h3M3 3l2 2M11 11l-2-2M11 3l-2 2M3 11l2-2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>,
  search:  <><circle cx="6" cy="6" r="3.5" stroke="currentColor" strokeWidth="1.3" fill="none"/><line x1="9" y1="9" x2="11" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></>,
  plus:    <><line x1="7" y1="2" x2="7" y2="12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><line x1="2" y1="7" x2="12" y2="7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></>,
  check:   <path d="M2 7l3 3 7-7" stroke="currentColor" strokeWidth="1.6" fill="none" strokeLinecap="round" strokeLinejoin="round"/>,
  trend:   <path d="M2 11l4-4 3 3 5-5" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>,
  trash:   <><path d="M3 4h8l-1 8H4L3 4zM5 4V2h4v2" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinejoin="round"/></>,
  edit:    <><path d="M2 12l1-3 7-7 2 2-7 7-3 1zM8 4l2 2" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinejoin="round"/></>,
  music:   <><circle cx="4" cy="11" r="1.5" stroke="currentColor" strokeWidth="1.3" fill="none"/><circle cx="11" cy="9" r="1.5" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M5.5 11V3l7-1.5v7.5" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinejoin="round"/></>,
  moon:    <path d="M11 8a4.5 4.5 0 1 1-5-5 3.5 3.5 0 0 0 5 5z" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinejoin="round"/>,
  sun:     <><circle cx="7" cy="7" r="2.5" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M7 1v2M7 11v2M1 7h2M11 7h2M2.5 2.5l1.5 1.5M10 10l1.5 1.5M11.5 2.5L10 4M4 10l-1.5 1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></>,
};

function PageIcon({ name, size = 14, color = 'currentColor' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 14 14" fill="none" style={{ color }}>
      {PageIcons[name] || PageIcons.cpu}
    </svg>
  );
}

// SearchBar atom
function SearchBar({ value, onChange, placeholder = 'Search…', width = 280 }) {
  return (
    <div style={{
      display:'flex', alignItems:'center', gap:8, padding:'6px 12px',
      width, borderRadius:8,
      background:'rgba(8,12,22,0.85)',
      border:'1px solid rgba(30,41,59,0.7)',
      transition:'border-color 0.2s',
    }}>
      <PageIcon name="search" size={13} color={J.textMut} />
      <input value={value} onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        style={{ flex:1, background:'transparent', border:'none', outline:'none',
          fontSize:11.5, color:J.textPri, fontFamily:"'JetBrains Mono',monospace",
          letterSpacing:'0.2px' }} />
    </div>
  );
}

// Pill button
function PillButton({ children, onClick, color = J.cyan, primary = false, icon = null }) {
  const [hov, setHov] = React.useState(false);
  return (
    <button onClick={onClick}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{
        display:'inline-flex', alignItems:'center', gap:6,
        padding:'6px 12px', borderRadius:8, cursor:'pointer',
        background: primary
          ? (hov ? `linear-gradient(135deg, ${color}, ${ca(color,0.6)})` : `linear-gradient(135deg, ${ca(color,0.85)}, ${ca(color,0.5)})`)
          : (hov ? ca(color, 0.12) : 'rgba(255,255,255,0.025)'),
        border:`1px solid ${primary ? color : (hov ? ca(color, 0.4) : 'rgba(255,255,255,0.08)')}`,
        boxShadow: primary ? `0 0 14px ${ca(color, 0.4)}` : (hov ? `0 0 10px ${ca(color, 0.15)}` : 'none'),
        fontSize:10.5, fontWeight:600, letterSpacing:'0.3px',
        color: primary ? '#0A0F1C' : (hov ? color : J.textSec),
        transition:'all 0.18s',
      }}>
      {icon && <PageIcon name={icon} size={11} />}
      {children}
    </button>
  );
}

Object.assign(window, {
  WindowControls, PageHeader, PageContainer, PageCard, StatTile,
  ListRow, BarChart, LineChart, RingProgress, SearchBar, PillButton,
  PageIcon, PageIcons,
});
