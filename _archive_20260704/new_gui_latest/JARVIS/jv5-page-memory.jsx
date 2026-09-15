// ─── JARVIS v5 — Memory Page ────────────────────────────────────────────────
const { J, ca } = window;

const MEMORY_GROUPS = [
  {
    period:'TODAY', stamp:'May 25',
    items: [
      { kind:'project', title:'SehatUP redesign · onboarding screens',     ts:'14:32', detail:'Continued from yesterday · 3h 42m focus', color:J.cyan,    icon:'edit'   },
      { kind:'chat',    title:'"Open my dev workspace"',                   ts:'12:08', detail:'Triggered Coding Mode automation', color:J.purple,  icon:'chat'   },
      { kind:'pref',    title:'Set focus playlist · Night Coding',         ts:'10:45', detail:'Auto-resumes when Coding Mode activates', color:J.amber, icon:'music'  },
      { kind:'task',    title:'Resolved 4 PR comments on auth-flow',       ts:'09:14', detail:'VS Code · pull/482', color:J.green, icon:'check' },
    ]
  },
  {
    period:'YESTERDAY', stamp:'May 24',
    items: [
      { kind:'chat',    title:'"Schedule meeting with design team"',        ts:'18:20', detail:'Slot found: today 16:30', color:J.purple,  icon:'chat'   },
      { kind:'project', title:'Started SehatUP redesign',                   ts:'14:00', detail:'New project · 8 design references uploaded', color:J.cyan, icon:'edit'   },
      { kind:'pattern', title:'Habit detected: peak focus 14:00–17:30',     ts:'21:00', detail:'Suggesting DND auto-enable in this window', color:J.magenta, icon:'spark' },
    ]
  },
  {
    period:'THIS WEEK', stamp:'May 19 – 23',
    items: [
      { kind:'project', title:'Completed Hindi voice training session',     ts:'May 22', detail:'42 new patterns learned · +1.8% accuracy', color:J.cyan,    icon:'brain' },
      { kind:'pref',    title:'Preferred greeting changed to Hinglish',     ts:'May 21', detail:'"Yo Shivang" instead of formal', color:J.amber, icon:'music' },
      { kind:'auto',    title:'New automation: Morning Brief (7:30am)',     ts:'May 20', detail:'Triggered 5 times so far · 100% success', color:J.green, icon:'bolt'  },
    ]
  },
  {
    period:'THIS MONTH', stamp:'May',
    items: [
      { kind:'pattern', title:'Learned: you skip news on weekends',         ts:'May 12', detail:'Morning Brief now skips news Sat/Sun', color:J.magenta, icon:'spark' },
      { kind:'project', title:'Finished JARVIS UI redesign · v3.2 shipped', ts:'May 08', detail:'Major version · 14 settings categories', color:J.cyan, icon:'check' },
    ]
  },
];

const MEMORY_CATEGORIES = [
  { key:'all',      label:'All',          count: 26, color: J.cyan    },
  { key:'project',  label:'Projects',     count: 4,  color: J.cyan    },
  { key:'chat',     label:'Conversations',count: 6,  color: J.purple  },
  { key:'pref',     label:'Preferences',  count: 8,  color: J.amber   },
  { key:'task',     label:'Tasks',        count: 5,  color: J.green   },
  { key:'pattern',  label:'Patterns',     count: 3,  color: J.magenta },
];

function MemoryPage() {
  const [filter, setFilter] = React.useState('all');
  const [query, setQuery]   = React.useState('');

  const filterFn = (item) => {
    if (filter !== 'all' && item.kind !== filter) return false;
    if (query && !item.title.toLowerCase().includes(query.toLowerCase())) return false;
    return true;
  };

  return (
    <window.PageContainer>
      <window.PageHeader title="Memory"
        subtitle="Everything I've learned about your habits, projects, and preferences. Persistent across sessions."
        accent={J.amber}
        badge={{ text:'PERSISTENT MODE', color:J.amber }}
        right={
          <div style={{ display:'flex', gap:8 }}>
            <window.SearchBar value={query} onChange={setQuery} placeholder="Search memory…" width={240}/>
            <window.PillButton icon="trash" color={J.red}>Forget Selected</window.PillButton>
          </div>
        } />

      <div style={{ flex:1, overflow:'hidden', padding:'18px 32px 28px',
        display:'grid', gridTemplateColumns:'220px 1fr 280px', gap:16, minHeight:0 }}>

        {/* LEFT — categories */}
        <div style={{ display:'flex', flexDirection:'column', gap:14, minHeight:0 }}>
          <window.PageCard title="CATEGORIES" accent={J.amber}>
            {MEMORY_CATEGORIES.map(c => (
              <button key={c.key} onClick={() => setFilter(c.key)} style={{
                width:'100%', display:'flex', justifyContent:'space-between', alignItems:'center',
                padding:'8px 10px', borderRadius:7, cursor:'pointer',
                background: filter === c.key ? ca(c.color, 0.1) : 'transparent',
                border:`1px solid ${filter === c.key ? ca(c.color, 0.4) : 'transparent'}`,
                marginBottom:2, transition:'all 0.15s',
              }}>
                <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                  <div style={{ width:7, height:7, borderRadius:'50%', background:c.color,
                    boxShadow: filter === c.key ? `0 0 5px ${c.color}` : 'none' }} />
                  <span style={{ fontSize:11.5, fontWeight: filter === c.key ? 600 : 500,
                    color: filter === c.key ? J.textPri : J.textSec, letterSpacing:'0.1px' }}>{c.label}</span>
                </div>
                <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut, letterSpacing:'0.3px' }}>{c.count}</span>
              </button>
            ))}
          </window.PageCard>

          <window.PageCard title="MEMORY STATS" accent={J.amber}>
            <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
              <StatRow label="Total items"  value="2,847"   color={J.cyan} />
              <StatRow label="This week"    value="+ 42"    color={J.green} />
              <StatRow label="Persistent"   value="91%"     color={J.amber} />
              <StatRow label="Index size"   value="14.2 MB" color={J.purple} />
            </div>
          </window.PageCard>
        </div>

        {/* CENTER — timeline */}
        <div style={{ display:'flex', flexDirection:'column', gap:14, minHeight:0, overflow:'hidden' }}>
          <window.PageCard title="MEMORY TIMELINE" subtitle="Chronological · most recent first"
            accent={J.amber} fullHeight style={{ flex:1, minHeight:0 }}>
            <div style={{ overflowY:'auto', height:'100%', paddingRight:4 }}>
              {MEMORY_GROUPS.map(group => {
                const items = group.items.filter(filterFn);
                if (items.length === 0) return null;
                return (
                  <div key={group.period} style={{ marginBottom:18 }}>
                    {/* Period header */}
                    <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:10, padding:'4px 0' }}>
                      <div style={{ width:6, height:6, borderRadius:'50%', background:J.amber,
                        boxShadow:`0 0 5px ${J.amber}` }} />
                      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
                        letterSpacing:'2px', color:J.amber }}>{group.period}</span>
                      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut }}>· {group.stamp}</span>
                      <div style={{ flex:1, height:1, background:'rgba(251,191,36,0.15)' }} />
                      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut }}>{items.length}</span>
                    </div>
                    {items.map((item, i) => (
                      <MemoryCard key={i} item={item} />
                    ))}
                  </div>
                );
              })}
            </div>
          </window.PageCard>
        </div>

        {/* RIGHT — context awareness */}
        <div style={{ display:'flex', flexDirection:'column', gap:14, minHeight:0 }}>
          <window.PageCard title="LEARNED CONTEXT" subtitle="What I know about you" accent={J.purple}>
            <ContextRow label="Active project"   value="SehatUP redesign" color={J.cyan} />
            <ContextRow label="Peak focus time"  value="14:00 – 17:30"    color={J.amber} />
            <ContextRow label="Preferred music"  value="Night Coding"     color={J.purple} />
            <ContextRow label="Default language" value="Hinglish"         color={J.green} />
            <ContextRow label="Wake word"        value="Hey AERIS"        color={J.cyan} />
          </window.PageCard>

          <window.PageCard title="GROWTH" subtitle="Memory entries · 14 days" accent={J.green}>
            <window.BarChart color={J.green} height={80} data={[
              { value:12, label:'M' }, { value:8, label:'T' }, { value:18, label:'W' },
              { value:24, label:'T' }, { value:14, label:'F' }, { value:6,  label:'S' }, { value:4, label:'S' },
              { value:22, label:'M' }, { value:16, label:'T' }, { value:28, label:'W' },
              { value:32, label:'T' }, { value:21, label:'F' }, { value:9,  label:'S' }, { value:11, label:'S' },
            ]} />
          </window.PageCard>
        </div>
      </div>
    </window.PageContainer>
  );
}

function MemoryCard({ item }) {
  const [hov, setHov] = React.useState(false);
  return (
    <div
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{
        display:'flex', gap:11, padding:'10px 12px', borderRadius:8, marginBottom:6,
        background: hov ? 'rgba(13,21,37,0.7)' : 'rgba(13,21,37,0.45)',
        border:`1px solid ${hov ? ca(item.color, 0.3) : 'rgba(30,41,59,0.5)'}`,
        boxShadow: hov ? `0 0 12px ${ca(item.color, 0.1)}` : 'none',
        transition:'all 0.18s',
      }}>
      <div style={{ width:30, height:30, borderRadius:7, flexShrink:0,
        background:ca(item.color, 0.12), border:`1px solid ${ca(item.color, 0.3)}`,
        display:'flex', alignItems:'center', justifyContent:'center', color:item.color,
      }}><window.PageIcon name={item.icon} size={13} /></div>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:8 }}>
          <span style={{ fontSize:11.5, fontWeight:600, color:J.textPri, letterSpacing:'0.1px',
            lineHeight:1.4 }}>{item.title}</span>
          <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut,
            flexShrink:0, letterSpacing:'0.4px' }}>{item.ts}</span>
        </div>
        <div style={{ fontSize:10, color:J.textMut, marginTop:3, letterSpacing:'0.2px', lineHeight:1.5 }}>
          {item.detail}
        </div>
      </div>
    </div>
  );
}

function ContextRow({ label, value, color }) {
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
      padding:'7px 0', borderBottom:'1px solid rgba(255,255,255,0.04)' }}>
      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut, letterSpacing:'0.4px' }}>{label}</span>
      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, fontWeight:600, color, letterSpacing:'0.2px' }}>{value}</span>
    </div>
  );
}

function StatRow({ label, value, color }) {
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
      <span style={{ fontSize:11, color:J.textSec, letterSpacing:'0.1px' }}>{label}</span>
      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:13, fontWeight:700, color }}>{value}</span>
    </div>
  );
}

Object.assign(window, { MemoryPage });
