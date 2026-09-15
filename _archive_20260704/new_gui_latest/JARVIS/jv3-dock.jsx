// ─── JARVIS v3 — Floating Arc-Style Dock ─────────────────────────────────────

const DOCK_ITEMS = [
  { key:'home',      label:'Home',         icon:'home',      section:'core'    },
  { key:'chat',      label:'Conversations',icon:'chat',      section:'core'    },
  { key:'auto',      label:'Automations',  icon:'auto',      section:'core'    },
  null,
  { key:'brain',     label:'Brain',        icon:'brain',     section:'intel'   },
  { key:'memory',    label:'Memory',       icon:'memory',    section:'intel'   },
  null,
  { key:'system',    label:'System',       icon:'system',    section:'system'  },
  { key:'settings',  label:'Settings',     icon:'settings',  section:'system'  },
];

function DockIcon({ name, color = 'currentColor' }) {
  const icons = {
    home:     <><path d="M2 7L8 2l6 5v7H10V9H6v5H2z" stroke={color} strokeWidth="1.4" fill="none" strokeLinejoin="round"/></>,
    chat:     <><path d="M2 3h12v8H2z" stroke={color} strokeWidth="1.4" fill="none" strokeLinejoin="round"/><path d="M5 11l-2.5 2.5" stroke={color} strokeWidth="1.4" strokeLinecap="round"/></>,
    auto:     <><path d="M8 2v3M8 11v3M2 8h3M11 8h3" stroke={color} strokeWidth="1.4" strokeLinecap="round"/><circle cx="8" cy="8" r="3" stroke={color} strokeWidth="1.4" fill="none"/></>,
    brain:    <><ellipse cx="8" cy="7" rx="4" ry="5" stroke={color} strokeWidth="1.4" fill="none"/><path d="M6 12v2M10 12v2M5 7h6" stroke={color} strokeWidth="1.4" strokeLinecap="round"/></>,
    memory:   <><rect x="3" y="4" width="10" height="8" rx="1.5" stroke={color} strokeWidth="1.4" fill="none"/><path d="M6 4V2.5M10 4V2.5M6 12v1.5M10 12v1.5M3 8h10" stroke={color} strokeWidth="1.4" strokeLinecap="round"/></>,
    system:   <><rect x="2" y="3" width="12" height="9" rx="1.5" stroke={color} strokeWidth="1.4" fill="none"/><path d="M5 14h6M8 12v2" stroke={color} strokeWidth="1.4" strokeLinecap="round"/></>,
    settings: <><circle cx="8" cy="8" r="2.5" stroke={color} strokeWidth="1.4" fill="none"/><path d="M8 2v1.5M8 12.5V14M2 8h1.5M12.5 8H14M3.6 3.6l1 1M11.4 11.4l1 1M11.4 3.6l-1 1M3.6 11.4l1-1" stroke={color} strokeWidth="1.4" strokeLinecap="round"/></>,
  };
  return (
    <svg width="18" height="18" viewBox="0 0 16 16" fill="none" style={{ flexShrink:0 }}>
      {icons[name] || <circle cx="8" cy="8" r="4" stroke={color} strokeWidth="1.4" fill="none"/>}
    </svg>
  );
}

function DockItem({ item, active, expanded, onClick }) {
  const J = window.J;
  const [hov, setHov] = React.useState(false);
  const accent = active ? J.cyan : hov ? 'rgba(0,212,255,0.85)' : J.textMut;

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      title={!expanded ? item.label : ''}
      style={{
        display:'flex', alignItems:'center', gap:12,
        padding: expanded ? '9px 14px' : '9px 0',
        justifyContent: expanded ? 'flex-start' : 'center',
        borderRadius:10, cursor:'pointer', position:'relative',
        background: active  ? ca(J.cyan,0.09)  : hov ? ca(J.cyan,0.05) : 'transparent',
        border:`1px solid ${active ? ca(J.cyan,0.35) : hov ? ca(J.cyan,0.15) : 'transparent'}`,
        boxShadow: active ? `0 0 18px ${ca(J.cyan,0.18)}` : hov ? `0 0 10px ${ca(J.cyan,0.1)}` : 'none',
        transition:'all 0.22s ease',
        overflow:'hidden',
      }}
    >
      {/* Active edge trace */}
      {active && (
        <div style={{ position:'absolute', left:0, top:'20%', bottom:'20%', width:2, borderRadius:1,
          background:`linear-gradient(180deg, transparent, ${J.cyan}, transparent)`,
          boxShadow:`0 0 6px ${J.cyan}` }} />
      )}

      <DockIcon name={item.icon} color={accent} />

      {expanded && (
        <span style={{ fontSize:13, fontWeight: active ? 700 : 500, color: active ? J.textPri : hov ? 'rgb(210,225,240)' : J.textSec,
          transition:'color 0.2s', whiteSpace:'nowrap', letterSpacing:'0.1px' }}>
          {item.label}
        </span>
      )}

      {/* Hover glow dot */}
      {hov && !active && (
        <div style={{ position:'absolute', right:8, top:'50%', transform:'translateY(-50%)',
          width:4, height:4, borderRadius:'50%', background:J.cyan, opacity:0.6,
          boxShadow:`0 0 5px ${J.cyan}` }} />
      )}
    </div>
  );
}

function FloatingDock({ active, setActive }) {
  const J = window.J;
  const [hovered, setHovered] = React.useState(false);
  const expanded = hovered;

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        position:'absolute', left:12, top:'50%', transform:'translateY(-50%)',
        width: expanded ? 210 : 56,
        background:`rgba(13,21,37,0.88)`,
        backdropFilter:'blur(12px)',
        border:`1px solid ${expanded ? ca(J.cyan,0.2) : 'rgba(30,41,59,0.8)'}`,
        borderRadius:18,
        padding: expanded ? '14px 10px' : '14px 8px',
        display:'flex', flexDirection:'column', gap:3,
        transition:'width 0.32s cubic-bezier(0.4,0,0.2,1), border-color 0.3s, background 0.3s, padding 0.3s',
        boxShadow: expanded ? '0 8px 40px rgba(0,0,0,0.5), 0 0 24px rgba(0,212,255,0.08)' : '0 4px 24px rgba(0,0,0,0.4)',
        zIndex:50, overflow:'hidden',
      }}
    >
      {/* Logo mark */}
      <div style={{ display:'flex', alignItems:'center', justifyContent: expanded ? 'flex-start' : 'center',
        gap:10, paddingBottom:10, borderBottom:`1px solid ${ca(J.cyan,0.1)}`, marginBottom:4,
        paddingLeft: expanded ? 4 : 0 }}>
        <div style={{ position:'relative', width:30, height:30, flexShrink:0 }}>
          <div style={{ position:'absolute', inset:0, borderRadius:'50%', border:`1.5px solid ${ca(J.cyan,0.6)}`, animation:'j-spin 6s linear infinite' }} />
          <div style={{ position:'absolute', inset:5, borderRadius:'50%', border:`1px solid ${ca(J.cyan,0.4)}`, animation:'j-spin-rev 4s linear infinite' }} />
          <div style={{ position:'absolute', inset:10, borderRadius:'50%', background:J.cyan, boxShadow:`0 0 8px ${J.cyan}` }} />
        </div>
        {expanded && (
          <div>
            <div style={{ fontSize:12, fontWeight:700, letterSpacing:'1.5px', color:J.textPri, lineHeight:1.2 }}>A.E.R.I.S</div>
            <div style={{ fontSize:9, color:J.textMut, letterSpacing:'0.5px' }}>JARVIS v3.0</div>
          </div>
        )}
      </div>

      {/* Items */}
      {DOCK_ITEMS.map((item, i) => {
        if (!item) return (
          <div key={`sep-${i}`} style={{ height:1, background:ca(J.cyan,0.06), margin:'3px 0' }} />
        );
        return (
          <DockItem key={item.key} item={item} active={active===item.key} expanded={expanded} onClick={() => setActive(item.key)} />
        );
      })}

      {/* User card at bottom */}
      <div style={{ marginTop:8, paddingTop:8, borderTop:`1px solid ${ca(J.cyan,0.08)}`,
        display:'flex', alignItems:'center', gap:10, padding:'6px 4px 0',
        justifyContent: expanded ? 'flex-start' : 'center' }}>
        <div style={{ width:28, height:28, borderRadius:'50%', flexShrink:0,
          background:`linear-gradient(135deg, rgb(168,85,247), rgb(255,45,149))`,
          boxShadow:'0 0 10px rgba(168,85,247,0.5)',
          display:'flex', alignItems:'center', justifyContent:'center',
          fontSize:12, fontWeight:700, color:'white' }}>S</div>
        {expanded && (
          <div>
            <div style={{ fontSize:12, fontWeight:600, color:J.textPri }}>Shivang</div>
            <div style={{ fontSize:9, color:J.textMut }}>Pro · Admin</div>
          </div>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { FloatingDock });
