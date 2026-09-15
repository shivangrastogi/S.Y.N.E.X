// ─── JARVIS v4 — Mission Control Chat Panel ─────────────────────────────────
// Restructured AI messages as 3-part cards: status band + content + meta footer
// User messages stay minimal & right-aligned

const { J, ca } = window;

const ACT_STYLES = {
  executed:           { label:'EXECUTED',     color: J.green   },
  knowledge:          { label:'KNOWLEDGE',    color: J.cyan    },
  knowledge_retrieved:{ label:'RETRIEVED',    color: J.cyan    },
  slot_filling:       { label:'CLARIFYING',   color: J.amber   },
  clarifying:         { label:'CLARIFYING',   color: J.amber   },
  clarification_needed:{label:'CLARIFYING',   color: J.amber   },
  error:              { label:'ERROR',        color: J.red     },
};

function getActStyle(act) {
  return ACT_STYLES[act] || { label: (act||'PROCESSED').toUpperCase(), color: J.cyan };
}

// ─── MISSION CONTROL AI MESSAGE CARD ─────────────────────────────────────────
function AIMissionCard({ msg, isStreaming, streamText }) {
  const text = isStreaming ? streamText : msg.text;
  const meta = msg.meta || {};
  const intent = meta.intent || 'general';
  const conf   = meta.conf   ?? meta.confidence ?? null;
  const ms     = meta.ms     ?? meta.latency_ms ?? null;
  const act    = meta.act    || meta.action     || 'executed';
  const style  = getActStyle(act);

  return (
    <div style={{ animation:'j-fadein 0.3s ease', maxWidth:'92%' }}>
      {/* Sender line */}
      <div style={{ display:'flex', gap:6, alignItems:'center', marginBottom:5 }}>
        <div style={{ width:6, height:6, borderRadius:'50%', background:J.cyan,
          boxShadow:`0 0 5px ${J.cyan}`,
          animation: isStreaming ? 'j-blink 0.7s infinite' : 'none' }} />
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9.5, fontWeight:700,
          letterSpacing:'1.2px', color:J.cyan }}>A.E.R.I.S</span>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut }}>· {msg.time}</span>
      </div>

      {/* The card */}
      <div style={{
        position:'relative',
        borderRadius:8, overflow:'hidden',
        background:'rgba(13,21,37,0.85)',
        backdropFilter:'blur(10px)',
        border:`1px solid rgba(30,41,59,0.8)`,
        boxShadow:'0 4px 16px rgba(0,0,0,0.35)',
      }}>
        {/* Left accent stripe — the ONLY bright element on the card */}
        <div style={{ position:'absolute', left:0, top:0, bottom:0, width:3,
          background: style.color,
          boxShadow:`0 0 8px ${style.color}`,
        }} />

        {/* Status header band */}
        {!isStreaming && (
          <div style={{
            padding:'6px 14px 6px 17px',
            display:'flex', justifyContent:'space-between', alignItems:'center',
            background:`linear-gradient(90deg, ${ca(style.color,0.08)}, transparent)`,
            borderBottom:`1px solid rgba(255,255,255,0.04)`,
          }}>
            <div style={{ display:'flex', alignItems:'center', gap:8 }}>
              {/* tiny status dot */}
              <div style={{ width:5, height:5, borderRadius:'50%',
                background:style.color, boxShadow:`0 0 4px ${style.color}`,
                animation:'j-blink 2s ease-in-out infinite' }} />
              <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5, fontWeight:700,
                letterSpacing:'2px', color:style.color }}>{style.label}</span>
            </div>
            {ms !== null && (
              <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5,
                color:J.textMut, letterSpacing:'0.5px' }}>{ms}ms</span>
            )}
          </div>
        )}

        {/* Content body */}
        <div style={{ padding:'12px 14px 12px 17px' }}>
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:12.5,
            color:J.textPri, lineHeight:'1.65', whiteSpace:'pre-wrap', letterSpacing:'0.1px' }}>
            {text}
            {isStreaming && <span style={{ animation:'j-cursor 0.5s step-end infinite', color:J.cyan }}>▌</span>}
          </span>
        </div>

        {/* Meta footer */}
        {!isStreaming && conf !== null && (
          <div style={{
            padding:'5px 14px 6px 17px',
            display:'flex', justifyContent:'space-between', alignItems:'center',
            borderTop:`1px solid rgba(255,255,255,0.03)`,
            background:'rgba(0,0,0,0.15)',
          }}>
            <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5,
              color:J.textMut, letterSpacing:'0.5px' }}>
              intent: <span style={{ color:J.textSec }}>{intent}</span>
            </span>
            <div style={{ display:'flex', alignItems:'center', gap:5 }}>
              {/* Mini confidence bar */}
              <div style={{ width:36, height:3, borderRadius:2,
                background:'rgba(255,255,255,0.08)', overflow:'hidden' }}>
                <div style={{
                  width:`${conf}%`, height:'100%',
                  background:`linear-gradient(90deg,${J.cyan},${style.color})`,
                  boxShadow:`0 0 4px ${style.color}`,
                }} />
              </div>
              <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8.5,
                color:style.color, fontWeight:700, letterSpacing:'0.4px' }}>
                {conf}%
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── USER MESSAGE (minimal, right-aligned) ──────────────────────────────────
function UserMessage({ msg }) {
  return (
    <div style={{ animation:'j-fadein 0.3s ease', alignSelf:'flex-end', maxWidth:'82%' }}>
      <div style={{ display:'flex', gap:6, alignItems:'center', justifyContent:'flex-end', marginBottom:4 }}>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut }}>{msg.time} ·</span>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9.5, fontWeight:700,
          letterSpacing:'1.2px', color:J.textSec }}>YOU</span>
      </div>
      <div style={{
        padding:'9px 14px', borderRadius:'14px 14px 4px 14px',
        background:'rgba(0,212,255,0.06)',
        border:`1px solid ${ca(J.cyan,0.22)}`,
        boxShadow:`0 2px 10px ${ca(J.cyan,0.05)}`,
      }}>
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:12,
          color:J.textPri, lineHeight:'1.6' }}>{msg.text}</span>
      </div>
    </div>
  );
}

// ─── THINKING DOTS ──────────────────────────────────────────────────────────
function ThinkingIndicator() {
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:5,
      alignItems:'flex-start', animation:'j-fadein 0.3s ease' }}>
      <div style={{ display:'flex', gap:6, alignItems:'center' }}>
        <div style={{ width:6, height:6, borderRadius:'50%', background:J.magenta,
          animation:'j-blink 0.8s infinite' }} />
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9.5, fontWeight:700,
          color:J.magenta, letterSpacing:'1.2px' }}>A.E.R.I.S</span>
      </div>
      <div style={{ padding:'10px 14px', borderRadius:8,
        background:'rgba(13,21,37,0.85)', border:`1px solid rgba(30,41,59,0.8)`,
        borderLeft:`3px solid ${J.magenta}`,
        display:'flex', gap:5, alignItems:'center' }}>
        {[0,1,2].map(i => (
          <div key={i} style={{ width:5, height:5, borderRadius:'50%', background:J.magenta,
            boxShadow:`0 0 4px ${J.magenta}`,
            animation:`j-blink 0.9s ${i*0.3}s infinite` }} />
        ))}
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10,
          color:J.textMut, marginLeft:8, letterSpacing:'0.5px' }}>thinking</span>
      </div>
    </div>
  );
}

// ─── SMART SUGGESTIONS (below input, context-aware) ─────────────────────────
function SmartSuggestions({ onSelect, hasMessages }) {
  // Show different suggestions based on context
  const suggestions = hasMessages
    ? ['Tell me more', 'Why?', 'Different approach', 'Show example']
    : ['What did I do today?', 'Resume my last task', 'Open dev workspace', 'System health check'];

  return (
    <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginBottom:10 }}>
      {suggestions.map(s => (
        <button
          key={s}
          onClick={() => onSelect(s)}
          style={{
            padding:'4px 10px', borderRadius:14, cursor:'pointer',
            fontFamily:"'JetBrains Mono',monospace", fontSize:10,
            background:'rgba(255,255,255,0.025)',
            border:`1px solid rgba(255,255,255,0.08)`,
            color: J.textSec, transition:'all 0.18s', letterSpacing:'0.2px',
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = ca(J.cyan, 0.08);
            e.currentTarget.style.borderColor = ca(J.cyan, 0.3);
            e.currentTarget.style.color = J.cyan;
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = 'rgba(255,255,255,0.025)';
            e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)';
            e.currentTarget.style.color = J.textSec;
          }}
        >
          {s}
        </button>
      ))}
    </div>
  );
}

// ─── CHAT INPUT ─────────────────────────────────────────────────────────────
function ChatInputBar({ onSend, onMic, aiState }) {
  const [val, setVal] = React.useState('');
  const inputRef = React.useRef(null);
  const busy = aiState === 'PROCESSING' || aiState === 'SPEAKING';
  const isListening = aiState === 'LISTENING';

  const handleSend = () => {
    if (!val.trim() || busy) return;
    onSend(val.trim());
    setVal('');
    setTimeout(() => inputRef.current?.focus(), 60);
  };

  return (
    <div style={{ padding:'10px 14px 14px', flexShrink:0 }}>
      <SmartSuggestions onSelect={onSend} hasMessages={true} />

      <div style={{ display:'flex', gap:7, alignItems:'center',
        borderRadius:14, background:'rgba(8,12,22,0.95)',
        border:`1px solid ${busy ? ca(J.cyan,0.1) : ca(J.cyan,0.3)}`,
        boxShadow:`0 0 12px ${ca(J.cyan, busy?0.04:0.12)}`,
        padding:'6px 6px 6px 14px',
        backdropFilter:'blur(8px)',
        transition:'border-color 0.3s, box-shadow 0.3s',
      }}>
        <input ref={inputRef} value={val}
          onChange={e => setVal(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
          disabled={busy || isListening}
          placeholder={isListening ? 'Listening…' : busy ? 'A.E.R.I.S responding…' : 'Ask anything…'}
          style={{ flex:1, background:'transparent', border:'none', outline:'none',
            fontFamily:"'JetBrains Mono',monospace", fontSize:12.5,
            color: busy ? J.textMut : J.textPri, cursor: busy ? 'not-allowed' : 'text',
            letterSpacing:'0.2px' }} />

        {/* Mic */}
        <div onClick={onMic} style={{
          width:32, height:32, borderRadius:16, cursor:'pointer', flexShrink:0,
          background: isListening ? ca(J.green,0.2) : 'rgba(255,255,255,0.04)',
          border:`1px solid ${isListening ? ca(J.green,0.6) : 'rgba(255,255,255,0.1)'}`,
          boxShadow: isListening ? `0 0 14px ${J.green}, 0 0 28px ${ca(J.green,0.25)}` : 'none',
          display:'flex', alignItems:'center', justifyContent:'center',
          transition:'all 0.25s',
          animation: isListening ? 'j-glow-green 0.9s ease-in-out infinite' : 'none',
        }}>
          {isListening
            ? <div style={{ width:10, height:10, borderRadius:2, background:J.green }} />
            : <svg width="12" height="16" viewBox="0 0 14 18" fill="none">
                <rect x="4" y="0" width="6" height="12" rx="3" fill={J.textSec}/>
                <path d="M1 9c0 3.3 2.7 6 6 6s6-2.7 6-6" stroke={J.textSec} strokeWidth="1.5" fill="none" strokeLinecap="round"/>
                <line x1="7" y1="15" x2="7" y2="18" stroke={J.textSec} strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
          }
        </div>

        {/* Send */}
        <div onClick={handleSend} style={{
          width:32, height:32, borderRadius:16,
          cursor: val.trim() && !busy ? 'pointer' : 'default',
          background: val.trim() && !busy
            ? `linear-gradient(135deg, ${J.cyan}, ${J.purple})`
            : 'rgba(255,255,255,0.05)',
          boxShadow: val.trim() && !busy
            ? `0 0 16px ${ca(J.cyan,0.6)}, 0 0 6px ${ca(J.purple,0.3)}`
            : 'none',
          display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0,
          transition:'all 0.2s',
        }}>
          <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
            <path d="M1 7h12M7 1l6 6-6 6"
              stroke={val.trim() && !busy ? J.bg : J.textMut}
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </div>

      {/* Hints */}
      <div style={{ display:'flex', gap:14, marginTop:7, paddingLeft:4 }}>
        {['↵ send', '⌥ mic', 'Hinglish supported'].map(h => (
          <span key={h} style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut, letterSpacing:'0.3px' }}>{h}</span>
        ))}
      </div>
    </div>
  );
}

// ─── MAIN CHAT PANEL ────────────────────────────────────────────────────────
function MissionControlChatPanel({ messages, streamId, streamText, aiState, onSend, onMic }) {
  const bottomRef = React.useRef(null);

  React.useEffect(() => {
    if (bottomRef.current) {
      const el = bottomRef.current.parentElement;
      el.scrollTop = el.scrollHeight;
    }
  }, [messages.length, streamText]);

  return (
    <div style={{
      width:390, height:'100%', display:'flex', flexDirection:'column',
      background:'rgba(13,21,37,0.65)',
      backdropFilter:'blur(20px)',
      borderLeft:`1px solid rgba(30,41,59,0.7)`,
      boxShadow:'-8px 0 40px rgba(0,0,0,0.4), inset 1px 0 0 rgba(0,212,255,0.04)',
      flexShrink:0,
    }}>
      {/* Header — Mission Control feel */}
      <div style={{
        height:56, padding:'0 18px',
        display:'flex', alignItems:'center', justifyContent:'space-between',
        flexShrink:0,
        borderBottom:`1px solid rgba(30,41,59,0.6)`,
        background:'rgba(8,12,22,0.55)',
      }}>
        <div>
          <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10.5, fontWeight:700,
            letterSpacing:'2.5px', color:J.textPri }}>MISSION CONTROL</div>
          <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9.5,
            color:J.textMut, marginTop:3, letterSpacing:'0.3px' }}>
            Session · {messages.length} messages · encrypted
          </div>
        </div>
        <div style={{ display:'flex', gap:5, alignItems:'center' }}>
          {(aiState === 'PROCESSING' || aiState === 'SPEAKING') && (
            <div style={{ padding:'2px 7px', borderRadius:6,
              background: ca(aiState === 'PROCESSING' ? J.magenta : J.purple, 0.12),
              border:`1px solid ${ca(aiState === 'PROCESSING' ? J.magenta : J.purple, 0.35)}`,
              display:'flex', alignItems:'center', gap:5 }}>
              <div style={{ width:4, height:4, borderRadius:'50%',
                background: aiState === 'PROCESSING' ? J.magenta : J.purple,
                animation:'j-blink 0.8s infinite' }} />
              <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, fontWeight:700,
                letterSpacing:'1.2px',
                color: aiState === 'PROCESSING' ? J.magenta : J.purple }}>
                {aiState === 'PROCESSING' ? 'THINKING' : 'STREAMING'}
              </span>
            </div>
          )}
          <div style={{ padding:'2px 7px', borderRadius:6,
            background: ca(J.red, 0.1),
            border:`1px solid ${ca(J.red, 0.3)}`,
            display:'flex', alignItems:'center', gap:5 }}>
            <div style={{ width:4, height:4, borderRadius:'50%', background:J.red,
              animation:'j-blink 1s infinite' }} />
            <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, fontWeight:700,
              letterSpacing:'1.2px', color:J.red }}>LIVE</span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex:1, overflowY:'auto', padding:'16px 14px', display:'flex',
        flexDirection:'column', gap:14 }}>
        {messages.map(msg => {
          if (msg.role === 'ai') {
            return <AIMissionCard key={msg.id} msg={msg}
              isStreaming={msg.id === streamId}
              streamText={msg.id === streamId ? streamText : ''} />;
          }
          return <UserMessage key={msg.id} msg={msg} />;
        })}
        {aiState === 'PROCESSING' && <ThinkingIndicator />}
        <div ref={bottomRef} />
      </div>

      <ChatInputBar onSend={onSend} onMic={onMic} aiState={aiState} />
    </div>
  );
}

Object.assign(window, { MissionControlChatPanel });
