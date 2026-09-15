// ─── JARVIS v3 — Premium Glass Chat Panel ────────────────────────────────────

const SUGGESTION_CHIPS = [
  'Open Chrome', 'Check Weather', 'Play Music', 'System Stats', 'Schedule Meeting',
];

function ChatBubble({ msg, isStreaming, streamText }) {
  const J = window.J;
  const isAI = msg.role === 'ai';
  const text  = isStreaming ? streamText : msg.text;

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:5,
      alignItems: isAI ? 'flex-start' : 'flex-end',
      animation:'j-fadein 0.28s ease',
    }}>
      {/* Sender */}
      <div style={{ display:'flex', gap:6, alignItems:'center' }}>
        {isAI && (
          <div style={{ width:6,height:6,borderRadius:'50%', background:J.cyan,
            boxShadow:`0 0 5px ${J.cyan}`,
            animation: isStreaming ? 'j-blink 0.7s infinite' : 'none' }} />
        )}
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9.5, fontWeight:700,
          letterSpacing:'1px', color: isAI ? J.cyan : J.textSec }}>
          {isAI ? 'A.E.R.I.S' : 'YOU'}
        </span>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut }}>{msg.time}</span>
      </div>

      {/* Bubble */}
      <div style={{
        maxWidth:'88%', padding:'10px 14px', borderRadius: isAI ? '4px 14px 14px 14px' : '14px 4px 14px 14px',
        background: isAI
          ? 'rgba(13,21,37,0.85)'
          : `linear-gradient(135deg,${ca(J.cyan,0.1)},${ca(J.purple,0.06)})`,
        border:`1px solid ${isAI ? 'rgba(30,41,59,0.8)' : ca(J.cyan,0.25)}`,
        backdropFilter:'blur(8px)',
        boxShadow: isAI
          ? '0 2px 16px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.04)'
          : `0 2px 14px ${ca(J.cyan,0.08)}`,
      }}>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:12, color:J.textPri,
          lineHeight:'1.7', whiteSpace:'pre-wrap' }}>
          {text}
          {isStreaming && <span style={{ animation:'j-cursor 0.5s step-end infinite', color:J.cyan }}>▌</span>}
        </span>
      </div>

      {/* Meta tag */}
      {msg.tag && !isStreaming && (
        <window.JTag text={msg.tag.text} color={msg.tag.color} />
      )}
    </div>
  );
}

function TypingDots() {
  const J = window.J;
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:5, alignItems:'flex-start', animation:'j-fadein 0.3s ease' }}>
      <div style={{ display:'flex', gap:6, alignItems:'center' }}>
        <div style={{ width:6,height:6,borderRadius:'50%', background:J.cyan, animation:'j-blink 0.8s infinite' }} />
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9.5, fontWeight:700, color:J.cyan }}>A.E.R.I.S</span>
      </div>
      <div style={{ padding:'10px 14px', borderRadius:'4px 14px 14px 14px',
        background:'rgba(13,21,37,0.85)', border:`1px solid rgba(30,41,59,0.8)`,
        display:'flex', gap:5, alignItems:'center' }}>
        {[0,1,2].map(i=>(
          <div key={i} style={{ width:6,height:6,borderRadius:'50%', background:J.cyan,
            boxShadow:`0 0 4px ${J.cyan}`,
            animation:`j-blink 0.9s ${i*0.3}s infinite` }} />
        ))}
      </div>
    </div>
  );
}

function CommandPreview({ intent, conf }) {
  const J = window.J;
  if (!intent) return null;
  return (
    <div style={{ padding:'6px 12px', borderRadius:8, marginBottom:6,
      background:`linear-gradient(90deg,${ca(J.cyan,0.06)},${ca(J.purple,0.04)})`,
      border:`1px solid ${ca(J.cyan,0.18)}`,
      display:'flex', gap:12, alignItems:'center' }}>
      <div style={{ width:5,height:5,borderRadius:'50%', background:J.green,
        boxShadow:`0 0 5px ${J.green}`, animation:'j-blink 1.5s infinite' }} />
      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.cyan }}>
        intent → <strong>{intent}</strong>
      </span>
      {conf && (
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.green }}>
          {conf}% confidence
        </span>
      )}
    </div>
  );
}

function ChatInput({ onSend, onMic, aiState }) {
  const J = window.J;
  const [val, setVal] = React.useState('');
  const [preview, setPreview] = React.useState(null);
  const inputRef = React.useRef(null);
  const busy = aiState === 'PROCESSING' || aiState === 'SPEAKING';
  const isListening = aiState === 'LISTENING';

  const handleSend = () => {
    if (!val.trim() || busy) return;
    onSend(val.trim());
    setVal('');
    setPreview(null);
    setTimeout(() => inputRef.current?.focus(), 60);
  };

  // Naive live intent preview
  React.useEffect(() => {
    if (!val.trim()) { setPreview(null); return; }
    const intents = [
      { words:['chrome','browser','open','launch'], intent:'open_app', conf:97.2 },
      { words:['weather','mausam','rain','temp'],   intent:'weather_query', conf:98.1 },
      { words:['music','song','play','gana'],       intent:'music_control', conf:96.4 },
      { words:['schedule','meeting','cal','remind'], intent:'schedule', conf:94.8 },
      { words:['cpu','ram','battery','system'],     intent:'system_check', conf:99.1 },
    ];
    const lower = val.toLowerCase();
    const match = intents.find(i => i.words.some(w => lower.includes(w)));
    setPreview(match ? { intent:match.intent, conf:match.conf } : null);
  }, [val]);

  return (
    <div style={{ padding:'10px 14px 14px', flexShrink:0 }}>
      {/* Listening waveform */}
      {isListening && (
        <div style={{ height:34, marginBottom:8, borderRadius:10, display:'flex',
          alignItems:'center', justifyContent:'center', gap:3, padding:'0 16px',
          background:ca(J.green,0.07), border:`1px solid ${ca(J.green,0.25)}` }}>
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.green, marginRight:10 }}>LISTENING</span>
          {Array.from({length:20}).map((_,i)=>(
            <div key={i} style={{ width:3, borderRadius:2, background:J.green, opacity:0.8,
              height: 6 + (Math.sin(i)*10+10),
              animation:`j-wave ${0.4+(i%4)*0.15}s ease-in-out ${(i%5)*0.08}s infinite`,
              transformOrigin:'center' }} />
          ))}
        </div>
      )}

      {/* Intent preview */}
      {preview && <CommandPreview {...preview} />}

      {/* Input row */}
      <div style={{ display:'flex', gap:8, alignItems:'center',
        borderRadius:16, background:'rgba(10,15,28,0.9)',
        border:`1px solid ${busy ? ca(J.cyan,0.12) : ca(J.cyan,0.38)}`,
        boxShadow:`0 0 14px ${ca(J.cyan, busy?0.06:0.16)}`,
        padding:'7px 7px 7px 16px',
        backdropFilter:'blur(8px)',
        transition:'border-color 0.3s, box-shadow 0.3s',
      }}>
        <input ref={inputRef} value={val}
          onChange={e=>setVal(e.target.value)}
          onKeyDown={e=>{ if(e.key==='Enter'&&!e.shiftKey){ e.preventDefault(); handleSend(); }}}
          disabled={busy||isListening}
          placeholder={isListening?'Listening…':busy?'A.E.R.I.S responding…':'Ask anything…'}
          style={{ flex:1, background:'transparent', border:'none', outline:'none',
            fontFamily:"'JetBrains Mono',monospace", fontSize:13,
            color: busy ? J.textMut : J.textPri, cursor: busy?'not-allowed':'text' }} />

        {/* Mic */}
        <div onClick={onMic} style={{ width:36,height:36,borderRadius:18,cursor:'pointer',
          background: isListening ? ca(J.green,0.2) : ca(J.cyan,0.12),
          border:`1px solid ${isListening ? ca(J.green,0.7) : ca(J.cyan,0.45)}`,
          boxShadow: isListening ? `0 0 18px ${J.green},0 0 36px ${ca(J.green,0.25)}` : `0 0 10px ${ca(J.cyan,0.25)}`,
          display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0,
          transition:'all 0.25s',
          animation: isListening ? 'j-glow-green 0.9s ease-in-out infinite' : 'none',
        }}>
          {isListening
            ? <div style={{ width:12,height:12,borderRadius:3, background:J.green }} />
            : <svg width="14" height="18" viewBox="0 0 14 18" fill="none">
                <rect x="4" y="0" width="6" height="12" rx="3" fill={J.cyan}/>
                <path d="M1 9c0 3.3 2.7 6 6 6s6-2.7 6-6" stroke={J.cyan} strokeWidth="1.5" fill="none" strokeLinecap="round"/>
                <line x1="7" y1="15" x2="7" y2="18" stroke={J.cyan} strokeWidth="1.5" strokeLinecap="round"/>
                <line x1="4" y1="18" x2="10" y2="18" stroke={J.cyan} strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
          }
        </div>

        {/* Send */}
        <div onClick={handleSend} style={{ width:36,height:36,borderRadius:18,cursor:val.trim()&&!busy?'pointer':'default',
          background: val.trim()&&!busy ? `linear-gradient(135deg,${J.cyan},${J.purple})` : ca(J.cyan,0.2),
          boxShadow: val.trim()&&!busy ? `0 0 20px ${ca(J.cyan,0.7)},0 0 8px ${ca(J.purple,0.4)}` : 'none',
          display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0,
          transition:'all 0.2s',
        }}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M1 7h12M7 1l6 6-6 6" stroke={J.bg} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </div>

      {/* Hints */}
      <div style={{ display:'flex', gap:14, marginTop:7, paddingLeft:4 }}>
        {['↵ send','⌥ mic','Hinglish OK'].map(h=>(
          <span key={h} style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut }}>{h}</span>
        ))}
      </div>
    </div>
  );
}

function GlassChatPanel({ messages, streamId, streamText, aiState, onSend, onMic }) {
  const J = window.J;
  const bottomRef = React.useRef(null);
  const latestAI = [...messages].reverse().find(m=>m.role==='ai')?.id;

  React.useEffect(() => {
    if (bottomRef.current) {
      const el = bottomRef.current.parentElement;
      el.scrollTop = el.scrollHeight;
    }
  }, [messages.length, streamText]);

  return (
    <div style={{ width:390, height:'100%', display:'flex', flexDirection:'column',
      background:'rgba(13,21,37,0.75)', backdropFilter:'blur(16px)',
      borderLeft:`1px solid rgba(30,41,59,0.6)`,
      boxShadow:'-8px 0 40px rgba(0,0,0,0.4), inset 1px 0 0 rgba(0,212,255,0.06)',
      flexShrink:0,
    }}>
      {/* Header */}
      <div style={{ height:56, padding:'0 20px', display:'flex', alignItems:'center',
        justifyContent:'space-between', flexShrink:0,
        borderBottom:`1px solid rgba(30,41,59,0.7)`,
        background:'rgba(10,15,28,0.4)',
      }}>
        <div>
          <div style={{ fontSize:11, fontWeight:700, letterSpacing:'2px', color:J.textPri }}>CONVERSATION</div>
          <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:J.textMut, marginTop:2 }}>
            Session · {messages.length} messages
          </div>
        </div>
        <div style={{ display:'flex', gap:6, alignItems:'center' }}>
          {(aiState==='PROCESSING'||aiState==='SPEAKING') && (
            <window.JTag text={aiState==='PROCESSING'?'THINKING':'GENERATING'} color={aiState==='PROCESSING'?J.magenta:J.purple} pulse />
          )}
          <window.JTag text="LIVE" color={J.red} pulse />
        </div>
      </div>

      {/* Suggestion chips */}
      <div style={{ padding:'10px 14px 0', display:'flex', gap:6, flexWrap:'wrap', flexShrink:0 }}>
        {SUGGESTION_CHIPS.map(chip=>(
          <div key={chip} onClick={() => onSend(chip)} style={{
            padding:'4px 10px', borderRadius:20, cursor:'pointer', fontSize:11,
            fontFamily:"'JetBrains Mono',monospace",
            background:ca(J.cyan,0.07), border:`1px solid ${ca(J.cyan,0.2)}`, color:J.textSec,
            transition:'all 0.18s',
          }}
          onMouseEnter={e=>{e.currentTarget.style.background=ca(J.cyan,0.14);e.currentTarget.style.color=J.textPri;}}
          onMouseLeave={e=>{e.currentTarget.style.background=ca(J.cyan,0.07);e.currentTarget.style.color=J.textSec;}}
          >{chip}</div>
        ))}
      </div>

      {/* Messages */}
      <div style={{ flex:1, overflowY:'auto', padding:'14px 16px', display:'flex', flexDirection:'column', gap:14 }}>
        {messages.map(msg=>(
          <ChatBubble key={msg.id} msg={msg}
            isStreaming={msg.id===streamId}
            streamText={msg.id===streamId?streamText:''} />
        ))}
        {aiState==='PROCESSING' && <TypingDots />}
        <div ref={bottomRef} />
      </div>

      <ChatInput onSend={onSend} onMic={onMic} aiState={aiState} />
    </div>
  );
}

Object.assign(window, { GlassChatPanel });
