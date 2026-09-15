// ─── JARVIS v3 — Command Capsules + System Micro Cards + Logs ────────────────

const CAPSULES = [
  { icon:'app',    label:'Open Apps',     color:'rgb(0,212,255)'   },
  { icon:'clean',  label:'Clean System',  color:'rgb(16,185,129)'  },
  { icon:'cloud',  label:'Weather',       color:'rgb(168,85,247)'  },
  { icon:'music',  label:'Music',         color:'rgb(255,45,149)'  },
  { icon:'cam',    label:'Screenshot',    color:'rgb(251,191,36)'  },
  { icon:'search', label:'Search',        color:'rgb(0,212,255)'   },
];

function CapsuleIcon({ name, color }) {
  const icons = {
    app:   <><rect x="2" y="2" width="5" height="5" rx="1" stroke={color} strokeWidth="1.3" fill="none"/><rect x="9" y="2" width="5" height="5" rx="1" stroke={color} strokeWidth="1.3" fill="none"/><rect x="2" y="9" width="5" height="5" rx="1" stroke={color} strokeWidth="1.3" fill="none"/><rect x="9" y="9" width="5" height="5" rx="1" stroke={color} strokeWidth="1.3" fill="none"/></>,
    clean: <><path d="M3 6l5-4 5 4v7H3z" stroke={color} strokeWidth="1.3" fill="none" strokeLinejoin="round"/><path d="M6 13V9h4v4" stroke={color} strokeWidth="1.3" fill="none"/></>,
    cloud: <><path d="M3 9a3 3 0 1 1 5.8-1A3 3 0 1 1 12 11H3z" stroke={color} strokeWidth="1.3" fill="none"/></>,
    music: <><circle cx="5" cy="11" r="2" stroke={color} strokeWidth="1.3" fill="none"/><circle cx="11" cy="9" r="2" stroke={color} strokeWidth="1.3" fill="none"/><path d="M7 11V4l6-2v5" stroke={color} strokeWidth="1.3" fill="none" strokeLinejoin="round"/></>,
    cam:   <><rect x="2" y="4" width="12" height="9" rx="1.5" stroke={color} strokeWidth="1.3" fill="none"/><circle cx="8" cy="8.5" r="2.5" stroke={color} strokeWidth="1.3" fill="none"/><path d="M5 4V3h6v1" stroke={color} strokeWidth="1.3" fill="none"/></>,
    search:<><circle cx="7" cy="7" r="4" stroke={color} strokeWidth="1.3" fill="none"/><line x1="10" y1="10" x2="13" y2="13" stroke={color} strokeWidth="1.5" strokeLinecap="round"/></>,
  };
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      {icons[name] || <circle cx="8" cy="8" r="4" stroke={color} strokeWidth="1.3" fill="none"/>}
    </svg>
  );
}

function CommandCapsule({ cap, onClick }) {
  const J = window.J;
  const [hov, setHov] = React.useState(false);
  return (
    <div
      onClick={onClick}
      onMouseEnter={()=>setHov(true)}
      onMouseLeave={()=>setHov(false)}
      style={{
        display:'flex', alignItems:'center', gap:8,
        padding:'8px 16px', borderRadius:40, cursor:'pointer',
        background: hov ? ca(cap.color,0.15) : 'rgba(13,21,37,0.7)',
        border:`1px solid ${hov ? ca(cap.color,0.5) : ca(cap.color,0.2)}`,
        boxShadow: hov ? `0 0 16px ${ca(cap.color,0.25)},0 4px 16px rgba(0,0,0,0.3)` : '0 2px 8px rgba(0,0,0,0.2)',
        backdropFilter:'blur(8px)',
        transition:'all 0.22s ease',
        transform: hov ? 'translateY(-2px)' : 'none',
      }}
    >
      <CapsuleIcon name={cap.icon} color={hov ? cap.color : J.textSec} />
      <span style={{ fontFamily:'Inter,sans-serif', fontSize:12, fontWeight:500,
        color: hov ? J.textPri : J.textSec, transition:'color 0.2s',
        whiteSpace:'nowrap' }}>{cap.label}</span>
    </div>
  );
}

function CommandBar({ onCommand }) {
  const J = window.J;
  return (
    <div style={{ position:'absolute', bottom:28, left:'50%', transform:'translateX(-50%)',
      display:'flex', gap:8, alignItems:'center',
      padding:'10px 16px', borderRadius:50,
      background:'rgba(10,15,28,0.8)', backdropFilter:'blur(16px)',
      border:`1px solid rgba(30,41,59,0.7)`,
      boxShadow:'0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(0,212,255,0.06)',
    }}>
      {CAPSULES.map(cap=>(
        <CommandCapsule key={cap.label} cap={cap} onClick={()=>onCommand(cap.label)} />
      ))}
    </div>
  );
}

// ── System Micro Cards ────────────────────────────────────────────────────────

function MicroCard({ label, value, unit, color, graph }) {
  const J = window.J;
  return (
    <div style={{
      width:130, borderRadius:12,
      background:'rgba(13,21,37,0.82)', backdropFilter:'blur(12px)',
      border:`1px solid ${ca(color,0.25)}`,
      boxShadow:`0 4px 20px rgba(0,0,0,0.4),0 0 12px ${ca(color,0.08)}`,
      padding:'10px 12px', display:'flex', flexDirection:'column', gap:6,
    }}>
      <window.JLabel color={J.textMut}>{label}</window.JLabel>
      <div style={{ display:'flex', alignItems:'baseline', gap:3 }}>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:22, fontWeight:700,
          color, lineHeight:1 }}>{value}</span>
        {unit && <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:J.textMut }}>{unit}</span>}
      </div>
      {/* Mini sparkline */}
      <div style={{ height:24, display:'flex', gap:2, alignItems:'flex-end' }}>
        {graph.map((h,i)=>(
          <div key={i} style={{ flex:1, borderRadius:2,
            background: `linear-gradient(180deg,${color},${ca(color,0.3)})`,
            height:`${h}%`, minHeight:3,
            opacity:0.7+(i/graph.length)*0.3,
          }} />
        ))}
      </div>
      <div style={{ height:1, background:`linear-gradient(90deg,${color},transparent)`, opacity:0.4 }} />
    </div>
  );
}

function SystemCards() {
  const J = window.J;
  const [data, setData] = React.useState({
    cpu:  { val:12, history:[8,11,9,14,12,15,11,12] },
    ram:  { val:4.2,history:[3.8,4.0,4.1,4.0,4.2,4.3,4.1,4.2] },
    bat:  { val:87, history:[92,91,90,89,88,88,87,87] },
    net:  { val:1.4,history:[0.8,1.2,0.9,1.4,1.6,1.1,1.3,1.4] },
  });

  React.useEffect(() => {
    const iv = setInterval(()=>{
      setData(d=>({
        cpu:  { val:Math.max(5,Math.min(95,d.cpu.val+(Math.random()-0.5)*8|0)), history:[...d.cpu.history.slice(1),d.cpu.val] },
        ram:  { val:+(d.ram.val+(Math.random()-0.48)*0.15).toFixed(1), history:[...d.ram.history.slice(1),d.ram.val] },
        bat:  { val:Math.max(10,d.bat.val-(Math.random()>0.9?1:0)), history:[...d.bat.history.slice(1),d.bat.val] },
        net:  { val:+(Math.random()*3).toFixed(1), history:[...d.net.history.slice(1),d.net.val] },
      }));
    },3000);
    return ()=>clearInterval(iv);
  },[]);

  const normalize = arr => { const mx=Math.max(...arr,1); return arr.map(v=>Math.max(10,(v/mx)*100)); };

  return (
    <div style={{ position:'absolute', top:56, right:16, display:'flex', flexDirection:'column', gap:8, zIndex:40 }}>
      <MicroCard label="CPU" value={data.cpu.val} unit="%" color={J.cyan}   graph={normalize(data.cpu.history)} />
      <MicroCard label="RAM" value={data.ram.val} unit="GB" color={J.purple} graph={normalize(data.ram.history)} />
      <MicroCard label="BAT" value={data.bat.val} unit="%" color={J.green}  graph={normalize(data.bat.history)} />
      <MicroCard label="NET" value={data.net.val} unit="MB/s" color={J.amber} graph={normalize(data.net.history)} />
    </div>
  );
}

// ── Stats Row ─────────────────────────────────────────────────────────────────

function StatPill({ label, value, color }) {
  const J = window.J;
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:4, padding:'12px 20px',
      borderRadius:14, flex:1,
      background:'rgba(13,21,37,0.65)', backdropFilter:'blur(8px)',
      border:`1px solid rgba(30,41,59,0.7)`,
      transition:'border-color 0.2s, box-shadow 0.2s',
    }}
    onMouseEnter={e=>{e.currentTarget.style.borderColor=ca(color,0.3);e.currentTarget.style.boxShadow=`0 0 18px ${ca(color,0.12)}`;}}
    onMouseLeave={e=>{e.currentTarget.style.borderColor='rgba(30,41,59,0.7)';e.currentTarget.style.boxShadow='none';}}
    >
      <window.JLabel color={J.textMut}>{label}</window.JLabel>
      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:22, fontWeight:700,
        color, letterSpacing:'0.5px' }}>{value}</span>
    </div>
  );
}

Object.assign(window, { CommandBar, SystemCards, StatPill });
