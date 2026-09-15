// ─── JARVIS v3.1 — Upgraded Boot Screen ──────────────────────────────────────
// Circular segmented progress + glitch effect + improved sequence

const BOOT_LINES = [
  { text:'Initializing Neural Core…',  color:'rgb(0,212,255)'   },
  { text:'Loading Voice Systems…',     color:'rgb(168,85,247)'  },
  { text:'Syncing Intelligence…',      color:'rgb(255,45,149)'  },
  { text:'Calibrating Wiring Grid…',   color:'rgb(0,212,255)'   },
  { text:'A.E.R.I.S Online.',          color:'rgb(16,185,129)'  },
];

// Circular segmented progress ring (SVG-based)
function CircularProgress({ step, total = 5, r = 148 }) {
  const J = window.J;
  const cx = 160, cy = 160;
  const segs = total;
  const gapDeg = 6;
  const arcDeg = (360 / segs) - gapDeg;

  function polarToXY(deg, radius) {
    const rad = (deg - 90) * Math.PI / 180;
    return { x: cx + radius * Math.cos(rad), y: cy + radius * Math.sin(rad) };
  }

  function arcPath(startDeg, endDeg, radius) {
    const s = polarToXY(startDeg, radius);
    const e = polarToXY(endDeg, radius);
    const large = (endDeg - startDeg) > 180 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${radius} ${radius} 0 ${large} 1 ${e.x} ${e.y}`;
  }

  const SEGMENT_COLORS = [
    'rgb(0,212,255)', 'rgb(168,85,247)', 'rgb(255,45,149)',
    'rgb(0,212,255)', 'rgb(16,185,129)',
  ];

  return (
    <svg width="320" height="320" viewBox="0 0 320 320"
      style={{ position:'absolute', top:0, left:0 }}>
      {Array.from({length:segs}).map((_,i) => {
        const startDeg = i * (360/segs) + gapDeg/2;
        const endDeg   = startDeg + arcDeg;
        const filled   = i < step;
        const color    = SEGMENT_COLORS[i % SEGMENT_COLORS.length];
        return (
          <g key={i}>
            {/* Background segment */}
            <path d={arcPath(startDeg, endDeg, r)}
              stroke="rgba(255,255,255,0.06)" strokeWidth="3"
              fill="none" strokeLinecap="round" />
            {/* Filled segment */}
            {filled && (
              <path d={arcPath(startDeg, endDeg, r)}
                stroke={color} strokeWidth="3"
                fill="none" strokeLinecap="round"
                style={{
                  filter:`drop-shadow(0 0 4px ${color})`,
                  animation:'j-fadein 0.3s ease',
                }} />
            )}
          </g>
        );
      })}
      {/* Inner ring */}
      <circle cx={cx} cy={cy} r={r - 12}
        stroke="rgba(0,212,255,0.06)" strokeWidth="1" fill="none" />
    </svg>
  );
}

// Glitch text effect
function GlitchText({ text, color, className }) {
  const J = window.J;
  const [glitch, setGlitch] = React.useState(false);
  React.useEffect(() => {
    const iv = setInterval(() => {
      setGlitch(true);
      setTimeout(() => setGlitch(false), 80);
    }, 3200 + Math.random() * 2000);
    return () => clearInterval(iv);
  }, []);

  return (
    <span style={{ position:'relative', display:'inline-block' }}>
      <span style={{
        fontSize:32, fontWeight:700, letterSpacing:'10px',
        color, textShadow:`0 0 30px ${ca(color, 0.55)}`,
        display:'inline-block',
        transform: glitch ? `translate(${Math.random()*4-2}px,${Math.random()*2-1}px) skewX(${Math.random()*3-1.5}deg)` : 'none',
        transition: glitch ? 'none' : 'transform 0.08s',
        filter: glitch ? 'brightness(1.5)' : 'none',
      }}>{text}</span>
      {glitch && (
        <>
          <span style={{ position:'absolute', left:2, top:0, color:'rgb(255,45,149)',
            opacity:0.5, fontSize:32, fontWeight:700, letterSpacing:'10px',
            mixBlendMode:'screen', pointerEvents:'none' }}>{text}</span>
          <span style={{ position:'absolute', left:-2, top:0, color:'rgb(0,212,255)',
            opacity:0.5, fontSize:32, fontWeight:700, letterSpacing:'10px',
            mixBlendMode:'screen', pointerEvents:'none' }}>{text}</span>
        </>
      )}
    </span>
  );
}

function BootScreen({ onComplete }) {
  const J = window.J;
  const ca = window.ca;
  const [phase, setPhase]     = React.useState(0);
  const [step, setStep]       = React.useState(0);
  const [typed, setTyped]     = React.useState('');
  const [done, setDone]       = React.useState([]);
  const [exiting, setExiting] = React.useState(false);

  React.useEffect(() => {
    const t = [
      { d:200,  fn:()=>setPhase(1) },
      { d:900,  fn:()=>setPhase(2) },
      { d:1500, fn:()=>setPhase(3) },
      { d:1800, fn:()=>runLine(0)  },
    ];
    const ids = t.map(({ d, fn }) => setTimeout(fn, d));
    return () => ids.forEach(clearTimeout);
  }, []);

  function runLine(idx) {
    if (idx >= BOOT_LINES.length) {
      setTimeout(() => { setExiting(true); setTimeout(onComplete, 750); }, 700);
      return;
    }
    setStep(idx + 1);
    const full = BOOT_LINES[idx].text;
    let i = 0; setTyped('');
    const iv = setInterval(() => {
      i++; setTyped(full.slice(0, i));
      if (i >= full.length) {
        clearInterval(iv);
        setDone(prev => [...prev, BOOT_LINES[idx]]);
        setTyped('');
        setTimeout(() => runLine(idx + 1), 160);
      }
    }, 26);
  }

  return (
    <div style={{
      position:'absolute', inset:0, zIndex:200,
      background:`radial-gradient(ellipse at 50% 45%, #0d1b30 0%, #05070D 70%)`,
      display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center',
      opacity: exiting ? 0 : 1, transition:'opacity 0.75s ease',
      overflow:'hidden',
    }}>
      {/* Animated grid */}
      <div style={{ position:'absolute', inset:0, pointerEvents:'none',
        backgroundImage:`linear-gradient(rgba(0,212,255,${phase>=1?0.038:0}) 1px,transparent 1px),linear-gradient(90deg,rgba(0,212,255,${phase>=1?0.038:0}) 1px,transparent 1px)`,
        backgroundSize:'56px 56px', transition:'background 1.8s ease' }} />

      {/* Scan line */}
      <div style={{ position:'absolute', left:0, right:0, height:1,
        background:'linear-gradient(90deg,transparent,rgba(0,212,255,0.3),transparent)',
        animation:'j-scan 5s linear infinite', pointerEvents:'none',
        opacity:phase>=1?1:0, transition:'opacity 0.6s' }} />

      {/* Corner brackets */}
      {[[{top:20,left:20},{borderTop:'1px solid',borderLeft:'1px solid'}],
        [{top:20,right:20},{borderTop:'1px solid',borderRight:'1px solid'}],
        [{bottom:20,left:20},{borderBottom:'1px solid',borderLeft:'1px solid'}],
        [{bottom:20,right:20},{borderBottom:'1px solid',borderRight:'1px solid'}],
      ].map(([pos,border],i)=>(
        <div key={i} style={{ position:'absolute',...pos,...border,
          width:40,height:40, borderColor:'rgba(0,212,255,0.3)',
          opacity:phase>=1?1:0, transition:`opacity 0.5s ${i*0.08}s` }} />
      ))}

      {/* Circular progress ring + rings + sphere */}
      <div style={{ position:'relative', width:320, height:320,
        opacity:phase>=1?1:0, transition:'opacity 0.9s' }}>
        <CircularProgress step={step} total={BOOT_LINES.length} />

        {/* Rotating rings inside circle */}
        <div style={{ position:'absolute', inset:16, display:'flex', alignItems:'center', justifyContent:'center' }}>
          <div style={{ position:'relative', width:240, height:240 }}>
            {/* Ring 1 */}
            <div style={{ position:'absolute', inset:8, borderRadius:'50%',
              border:`1.5px dashed rgba(0,212,255,0.22)`,
              animation:`j-spin ${phase>=3?'3.5s':'12s'} linear infinite`, transition:'animation-duration 0.5s' }}>
              <div style={{ position:'absolute', top:-5, left:'50%', transform:'translateX(-50%)',
                width:10,height:10,borderRadius:'50%', background:J.cyan, boxShadow:`0 0 10px ${J.cyan}` }} />
            </div>
            {/* Ring 2 */}
            <div style={{ position:'absolute', inset:36, borderRadius:'50%',
              border:`1.5px solid rgba(0,212,255,0.35)`, boxShadow:'0 0 14px rgba(0,212,255,0.2)',
              animation:`j-spin-rev ${phase>=3?'2.2s':'8s'} linear infinite` }}>
              <div style={{ position:'absolute', bottom:-6, left:'50%', transform:'translateX(-50%)',
                width:12,height:12,borderRadius:'50%', background:J.cyan, boxShadow:`0 0 14px ${J.cyan}` }} />
            </div>
            {/* Ring 3 */}
            <div style={{ position:'absolute', inset:72, borderRadius:'50%',
              border:`2px solid rgba(0,212,255,0.55)`, boxShadow:'0 0 20px rgba(0,212,255,0.3)',
              animation:`j-spin ${phase>=3?'1.3s':'5s'} linear infinite` }} />
            {/* Sphere */}
            <div style={{ position:'absolute', inset:0, display:'flex', alignItems:'center', justifyContent:'center',
              opacity:phase>=2?1:0, transition:'opacity 1s' }}>
              <div style={{ position:'relative', width:88, height:88, animation:'j-spin-rev 20s linear infinite' }}>
                {[-30,-10,10,30].map((d,i) => {
                  const s = Math.cos(d*Math.PI/180);
                  return (
                    <div key={i} style={{ position:'absolute', left:'50%', top:'50%',
                      width:s*88, height:s*88, marginLeft:-(s*44), marginTop:Math.sin(d*Math.PI/180)*44-(s*44),
                      borderRadius:'50%', border:`1px solid rgba(0,212,255,${0.1+i*0.03})` }} />
                  );
                })}
                {[0,36,72,108,144].map((deg,i)=>(
                  <div key={i} style={{ position:'absolute', inset:0, borderRadius:'50%',
                    border:`1px solid rgba(0,212,255,0.1)`, transform:`rotateY(${deg}deg)` }} />
                ))}
                <div style={{ position:'absolute', inset:0, display:'flex', alignItems:'center', justifyContent:'center' }}>
                  <div style={{ width:12,height:12,borderRadius:'50%', background:J.cyan,
                    boxShadow:`0 0 18px ${J.cyan}`, animation:'j-pulse 2s ease-in-out infinite' }} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Step counter in center */}
        <div style={{ position:'absolute', inset:0, display:'flex', alignItems:'center',
          justifyContent:'center', pointerEvents:'none', paddingTop:144 }}>
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, fontWeight:700,
            color:J.textMut, letterSpacing:'1px' }}>{step}/{BOOT_LINES.length}</span>
        </div>
      </div>

      {/* Brand */}
      <div style={{ marginTop:28, textAlign:'center',
        opacity:phase>=2?1:0, transition:'opacity 0.8s 0.2s' }}>
        <GlitchText text="A.E.R.I.S" color={J.cyan} />
        <div style={{ fontSize:10, fontWeight:700, letterSpacing:'4px', color:J.textMut, marginTop:8 }}>
          JARVIS v3.0 — ADAPTIVE INTELLIGENCE SYSTEM
        </div>
      </div>

      {/* Text log */}
      <div style={{ marginTop:36, width:440, minHeight:112,
        opacity:phase>=3?1:0, transition:'opacity 0.4s' }}>
        {done.map((l,i)=>(
          <div key={i} style={{ display:'flex', alignItems:'center', gap:10, marginBottom:7,
            animation:'j-fadein 0.2s ease' }}>
            <svg width="10" height="10" viewBox="0 0 10 10">
              <path d="M2 5l3 3 3-3" stroke={l.color} strokeWidth="1.5" fill="none" strokeLinecap="round"/>
            </svg>
            <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:11, color:l.color==='rgb(16,185,129)' ? J.green : J.textSec }}>{l.text}</span>
          </div>
        ))}
        {typed && (
          <div style={{ display:'flex', alignItems:'center', gap:10 }}>
            <div style={{ width:6,height:6,borderRadius:'50%',
              background:BOOT_LINES[step-1]?.color||J.cyan,
              animation:'j-blink 0.5s ease-in-out infinite' }} />
            <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:11, color:J.textSec }}>
              {typed}<span style={{ animation:'j-cursor 0.5s step-end infinite', color:J.cyan }}>▌</span>
            </span>
          </div>
        )}
      </div>

      <div style={{ position:'absolute', bottom:22, right:28,
        fontFamily:"'JetBrains Mono',monospace", fontSize:8.5, color:J.textMut, letterSpacing:'1.5px',
        opacity:phase>=1?0.55:0, transition:'opacity 1s' }}>
        BUILD 2026.04 · GPU-OPTIMIZED · 60FPS
      </div>
    </div>
  );
}

Object.assign(window, { BootScreen });
