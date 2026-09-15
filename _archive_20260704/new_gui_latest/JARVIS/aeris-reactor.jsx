// ─── A.E.R.I.S REACTOR — animated state-driven core ──────────────────────────

function ArcReactor({ state }) {
  const C = window.AERIS_COLORS;
  const STATES = window.AERIS_STATES;
  const s = STATES[state] || STATES.IDLE;
  const col = s.color;
  const colA = (op) => col.replace('rgb','rgba').replace(')',`,${op})`);

  const isListening  = state === 'LISTENING';
  const isSpeaking   = state === 'SPEAKING';
  const isProcessing = state === 'PROCESSING';
  const isError      = state === 'ERROR';

  return (
    <div style={{ position:'relative', width:440, height:440 }}>

      {/* Ambient radial glow */}
      <div style={{
        position:'absolute', inset:0, borderRadius:'50%',
        background: `radial-gradient(circle at 50% 50%, ${colA(s.glowOp * 0.12)} 0%, transparent 65%)`,
        transition: 'background 0.8s ease', pointerEvents:'none',
      }} />

      {/* Listening ripples */}
      {isListening && [0,1,2].map(i => (
        <div key={i} style={{
          position:'absolute', inset:`${55+i*20}px`, borderRadius:'50%',
          border:`1px solid ${C.green.replace('rgb','rgba').replace(')',',0.4)')}`,
          animation:`aeris-ripple 2.4s ease-out ${i*0.8}s infinite`,
          pointerEvents:'none',
        }} />
      ))}

      {/* Speaking ripples */}
      {isSpeaking && [0,1,2].map(i => (
        <div key={i} style={{
          position:'absolute', inset:`${45+i*18}px`, borderRadius:'50%',
          border:`1px solid ${C.purple.replace('rgb','rgba').replace(')',',0.45)')}`,
          animation:`aeris-ripple 1.8s ease-out ${i*0.6}s infinite`,
          pointerEvents:'none',
        }} />
      ))}

      {/* Error pulse */}
      {isError && [0,1].map(i => (
        <div key={i} style={{
          position:'absolute', inset:`${60+i*30}px`, borderRadius:'50%',
          border:`1px solid ${C.red.replace('rgb','rgba').replace(')',',0.5)')}`,
          animation:`aeris-ripple 1.2s ease-out ${i*0.4}s infinite`,
          pointerEvents:'none',
        }} />
      ))}

      {/* RING 1 — outer dashed */}
      <div style={{
        position:'absolute', inset:24, borderRadius:'50%',
        border:`1.5px dashed ${colA(0.22)}`,
        animation:`aeris-spin ${s.ring.r1} linear infinite`,
        transition:'border-color 0.7s',
      }}>
        <div style={{
          position:'absolute', top:-5, left:'50%', transform:'translateX(-50%)',
          width:10, height:10, borderRadius:'50%',
          background: colA(0.6), boxShadow:`0 0 8px ${col}`,
          transition:'background 0.7s',
        }} />
      </div>

      {/* RING 1 — outer solid */}
      <div style={{
        position:'absolute', inset:34, borderRadius:'50%',
        border:`1px solid ${colA(0.18)}`,
        boxShadow:`0 0 14px ${colA(s.glowOp * 0.3)}`,
        animation:`aeris-spin ${s.ring.r1} linear infinite`,
        transition:'border-color 0.7s, box-shadow 0.7s',
      }} />

      {/* RING 2 — middle */}
      <div style={{
        position:'absolute', inset:82, borderRadius:'50%',
        border:`1.5px solid ${colA(0.4)}`,
        boxShadow:`0 0 20px ${colA(s.glowOp * 0.45)}`,
        animation:`aeris-spin-rev ${s.ring.r2} linear infinite`,
        transition:'border-color 0.7s, box-shadow 0.7s',
      }}>
        <div style={{
          position:'absolute', bottom:-6, left:'50%', transform:'translateX(-50%)',
          width:12, height:12, borderRadius:'50%',
          background: col, boxShadow:`0 0 16px ${col}, 0 0 6px white`,
          transition:'background 0.7s',
        }} />
        <div style={{
          position:'absolute', top:-4, right:'22%',
          width:7, height:7, borderRadius:'50%',
          background: colA(0.55), transition:'background 0.7s',
        }} />
      </div>

      {/* RING 3 — inner fast */}
      <div style={{
        position:'absolute', inset:142, borderRadius:'50%',
        border:`2px solid ${colA(0.6)}`,
        boxShadow:`0 0 28px ${colA(s.glowOp * 0.55)}`,
        animation:`aeris-spin ${s.ring.r3} linear infinite`,
        transition:'border-color 0.7s, box-shadow 0.7s',
      }}>
        <div style={{
          position:'absolute', top:-7, left:'50%', transform:'translateX(-50%)',
          width:14, height:14, borderRadius:'50%',
          background: col, boxShadow:`0 0 20px ${col}, 0 0 8px white`,
          transition:'background 0.7s',
        }} />
        <div style={{
          position:'absolute', bottom:-5, right:'15%',
          width:8, height:8, borderRadius:'50%',
          background: colA(0.7), transition:'background 0.7s',
        }} />
      </div>

      {/* Core glow */}
      <div style={{
        position:'absolute', inset:172, borderRadius:'50%',
        background:`radial-gradient(circle, ${colA(s.glowOp * 0.5)} 0%, ${colA(0.1)} 60%, transparent 100%)`,
        animation:`aeris-pulse ${s.pulse} ease-in-out infinite`,
        transition:'background 0.7s',
      }} />

      {/* Core center disk */}
      <div style={{
        position:'absolute', inset:0,
        display:'flex', alignItems:'center', justifyContent:'center',
      }}>
        <div style={{
          width:104, height:104, borderRadius:'50%',
          background:`radial-gradient(circle, ${colA(s.glowOp * 0.7)} 0%, ${colA(0.12)} 60%, transparent 100%)`,
          border:`2px solid ${colA(0.85)}`,
          boxShadow:`0 0 32px ${colA(s.glowOp)}, 0 0 64px ${colA(0.25)}, inset 0 0 20px ${colA(0.1)}`,
          display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:6,
          animation:`aeris-pulse ${s.pulse} ease-in-out infinite`,
          transition:'background 0.7s, border-color 0.7s, box-shadow 0.7s',
        }}>
          {/* Inner content by state */}
          {isProcessing && (
            <div style={{
              width:28, height:28, borderRadius:'50%',
              border:`2.5px solid ${colA(0.3)}`,
              borderTopColor: col,
              animation:'aeris-spin 0.55s linear infinite',
            }} />
          )}
          {isSpeaking && (
            <div style={{ display:'flex', gap:3, alignItems:'center', height:34 }}>
              {[0,1,2,3,4,5].map(i => (
                <div key={i} style={{
                  width:4, borderRadius:2,
                  background: C.purple,
                  boxShadow:`0 0 6px ${C.purple}`,
                  height: 28,
                  animation:`aeris-wavebar ${0.5+i*0.1}s ease-in-out ${i*0.08}s infinite`,
                  transformOrigin:'center',
                }} />
              ))}
            </div>
          )}
          {isListening && (
            <div style={{ display:'flex', gap:3, alignItems:'center', height:28 }}>
              {[0,1,2,3,4].map(i => (
                <div key={i} style={{
                  width:4, borderRadius:2,
                  background: C.green,
                  boxShadow:`0 0 5px ${C.green}`,
                  height: 20,
                  animation:`aeris-wavebar ${0.7+i*0.15}s ease-in-out ${i*0.12}s infinite`,
                  transformOrigin:'center',
                }} />
              ))}
            </div>
          )}
          {!isProcessing && !isSpeaking && !isListening && (
            <div style={{
              width:18, height:18, borderRadius:'50%',
              background: col, boxShadow:`0 0 14px ${col}`,
              transition:'background 0.7s',
            }} />
          )}
          <span style={{
            fontFamily:"'JetBrains Mono', monospace",
            fontSize:9, fontWeight:700, letterSpacing:'1.2px',
            color: col, transition:'color 0.7s',
            marginTop: (isProcessing||isSpeaking||isListening) ? 2 : 0,
          }}>{state}</span>
        </div>
      </div>

      {/* Tick marks */}
      {[0,30,60,90,120,150,180,210,240,270,300,330].map(angle => (
        <div key={angle} style={{
          position:'absolute', inset:0,
          display:'flex', alignItems:'flex-start', justifyContent:'center',
          transform:`rotate(${angle}deg)`, pointerEvents:'none',
        }}>
          <div style={{
            width:1, height: angle%90===0 ? 14 : angle%30===0 ? 9 : 5,
            marginTop: 4,
            background: colA(angle%90===0 ? 0.5 : 0.2),
            transition:'background 0.7s',
          }} />
        </div>
      ))}
    </div>
  );
}

function ReactorStateText({ state, lastInput }) {
  const C = window.AERIS_COLORS;
  const STATES = window.AERIS_STATES;
  const s = STATES[state] || STATES.IDLE;
  const infoMap = {
    IDLE:       { main:'AWAITING INPUT',         sub:'System nominal. All modules active.',         tag:null },
    LISTENING:  { main:'LISTENING',              sub: lastInput ? `"${lastInput}"` : '"Awaiting voice stream…"', tag:'Voice capture active' },
    PROCESSING: { main:'PROCESSING',             sub: lastInput ? `Analyzing: "${lastInput.slice(0,42)}${lastInput.length>42?'…':''}"` : 'Running semantic engine…', tag:'NLU inference active' },
    SPEAKING:   { main:'GENERATING RESPONSE',    sub:'Streaming output to terminal…',              tag:'TTS pipeline active' },
    ERROR:      { main:'SYSTEM ERROR',           sub:'Reconnecting to semantic core…',             tag:'Attempting recovery' },
  };
  const info = infoMap[state] || infoMap.IDLE;
  return (
    <div style={{ textAlign:'center', display:'flex', flexDirection:'column', gap:10, alignItems:'center' }}>
      <div style={{ display:'flex', alignItems:'center', gap:10 }}>
        {state !== 'IDLE' && (
          <div style={{ width:8, height:8, borderRadius:'50%', background:s.color, boxShadow:`0 0 8px ${s.color}`, animation:'aeris-blink 1.2s ease-in-out infinite' }} />
        )}
        <span style={{
          fontFamily:"'JetBrains Mono', monospace",
          fontSize:20, fontWeight:700, letterSpacing:'4px',
          color: s.color, transition:'color 0.6s',
        }}>{info.main}</span>
      </div>
      <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:11, color:C.textMut, letterSpacing:'0.4px', maxWidth:460 }}>{info.sub}</span>
      {info.tag && <window.Pill text={info.tag} color={s.color} blink={true} />}
    </div>
  );
}

Object.assign(window, { ArcReactor, ReactorStateText });
