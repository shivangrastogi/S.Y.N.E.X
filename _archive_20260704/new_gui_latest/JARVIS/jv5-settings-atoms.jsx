// ─── JARVIS v5 — Settings Atoms ─────────────────────────────────────────────
// Reusable primitives for the settings console: Toggle, Slider, Radio,
// OptionCard, MiniReactor variants, Card, etc.

const { J, ca } = window;

// ─── Toggle Switch ──────────────────────────────────────────────────────────
function SToggle({ on, onChange, color = J.cyan, size = 'md' }) {
  const sizes = {
    sm: { w: 28, h: 16, thumb: 10 },
    md: { w: 36, h: 20, thumb: 14 },
  };
  const dim = sizes[size];
  return (
    <div
      onClick={() => onChange(!on)}
      style={{
        width: dim.w, height: dim.h, borderRadius: dim.h / 2,
        background: on ? ca(color, 0.25) : 'rgba(255,255,255,0.06)',
        border: `1px solid ${on ? ca(color, 0.55) : 'rgba(255,255,255,0.1)'}`,
        boxShadow: on ? `0 0 8px ${ca(color, 0.35)}, inset 0 0 4px ${ca(color, 0.15)}` : 'none',
        position: 'relative', cursor: 'pointer',
        transition: 'all 0.2s cubic-bezier(0.4,0,0.2,1)',
        flexShrink: 0,
      }}
    >
      <div style={{
        position: 'absolute',
        left: on ? dim.w - dim.thumb - 3 : 2,
        top: (dim.h - dim.thumb) / 2 - 1,
        width: dim.thumb, height: dim.thumb, borderRadius: '50%',
        background: on ? color : 'rgba(200,210,225,0.6)',
        boxShadow: on ? `0 0 6px ${color}` : 'none',
        transition: 'all 0.22s cubic-bezier(0.4,0,0.2,1)',
      }} />
    </div>
  );
}

// ─── Slider ────────────────────────────────────────────────────────────────
function SSlider({ value, onChange, min = 0, max = 100, color = J.cyan, unit = '' }) {
  const trackRef = React.useRef(null);
  const [dragging, setDragging] = React.useState(false);

  const update = (clientX) => {
    if (!trackRef.current) return;
    const rect = trackRef.current.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    onChange(Math.round(min + pct * (max - min)));
  };

  const onMouseDown = (e) => {
    setDragging(true);
    update(e.clientX);
    const onMove = (ev) => update(ev.clientX);
    const onUp = () => {
      setDragging(false);
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  };

  const pct = ((value - min) / (max - min)) * 100;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1 }}>
      <div
        ref={trackRef}
        onMouseDown={onMouseDown}
        style={{
          flex: 1, height: 4, borderRadius: 2,
          background: 'rgba(255,255,255,0.06)',
          position: 'relative', cursor: 'pointer',
        }}
      >
        {/* Fill */}
        <div style={{
          position: 'absolute', left: 0, top: 0, height: '100%',
          width: `${pct}%`, borderRadius: 2,
          background: `linear-gradient(90deg, ${ca(color, 0.5)}, ${color})`,
          boxShadow: `0 0 6px ${ca(color, 0.5)}`,
        }} />
        {/* Thumb */}
        <div style={{
          position: 'absolute', left: `${pct}%`, top: '50%',
          transform: `translate(-50%, -50%) scale(${dragging ? 1.15 : 1})`,
          width: 12, height: 12, borderRadius: '50%',
          background: color,
          boxShadow: `0 0 ${dragging ? 14 : 8}px ${color}, 0 0 0 2px rgba(8,12,22,0.95)`,
          transition: 'transform 0.15s, box-shadow 0.15s',
        }} />
      </div>
      <span style={{
        fontFamily: "'JetBrains Mono',monospace", fontSize: 10, fontWeight: 700,
        color: color, minWidth: 32, textAlign: 'right',
      }}>{value}{unit}</span>
    </div>
  );
}

// ─── Radio Group (segmented) ────────────────────────────────────────────────
function SRadio({ options, value, onChange, color = J.cyan, compact = false }) {
  return (
    <div style={{
      display: 'inline-flex', borderRadius: 8, padding: 3,
      background: 'rgba(0,0,0,0.25)',
      border: '1px solid rgba(255,255,255,0.05)',
      flexShrink: 0,
    }}>
      {options.map(opt => {
        const v   = typeof opt === 'string' ? opt : opt.value;
        const lbl = typeof opt === 'string' ? opt : opt.label;
        const active = value === v;
        return (
          <button
            key={v}
            onClick={() => onChange(v)}
            style={{
              padding: compact ? '3px 8px' : '5px 12px',
              borderRadius: 6, border: 'none',
              background: active ? ca(color, 0.16) : 'transparent',
              boxShadow: active ? `inset 0 0 0 1px ${ca(color, 0.4)}` : 'none',
              fontFamily: "'JetBrains Mono',monospace",
              fontSize: compact ? 9 : 10,
              fontWeight: 700, letterSpacing: '0.5px',
              color: active ? color : J.textSec,
              cursor: 'pointer', transition: 'all 0.15s',
            }}
          >{lbl}</button>
        );
      })}
    </div>
  );
}

// ─── Setting Row (label + control) ──────────────────────────────────────────
function SRow({ label, hint, children, vertical = false }) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: vertical ? 'column' : 'row',
      alignItems: vertical ? 'stretch' : 'center',
      gap: vertical ? 8 : 16,
      padding: '10px 0',
      borderBottom: '1px solid rgba(255,255,255,0.04)',
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 500, color: J.textPri, letterSpacing: '0.1px' }}>{label}</div>
        {hint && (
          <div style={{ fontSize: 10, color: J.textMut, marginTop: 3, letterSpacing: '0.2px' }}>{hint}</div>
        )}
      </div>
      <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
        {children}
      </div>
    </div>
  );
}

// ─── Card ───────────────────────────────────────────────────────────────────
function SCard({ title, subtitle, accent = J.cyan, children, badge = null }) {
  return (
    <div style={{
      borderRadius: 12, position: 'relative',
      background: 'rgba(13,21,37,0.55)',
      border: '1px solid rgba(30,41,59,0.7)',
      padding: '16px 18px',
      marginBottom: 12,
    }}>
      {/* Accent stripe */}
      <div style={{
        position: 'absolute', left: 0, top: 14, bottom: 14, width: 2,
        background: accent, borderRadius: '0 2px 2px 0',
        boxShadow: `0 0 6px ${ca(accent, 0.5)}`,
      }} />

      {title && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
          <div>
            <div style={{
              fontFamily: "'JetBrains Mono',monospace", fontSize: 10, fontWeight: 700,
              letterSpacing: '2px', color: accent, marginBottom: 3,
            }}>{title}</div>
            {subtitle && (
              <div style={{ fontSize: 11, color: J.textMut, letterSpacing: '0.2px' }}>{subtitle}</div>
            )}
          </div>
          {badge && (
            <div style={{
              padding: '2px 7px', borderRadius: 6,
              background: ca(badge.color || J.amber, 0.12),
              border: `1px solid ${ca(badge.color || J.amber, 0.35)}`,
              fontFamily: "'JetBrains Mono',monospace", fontSize: 8, fontWeight: 700,
              letterSpacing: '1.2px', color: badge.color || J.amber,
            }}>{badge.text}</div>
          )}
        </div>
      )}

      {children}
    </div>
  );
}

// ─── Option Card (clickable, big) ───────────────────────────────────────────
function SOptionCard({ icon, label, sub, active, onClick, color = J.cyan, compact = false }) {
  const [hov, setHov] = React.useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        textAlign: 'left',
        padding: compact ? '10px 12px' : '14px 14px',
        borderRadius: 10,
        background: active ? ca(color, 0.1) : hov ? 'rgba(255,255,255,0.025)' : 'rgba(13,21,37,0.5)',
        border: `1px solid ${active ? ca(color, 0.5) : hov ? 'rgba(0,212,255,0.18)' : 'rgba(30,41,59,0.65)'}`,
        boxShadow: active ? `0 0 16px ${ca(color, 0.2)}` : 'none',
        cursor: 'pointer', transition: 'all 0.18s',
        display: 'flex', flexDirection: 'column', gap: 4,
        position: 'relative', overflow: 'hidden',
      }}
    >
      {/* Active indicator dot */}
      {active && (
        <div style={{
          position: 'absolute', top: 8, right: 8,
          width: 6, height: 6, borderRadius: '50%',
          background: color, boxShadow: `0 0 6px ${color}`,
        }} />
      )}

      {icon && (
        <div style={{ marginBottom: 4, color: active ? color : J.textSec, transition: 'color 0.2s' }}>
          {icon}
        </div>
      )}
      <div style={{
        fontSize: compact ? 11 : 12, fontWeight: 600,
        color: active ? J.textPri : J.textSec, letterSpacing: '0.1px',
      }}>{label}</div>
      {sub && (
        <div style={{ fontSize: 9.5, color: J.textMut, letterSpacing: '0.2px', lineHeight: 1.4 }}>{sub}</div>
      )}
    </button>
  );
}

// ─── Mini Reactor variants (for visualizer picker) ──────────────────────────
function MiniReactor({ variant, size = 72 }) {
  const half = size / 2;
  if (variant === 'orbital') {
    return (
      <div style={{ position: 'relative', width: size, height: size }}>
        <div style={{ position: 'absolute', inset: 2, borderRadius: '50%',
          border: `1px dashed ${ca(J.cyan, 0.4)}`,
          animation: 'j-spin 8s linear infinite' }} />
        <div style={{ position: 'absolute', inset: 10, borderRadius: '50%',
          border: `1.5px solid ${ca(J.cyan, 0.6)}`,
          animation: 'j-spin-rev 5s linear infinite' }}>
          <div style={{ position: 'absolute', bottom: -3, left: '50%', transform: 'translateX(-50%)',
            width: 6, height: 6, borderRadius: '50%', background: J.cyan, boxShadow: `0 0 5px ${J.cyan}` }} />
        </div>
        <div style={{ position: 'absolute', inset: 22, borderRadius: '50%',
          border: `1.5px solid ${ca(J.cyan, 0.7)}`,
          animation: 'j-spin 3s linear infinite' }} />
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: J.cyan,
            boxShadow: `0 0 8px ${J.cyan}`, animation: 'j-pulse 2s ease-in-out infinite' }} />
        </div>
      </div>
    );
  }
  if (variant === 'neural') {
    const nodes = [
      [0.5, 0.15], [0.2, 0.35], [0.8, 0.35],
      [0.5, 0.5], [0.25, 0.75], [0.75, 0.75], [0.5, 0.85],
    ];
    return (
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <g style={{ animation: 'j-spin 24s linear infinite', transformOrigin: 'center' }}>
          {nodes.flatMap((a, i) =>
            nodes.slice(i + 1).map((b, j) => (
              <line key={`${i}-${j}`}
                x1={a[0] * size} y1={a[1] * size}
                x2={b[0] * size} y2={b[1] * size}
                stroke={ca(J.cyan, 0.18)} strokeWidth="0.6" />
            ))
          )}
          {nodes.map((n, i) => (
            <circle key={i} cx={n[0] * size} cy={n[1] * size} r="2.2"
              fill={J.cyan} opacity="0.85"
              style={{ filter: `drop-shadow(0 0 3px ${J.cyan})`,
                animation: `j-blink ${1.5 + i * 0.2}s ease-in-out ${i * 0.15}s infinite` }} />
          ))}
        </g>
      </svg>
    );
  }
  if (variant === 'liquid') {
    return (
      <div style={{ position: 'relative', width: size, height: size,
        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{
          width: size * 0.7, height: size * 0.7, borderRadius: '50%',
          background: `radial-gradient(circle, ${J.cyan}, ${ca(J.purple, 0.6)}, transparent 70%)`,
          filter: 'blur(2px)',
          animation: 'j-pulse 2.4s ease-in-out infinite',
        }} />
        <div style={{ position: 'absolute', inset: 0 }}>
          {[0,1,2,3,4].map(i => (
            <div key={i} style={{
              position: 'absolute',
              left: `${30 + Math.cos(i * 1.3) * 20}%`,
              top:  `${30 + Math.sin(i * 1.3) * 20}%`,
              width: 3, height: 3, borderRadius: '50%',
              background: J.cyan, boxShadow: `0 0 4px ${J.cyan}`,
              animation: `j-float-${i % 4} ${3 + i * 0.5}s ease-in-out infinite`,
            }} />
          ))}
        </div>
      </div>
    );
  }
  if (variant === 'quantum') {
    return (
      <div style={{ position: 'relative', width: size, height: size,
        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ position: 'relative', width: size * 0.7, height: size * 0.7,
          animation: 'j-spin-rev 16s linear infinite' }}>
          {[-25, -10, 5, 20].map((d, i) => {
            const s = Math.cos(d * Math.PI / 180);
            return (
              <div key={i} style={{
                position: 'absolute', left: '50%', top: '50%',
                width: s * size * 0.7, height: s * size * 0.7,
                marginLeft: -(s * size * 0.35),
                marginTop: Math.sin(d * Math.PI / 180) * size * 0.35 - (s * size * 0.35),
                borderRadius: '50%',
                border: `1px solid ${ca(J.cyan, 0.15 + i * 0.06)}`,
              }} />
            );
          })}
          {[0, 36, 72, 108, 144].map((deg, i) => (
            <div key={i} style={{
              position: 'absolute', inset: 0, borderRadius: '50%',
              border: `1px solid ${ca(J.cyan, 0.12)}`, transform: `rotateY(${deg}deg)`,
            }} />
          ))}
        </div>
      </div>
    );
  }
  if (variant === 'minimal') {
    return (
      <div style={{ width: size, height: size, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ width: 18, height: 18, borderRadius: '50%',
          background: `radial-gradient(circle, ${J.cyan}, ${ca(J.cyan, 0.3)} 60%, transparent)`,
          boxShadow: `0 0 16px ${J.cyan}`,
          animation: 'j-pulse 2.6s ease-in-out infinite' }} />
      </div>
    );
  }
  if (variant === 'holographic') {
    return (
      <div style={{ position: 'relative', width: size, height: size,
        display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {[0.95, 0.7, 0.45, 0.22].map((s, i) => (
          <div key={i} style={{
            position: 'absolute',
            width: size * s, height: size * s, borderRadius: '50%',
            border: `1px solid ${ca(i % 2 ? J.purple : J.cyan, 0.45)}`,
            animation: `j-pulse ${2 + i * 0.4}s ease-in-out ${i * 0.2}s infinite`,
          }} />
        ))}
        <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#fff',
          boxShadow: `0 0 8px white, 0 0 14px ${J.cyan}` }} />
      </div>
    );
  }
  return null;
}

// ─── Section Header ─────────────────────────────────────────────────────────
function SSectionHeader({ title, subtitle, accent = J.cyan }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{
        fontFamily: "'JetBrains Mono',monospace", fontSize: 9, fontWeight: 700,
        letterSpacing: '2.5px', color: accent, marginBottom: 8,
      }}>SETTINGS · {title.toUpperCase()}</div>
      <div style={{ fontSize: 22, fontWeight: 600, color: J.textPri, letterSpacing: '-0.2px', lineHeight: 1.2 }}>
        {title}
      </div>
      {subtitle && (
        <div style={{ fontSize: 12, color: J.textSec, marginTop: 6, lineHeight: 1.5, letterSpacing: '0.1px' }}>
          {subtitle}
        </div>
      )}
    </div>
  );
}

// ─── Tag/Pill ──────────────────────────────────────────────────────────────
function STag({ text, color = J.cyan, variant = 'solid' }) {
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '2px 8px', borderRadius: 5,
      background: ca(color, 0.1),
      border: `1px solid ${ca(color, 0.32)}`,
    }}>
      <div style={{ width: 4, height: 4, borderRadius: '50%', background: color,
        boxShadow: `0 0 3px ${color}` }} />
      <span style={{
        fontFamily: "'JetBrains Mono',monospace", fontSize: 8.5, fontWeight: 700,
        letterSpacing: '1px', color,
      }}>{text}</span>
    </div>
  );
}

Object.assign(window, {
  SToggle, SSlider, SRadio, SRow, SCard, SOptionCard, MiniReactor,
  SSectionHeader, STag,
});
