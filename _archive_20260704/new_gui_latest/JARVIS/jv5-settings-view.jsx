// ─── JARVIS v5 — Settings Main View + Live Preview ──────────────────────────

const { J, ca } = window;

// ─── Default settings state ──────────────────────────────────────────────────
const DEFAULT_SETTINGS = {
  // AI Core
  personality:'jarvis', humor:60, verbosity:45, technical:70, emotion:55,
  showReasoning:true, showLogs:true, showConfidence:true, showPlanning:false,
  rememberProjects:true, workspaceMemory:true, sessionContinuity:true, learnHabits:true,
  // Appearance
  theme:'tactical', density:'Balanced', visualizer:'orbital',
  animations:80, particles:65, glow:55,
  fog:true, depthBlur:true, liveParts:true, reactGlow:true, audioReact:true,
  // Voice
  wakeWord:'aeris', recogMode:'hybrid',
  micSens:65, noiseSupp:true, echoCanc:true, vadThresh:40,
  ttsVoice:'aria', ttsSpeed:60, ttsTone:55, ttsDepth:50,
  langEn:true, langHi:true, langHinglish:true, langAuto:true,
  // Automation
  autoLevel:'assisted', confirmDest:true, appPerms:{},
  actOpen:true, actClose:true, actBrowser:true, actFiles:false,
  actClip:true, actKbd:true, actMouse:false,
  // Memory
  memMode:'persist', memConv:true, memProj:true, memPref:true,
  memApps:true, memRoutines:true, memPatterns:false,
  // Models
  model:'claude-haiku', vram:8, gpuAccel:true, quant:'q5',
  // General
  launchBoot:true, minTray:true, silent:false, compactStart:false,
  autoFocus:true, smartSugg:true, hideIdle:false, adaptive:true,
  timeFmt:'24h', tempUnit:'°C',
  // Desktop
  detectApps:true, detectCoding:true, detectBrowser:true, detectTitle:true,
  restoreFlow:true, workspaceSugg:true, smartGroup:false, focusDetect:true,
  ocr:false, uiDetect:false, workflowAssist:false,
  // Gestures
  handTrack:false, webcamGest:false, airGest:false, poseDetect:false,
  gestSens:50, trackMode:'bal', gestOverlay:true,
  // Security
  permMic:true, permCam:false, permAuto:true, permFs:false, permBrowser:true,
  privacyMode:'hybrid',
  confDelete:true, confTerm:true, confBrowser:false, confSystem:true,
  bioFace:false, bioVoice:false, bioGest:false,
  // Notifications
  notifTask:true, notifWorkspace:true, notifAI:true, notifAuto:false, notifVoice:true,
  notifStyle:'glass',
  // Performance
  perfMode:'bal', gpuCap:75, cpuCap:60, partComplex:50, fps:60,
  // Developer
  dbgRouting:false, dbgLatency:true, dbgTokens:false, dbgExec:false, dbgMem:false, dbgAuto:true,
  // Labs
  labs:{ proactive:true, ambient:true },
};

// ─── Category nav rail ──────────────────────────────────────────────────────
function SettingsNav({ active, onSelect }) {
  const cats = window.SETTINGS_CATEGORIES;
  const icons = window.CAT_ICONS;
  return (
    <div style={{
      width:240, flexShrink:0, height:'100%', overflowY:'auto',
      borderRight:`1px solid rgba(30,41,59,0.6)`,
      background:'rgba(8,12,22,0.5)', padding:'18px 12px',
    }}>
      <div style={{
        fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
        letterSpacing:'2.5px', color:J.textMut, padding:'4px 10px 12px',
      }}>SETTINGS</div>

      {cats.map(cat => {
        const isActive = active === cat.key;
        return (
          <NavItem key={cat.key} cat={cat} active={isActive}
            onClick={() => onSelect(cat.key)} icon={icons[cat.icon]} />
        );
      })}

      {/* Footer */}
      <div style={{ marginTop:18, padding:'12px 10px 0',
        borderTop:'1px solid rgba(30,41,59,0.5)' }}>
        <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut, letterSpacing:'1px' }}>
          JARVIS v3.2 · Build 2026.05
        </div>
        <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut, marginTop:3, letterSpacing:'0.4px' }}>
          {Object.keys(DEFAULT_SETTINGS).length} settings · 14 categories
        </div>
      </div>
    </div>
  );
}

function NavItem({ cat, active, onClick, icon }) {
  const [hov, setHov] = React.useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        width:'100%', display:'flex', alignItems:'center', gap:10,
        padding:'8px 10px', borderRadius:8, cursor:'pointer',
        background: active ? ca(cat.accent, 0.1) : hov ? 'rgba(255,255,255,0.025)' : 'transparent',
        border:`1px solid ${active ? ca(cat.accent, 0.32) : 'transparent'}`,
        boxShadow: active ? `0 0 12px ${ca(cat.accent, 0.12)}` : 'none',
        marginBottom:2, transition:'all 0.18s ease',
        position:'relative',
      }}
    >
      {active && (
        <div style={{ position:'absolute', left:-1, top:8, bottom:8, width:2,
          background: cat.accent, borderRadius:'0 2px 2px 0',
          boxShadow:`0 0 6px ${cat.accent}` }} />
      )}
      <div style={{ color: active ? cat.accent : hov ? J.textSec : J.textMut, transition:'color 0.2s', flexShrink:0 }}>
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none">{icon}</svg>
      </div>
      <span style={{
        flex:1, textAlign:'left',
        fontSize:12, fontWeight: active ? 600 : 500,
        color: active ? J.textPri : hov ? 'rgb(210,225,240)' : J.textSec,
        transition:'color 0.2s', letterSpacing:'0.1px',
      }}>{cat.label}</span>
      {cat.beta && (
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:7.5, fontWeight:700,
          letterSpacing:'1px', color: J.magenta,
          background: ca(J.magenta, 0.12), padding:'1px 5px', borderRadius:3 }}>BETA</span>
      )}
    </button>
  );
}

// ─── Live Preview Pane ──────────────────────────────────────────────────────
function LivePreview({ s }) {
  const themeColors = {
    tactical: J.cyan,
    neon:     J.magenta,
    focus:    J.textSec,
    work:     '#5B9BD5',
    minimal:  J.textPri,
    glass:    '#A0E9FF',
    holo:     J.purple,
    black:    J.cyan,
  };
  const accent = themeColors[s.theme] || J.cyan;

  return (
    <div style={{
      width:360, flexShrink:0, height:'100%',
      borderLeft:`1px solid rgba(30,41,59,0.6)`,
      background:'rgba(8,12,22,0.5)',
      display:'flex', flexDirection:'column',
      overflow:'hidden',
    }}>
      {/* Header */}
      <div style={{ padding:'16px 18px 14px', borderBottom:'1px solid rgba(30,41,59,0.5)',
        display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <div>
          <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
            letterSpacing:'2px', color:J.cyan }}>LIVE PREVIEW</div>
          <div style={{ fontSize:11, color:J.textMut, marginTop:2 }}>
            Changes reflect here in real-time
          </div>
        </div>
        <div style={{ width:6, height:6, borderRadius:'50%', background:J.green,
          boxShadow:`0 0 6px ${J.green}`, animation:'j-blink 1.5s infinite' }} />
      </div>

      {/* Preview content */}
      <div style={{ flex:1, overflowY:'auto', padding:'18px' }}>

        {/* Mini reactor */}
        <div style={{ display:'flex', justifyContent:'center', alignItems:'center',
          height: 180, position:'relative',
          background:'radial-gradient(circle, rgba(0,212,255,0.06), transparent 70%)',
          borderRadius:12, marginBottom:18,
        }}>
          <div style={{ transform: `scale(${1 + (s.glow - 50)/200})`, transition:'transform 0.3s' }}>
            <window.MiniReactor variant={s.visualizer || 'orbital'} size={120} />
          </div>
          {/* Particles overlay (intensity-based) */}
          {s.liveParts && Array.from({length: Math.round(s.particles / 10)}).map((_,i) => (
            <div key={i} style={{
              position:'absolute',
              left:`${20 + (i * 47) % 60}%`, top:`${15 + (i * 31) % 70}%`,
              width:2, height:2, borderRadius:'50%',
              background:accent, boxShadow:`0 0 4px ${accent}`,
              opacity: s.particles / 100,
              animation:`j-float-${i % 4} ${3 + (i % 5) * 0.5}s ease-in-out infinite`,
            }} />
          ))}
        </div>

        {/* AI mode card preview */}
        <div style={{
          borderRadius:10, padding:'12px 14px', marginBottom:12,
          background: 'rgba(13,21,37,0.6)',
          border:`1px solid ${ca(accent, 0.3)}`,
          position:'relative',
        }}>
          <div style={{ position:'absolute', left:0, top:10, bottom:10, width:2,
            background:accent, borderRadius:'0 2px 2px 0',
            boxShadow:`0 0 6px ${accent}` }} />
          <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9,
            color:accent, letterSpacing:'1.5px', fontWeight:700 }}>
            CURRENT MODE
          </div>
          <div style={{ fontSize:14, fontWeight:600, color:J.textPri, marginTop:4 }}>
            {(window.PERSONALITY_MODES.find(p => p.key === s.personality) || {}).label || s.personality}
          </div>
          <div style={{ fontSize:10, color:J.textMut, marginTop:3, letterSpacing:'0.2px' }}>
            {(window.PERSONALITY_MODES.find(p => p.key === s.personality) || {}).sub || ''}
          </div>
        </div>

        {/* Sample AI message */}
        <div style={{ marginBottom:14 }}>
          <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
            letterSpacing:'1.5px', color:J.cyan, marginBottom:6 }}>SAMPLE OUTPUT</div>
          <div style={{
            borderRadius:8, position:'relative', overflow:'hidden',
            background:'rgba(13,21,37,0.7)',
            border:'1px solid rgba(30,41,59,0.7)',
          }}>
            <div style={{ position:'absolute', left:0, top:0, bottom:0, width:2,
              background:J.green, boxShadow:`0 0 6px ${J.green}` }} />
            <div style={{ padding:'5px 12px 5px 14px',
              background:`linear-gradient(90deg, ${ca(J.green, 0.06)}, transparent)`,
              borderBottom:'1px solid rgba(255,255,255,0.03)',
              display:'flex', justifyContent:'space-between', alignItems:'center' }}>
              <div style={{ display:'flex', alignItems:'center', gap:6 }}>
                <div style={{ width:4, height:4, borderRadius:'50%', background:J.green,
                  boxShadow:`0 0 3px ${J.green}` }} />
                <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, fontWeight:700,
                  letterSpacing:'1.5px', color:J.green }}>EXECUTED</span>
              </div>
              <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, color:J.textMut }}>180ms</span>
            </div>
            <div style={{ padding:'10px 12px 10px 14px',
              fontFamily:"'JetBrains Mono',monospace", fontSize:11, color:J.textPri, lineHeight:1.55 }}>
              {samplePreviewText(s)}
            </div>
            {s.showConfidence && (
              <div style={{ padding:'4px 12px 5px 14px',
                background:'rgba(0,0,0,0.15)', borderTop:'1px solid rgba(255,255,255,0.03)',
                display:'flex', justifyContent:'space-between' }}>
                <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, color:J.textMut }}>
                  intent: <span style={{ color:J.textSec }}>{samplePreviewIntent(s)}</span>
                </span>
                <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:8, color:J.green, fontWeight:700 }}>
                  98.4%
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Settings summary */}
        <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
          <PreviewLine label="Theme"        value={s.theme}        color={accent} />
          <PreviewLine label="Visualizer"   value={s.visualizer}   color={J.purple} />
          <PreviewLine label="Personality"  value={s.personality}  color={J.cyan} />
          <PreviewLine label="Wake word"    value={s.wakeWord==='aeris' ? 'Hey AERIS' : s.wakeWord==='jarvis' ? 'Jarvis' : 'Custom'} color={J.green} />
          <PreviewLine label="Autonomy"     value={s.autoLevel}    color={J.amber} />
          <PreviewLine label="Memory mode"  value={s.memMode}      color={J.amber} />
          <PreviewLine label="Model"        value={s.model.replace('claude-','')}        color={J.purple} />
          <PreviewLine label="Animations"   value={`${s.animations}%`} color={accent} />
          <PreviewLine label="Particles"    value={`${s.particles}%`}  color={accent} />
          <PreviewLine label="Glow"         value={`${s.glow}%`}       color={accent} />
        </div>
      </div>
    </div>
  );
}

function PreviewLine({ label, value, color }) {
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
      padding:'5px 0', borderBottom:'1px solid rgba(255,255,255,0.04)' }}>
      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut, letterSpacing:'0.4px' }}>{label}</span>
      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9.5, color, letterSpacing:'0.3px', fontWeight:600 }}>{value}</span>
    </div>
  );
}

function samplePreviewText(s) {
  const verbose = s.verbosity > 60;
  const humor   = s.humor > 60;
  const tech    = s.technical > 60;
  if (s.personality === 'minimal') return 'Chrome opened.';
  if (s.personality === 'tactical') return 'Chrome launched. Target acquired.';
  if (s.personality === 'jarvis') {
    if (humor) return verbose
      ? "Chrome's open, boss. Three tabs auto-restored — last one looks suspicious."
      : 'Chrome up, sir.';
    return tech ? 'Chrome 121.0.6167.140 launched · process PID 8421.' : 'Chrome khol diya, sir.';
  }
  if (s.personality === 'creative') return 'Browser portal opened — let\'s explore.';
  if (s.personality === 'companion') return 'There you go — Chrome\'s ready when you are 💙';
  if (s.personality === 'professional') return 'Chrome has been launched successfully.';
  return 'Chrome is now open.';
}

function samplePreviewIntent(s) {
  return 'open_app';
}

// ─── Main Settings View ─────────────────────────────────────────────────────
function SettingsView({ onClose }) {
  const [settings, setSettings] = React.useState(DEFAULT_SETTINGS);
  const [active, setActive]     = React.useState('aiCore');

  const set = (key, value) => setSettings(s => ({ ...s, [key]: value }));

  const SectionComponent = window.SECTION_COMPONENTS[active];

  return (
    <div style={{
      width:'100%', height:'100%',
      display:'flex', flexDirection:'column',
      animation:'j-fadein 0.32s ease',
      background:'rgba(6,10,18,0.5)',
      paddingLeft: 80,
      position: 'relative',
    }}>
      {/* Header */}
      <div style={{
        height:48, padding:'0 18px',
        display:'flex', alignItems:'center', justifyContent:'space-between',
        borderBottom:'1px solid rgba(30,41,59,0.6)',
        background:'rgba(8,12,22,0.7)', backdropFilter:'blur(10px)',
        flexShrink:0,
      }}>
        <div style={{ display:'flex', alignItems:'center', gap:10 }}>
          <div style={{ width:10, height:10, borderRadius:'50%', background:J.cyan, boxShadow:`0 0 8px ${J.cyan}` }} />
          <span style={{ fontSize:12, fontWeight:700, letterSpacing:'2.5px', color:J.textPri }}>JARVIS · SETTINGS</span>
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:J.textMut, letterSpacing:'0.3px' }}>
            · configure your AI consciousness
          </span>
        </div>

        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
          <button
            onClick={() => setSettings(DEFAULT_SETTINGS)}
            style={{
              padding:'5px 11px', borderRadius:6, cursor:'pointer',
              background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.08)',
              fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700, letterSpacing:'1px',
              color:J.textSec, transition:'all 0.18s',
            }}
            onMouseEnter={e => { e.currentTarget.style.color = J.amber; e.currentTarget.style.borderColor = ca(J.amber,0.4); }}
            onMouseLeave={e => { e.currentTarget.style.color = J.textSec; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'; }}
          >RESET</button>
          <button
            onClick={onClose}
            style={{
              padding:'5px 14px', borderRadius:6, cursor:'pointer',
              background:`linear-gradient(135deg, ${ca(J.cyan,0.2)}, ${ca(J.cyan,0.1)})`,
              border:`1px solid ${ca(J.cyan, 0.5)}`,
              boxShadow:`0 0 10px ${ca(J.cyan, 0.2)}`,
              fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700, letterSpacing:'1px',
              color:J.cyan, transition:'all 0.18s',
            }}
          >DONE</button>
          <button
            onClick={onClose}
            style={{ width:28, height:28, borderRadius:6, cursor:'pointer',
              background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.08)',
              display:'flex', alignItems:'center', justifyContent:'center',
              transition:'all 0.18s' }}
            onMouseEnter={e => e.currentTarget.style.background='rgba(248,113,113,0.1)'}
            onMouseLeave={e => e.currentTarget.style.background='rgba(255,255,255,0.04)'}
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M2 2l8 8M10 2l-8 8" stroke={J.textSec} strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </button>
        </div>
      </div>

      {/* 3-column body */}
      <div style={{ flex:1, display:'flex', overflow:'hidden' }}>
        <SettingsNav active={active} onSelect={setActive} />

        {/* Center content */}
        <div style={{ flex:1, overflowY:'auto', padding:'28px 32px', position:'relative' }}>
          {/* subtle grid background */}
          <div style={{ position:'absolute', inset:0, pointerEvents:'none',
            backgroundImage:`linear-gradient(rgba(0,212,255,0.012) 1px, transparent 1px),linear-gradient(90deg, rgba(0,212,255,0.012) 1px, transparent 1px)`,
            backgroundSize:'48px 48px' }} />
          <div style={{ maxWidth:680, position:'relative' }}>
            {SectionComponent && <SectionComponent s={settings} set={set} />}
          </div>
        </div>

        <LivePreview s={settings} />
      </div>
    </div>
  );
}

Object.assign(window, { SettingsView, DEFAULT_SETTINGS });
