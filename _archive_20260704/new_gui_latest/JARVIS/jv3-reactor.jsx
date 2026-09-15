// ─── JARVIS v3 — Animated Core Reactor + Sphere + Particles ─────────────────

function Particle({ seed }) {
  const J = window.J;
  const colors = [J.cyan, J.magenta, J.purple, J.green];
  const col = colors[seed % colors.length];
  const size = 2 + (seed % 3);
  const dur  = 4 + (seed % 6);
  const x    = 10 + (seed * 37 % 80);
  const y    = 10 + (seed * 53 % 80);
  const delay = -(seed * 0.7);

  return (
    <div style={{
      position:'absolute',
      left:`${x}%`, top:`${y}%`,
      width:size, height:size, borderRadius:'50%',
      background:col, boxShadow:`0 0 ${size*3}px ${col}`,
      animation:`j-float-${seed%4} ${dur}s ease-in-out ${delay}s infinite`,
      opacity:0.55,
    }} />
  );
}

function WireframeSphere({ state }) {
  const J   = window.J;
  const col = (window.JSTATES[state]||window.JSTATES.IDLE).col;
  const size = 130;

  const latitudes  = [-48,-28,-8,12,32,50];
  const longitudes = [0,30,60,90,120,150];

  return (
    <div style={{ position:'relative', width:size, height:size,
      animation:'j-spin-rev 22s linear infinite' }}>
      {/* Latitude rings */}
      {latitudes.map((deg,i) => {
        const scale = Math.cos(deg * Math.PI/180);
        const offset = size/2 + Math.sin(deg*Math.PI/180) * (size/2);
        return (
          <div key={i} style={{
            position:'absolute',
            left:'50%', top: offset - (scale*size/2),
            marginLeft: -(scale*size/2),
            width: scale*size, height: scale*size,
            borderRadius:'50%',
            border:`1px solid ${ca(col, 0.12 + i*0.025)}`,
            transition:'border-color 0.7s',
          }} />
        );
      })}
      {/* Longitude arcs */}
      {longitudes.map((deg,i) => (
        <div key={i} style={{
          position:'absolute', inset:0, borderRadius:'50%',
          border:`1px solid ${ca(col,0.1)}`,
          transform:`rotateY(${deg}deg)`,
          transition:'border-color 0.7s',
        }} />
      ))}
      {/* Nodes at intersections */}
      {[0,1,2,3,4,5,6].map(i => {
        const a = i * 51.4 * Math.PI/180;
        const b = i * 31.7 * Math.PI/180;
        const x = size/2 + (size/2-6) * Math.cos(a) * Math.sin(b);
        const y = size/2 + (size/2-6) * Math.sin(a);
        return (
          <div key={i} style={{ position:'absolute',
            left:x-2, top:y-2, width:4, height:4, borderRadius:'50%',
            background: col, boxShadow:`0 0 6px ${col}`,
            opacity:0.7, transition:'background 0.7s',
            animation:`j-blink ${1.5+i*0.3}s ease-in-out ${i*0.2}s infinite`,
          }} />
        );
      })}
      {/* Core glow */}
      <div style={{ position:'absolute', inset:0, display:'flex', alignItems:'center', justifyContent:'center' }}>
        <div style={{ width:18, height:18, borderRadius:'50%',
          background: col, boxShadow:`0 0 20px ${col}, 0 0 40px ${ca(col,0.4)}`,
          animation:'j-pulse 2.5s ease-in-out infinite',
          transition:'background 0.7s, box-shadow 0.7s',
        }} />
      </div>
    </div>
  );
}

function ReactorRings({ state }) {
  const J = window.J;
  const s = window.JSTATES[state] || window.JSTATES.IDLE;
  const col = s.col;

  const isListening  = state === 'LISTENING';
  const isSpeaking   = state === 'SPEAKING';
  const isProcessing = state === 'PROCESSING';
  const size = 460;

  return (
    <div style={{ position:'relative', width:size, height:size }}>
      {/* Ambient glow */}
      <div style={{ position:'absolute', inset:0, borderRadius:'50%',
        background:`radial-gradient(circle,${ca(col,s.glowOp*0.1)} 0%,transparent 62%)`,
        transition:'background 0.8s' }} />

      {/* Ripple rings — LISTENING */}
      {isListening && [0,1,2].map(i=>(
        <div key={i} style={{ position:'absolute', inset:`${50+i*22}px`, borderRadius:'50%',
          border:`1px solid ${ca(J.green,0.4)}`,
          animation:`j-ripple 2.5s ease-out ${i*0.85}s infinite` }} />
      ))}

      {/* Ripple rings — SPEAKING */}
      {isSpeaking && [0,1,2].map(i=>(
        <div key={i} style={{ position:'absolute', inset:`${42+i*20}px`, borderRadius:'50%',
          border:`1px solid ${ca(J.purple,0.45)}`,
          animation:`j-ripple 1.9s ease-out ${i*0.65}s infinite` }} />
      ))}

      {/* Ripple rings — PROCESSING */}
      {isProcessing && [0,1].map(i=>(
        <div key={i} style={{ position:'absolute', inset:`${55+i*30}px`, borderRadius:'50%',
          border:`1px solid ${ca(J.magenta,0.35)}`,
          animation:`j-ripple 1.4s ease-out ${i*0.5}s infinite` }} />
      ))}

      {/* RING 1 — outer */}
      <div style={{ position:'absolute', inset:18, borderRadius:'50%',
        border:`1px dashed ${ca(col,0.2)}`,
        animation:`j-spin ${s.ring.r1} linear infinite`,
        transition:'border-color 0.7s' }}>
        <OrbitDot size={9} col={col} />
      </div>
      <div style={{ position:'absolute', inset:28, borderRadius:'50%',
        border:`1px solid ${ca(col,0.16)}`, boxShadow:`0 0 12px ${ca(col,s.glowOp*0.28)}`,
        animation:`j-spin ${s.ring.r1} linear infinite`, transition:'all 0.7s' }} />

      {/* RING 2 — middle */}
      <div style={{ position:'absolute', inset:88, borderRadius:'50%',
        border:`1.5px solid ${ca(col,0.42)}`, boxShadow:`0 0 20px ${ca(col,s.glowOp*0.45)}`,
        animation:`j-spin-rev ${s.ring.r2} linear infinite`, transition:'all 0.7s' }}>
        <OrbitDot size={11} col={col} bottom />
        <OrbitDot size={7} col={col} right op={0.6} />
      </div>

      {/* RING 3 — inner fast */}
      <div style={{ position:'absolute', inset:148, borderRadius:'50%',
        border:`2px solid ${ca(col,0.6)}`, boxShadow:`0 0 28px ${ca(col,s.glowOp*0.55)}`,
        animation:`j-spin ${s.ring.r3} linear infinite`, transition:'all 0.7s' }}>
        <OrbitDot size={13} col={col} glow />
        <OrbitDot size={8}  col={col} bottom op={0.7} />
      </div>

      {/* Core zone */}
      <div style={{ position:'absolute', inset:180, borderRadius:'50%',
        background:`radial-gradient(circle,${ca(col,s.glowOp*0.45)} 0%,transparent 70%)`,
        animation:`j-pulse ${s.pulse} ease-in-out infinite`, transition:'background 0.7s' }} />

      {/* Center disk */}
      <div style={{ position:'absolute', inset:0, display:'flex', alignItems:'center', justifyContent:'center' }}>
        <div style={{
          width:180, height:180, borderRadius:'50%',
          background:`radial-gradient(circle,${ca(col,s.glowOp*0.6)} 0%,${ca(col,0.08)} 55%,transparent 100%)`,
          border:`2px solid ${ca(col,0.8)}`,
          boxShadow:`0 0 36px ${ca(col,s.glowOp)},0 0 70px ${ca(col,0.22)},inset 0 0 20px ${ca(col,0.08)}`,
          display:'flex', alignItems:'center', justifyContent:'center',
          animation:`j-pulse ${s.pulse} ease-in-out infinite`,
          transition:'all 0.7s',
        }}>
          <WireframeSphere state={state} />
        </div>
      </div>

      {/* Tick marks */}
      {[0,30,60,90,120,150,180,210,240,270,300,330].map(a => (
        <div key={a} style={{ position:'absolute', inset:0, display:'flex', alignItems:'flex-start',
          justifyContent:'center', transform:`rotate(${a}deg)`, pointerEvents:'none' }}>
          <div style={{ width:1, height:a%90===0?14:a%30===0?9:5, marginTop:3,
            background:ca(col, a%90===0?0.55:0.18), transition:'background 0.7s' }} />
        </div>
      ))}

      {/* State indicator inside core ring */}
      <div style={{ position:'absolute', inset:0, display:'flex', flexDirection:'column',
        alignItems:'center', justifyContent:'flex-end', paddingBottom:80 }}>
        {isProcessing && (
          <div style={{ width:24,height:24,borderRadius:'50%',
            border:`2.5px solid ${ca(col,0.3)}`, borderTopColor:col,
            animation:'j-spin 0.5s linear infinite' }} />
        )}
        {isSpeaking && (
          <div style={{ display:'flex', gap:3, alignItems:'center', height:28 }}>
            {[0,1,2,3,4,5].map(i=>(
              <div key={i} style={{ width:3, height:24, borderRadius:2, background:J.purple,
                boxShadow:`0 0 5px ${J.purple}`,
                animation:`j-wave ${0.5+i*0.1}s ease-in-out ${i*0.08}s infinite`,
                transformOrigin:'center' }} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function OrbitDot({ size=8, col, bottom=false, right=false, op=1, glow=false }) {
  const pos = bottom
    ? { bottom: -(size/2), left:'50%', transform:'translateX(-50%)' }
    : right
    ? { right: '20%', top: -(size/2) }
    : { top: -(size/2), left:'50%', transform:'translateX(-50%)' };
  return (
    <div style={{ position:'absolute', ...pos,
      width:size, height:size, borderRadius:'50%',
      background:col, opacity:op,
      boxShadow: glow ? `0 0 18px ${col},0 0 6px white` : `0 0 ${size}px ${col}`,
      transition:'background 0.7s',
    }} />
  );
}

function ReactorStateText({ state, lastInput }) {
  const J = window.J;
  const s = window.JSTATES[state] || window.JSTATES.IDLE;
  const info = {
    IDLE:       { main:'AWAITING INPUT',      sub:'All systems nominal. Ready for your command.' },
    LISTENING:  { main:'LISTENING',           sub: lastInput ? `"${lastInput}"` : 'Voice stream active…' },
    PROCESSING: { main:'PROCESSING',          sub: lastInput ? `Parsing: "${lastInput.slice(0,44)}${lastInput.length>44?'…':''}"` : 'Running inference…' },
    SPEAKING:   { main:'GENERATING',          sub:'Streaming response to terminal…' },
  };
  const d = info[state] || info.IDLE;

  return (
    <div style={{ textAlign:'center', display:'flex', flexDirection:'column', alignItems:'center', gap:8 }}>
      <div style={{ display:'flex', alignItems:'center', gap:10 }}>
        {state !== 'IDLE' && (
          <div style={{ width:8,height:8,borderRadius:'50%',background:s.col,
            boxShadow:`0 0 8px ${s.col}`, animation:'j-blink 1.2s ease-in-out infinite' }} />
        )}
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:22, fontWeight:700,
          letterSpacing:'4px', color:s.col, transition:'color 0.6s',
          textShadow:`0 0 24px ${ca(s.col,0.5)}` }}>
          {d.main}
        </span>
      </div>
      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:11,
        color:J.textMut, letterSpacing:'0.4px', maxWidth:460 }}>{d.sub}</span>
      {state !== 'IDLE' && (
        <window.JTag text={`${s.label} — ${state==='PROCESSING'?'NLU ACTIVE':state==='LISTENING'?'VOICE CAPTURE':state==='SPEAKING'?'TTS ACTIVE':'STANDBY'}`} color={s.col} pulse />
      )}
    </div>
  );
}

function ParticleField({ count = 24 }) {
  return (
    <div style={{ position:'absolute', inset:0, pointerEvents:'none', overflow:'hidden' }}>
      {Array.from({length:count}).map((_,i)=>(
        <Particle key={i} seed={i} />
      ))}
    </div>
  );
}

Object.assign(window, { ReactorRings, ReactorStateText, ParticleField });
