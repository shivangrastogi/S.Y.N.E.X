// ─── A.E.R.I.S CHAT PANEL — real API + streaming responses ───────────────────

function ChatMessage({ msg, isStreaming, streamText }) {
  const C = window.AERIS_COLORS;
  const isAeris = msg.role === 'aeris';
  const displayText = isStreaming ? streamText : msg.text;

  return (
    <div style={{
      display:'flex', flexDirection:'column', gap:5,
      alignItems: isAeris ? 'flex-start' : 'flex-end',
      animation:'aeris-fadein 0.3s ease',
    }}>
      {/* Sender row */}
      <div style={{ display:'flex', gap:6, alignItems:'center' }}>
        {isAeris && (
          <div style={{
            width:6, height:6, borderRadius:'50%',
            background:C.cyan, boxShadow:`0 0 5px ${C.cyan}`,
            animation: isStreaming ? 'aeris-blink 0.7s infinite' : 'none',
          }} />
        )}
        <span style={{
          fontFamily:"'JetBrains Mono', monospace", fontSize:10, fontWeight:700,
          letterSpacing:'1px', color: isAeris ? C.cyan : C.textSec,
        }}>{isAeris ? 'A.E.R.I.S' : 'YOU'}</span>
        <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:9, color:C.textMut }}>{msg.time}</span>
      </div>

      {/* Bubble */}
      <div style={{
        maxWidth:'88%', padding:'10px 14px', borderRadius:14,
        background: isAeris ? 'rgba(13,21,37,0.9)' : 'rgba(0,212,255,0.08)',
        border:`1px solid ${isAeris ? C.border : 'rgba(0,212,255,0.28)'}`,
        backdropFilter:'blur(4px)',
        boxShadow: isAeris ? '0 2px 16px rgba(0,0,0,0.35)' : '0 2px 12px rgba(0,212,255,0.06)',
      }}>
        <span style={{
          fontFamily:"'JetBrains Mono', monospace", fontSize:12,
          color:C.textPri, lineHeight:'1.65', whiteSpace:'pre-wrap',
        }}>
          {displayText}
          {isStreaming && <span style={{ animation:'aeris-cursor 0.55s step-end infinite', color:C.cyan }}>▌</span>}
        </span>
      </div>

      {/* Execution tag */}
      {msg.tag && !isStreaming && (
        <window.Pill text={msg.tag.text} color={msg.tag.color} blink={false} />
      )}
    </div>
  );
}

function MicButton({ aiState, onMicClick, isListening }) {
  const C = window.AERIS_COLORS;
  const active = isListening;

  return (
    <div
      onClick={onMicClick}
      title={active ? 'Stop listening' : 'Click to speak'}
      style={{
        width:36, height:36, borderRadius:18, cursor:'pointer', flexShrink:0,
        background: active ? C.green.replace('rgb','rgba').replace(')',',0.25)') : 'rgba(0,212,255,0.15)',
        border:`1px solid ${active ? C.green.replace('rgb','rgba').replace(')',',0.7)') : 'rgba(0,212,255,0.5)'}`,
        boxShadow: active ? `0 0 18px ${C.green}, 0 0 32px ${C.green.replace('rgb','rgba').replace(')',',0.3)')}` : '0 0 12px rgba(0,212,255,0.3)',
        display:'flex', alignItems:'center', justifyContent:'center',
        transition:'all 0.25s ease',
        animation: active ? 'aeris-glow-green 1s ease-in-out infinite' : 'none',
      }}
    >
      {active ? (
        // Stop icon when listening
        <div style={{ width:12, height:12, borderRadius:3, background:C.green }} />
      ) : (
        <svg width="14" height="18" viewBox="0 0 14 18" fill="none">
          <rect x="4" y="0" width="6" height="12" rx="3" fill={C.cyan} />
          <path d="M1 9c0 3.3 2.7 6 6 6s6-2.7 6-6" stroke={C.cyan} strokeWidth="1.5" fill="none" strokeLinecap="round" />
          <line x1="7" y1="15" x2="7" y2="18" stroke={C.cyan} strokeWidth="1.5" strokeLinecap="round" />
          <line x1="4" y1="18" x2="10" y2="18" stroke={C.cyan} strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      )}
    </div>
  );
}

function ChatPanel({ messages, streamingId, streamText, aiState, onSend, onMicClick }) {
  const C = window.AERIS_COLORS;
  const [input, setInput] = React.useState('');
  const bottomRef = React.useRef(null);
  const inputRef  = React.useRef(null);
  const isListening = aiState === 'LISTENING';
  const isBusy = aiState === 'PROCESSING' || aiState === 'SPEAKING';

  React.useEffect(() => {
    if (bottomRef.current) {
      const parent = bottomRef.current.parentElement;
      parent.scrollTop = parent.scrollHeight;
    }
  }, [messages.length, streamText]);

  const handleSend = () => {
    const t = input.trim();
    if (!t || isBusy) return;
    setInput('');
    onSend(t);
    setTimeout(() => inputRef.current?.focus(), 50);
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  const msgCount = messages.length;

  return (
    <div style={{
      width:380, height:'100%', display:'flex', flexDirection:'column',
      background:C.panel, borderLeft:`1px solid ${C.border}`, flexShrink:0,
    }}>
      {/* Header */}
      <div style={{
        height:56, padding:'0 20px',
        display:'flex', alignItems:'center', justifyContent:'space-between',
        borderBottom:`1px solid ${C.border}`, flexShrink:0,
      }}>
        <div>
          <div style={{ fontSize:11, fontWeight:700, letterSpacing:'2px', color:C.textPri }}>CONVERSATION</div>
          <div style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:10, color:C.textMut, marginTop:2 }}>
            Session • {msgCount} messages
          </div>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          {isBusy && (
            <window.Pill
              text={aiState === 'PROCESSING' ? 'THINKING' : 'SPEAKING'}
              color={aiState === 'PROCESSING' ? C.cyan : C.purple}
              blink={true}
            />
          )}
          <window.Pill text="LIVE" color={C.red} blink={true} />
        </div>
      </div>

      {/* Messages */}
      <div style={{ flex:1, overflowY:'auto', padding:'16px', display:'flex', flexDirection:'column', gap:16 }}>
        {messages.map(msg => (
          <ChatMessage
            key={msg.id}
            msg={msg}
            isStreaming={msg.id === streamingId}
            streamText={msg.id === streamingId ? streamText : ''}
          />
        ))}

        {/* Processing dots */}
        {aiState === 'PROCESSING' && (
          <div style={{ display:'flex', flexDirection:'column', gap:5, alignItems:'flex-start', animation:'aeris-fadein 0.3s ease' }}>
            <div style={{ display:'flex', gap:6, alignItems:'center' }}>
              <div style={{ width:6, height:6, borderRadius:'50%', background:C.cyan, animation:'aeris-blink 0.8s infinite' }} />
              <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:10, fontWeight:700, color:C.cyan }}>A.E.R.I.S</span>
            </div>
            <div style={{
              padding:'12px 16px', borderRadius:14,
              background:'rgba(13,21,37,0.9)', border:`1px solid ${C.border}`,
              display:'flex', gap:5, alignItems:'center',
            }}>
              {[0,1,2].map(i => (
                <div key={i} style={{
                  width:6, height:6, borderRadius:'50%', background:C.cyan,
                  boxShadow:`0 0 4px ${C.cyan}`,
                  animation:`aeris-blink 1s ${i*0.33}s infinite`,
                }} />
              ))}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div style={{ padding:'14px 16px 16px', borderTop:`1px solid ${C.border}`, flexShrink:0 }}>
        {/* Listening waveform */}
        {isListening && (
          <div style={{
            height:32, marginBottom:10, padding:'0 4px',
            display:'flex', alignItems:'center', justifyContent:'center', gap:3,
            borderRadius:10, background:'rgba(16,185,129,0.07)',
            border:`1px solid rgba(16,185,129,0.25)`,
          }}>
            <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:9, color:C.green, marginRight:8 }}>LISTENING</span>
            {Array.from({length:18}).map((_,i) => (
              <div key={i} style={{
                width:3, borderRadius:2,
                background:C.green, opacity:0.8,
                height: 6 + Math.random() * 18,
                animation:`aeris-wavebar ${0.4+Math.random()*0.5}s ease-in-out ${Math.random()*0.4}s infinite`,
                transformOrigin:'center',
              }} />
            ))}
          </div>
        )}

        <div style={{
          borderRadius:14, background:C.bg,
          border:`1px solid ${isBusy ? 'rgba(0,212,255,0.15)' : 'rgba(0,212,255,0.38)'}`,
          boxShadow:`0 0 14px rgba(0,212,255,${isBusy ? '0.08' : '0.18'})`,
          padding:'6px 6px 6px 14px',
          display:'flex', alignItems:'center', gap:8,
          transition:'border-color 0.3s, box-shadow 0.3s',
        }}>
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            disabled={isBusy || isListening}
            placeholder={isListening ? 'Listening…' : isBusy ? 'A.E.R.I.S is responding…' : 'Message A.E.R.I.S…'}
            style={{
              flex:1, background:'transparent', border:'none', outline:'none',
              fontFamily:"'JetBrains Mono', monospace", fontSize:13,
              color: isBusy ? C.textMut : C.textPri,
              cursor: isBusy ? 'not-allowed' : 'text',
            }}
          />
          <MicButton aiState={aiState} onMicClick={onMicClick} isListening={isListening} />
          <div
            onClick={handleSend}
            style={{
              width:36, height:36, borderRadius:18, cursor: (input.trim() && !isBusy) ? 'pointer' : 'default',
              background: (input.trim() && !isBusy) ? C.cyan : 'rgba(0,212,255,0.25)',
              boxShadow: (input.trim() && !isBusy) ? '0 0 20px rgba(0,212,255,0.85)' : 'none',
              display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0,
              transition:'background 0.2s, box-shadow 0.2s',
            }}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M1 7h12M7 1l6 6-6 6" stroke={C.bg} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
        </div>
        <div style={{ display:'flex', gap:16, marginTop:8 }}>
          {['↵ send', '⌥ mic', 'Hinglish OK'].map(h => (
            <span key={h} style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:9, color:C.textMut }}>{h}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { ChatPanel });
