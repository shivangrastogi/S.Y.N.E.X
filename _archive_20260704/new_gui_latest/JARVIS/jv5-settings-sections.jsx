// ─── JARVIS v5 — Settings Sections ──────────────────────────────────────────
// All 14 categories. Each section is a pure component receiving (settings, update)
// and rendering its UI. The full settings object is shared state in SettingsView.

const { J, ca } = window;
const { SToggle, SSlider, SRadio, SRow, SCard, SOptionCard, MiniReactor, SSectionHeader, STag } = window;

// ─── Category data ──────────────────────────────────────────────────────────
const SETTINGS_CATEGORIES = [
  { key:'general',   label:'General',        accent: J.cyan,    icon:'settings'  },
  { key:'aiCore',    label:'AI Core',        accent: J.cyan,    icon:'brain'     },
  { key:'voice',     label:'Voice',          accent: J.green,   icon:'mic'       },
  { key:'appearance',label:'Appearance',     accent: J.purple,  icon:'paint'     },
  { key:'desktop',   label:'Desktop Awareness',accent: J.cyan,  icon:'monitor'   },
  { key:'automation',label:'Automation',     accent: J.amber,   icon:'bolt'      },
  { key:'memory',    label:'Memory',         accent: J.amber,   icon:'memory'    },
  { key:'gestures',  label:'Gestures',       accent: J.magenta, icon:'hand', beta:true },
  { key:'security',  label:'Security',       accent: J.red,     icon:'lock'      },
  { key:'notifications',label:'Notifications',accent: J.cyan,   icon:'bell'      },
  { key:'models',    label:'Models',         accent: J.purple,  icon:'cpu'       },
  { key:'performance',label:'Performance',   accent: J.green,   icon:'gauge'     },
  { key:'developer', label:'Developer',      accent: J.cyan,    icon:'code'      },
  { key:'labs',      label:'Experimental Labs',accent: J.magenta,icon:'flask', beta:true },
];

const CAT_ICONS = {
  settings: <><circle cx="8" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M8 2v1.5M8 12.5V14M2 8h1.5M12.5 8H14" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></>,
  brain:    <><ellipse cx="8" cy="7" rx="4" ry="5" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M5 7h6M6 4.5h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></>,
  mic:      <><rect x="6" y="2" width="4" height="8" rx="2" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M3 8a5 5 0 0 0 10 0M8 13v2" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinecap="round"/></>,
  paint:    <><circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.3" fill="none"/><circle cx="6" cy="6" r="1" fill="currentColor"/><circle cx="11" cy="6" r="1" fill="currentColor"/><circle cx="11" cy="10" r="1" fill="currentColor"/></>,
  monitor:  <><rect x="2" y="3" width="12" height="8" rx="1" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M6 14h4M8 11v3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></>,
  bolt:     <><path d="M9 1L3 9h4l-1 6 6-8H8l1-6z" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinejoin="round"/></>,
  memory:   <><rect x="2" y="5" width="12" height="6" rx="1" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M5 5V3M9 5V3M5 11v2M9 11v2" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></>,
  hand:     <><path d="M5 8V3.5a1 1 0 0 1 2 0V8M7 8V2.5a1 1 0 0 1 2 0V8M9 8V3a1 1 0 0 1 2 0v7c0 2-1.5 3.5-3.5 3.5S4 12 4 10V6a1 1 0 0 1 2 0v3" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinecap="round"/></>,
  lock:     <><rect x="3" y="7" width="10" height="7" rx="1" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M5 7V5a3 3 0 0 1 6 0v2" stroke="currentColor" strokeWidth="1.3" fill="none"/></>,
  bell:     <><path d="M5 7a3 3 0 0 1 6 0v3l2 2H3l2-2V7zM7 13a1 1 0 0 0 2 0" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinejoin="round"/></>,
  cpu:      <><rect x="4" y="4" width="8" height="8" rx="1" stroke="currentColor" strokeWidth="1.3" fill="none"/><rect x="6" y="6" width="4" height="4" stroke="currentColor" strokeWidth="1" fill="none"/><path d="M6 4V2M10 4V2M6 14v-2M10 14v-2M4 6H2M4 10H2M14 6h-2M14 10h-2" stroke="currentColor" strokeWidth="1" strokeLinecap="round"/></>,
  gauge:    <><path d="M3 11a5 5 0 0 1 10 0" stroke="currentColor" strokeWidth="1.3" fill="none"/><path d="M8 11l3-3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></>,
  code:     <><path d="M5 4L2 8l3 4M11 4l3 4-3 4" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinecap="round" strokeLinejoin="round"/></>,
  flask:    <><path d="M6 2v4l-3 6c-.5 1 .3 2 1.4 2h7.2c1.1 0 1.9-1 1.4-2l-3-6V2" stroke="currentColor" strokeWidth="1.3" fill="none" strokeLinejoin="round"/><path d="M5 2h6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/></>,
};

// ── Personality modes ──
const PERSONALITY_MODES = [
  { key:'jarvis',       label:'Jarvis-like',  sub:'Calm genius. Iron Man feel.', icon:'⚡' },
  { key:'professional', label:'Professional', sub:'Crisp. Efficient. Formal.',   icon:'◆' },
  { key:'friendly',     label:'Friendly',     sub:'Warm, conversational.',       icon:'✦' },
  { key:'minimal',      label:'Minimal',      sub:'Just facts. No fluff.',       icon:'▪' },
  { key:'creative',     label:'Creative',     sub:'Playful, imaginative.',       icon:'✺' },
  { key:'tactical',     label:'Tactical',     sub:'Direct. Mission-focused.',    icon:'▲' },
  { key:'companion',    label:'Companion',    sub:'Personal. Empathetic.',       icon:'◉' },
  { key:'assistant',    label:'Assistant',    sub:'Neutral utility.',            icon:'○' },
];

// ─── SECTION: AI CORE ──────────────────────────────────────────────────────
function SecAICore({ s, set }) {
  return (
    <>
      <SSectionHeader title="AI Core" accent={J.cyan}
        subtitle="The brain. Personality, response style, and how transparently I think." />

      <SCard title="PERSONALITY MODE" subtitle="Choose how I behave by default." accent={J.cyan}>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginTop:6 }}>
          {PERSONALITY_MODES.map(p => (
            <SOptionCard key={p.key}
              icon={<span style={{ fontSize:18, color:s.personality===p.key?J.cyan:J.textMut }}>{p.icon}</span>}
              label={p.label} sub={p.sub}
              active={s.personality === p.key}
              onClick={() => set('personality', p.key)}
              color={J.cyan} compact />
          ))}
        </div>
      </SCard>

      <SCard title="RESPONSE STYLE" subtitle="Fine-tune how I express myself." accent={J.cyan}>
        <SRow label="Humor"           hint="Wit and lightness in replies">
          <div style={{ width:220 }}><SSlider value={s.humor}     onChange={v=>set('humor',v)}     color={J.cyan} /></div>
        </SRow>
        <SRow label="Verbosity"       hint="How much detail I include">
          <div style={{ width:220 }}><SSlider value={s.verbosity} onChange={v=>set('verbosity',v)} color={J.cyan} /></div>
        </SRow>
        <SRow label="Technical depth" hint="Domain language and precision">
          <div style={{ width:220 }}><SSlider value={s.technical} onChange={v=>set('technical',v)} color={J.cyan} /></div>
        </SRow>
        <SRow label="Emotion"         hint="Warmth in tone">
          <div style={{ width:220 }}><SSlider value={s.emotion}   onChange={v=>set('emotion',v)}   color={J.cyan} /></div>
        </SRow>
      </SCard>

      <SCard title="THINKING TRANSPARENCY" subtitle="See how I reach conclusions." accent={J.cyan}>
        <SRow label="Show reasoning stream"  hint="Display thinking steps live">
          <SToggle on={s.showReasoning} onChange={v=>set('showReasoning',v)} />
        </SRow>
        <SRow label="Show execution logs"    hint="Stream action history">
          <SToggle on={s.showLogs} onChange={v=>set('showLogs',v)} />
        </SRow>
        <SRow label="Show confidence levels" hint="Display intent confidence">
          <SToggle on={s.showConfidence} onChange={v=>set('showConfidence',v)} />
        </SRow>
        <SRow label="Show planning steps"    hint="Multi-step task plans before executing">
          <SToggle on={s.showPlanning} onChange={v=>set('showPlanning',v)} />
        </SRow>
      </SCard>

      <SCard title="CONTEXT INTELLIGENCE" subtitle="What I learn and remember." accent={J.cyan}>
        <SRow label="Remember ongoing projects"  hint="Track context across sessions">
          <SToggle on={s.rememberProjects} onChange={v=>set('rememberProjects',v)} />
        </SRow>
        <SRow label="Persistent workspace memory"hint="Recall window/app state">
          <SToggle on={s.workspaceMemory} onChange={v=>set('workspaceMemory',v)} />
        </SRow>
        <SRow label="Session continuity"         hint="Resume where you left off">
          <SToggle on={s.sessionContinuity} onChange={v=>set('sessionContinuity',v)} />
        </SRow>
        <SRow label="Learn habits over time"     hint="Adapt to your routines">
          <SToggle on={s.learnHabits} onChange={v=>set('learnHabits',v)} />
        </SRow>
      </SCard>
    </>
  );
}

// ─── SECTION: APPEARANCE ───────────────────────────────────────────────────
const THEMES = [
  { key:'tactical',     label:'Tactical',    sub:'Default. Cyan + purple.',  cs:[J.cyan, J.purple] },
  { key:'neon',         label:'Neon',        sub:'High contrast.',           cs:[J.cyan, J.magenta] },
  { key:'focus',        label:'Focus',       sub:'Muted, low-glow.',         cs:[J.textSec, J.cyan] },
  { key:'work',         label:'Work',        sub:'Blue, professional.',      cs:['#5B9BD5','#3F7DC9'] },
  { key:'minimal',      label:'Minimal',     sub:'Dark, no accents.',        cs:[J.textPri, J.textSec] },
  { key:'glass',        label:'Glass',       sub:'Soft glass, blur heavy.',  cs:['#A0E9FF','#B8B0FF'] },
  { key:'holo',         label:'Holographic', sub:'Iridescent shifts.',       cs:[J.cyan, J.purple, J.magenta] },
  { key:'black',        label:'Pure Black',  sub:'OLED-friendly.',           cs:[J.cyan, J.textPri] },
];

const VISUALIZERS = [
  { key:'orbital',     label:'Orbital Core',   sub:'Current style.'         },
  { key:'neural',      label:'Neural Mesh',    sub:'Connected nodes.'       },
  { key:'liquid',      label:'Liquid Energy',  sub:'Fluid simulation.'      },
  { key:'quantum',     label:'Quantum Sphere', sub:'Wireframe globe.'       },
  { key:'minimal',     label:'Minimal Pulse',  sub:'Single soft pulse.'     },
  { key:'holographic', label:'Holographic Eye',sub:'Concentric rings.'      },
];

function SecAppearance({ s, set }) {
  return (
    <>
      <SSectionHeader title="Appearance" accent={J.purple}
        subtitle="Themes, density, and how the AI core visually presents itself." />

      <SCard title="THEME" subtitle="Color and tone of the interface." accent={J.purple}>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8 }}>
          {THEMES.map(t => (
            <button key={t.key}
              onClick={() => set('theme', t.key)}
              style={{
                textAlign:'left', padding:'10px 12px', borderRadius:9, cursor:'pointer',
                background: s.theme === t.key ? ca(J.purple, 0.1) : 'rgba(13,21,37,0.5)',
                border:`1px solid ${s.theme === t.key ? ca(J.purple, 0.5) : 'rgba(30,41,59,0.65)'}`,
                boxShadow: s.theme === t.key ? `0 0 14px ${ca(J.purple, 0.18)}` : 'none',
                transition:'all 0.18s',
                display:'flex', alignItems:'center', gap:10,
              }}
            >
              <div style={{ display:'flex', gap:3 }}>
                {t.cs.map((c,i) => (
                  <div key={i} style={{ width:14, height:14, borderRadius:'50%', background:c,
                    boxShadow:`0 0 4px ${c}` }} />
                ))}
              </div>
              <div style={{ flex:1 }}>
                <div style={{ fontSize:11.5, fontWeight:600, color: s.theme === t.key ? J.textPri : J.textSec }}>{t.label}</div>
                <div style={{ fontSize:9.5, color: J.textMut, marginTop:1 }}>{t.sub}</div>
              </div>
            </button>
          ))}
        </div>
      </SCard>

      <SCard title="UI DENSITY" subtitle="How much breathing room." accent={J.purple}>
        <SRow label="Density">
          <SRadio options={['Compact','Balanced','Expanded','Cinematic']}
            value={s.density} onChange={v=>set('density',v)} color={J.purple} />
        </SRow>
      </SCard>

      <SCard title="CORE VISUALIZER" subtitle="The animated AI brain at the center." accent={J.purple} badge={{ text:'PREMIUM', color:J.amber }}>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:8 }}>
          {VISUALIZERS.map(v => (
            <button key={v.key}
              onClick={() => set('visualizer', v.key)}
              style={{
                padding:'12px 8px 10px', borderRadius:10, cursor:'pointer',
                background: s.visualizer === v.key ? ca(J.purple, 0.1) : 'rgba(13,21,37,0.5)',
                border:`1px solid ${s.visualizer === v.key ? ca(J.purple, 0.55) : 'rgba(30,41,59,0.65)'}`,
                boxShadow: s.visualizer === v.key ? `0 0 16px ${ca(J.purple, 0.2)}` : 'none',
                transition:'all 0.18s',
                display:'flex', flexDirection:'column', alignItems:'center', gap:6,
                position:'relative',
              }}
            >
              {s.visualizer === v.key && (
                <div style={{ position:'absolute', top:6, right:6, width:5, height:5, borderRadius:'50%',
                  background:J.purple, boxShadow:`0 0 5px ${J.purple}` }} />
              )}
              <MiniReactor variant={v.key} size={56} />
              <div style={{ fontSize:10, fontWeight:600, color: s.visualizer === v.key ? J.textPri : J.textSec }}>
                {v.label}
              </div>
              <div style={{ fontSize:8.5, color: J.textMut, textAlign:'center' }}>{v.sub}</div>
            </button>
          ))}
        </div>
      </SCard>

      <SCard title="ANIMATION" subtitle="Motion intensity and effects." accent={J.purple}>
        <SRow label="Animation intensity" hint="Overall motion strength">
          <div style={{ width:220 }}><SSlider value={s.animations} onChange={v=>set('animations',v)} color={J.purple} /></div>
        </SRow>
        <SRow label="Particle density"    hint="Ambient floating particles">
          <div style={{ width:220 }}><SSlider value={s.particles}  onChange={v=>set('particles',v)} color={J.purple} /></div>
        </SRow>
        <SRow label="Glow intensity"      hint="Halo and bloom">
          <div style={{ width:220 }}><SSlider value={s.glow}       onChange={v=>set('glow',v)} color={J.purple} /></div>
        </SRow>
      </SCard>

      <SCard title="AMBIENT EFFECTS" accent={J.purple}>
        <SRow label="Dynamic fog">      <SToggle color={J.purple} on={s.fog}        onChange={v=>set('fog',v)} /></SRow>
        <SRow label="Depth blur">       <SToggle color={J.purple} on={s.depthBlur}  onChange={v=>set('depthBlur',v)} /></SRow>
        <SRow label="Live particles">   <SToggle color={J.purple} on={s.liveParts}  onChange={v=>set('liveParts',v)} /></SRow>
        <SRow label="Reactive glow">    <SToggle color={J.purple} on={s.reactGlow}  onChange={v=>set('reactGlow',v)} /></SRow>
        <SRow label="Audio reactivity"> <SToggle color={J.purple} on={s.audioReact} onChange={v=>set('audioReact',v)} /></SRow>
      </SCard>
    </>
  );
}

// ─── SECTION: VOICE ────────────────────────────────────────────────────────
function SecVoice({ s, set }) {
  return (
    <>
      <SSectionHeader title="Voice" accent={J.green}
        subtitle="How I listen and speak. Hinglish-aware speech recognition + TTS." />

      <SCard title="WAKE WORD ENGINE" subtitle="The phrase that activates me." accent={J.green}>
        <SRow label="Wake word">
          <SRadio options={[
            { value:'aeris',  label:'Hey AERIS' },
            { value:'jarvis', label:'Jarvis' },
            { value:'custom', label:'Custom…' },
          ]} value={s.wakeWord} onChange={v=>set('wakeWord',v)} color={J.green} />
        </SRow>
        <SRow label="Recognition mode" hint="When am I actively listening">
          <SRadio options={[
            { value:'push',       label:'Push to talk' },
            { value:'continuous', label:'Continuous' },
            { value:'hybrid',     label:'Hybrid' },
            { value:'adaptive',   label:'Adaptive' },
          ]} value={s.recogMode} onChange={v=>set('recogMode',v)} color={J.green} compact />
        </SRow>
      </SCard>

      <SCard title="VOICE INPUT" accent={J.green}>
        <SRow label="Sensitivity"           hint="How quiet I can hear">
          <div style={{ width:220 }}><SSlider value={s.micSens} onChange={v=>set('micSens',v)} color={J.green} /></div>
        </SRow>
        <SRow label="Noise suppression"     hint="Filter background noise">
          <SToggle color={J.green} on={s.noiseSupp} onChange={v=>set('noiseSupp',v)} />
        </SRow>
        <SRow label="Echo cancellation">
          <SToggle color={J.green} on={s.echoCanc} onChange={v=>set('echoCanc',v)} />
        </SRow>
        <SRow label="Voice activity threshold" hint="When to start capturing">
          <div style={{ width:220 }}><SSlider value={s.vadThresh} onChange={v=>set('vadThresh',v)} color={J.green} /></div>
        </SRow>
      </SCard>

      <SCard title="VOICE OUTPUT (TTS)" accent={J.green}>
        <SRow label="Voice"      hint="Choose your speaking voice">
          <SRadio options={[
            { value:'aria',  label:'Aria' },
            { value:'kira',  label:'Kira' },
            { value:'orion', label:'Orion' },
            { value:'echo',  label:'Echo' },
          ]} value={s.ttsVoice} onChange={v=>set('ttsVoice',v)} color={J.green} compact />
        </SRow>
        <SRow label="Speaking speed"     hint="Words per minute">
          <div style={{ width:220 }}><SSlider value={s.ttsSpeed} onChange={v=>set('ttsSpeed',v)} color={J.green} /></div>
        </SRow>
        <SRow label="Emotional tone"     hint="Flatness vs expressiveness">
          <div style={{ width:220 }}><SSlider value={s.ttsTone} onChange={v=>set('ttsTone',v)} color={J.green} /></div>
        </SRow>
        <SRow label="Voice depth"        hint="Pitch / warmth">
          <div style={{ width:220 }}><SSlider value={s.ttsDepth} onChange={v=>set('ttsDepth',v)} color={J.green} /></div>
        </SRow>
      </SCard>

      <SCard title="LANGUAGE" accent={J.green}>
        <SRow label="English">    <SToggle color={J.green} on={s.langEn}  onChange={v=>set('langEn',v)} /></SRow>
        <SRow label="Hindi">      <SToggle color={J.green} on={s.langHi}  onChange={v=>set('langHi',v)} /></SRow>
        <SRow label="Hinglish (mixed)">  <SToggle color={J.green} on={s.langHinglish} onChange={v=>set('langHinglish',v)} /></SRow>
        <SRow label="Auto-detect language" hint="Switch dynamically per utterance">
          <SToggle color={J.green} on={s.langAuto} onChange={v=>set('langAuto',v)} />
        </SRow>
      </SCard>
    </>
  );
}

// ─── SECTION: AUTOMATION ───────────────────────────────────────────────────
function SecAutomation({ s, set }) {
  const apps = ['VS Code','Chrome','Spotify','Terminal','Finder','Slack','Notion','Figma'];
  return (
    <>
      <SSectionHeader title="Automation" accent={J.amber}
        subtitle="What I'm allowed to do on your behalf. Granular per-app control." />

      <SCard title="AUTONOMY LEVEL" subtitle="How much I act without confirmation." accent={J.amber}>
        <SRow label="Mode">
          <SRadio options={[
            { value:'manual',     label:'Manual' },
            { value:'assisted',   label:'Assisted' },
            { value:'semi',       label:'Semi-Auto' },
            { value:'auto',       label:'Autonomous' },
          ]} value={s.autoLevel} onChange={v=>set('autoLevel',v)} color={J.amber} compact />
        </SRow>
        <SRow label="Confirm destructive actions" hint="File delete, app close, etc">
          <SToggle color={J.amber} on={s.confirmDest} onChange={v=>set('confirmDest',v)} />
        </SRow>
      </SCard>

      <SCard title="APP PERMISSIONS" subtitle={`${apps.length} apps · grant or revoke automation`} accent={J.amber}>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:4 }}>
          {apps.map(app => {
            const enabled = s.appPerms?.[app] ?? true;
            return (
              <div key={app} style={{
                display:'flex', alignItems:'center', justifyContent:'space-between',
                padding:'8px 10px', borderRadius:8,
                background: 'rgba(255,255,255,0.02)',
                border:'1px solid rgba(255,255,255,0.04)',
              }}>
                <span style={{ fontSize:11, color:J.textSec, fontFamily:"'JetBrains Mono',monospace" }}>{app}</span>
                <SToggle size="sm" color={J.amber} on={enabled}
                  onChange={v => set('appPerms', { ...(s.appPerms||{}), [app]: v })} />
              </div>
            );
          })}
        </div>
      </SCard>

      <SCard title="ACTION CATEGORIES" subtitle="Coarse-grained capability switches" accent={J.amber}>
        <SRow label="Open apps">           <SToggle color={J.amber} on={s.actOpen}    onChange={v=>set('actOpen',v)} /></SRow>
        <SRow label="Close apps">          <SToggle color={J.amber} on={s.actClose}   onChange={v=>set('actClose',v)} /></SRow>
        <SRow label="Browser automation">  <SToggle color={J.amber} on={s.actBrowser} onChange={v=>set('actBrowser',v)} /></SRow>
        <SRow label="File operations">     <SToggle color={J.amber} on={s.actFiles}   onChange={v=>set('actFiles',v)} /></SRow>
        <SRow label="Clipboard access">    <SToggle color={J.amber} on={s.actClip}    onChange={v=>set('actClip',v)} /></SRow>
        <SRow label="Keyboard simulation"> <SToggle color={J.amber} on={s.actKbd}     onChange={v=>set('actKbd',v)} /></SRow>
        <SRow label="Mouse automation">    <SToggle color={J.amber} on={s.actMouse}   onChange={v=>set('actMouse',v)} /></SRow>
      </SCard>

      <SCard title="SAVED WORKFLOWS" subtitle="One-shot routines. Voice or click to run." accent={J.amber}>
        {[
          { name:'Coding Mode',  steps:'VS Code · Chrome (docs) · Spotify · Focus theme' },
          { name:'Study Mode',   steps:'Notion · Calendar · Do Not Disturb on' },
          { name:'Edit Mode',    steps:'Figma · Reference imgs · Lo-fi playlist' },
          { name:'Wind Down',    steps:'Close work apps · Save state · Night theme' },
        ].map(w => (
          <div key={w.name} style={{
            display:'flex', alignItems:'center', justifyContent:'space-between',
            padding:'10px 12px', borderRadius:8,
            background:'rgba(13,21,37,0.5)',
            border:'1px solid rgba(30,41,59,0.7)',
            marginBottom:6,
          }}>
            <div>
              <div style={{ fontSize:12, fontWeight:600, color:J.textPri }}>{w.name}</div>
              <div style={{ fontSize:9.5, color:J.textMut, marginTop:2, fontFamily:"'JetBrains Mono',monospace" }}>{w.steps}</div>
            </div>
            <button style={{
              padding:'4px 10px', borderRadius:6, cursor:'pointer',
              background: ca(J.amber, 0.12), border:`1px solid ${ca(J.amber, 0.35)}`,
              fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700, letterSpacing:'1px',
              color:J.amber,
            }}>RUN</button>
          </div>
        ))}
      </SCard>
    </>
  );
}

// ─── SECTION: MODELS ───────────────────────────────────────────────────────
function SecModels({ s, set }) {
  const MODELS = [
    { key:'claude-haiku', label:'Claude Haiku 4.5', sub:'Default · fast', tag:{text:'ACTIVE', color:J.green}, accent:J.cyan },
    { key:'claude-sonnet',label:'Claude Sonnet 4.5',sub:'Reasoning',     accent:J.cyan },
    { key:'gpt-4o',       label:'GPT-4o',           sub:'OpenAI',        accent:J.green },
    { key:'gemini',       label:'Gemini 2.5',       sub:'Google',        accent:J.amber },
    { key:'llama-local',  label:'Llama 3 (Local)',  sub:'On-device · private', tag:{text:'LOCAL', color:J.purple}, accent:J.purple },
    { key:'hybrid',       label:'Hybrid Routing',   sub:'Best per task', tag:{text:'SMART', color:J.cyan}, accent:J.cyan },
  ];
  return (
    <>
      <SSectionHeader title="Models" accent={J.purple}
        subtitle="Choose which AI does what. Route different tasks to different models." />

      <SCard title="ACTIVE MODEL" subtitle="Currently powering your conversations." accent={J.purple}>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8 }}>
          {MODELS.map(m => (
            <button key={m.key}
              onClick={() => set('model', m.key)}
              style={{
                textAlign:'left', padding:'12px 14px', borderRadius:10, cursor:'pointer',
                background: s.model === m.key ? ca(m.accent, 0.1) : 'rgba(13,21,37,0.5)',
                border:`1px solid ${s.model === m.key ? ca(m.accent, 0.5) : 'rgba(30,41,59,0.65)'}`,
                boxShadow: s.model === m.key ? `0 0 14px ${ca(m.accent, 0.18)}` : 'none',
                transition:'all 0.18s',
              }}>
              <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                <div style={{ fontSize:12, fontWeight:600, color: s.model === m.key ? J.textPri : J.textSec }}>{m.label}</div>
                {m.tag && <STag {...m.tag} />}
              </div>
              <div style={{ fontSize:10, color:J.textMut, marginTop:3, fontFamily:"'JetBrains Mono',monospace" }}>{m.sub}</div>
            </button>
          ))}
        </div>
      </SCard>

      <SCard title="MODEL ROUTING" subtitle="Auto-pick the right model per task" accent={J.purple}>
        {[
          { task:'Coding',          model:'Claude Sonnet 4.5' },
          { task:'Reasoning',       model:'GPT-4o' },
          { task:'Quick replies',   model:'Claude Haiku 4.5' },
          { task:'Offline / private',model:'Llama 3 (Local)' },
        ].map(r => (
          <div key={r.task} style={{
            display:'flex', alignItems:'center', justifyContent:'space-between',
            padding:'10px 12px', borderRadius:8, marginBottom:6,
            background:'rgba(255,255,255,0.02)', border:'1px solid rgba(255,255,255,0.04)',
          }}>
            <span style={{ fontSize:11.5, color:J.textPri }}>{r.task}</span>
            <div style={{ display:'flex', alignItems:'center', gap:8 }}>
              <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:J.cyan }}>→ {r.model}</span>
            </div>
          </div>
        ))}
      </SCard>

      <SCard title="LOCAL AI" subtitle="On-device inference settings" accent={J.purple} badge={{text:'BETA', color:J.amber}}>
        <SRow label="VRAM allocation" hint="GB available to local model">
          <div style={{ width:220 }}><SSlider value={s.vram} onChange={v=>set('vram',v)} color={J.purple} unit=" GB" min={2} max={24} /></div>
        </SRow>
        <SRow label="GPU acceleration"><SToggle color={J.purple} on={s.gpuAccel} onChange={v=>set('gpuAccel',v)} /></SRow>
        <SRow label="Quantization">
          <SRadio options={[{value:'q4',label:'Q4'},{value:'q5',label:'Q5'},{value:'q8',label:'Q8'},{value:'fp16',label:'FP16'}]}
            value={s.quant} onChange={v=>set('quant',v)} color={J.purple} compact />
        </SRow>
      </SCard>
    </>
  );
}

// ─── SECTION: LABS ─────────────────────────────────────────────────────────
function SecLabs({ s, set }) {
  const LABS = [
    { key:'emotion',     label:'Emotion Detection',       sub:'Adapt tone based on user mood',           },
    { key:'face',        label:'Face Recognition',         sub:'Personal greeting · multi-user awareness',},
    { key:'proactive',   label:'Proactive Mode',           sub:'Suggest before you ask',                  },
    { key:'multiAgent',  label:'Multi-Agent Orchestration',sub:'Coder · Researcher · Creative · Auto',    },
    { key:'predict',     label:'Smart Desktop Prediction', sub:'Anticipate your next action',             },
    { key:'vision',      label:'Vision Mode',              sub:'Read screen content + UI elements',       },
    { key:'ambient',     label:'Ambient Awareness',        sub:'Adapt to time, fatigue, productivity',    },
  ];
  return (
    <>
      <SSectionHeader title="Experimental Labs" accent={J.magenta}
        subtitle="Cutting-edge features still being polished. Use with curiosity." />

      <div style={{ padding:'10px 14px', borderRadius:8, marginBottom:14,
        background: ca(J.magenta, 0.06), border:`1px solid ${ca(J.magenta, 0.2)}`,
        display:'flex', gap:10, alignItems:'flex-start' }}>
        <div style={{ width:6, height:6, borderRadius:'50%', background:J.magenta, marginTop:5,
          boxShadow:`0 0 6px ${J.magenta}`, animation:'j-blink 1.5s infinite', flexShrink:0 }} />
        <div style={{ fontSize:11, color:J.textSec, lineHeight:1.55, letterSpacing:'0.2px' }}>
          These features are experimental. Behavior may change without notice. Feedback welcome.
        </div>
      </div>

      <SCard title="ENABLED LABS" subtitle={`${Object.values(s.labs||{}).filter(Boolean).length} of ${LABS.length} active`} accent={J.magenta}>
        {LABS.map(lab => (
          <div key={lab.key} style={{
            display:'flex', alignItems:'center', justifyContent:'space-between',
            padding:'12px 0', borderBottom:'1px solid rgba(255,255,255,0.04)',
            gap:16,
          }}>
            <div style={{ flex:1 }}>
              <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                <span style={{ fontSize:12, fontWeight:600, color:J.textPri }}>{lab.label}</span>
                <STag text="BETA" color={J.magenta} />
              </div>
              <div style={{ fontSize:10, color:J.textMut, marginTop:3, letterSpacing:'0.2px' }}>{lab.sub}</div>
            </div>
            <SToggle color={J.magenta}
              on={s.labs?.[lab.key] || false}
              onChange={v => set('labs', { ...(s.labs||{}), [lab.key]: v })} />
          </div>
        ))}
      </SCard>
    </>
  );
}

// ─── COMPACT SECTIONS (stubs but functional) ───────────────────────────────
function SecGeneral({ s, set }) {
  return (
    <>
      <SSectionHeader title="General" accent={J.cyan} subtitle="Basic environment preferences." />
      <SCard title="STARTUP" accent={J.cyan}>
        <SRow label="Launch on system boot"><SToggle on={s.launchBoot}    onChange={v=>set('launchBoot',v)} /></SRow>
        <SRow label="Minimize to system tray"><SToggle on={s.minTray}     onChange={v=>set('minTray',v)} /></SRow>
        <SRow label="Silent startup (no greeting)"><SToggle on={s.silent} onChange={v=>set('silent',v)} /></SRow>
        <SRow label="Open in compact mode"><SToggle on={s.compactStart}   onChange={v=>set('compactStart',v)} /></SRow>
      </SCard>
      <SCard title="INTERACTION" accent={J.cyan}>
        <SRow label="Auto-focus input"><SToggle on={s.autoFocus}            onChange={v=>set('autoFocus',v)} /></SRow>
        <SRow label="Smart command suggestions"><SToggle on={s.smartSugg} onChange={v=>set('smartSugg',v)} /></SRow>
        <SRow label="Auto-hide idle UI"><SToggle on={s.hideIdle}           onChange={v=>set('hideIdle',v)} /></SRow>
        <SRow label="Adaptive interface"><SToggle on={s.adaptive}          onChange={v=>set('adaptive',v)} /></SRow>
      </SCard>
      <SCard title="REGIONAL" accent={J.cyan}>
        <SRow label="Time format">
          <SRadio options={['12h','24h']} value={s.timeFmt} onChange={v=>set('timeFmt',v)} color={J.cyan} compact/>
        </SRow>
        <SRow label="Temperature units">
          <SRadio options={['°C','°F']} value={s.tempUnit} onChange={v=>set('tempUnit',v)} color={J.cyan} compact/>
        </SRow>
      </SCard>
    </>
  );
}

function SecDesktop({ s, set }) {
  return (
    <>
      <SSectionHeader title="Desktop Awareness" accent={J.cyan}
        subtitle="What I can observe about your workspace to assist proactively." />
      <SCard title="SCREEN UNDERSTANDING" accent={J.cyan}>
        <SRow label="Detect active applications"><SToggle on={s.detectApps}     onChange={v=>set('detectApps',v)} /></SRow>
        <SRow label="Detect coding sessions"><SToggle on={s.detectCoding}        onChange={v=>set('detectCoding',v)} /></SRow>
        <SRow label="Understand browser context"><SToggle on={s.detectBrowser}  onChange={v=>set('detectBrowser',v)} /></SRow>
        <SRow label="Read current window title"><SToggle on={s.detectTitle}     onChange={v=>set('detectTitle',v)} /></SRow>
      </SCard>
      <SCard title="WORKSPACE INTELLIGENCE" accent={J.cyan}>
        <SRow label="Restore previous workflow"><SToggle on={s.restoreFlow}      onChange={v=>set('restoreFlow',v)} /></SRow>
        <SRow label="Workspace suggestions"><SToggle on={s.workspaceSugg}        onChange={v=>set('workspaceSugg',v)} /></SRow>
        <SRow label="Smart app grouping"><SToggle on={s.smartGroup}              onChange={v=>set('smartGroup',v)} /></SRow>
        <SRow label="Focus detection"><SToggle on={s.focusDetect}                onChange={v=>set('focusDetect',v)} /></SRow>
      </SCard>
      <SCard title="SCREEN VISION" subtitle="OCR + computer vision (requires camera)" accent={J.cyan} badge={{text:'BETA', color:J.amber}}>
        <SRow label="Read visible content"><SToggle on={s.ocr}                  onChange={v=>set('ocr',v)} /></SRow>
        <SRow label="Detect UI elements"><SToggle on={s.uiDetect}               onChange={v=>set('uiDetect',v)} /></SRow>
        <SRow label="Assist with workflows"><SToggle on={s.workflowAssist}      onChange={v=>set('workflowAssist',v)} /></SRow>
      </SCard>
    </>
  );
}

function SecMemory({ s, set }) {
  return (
    <>
      <SSectionHeader title="Memory" accent={J.amber}
        subtitle="What I remember, for how long, and across which sessions." />
      <SCard title="MEMORY MODE" subtitle="The shape of my long-term recall." accent={J.amber}>
        <SRow label="Mode">
          <SRadio options={[
            { value:'temp',     label:'Temporary' },
            { value:'persist',  label:'Persistent' },
            { value:'project',  label:'Project-based' },
          ]} value={s.memMode} onChange={v=>set('memMode',v)} color={J.amber} compact />
        </SRow>
      </SCard>
      <SCard title="REMEMBER" accent={J.amber}>
        <SRow label="Conversations"><SToggle color={J.amber} on={s.memConv}       onChange={v=>set('memConv',v)} /></SRow>
        <SRow label="Projects"><SToggle color={J.amber} on={s.memProj}            onChange={v=>set('memProj',v)} /></SRow>
        <SRow label="Preferences"><SToggle color={J.amber} on={s.memPref}         onChange={v=>set('memPref',v)} /></SRow>
        <SRow label="Frequently used apps"><SToggle color={J.amber} on={s.memApps} onChange={v=>set('memApps',v)} /></SRow>
        <SRow label="Daily routines"><SToggle color={J.amber} on={s.memRoutines}  onChange={v=>set('memRoutines',v)} /></SRow>
        <SRow label="Work patterns"><SToggle color={J.amber} on={s.memPatterns}   onChange={v=>set('memPatterns',v)} /></SRow>
      </SCard>
      <SCard title="MEMORY TIMELINE" subtitle="Visual history of what I've learned" accent={J.amber}>
        {['Today','Yesterday','Last week','This month'].map((t,i) => (
          <div key={t} style={{ display:'flex', alignItems:'center', gap:10, padding:'8px 0' }}>
            <div style={{ width:8, height:8, borderRadius:'50%', background: i===0 ? J.amber : ca(J.amber, 0.3),
              boxShadow: i===0 ? `0 0 6px ${J.amber}` : 'none' }} />
            <div style={{ flex:1, fontSize:11, color:J.textSec, fontFamily:"'JetBrains Mono',monospace" }}>{t}</div>
            <span style={{ fontSize:10, color:J.textMut }}>{[24,18,87,243][i]} events</span>
          </div>
        ))}
      </SCard>
    </>
  );
}

function SecGestures({ s, set }) {
  return (
    <>
      <SSectionHeader title="Gestures" accent={J.magenta}
        subtitle="Hand tracking and air gestures via webcam. Futuristic, experimental." />
      <SCard title="GESTURE INPUT" subtitle="Enable camera-based gesture detection" accent={J.magenta} badge={{text:'BETA', color:J.magenta}}>
        <SRow label="Hand tracking"><SToggle color={J.magenta} on={s.handTrack} onChange={v=>set('handTrack',v)} /></SRow>
        <SRow label="Webcam gestures"><SToggle color={J.magenta} on={s.webcamGest} onChange={v=>set('webcamGest',v)} /></SRow>
        <SRow label="Air gestures"><SToggle color={J.magenta} on={s.airGest} onChange={v=>set('airGest',v)} /></SRow>
        <SRow label="Pose detection"><SToggle color={J.magenta} on={s.poseDetect} onChange={v=>set('poseDetect',v)} /></SRow>
      </SCard>
      <SCard title="GESTURES" subtitle="What each gesture triggers" accent={J.magenta}>
        {[
          { g:'Swipe Right',    a:'Next workspace' },
          { g:'Pinch',          a:'Activate listening' },
          { g:'Palm Raise',     a:'Pause assistant' },
          { g:'Double Tap (air)',a:'Open quick panel' },
          { g:'Finger Point',   a:'Select object' },
        ].map(x => (
          <div key={x.g} style={{ display:'flex', justifyContent:'space-between', padding:'8px 0',
            borderBottom:'1px solid rgba(255,255,255,0.04)' }}>
            <span style={{ fontSize:11.5, color:J.textPri, fontFamily:"'JetBrains Mono',monospace" }}>{x.g}</span>
            <span style={{ fontSize:11, color:J.textMut }}>→ {x.a}</span>
          </div>
        ))}
      </SCard>
      <SCard title="SENSITIVITY" accent={J.magenta}>
        <SRow label="Precision ↔ Speed">
          <div style={{ width:220 }}><SSlider value={s.gestSens} onChange={v=>set('gestSens',v)} color={J.magenta} /></div>
        </SRow>
        <SRow label="Tracking mode">
          <SRadio options={[
            { value:'low',  label:'Low Power' },
            { value:'bal',  label:'Balanced' },
            { value:'high', label:'High Accuracy' },
          ]} value={s.trackMode} onChange={v=>set('trackMode',v)} color={J.magenta} compact />
        </SRow>
        <SRow label="Visual gesture overlay" hint="Show skeleton + detection points"><SToggle color={J.magenta} on={s.gestOverlay} onChange={v=>set('gestOverlay',v)} /></SRow>
      </SCard>
    </>
  );
}

function SecSecurity({ s, set }) {
  return (
    <>
      <SSectionHeader title="Security" accent={J.red}
        subtitle="What I can access, and what stays private." />
      <SCard title="PERMISSIONS" subtitle="Per-feature access" accent={J.red}>
        <SRow label="Microphone"><SToggle color={J.red} on={s.permMic}     onChange={v=>set('permMic',v)} /></SRow>
        <SRow label="Camera"><SToggle color={J.red} on={s.permCam}         onChange={v=>set('permCam',v)} /></SRow>
        <SRow label="Automation"><SToggle color={J.red} on={s.permAuto}    onChange={v=>set('permAuto',v)} /></SRow>
        <SRow label="Filesystem"><SToggle color={J.red} on={s.permFs}      onChange={v=>set('permFs',v)} /></SRow>
        <SRow label="Browser access"><SToggle color={J.red} on={s.permBrowser} onChange={v=>set('permBrowser',v)} /></SRow>
      </SCard>
      <SCard title="PRIVACY MODE" accent={J.red}>
        <SRow label="Mode">
          <SRadio options={[
            { value:'local',  label:'Local Only' },
            { value:'hybrid', label:'Hybrid' },
            { value:'secure', label:'Secure Session' },
          ]} value={s.privacyMode} onChange={v=>set('privacyMode',v)} color={J.red} compact />
        </SRow>
      </SCard>
      <SCard title="CONFIRMATIONS REQUIRED" subtitle="High-risk actions" accent={J.red}>
        <SRow label="Deleting files"><SToggle color={J.red} on={s.confDelete}    onChange={v=>set('confDelete',v)} /></SRow>
        <SRow label="Terminal commands"><SToggle color={J.red} on={s.confTerm}   onChange={v=>set('confTerm',v)} /></SRow>
        <SRow label="Browser actions"><SToggle color={J.red} on={s.confBrowser}  onChange={v=>set('confBrowser',v)} /></SRow>
        <SRow label="System changes"><SToggle color={J.red} on={s.confSystem}    onChange={v=>set('confSystem',v)} /></SRow>
      </SCard>
      <SCard title="BIOMETRIC UNLOCK" subtitle="Identity verification methods" accent={J.red} badge={{text:'FUTURE', color:J.purple}}>
        <SRow label="Face unlock"><SToggle color={J.red} on={s.bioFace}        onChange={v=>set('bioFace',v)} /></SRow>
        <SRow label="Voice recognition"><SToggle color={J.red} on={s.bioVoice} onChange={v=>set('bioVoice',v)} /></SRow>
        <SRow label="Gesture unlock"><SToggle color={J.red} on={s.bioGest}      onChange={v=>set('bioGest',v)} /></SRow>
      </SCard>
    </>
  );
}

function SecNotifications({ s, set }) {
  return (
    <>
      <SSectionHeader title="Notifications" accent={J.cyan}
        subtitle="What I notify you about, and how it looks." />
      <SCard title="NOTIFICATION TYPES" accent={J.cyan}>
        <SRow label="Task reminders"><SToggle on={s.notifTask}              onChange={v=>set('notifTask',v)} /></SRow>
        <SRow label="Workspace suggestions"><SToggle on={s.notifWorkspace}  onChange={v=>set('notifWorkspace',v)} /></SRow>
        <SRow label="AI recommendations"><SToggle on={s.notifAI}            onChange={v=>set('notifAI',v)} /></SRow>
        <SRow label="Automation completed"><SToggle on={s.notifAuto}        onChange={v=>set('notifAuto',v)} /></SRow>
        <SRow label="Voice feedback"><SToggle on={s.notifVoice}             onChange={v=>set('notifVoice',v)} /></SRow>
      </SCard>
      <SCard title="STYLE" accent={J.cyan}>
        <SRow label="Notification style">
          <SRadio options={[
            { value:'min',   label:'Minimal' },
            { value:'glass', label:'Glass popup' },
            { value:'holo',  label:'Holographic' },
            { value:'side',  label:'Sidebar pulse' },
            { value:'voice', label:'Voice only' },
          ]} value={s.notifStyle} onChange={v=>set('notifStyle',v)} color={J.cyan} compact />
        </SRow>
      </SCard>
    </>
  );
}

function SecPerformance({ s, set }) {
  return (
    <>
      <SSectionHeader title="Performance" accent={J.green}
        subtitle="Battery and resource tradeoffs." />
      <SCard title="MODE" accent={J.green}>
        <SRow label="Power profile">
          <SRadio options={[
            { value:'saver',  label:'Battery Saver' },
            { value:'bal',    label:'Balanced' },
            { value:'perf',   label:'Performance' },
            { value:'ultra',  label:'Ultra Visual' },
          ]} value={s.perfMode} onChange={v=>set('perfMode',v)} color={J.green} compact />
        </SRow>
      </SCard>
      <SCard title="RESOURCE ALLOCATION" accent={J.green}>
        <SRow label="GPU usage cap" hint="Limit graphics rendering">
          <div style={{ width:220 }}><SSlider value={s.gpuCap} onChange={v=>set('gpuCap',v)} color={J.green} unit="%" /></div>
        </SRow>
        <SRow label="CPU limit" hint="Cap background work">
          <div style={{ width:220 }}><SSlider value={s.cpuCap} onChange={v=>set('cpuCap',v)} color={J.green} unit="%" /></div>
        </SRow>
        <SRow label="Particle complexity">
          <div style={{ width:220 }}><SSlider value={s.partComplex} onChange={v=>set('partComplex',v)} color={J.green} /></div>
        </SRow>
        <SRow label="Animation FPS">
          <div style={{ width:220 }}><SSlider value={s.fps} onChange={v=>set('fps',v)} color={J.green} min={30} max={120} unit=" fps" /></div>
        </SRow>
      </SCard>
    </>
  );
}

function SecDeveloper({ s, set }) {
  return (
    <>
      <SSectionHeader title="Developer" accent={J.cyan}
        subtitle="Debugging tools, telemetry, and skill testing." />
      <SCard title="DEBUG PANELS" subtitle="Live overlays for engineers" accent={J.cyan}>
        <SRow label="AI routing"><SToggle on={s.dbgRouting}            onChange={v=>set('dbgRouting',v)} /></SRow>
        <SRow label="Latency"><SToggle on={s.dbgLatency}               onChange={v=>set('dbgLatency',v)} /></SRow>
        <SRow label="Token usage"><SToggle on={s.dbgTokens}            onChange={v=>set('dbgTokens',v)} /></SRow>
        <SRow label="Execution graphs"><SToggle on={s.dbgExec}         onChange={v=>set('dbgExec',v)} /></SRow>
        <SRow label="Memory activity"><SToggle on={s.dbgMem}           onChange={v=>set('dbgMem',v)} /></SRow>
        <SRow label="Automation logs"><SToggle on={s.dbgAuto}          onChange={v=>set('dbgAuto',v)} /></SRow>
      </SCard>
      <SCard title="SKILL TESTS" subtitle="Run benchmarks on demand" accent={J.cyan}>
        {[
          { name:'Voice STT',          status:'94ms · pass', col:J.green },
          { name:'Automation',         status:'all pass',    col:J.green },
          { name:'Gesture detection',  status:'82% accuracy',col:J.amber },
          { name:'Model benchmark',    status:'run now',     col:J.cyan },
        ].map(t => (
          <div key={t.name} style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
            padding:'10px 12px', borderRadius:8, marginBottom:6,
            background:'rgba(255,255,255,0.02)', border:'1px solid rgba(255,255,255,0.04)' }}>
            <span style={{ fontSize:11.5, color:J.textPri }}>{t.name}</span>
            <STag text={t.status} color={t.col} />
          </div>
        ))}
      </SCard>
    </>
  );
}

// Map section keys to component
const SECTION_COMPONENTS = {
  general:       SecGeneral,
  aiCore:        SecAICore,
  voice:         SecVoice,
  appearance:    SecAppearance,
  desktop:       SecDesktop,
  automation:    SecAutomation,
  memory:        SecMemory,
  gestures:      SecGestures,
  security:      SecSecurity,
  notifications: SecNotifications,
  models:        SecModels,
  performance:   SecPerformance,
  developer:     SecDeveloper,
  labs:          SecLabs,
};

Object.assign(window, { SETTINGS_CATEGORIES, SECTION_COMPONENTS, CAT_ICONS, PERSONALITY_MODES, VISUALIZERS, THEMES });
