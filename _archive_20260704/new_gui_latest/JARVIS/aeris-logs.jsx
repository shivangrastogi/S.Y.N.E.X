// ─── A.E.R.I.S LOGS PANEL — real-time system log feed ────────────────────────

const LOG_TYPES = {
  SYS:    { label:'SYS',    color: window.AERIS_COLORS.textMut  },
  NLU:    { label:'NLU',    color: window.AERIS_COLORS.cyan     },
  ACT:    { label:'ACT',    color: window.AERIS_COLORS.green    },
  MIC:    { label:'MIC',    color: window.AERIS_COLORS.green    },
  TTS:    { label:'TTS',    color: window.AERIS_COLORS.purple   },
  ERR:    { label:'ERR',    color: window.AERIS_COLORS.red      },
  MEM:    { label:'MEM',    color: window.AERIS_COLORS.amber    },
};

function LogLine({ log, fresh }) {
  const C = window.AERIS_COLORS;
  const type = LOG_TYPES[log.type] || LOG_TYPES.SYS;
  return (
    <div style={{
      display:'flex', gap:8, alignItems:'flex-start', padding:'3px 0',
      animation: fresh ? 'aeris-fadein 0.25s ease' : 'none',
      borderBottom:`1px solid ${C.border}20`,
    }}>
      <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:9, color:C.textMut, flexShrink:0, marginTop:1 }}>{log.time}</span>
      <div style={{
        padding:'1px 6px', borderRadius:4, flexShrink:0,
        background: type.color.replace('rgb','rgba').replace(')',',0.12)'),
        border:`1px solid ${type.color.replace('rgb','rgba').replace(')',',0.25)')}`,
      }}>
        <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:8, fontWeight:700, color:type.color }}>{type.label}</span>
      </div>
      <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:9, color: log.highlight ? type.color : C.textSec, lineHeight:'1.5', flex:1 }}>{log.text}</span>
    </div>
  );
}

function SystemLogsPanel({ logs, expanded, onToggle }) {
  const C = window.AERIS_COLORS;
  const bottomRef = React.useRef(null);
  const prevLen   = React.useRef(0);

  React.useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ block:'nearest' });
    }
  }, [logs.length]);

  return (
    <div style={{
      borderTop:`1px solid ${C.border}`,
      background:`${C.card}cc`,
      transition:'height 0.3s cubic-bezier(0.4,0,0.2,1)',
      height: expanded ? 180 : 40,
      overflow:'hidden', flexShrink:0, position:'relative',
    }}>
      {/* Header */}
      <div
        onClick={onToggle}
        style={{
          height:40, display:'flex', alignItems:'center', justifyContent:'space-between',
          padding:'0 16px', cursor:'pointer',
          borderBottom: expanded ? `1px solid ${C.border}` : 'none',
        }}
      >
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <div style={{ width:6, height:6, borderRadius:'50%', background:C.green, boxShadow:`0 0 6px ${C.green}`, animation:'aeris-blink 1.5s infinite' }} />
          <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:10, fontWeight:700, letterSpacing:'1.8px', color:C.textSec }}>SYSTEM LOGS</span>
          <div style={{
            padding:'1px 6px', borderRadius:4,
            background:'rgba(0,212,255,0.1)', border:'1px solid rgba(0,212,255,0.25)',
          }}>
            <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:8, fontWeight:700, color:C.cyan }}>{logs.length}</span>
          </div>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:12 }}>
          {/* Latest log preview when collapsed */}
          {!expanded && logs.length > 0 && (
            <span style={{ fontFamily:"'JetBrains Mono', monospace", fontSize:9, color:C.textMut, maxWidth:320, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
              {logs[logs.length-1].text}
            </span>
          )}
          <svg width="12" height="8" viewBox="0 0 12 8" fill="none" style={{ transform: expanded ? 'rotate(180deg)' : 'none', transition:'transform 0.3s', flexShrink:0 }}>
            <path d="M1 1l5 5 5-5" stroke={C.textMut} strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </div>
      </div>

      {/* Log lines */}
      {expanded && (
        <div style={{ height:140, overflowY:'auto', padding:'6px 16px' }}>
          {logs.map((log, i) => (
            <LogLine key={log.id} log={log} fresh={i === logs.length - 1} />
          ))}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  );
}

Object.assign(window, { SystemLogsPanel, LOG_TYPES });
