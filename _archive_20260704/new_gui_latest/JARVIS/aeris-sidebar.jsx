// ─── A.E.R.I.S SIDEBAR ───────────────────────────────────────────────────────

function Sidebar({ activeTab, setActiveTab, collapsed }) {
  const C = window.AERIS_COLORS;

  const sections = [
    {
      title: 'NAVIGATION',
      items: [
        { key:'Chat',        badge:'3',    badgeColor: C.cyan   },
        { key:'History',     badge:null                         },
        { key:'Routines',    badge:null                         },
        { key:'Automations', badge:null                         },
      ],
    },
    {
      title: 'INTELLIGENCE',
      items: [
        { key:'Brain',    badge:'LIVE', badgeColor: C.green },
        { key:'Memory',   badge:null                        },
        { key:'Training', badge:null                        },
      ],
    },
    {
      title: 'SYSTEM',
      items: [
        { key:'Settings', badge:null },
      ],
    },
  ];

  const ICONS = {
    Chat:        <path d="M2 3h12v8H2z M5 11l-3 3v-3" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinejoin="round"/>,
    History:     <><circle cx="8" cy="8" r="5" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M8 5v3l2 2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></>,
    Routines:    <><path d="M3 8a5 5 0 0 1 10 0" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinecap="round"/><path d="M13 8a5 5 0 0 1-10 0" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinecap="round"/></>,
    Automations: <><rect x="3" y="3" width="4" height="4" rx="1" stroke="currentColor" strokeWidth="1.3" fill="none"/><rect x="9" y="9" width="4" height="4" rx="1" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M7 5h2a2 2 0 0 1 2 2v1M9 11H7a2 2 0 0 1-2-2V8" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinecap="round"/></>,
    Brain:       <><ellipse cx="8" cy="8" rx="4" ry="5" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M8 3v10M4 6h8M4 10h8" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinecap="round"/></>,
    Memory:      <><rect x="3" y="5" width="10" height="7" rx="1" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M6 5V4a2 2 0 0 1 4 0v1M6 9h4" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinecap="round"/></>,
    Training:    <><path d="M3 12L8 4l5 8H3z" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinejoin="round"/><line x1="8" y1="8" x2="8" y2="12" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></>,
    Settings:    <><circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M8 2v2M8 12v2M2 8h2M12 8h2M3.5 3.5l1.4 1.4M11.1 11.1l1.4 1.4M3.5 12.5l1.4-1.4M11.1 4.9l1.4-1.4" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></>,
  };

  function NavIcon({ name, active, hovered }) {
    const color = active ? C.cyan : hovered ? 'rgba(200,220,240,0.9)' : C.textMut;
    return (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ color, flexShrink:0, transition:'color 0.2s' }}>
        {ICONS[name] || <rect x="3" y="3" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.3" fill="none"/>}
      </svg>
    );
  }

  function NavItem({ item, active, onClick }) {
    const [hovered, setHovered] = React.useState(false);
    return (
      <div
        onClick={onClick}
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        title={collapsed ? item.key : ''}
        style={{
          display:'flex', alignItems:'center', gap:12,
          padding: collapsed ? '10px 0' : '10px 12px',
          justifyContent: collapsed ? 'center' : 'flex-start',
          borderRadius:10, cursor:'pointer',
          background: active   ? 'rgba(0,212,255,0.1)'  : hovered ? 'rgba(0,212,255,0.05)' : 'transparent',
          border:`1px solid ${active ? 'rgba(0,212,255,0.38)' : hovered ? 'rgba(0,212,255,0.15)' : 'transparent'}`,
          boxShadow: active ? '0 0 16px rgba(0,212,255,0.2)' : hovered ? '0 0 10px rgba(0,212,255,0.1)' : 'none',
          transition:'all 0.2s ease',
        }}
      >
        <NavIcon name={item.key} active={active} hovered={hovered} />
        {!collapsed && (
          <>
            <span style={{
              fontFamily:'Inter, sans-serif', fontSize:13, flex:1,
              fontWeight: active ? 700 : 500,
              color: active ? C.textPri : hovered ? 'rgb(210,225,240)' : C.textSec,
              transition:'color 0.2s',
              whiteSpace:'nowrap',
            }}>{item.key}</span>
            {item.badge && (
              <div style={{
                padding:'2px 7px', borderRadius:8, fontSize:9, fontWeight:700, letterSpacing:'0.4px',
                background: item.badgeColor ? item.badgeColor.replace('rgb','rgba').replace(')',',0.15)') : 'rgba(100,116,139,0.15)',
                border:`1px solid ${item.badgeColor ? item.badgeColor.replace('rgb','rgba').replace(')',',0.4)') : 'rgba(100,116,139,0.4)'}`,
                color: item.badgeColor || C.textSec,
              }}>{item.badge}</div>
            )}
          </>
        )}
      </div>
    );
  }

  return (
    <div style={{
      width: collapsed ? 62 : 240, height:'100%',
      background:C.panel, borderRight:`1px solid ${C.border}`,
      display:'flex', flexDirection:'column',
      padding: collapsed ? '20px 10px' : '20px 16px',
      transition:'width 0.32s cubic-bezier(0.4,0,0.2,1)',
      overflow:'hidden', flexShrink:0, position:'relative',
    }}>
      {/* Scanline */}
      <div style={{ position:'absolute', left:0, right:0, top:0, height:1, background:`linear-gradient(90deg,transparent,${C.cyan},transparent)`, opacity:0.12, animation:'aeris-scan 10s linear infinite', pointerEvents:'none' }} />

      {/* Brand */}
      <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:28, overflow:'hidden', justifyContent: collapsed ? 'center' : 'flex-start' }}>
        <div style={{ position:'relative', width:32, height:32, flexShrink:0 }}>
          <div style={{ position:'absolute', inset:0, borderRadius:'50%', border:`1.5px solid rgba(0,212,255,0.6)`, animation:'aeris-spin 6s linear infinite', boxShadow:'0 0 8px rgba(0,212,255,0.25)' }} />
          <div style={{ position:'absolute', inset:5, borderRadius:'50%', border:`1px solid rgba(0,212,255,0.4)`, animation:'aeris-spin-rev 4s linear infinite' }} />
          <div style={{ position:'absolute', inset:11, borderRadius:'50%', background:C.cyan, boxShadow:`0 0 8px ${C.cyan}` }} />
        </div>
        {!collapsed && (
          <div style={{ overflow:'hidden' }}>
            <div style={{ fontSize:13, fontWeight:700, letterSpacing:'1.8px', color:C.textPri, whiteSpace:'nowrap' }}>A.E.R.I.S</div>
            <div style={{ fontSize:10, color:C.textMut, letterSpacing:'0.4px', marginTop:2 }}>Assistant Core</div>
          </div>
        )}
      </div>

      {/* Nav */}
      <div style={{ flex:1, display:'flex', flexDirection:'column', gap:2, overflowY:'auto' }}>
        {sections.map(section => (
          <div key={section.title} style={{ marginBottom:8 }}>
            {!collapsed && (
              <div style={{ fontSize:9, fontWeight:700, letterSpacing:'1.8px', color:C.textMut, padding:'8px 12px 4px 12px', whiteSpace:'nowrap' }}>
                {section.title}
              </div>
            )}
            {collapsed && <div style={{ height:8 }} />}
            {section.items.map(item => (
              <NavItem key={item.key} item={item} active={activeTab===item.key} onClick={() => setActiveTab(item.key)} />
            ))}
          </div>
        ))}
      </div>

      {/* Brain card */}
      {!collapsed && (
        <div style={{ borderRadius:12, background:C.card, border:`1px solid ${C.border}`, padding:'12px 14px', marginBottom:8 }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:6 }}>
            <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:10, fontWeight:700, letterSpacing:'1.5px', color:C.textSec }}>BRAIN</span>
            <div style={{ display:'flex', alignItems:'center', gap:5 }}>
              <div style={{ width:6, height:6, borderRadius:'50%', background:C.green, boxShadow:`0 0 4px ${C.green}`, animation:'aeris-blink 2s infinite' }} />
              <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:9, fontWeight:700, color:C.green }}>ACTIVE</span>
            </div>
          </div>
          <div style={{ fontSize:10, color:C.textPri, marginBottom:3, fontFamily:"'JetBrains Mono', monospace" }}>21 intents • 301 patterns</div>
          <div style={{ fontSize:10, color:C.cyan, fontFamily:"'JetBrains Mono', monospace" }}>99.8% accuracy</div>
        </div>
      )}

      {/* User card */}
      {!collapsed && (
        <div style={{ borderRadius:12, background:C.card, border:`1px solid ${C.border}`, padding:'10px', display:'flex', alignItems:'center', gap:10 }}>
          <div style={{ width:32, height:32, borderRadius:'50%', background:C.purple, boxShadow:`0 0 8px rgba(168,85,247,0.5)`, display:'flex', alignItems:'center', justifyContent:'center', fontSize:13, fontWeight:700, color:'white', flexShrink:0 }}>S</div>
          <div>
            <div style={{ fontSize:12, fontWeight:700, color:C.textPri }}>Shivang</div>
            <div style={{ fontSize:10, color:C.textMut }}>Pro • Admin</div>
          </div>
        </div>
      )}
    </div>
  );
}

Object.assign(window, { Sidebar });
