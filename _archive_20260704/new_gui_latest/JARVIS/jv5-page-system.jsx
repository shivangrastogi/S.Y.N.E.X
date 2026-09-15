// ─── JARVIS v5 — System Page (Hardware Monitor) ─────────────────────────────
const { J, ca } = window;

function useLiveValues() {
  const [vals, setVals] = React.useState({
    cpu: { now: 12, history: Array.from({length: 30}, () => 8 + Math.random() * 14) },
    gpu: { now: 18, history: Array.from({length: 30}, () => 12 + Math.random() * 18) },
    ram: { now: 4.2, history: Array.from({length: 30}, () => 3.8 + Math.random() * 0.6) },
    net: { now: 1.4, history: Array.from({length: 30}, () => Math.random() * 3) },
    bat: { now: 87 },
    temp:{ now: 42, history: Array.from({length: 30}, () => 38 + Math.random() * 7) },
  });

  React.useEffect(() => {
    const iv = setInterval(() => {
      setVals(v => {
        const stepCpu  = Math.max(2,  Math.min(95, v.cpu.now + (Math.random()-0.5)*10));
        const stepGpu  = Math.max(2,  Math.min(95, v.gpu.now + (Math.random()-0.5)*12));
        const stepRam  = Math.max(3,  Math.min(15, v.ram.now + (Math.random()-0.5)*0.4));
        const stepNet  = Math.max(0.1,Math.min(8,  v.net.now + (Math.random()-0.5)*1.5));
        const stepTemp = Math.max(35, Math.min(75, v.temp.now+ (Math.random()-0.5)*3));
        return {
          cpu:  { now: stepCpu,  history: [...v.cpu.history.slice(1),  stepCpu]  },
          gpu:  { now: stepGpu,  history: [...v.gpu.history.slice(1),  stepGpu]  },
          ram:  { now: +stepRam.toFixed(1), history: [...v.ram.history.slice(1), stepRam] },
          net:  { now: +stepNet.toFixed(1), history: [...v.net.history.slice(1), stepNet] },
          bat:  { now: v.bat.now },
          temp: { now: Math.round(stepTemp), history: [...v.temp.history.slice(1), stepTemp] },
        };
      });
    }, 1500);
    return () => clearInterval(iv);
  }, []);

  return vals;
}

const PROCESSES = [
  { name:'jarvis-core',    pid:8421,  cpu:8.2, ram:412,  status:'running', color:J.cyan },
  { name:'chrome',         pid:12942, cpu:14.6,ram:1842, status:'running', color:J.green },
  { name:'code',           pid:18421, cpu:6.4, ram:892,  status:'running', color:J.purple },
  { name:'spotify',        pid:22018, cpu:3.1, ram:284,  status:'running', color:J.green },
  { name:'figma-desktop',  pid:25109, cpu:5.8, ram:642,  status:'idle',    color:J.amber },
  { name:'system_idle',    pid:0,     cpu:62, ram:0,    status:'idle',    color:J.textMut },
];

const HARDWARE = [
  { k:'CPU',     v:'Intel Core i9-13900K · 24 cores' },
  { k:'GPU',     v:'NVIDIA RTX 4080 · 16GB' },
  { k:'RAM',     v:'32GB DDR5-6000 · Dual Channel' },
  { k:'Storage', v:'2TB NVMe SSD · 64% free' },
  { k:'Network', v:'Intel WiFi 6E AX211 · 867 Mbps' },
  { k:'Battery', v:'68Wh Li-ion · 6h 20m remaining' },
  { k:'Display', v:'Dell U2723QE · 4K · 60Hz' },
  { k:'OS',      v:'macOS 14.5 · Build 23F79' },
];

function SystemPage() {
  const vals = useLiveValues();

  return (
    <window.PageContainer>
      <window.PageHeader title="System"
        subtitle="Real-time monitor for every metric. JARVIS watches everything so you don't have to."
        accent={J.green}
        badge={{ text:'ALL NOMINAL', color:J.green }}
        right={
          <div style={{ display:'flex', gap:8 }}>
            <window.PillButton icon="trend">View History</window.PillButton>
            <window.PillButton icon="spark" color={J.green} primary>Run Diagnostics</window.PillButton>
          </div>
        } />

      <div style={{ flex:1, overflow:'auto', padding:'18px 32px 28px',
        display:'flex', flexDirection:'column', gap:14 }}>

        {/* Top — 4 big live cards */}
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr 1fr', gap:12 }}>
          <LiveMonitorCard label="CPU"      value={`${Math.round(vals.cpu.now)}%`} sub="i9-13900K · 24 cores"
            history={vals.cpu.history} color={J.cyan} max={100} />
          <LiveMonitorCard label="GPU"      value={`${Math.round(vals.gpu.now)}%`} sub="RTX 4080 · 16GB"
            history={vals.gpu.history} color={J.magenta} max={100} />
          <LiveMonitorCard label="MEMORY"   value={`${vals.ram.now} GB`} sub={`${(vals.ram.now / 32 * 100).toFixed(0)}% of 32GB`}
            history={vals.ram.history} color={J.purple} max={32} />
          <LiveMonitorCard label="NETWORK"  value={`${vals.net.now} MB/s`} sub="↓ down · WiFi 6"
            history={vals.net.history} color={J.green} max={8} />
        </div>

        {/* Middle row — battery + temp + processes */}
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 2fr', gap:12, alignItems:'stretch' }}>
          <window.PageCard title="BATTERY" accent={J.amber}>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'center', padding:'8px 0' }}>
              <window.RingProgress value={vals.bat.now} color={J.amber} size={96} />
            </div>
            <div style={{ display:'flex', flexDirection:'column', gap:6, marginTop:8 }}>
              <BatRow label="State"      value="Discharging" color={J.amber} />
              <BatRow label="Remaining"  value="6h 20m"      color={J.textPri} />
              <BatRow label="Drain rate" value="2.1 W"       color={J.textSec} />
              <BatRow label="Health"     value="98%"         color={J.green} />
            </div>
          </window.PageCard>

          <window.PageCard title="THERMAL" accent={J.red}>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'center', padding:'8px 0' }}>
              <ThermalGauge value={vals.temp.now} />
            </div>
            <div style={{ display:'flex', flexDirection:'column', gap:6, marginTop:8 }}>
              <BatRow label="CPU"  value={`${vals.temp.now}°C`} color={vals.temp.now > 65 ? J.red : J.cyan} />
              <BatRow label="GPU"  value={`${vals.temp.now - 4}°C`} color={J.magenta} />
              <BatRow label="Fan"  value="1240 RPM" color={J.textPri} />
              <BatRow label="Mode" value="Quiet" color={J.green} />
            </div>
          </window.PageCard>

          <window.PageCard title="ACTIVE PROCESSES" subtitle="Top by resource usage" accent={J.cyan}
            right={<window.STag text={`${PROCESSES.length} RUNNING`} color={J.cyan} />}>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(5, auto) 1fr', gap:0,
              fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut,
              padding:'4px 0', borderBottom:'1px solid rgba(255,255,255,0.04)', marginBottom:4 }}>
              <span style={{ minWidth:130, paddingRight:10 }}>NAME</span>
              <span style={{ minWidth:50, paddingRight:10 }}>PID</span>
              <span style={{ minWidth:50, paddingRight:10 }}>CPU</span>
              <span style={{ minWidth:60, paddingRight:10 }}>RAM</span>
              <span style={{ minWidth:60 }}>STATUS</span>
              <span></span>
            </div>
            {PROCESSES.map((p, i) => (
              <div key={i} style={{ display:'grid', gridTemplateColumns:'repeat(5, auto) 1fr', gap:0,
                fontFamily:"'JetBrains Mono',monospace", fontSize:10, padding:'6px 0',
                borderBottom: i === PROCESSES.length-1 ? 'none' : '1px solid rgba(255,255,255,0.03)' }}>
                <span style={{ color:p.color, fontWeight:700, minWidth:130, paddingRight:10 }}>{p.name}</span>
                <span style={{ color:J.textMut, minWidth:50, paddingRight:10 }}>{p.pid || '—'}</span>
                <span style={{ color:p.cpu > 10 ? J.amber : J.textSec, minWidth:50, paddingRight:10 }}>{p.cpu}%</span>
                <span style={{ color:J.textSec, minWidth:60, paddingRight:10 }}>{p.ram} MB</span>
                <span style={{ color:p.status === 'running' ? J.green : J.textMut, minWidth:60 }}>{p.status}</span>
                <span></span>
              </div>
            ))}
          </window.PageCard>
        </div>

        {/* Bottom — hardware specs */}
        <window.PageCard title="HARDWARE SPECS" subtitle="Read at boot · cached" accent={J.purple}>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:0 }}>
            {HARDWARE.map(h => (
              <div key={h.k} style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
                padding:'8px 12px', borderBottom:'1px solid rgba(255,255,255,0.03)' }}>
                <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9.5, color:J.textMut,
                  letterSpacing:'1.5px', fontWeight:700 }}>{h.k.toUpperCase()}</span>
                <span style={{ fontSize:11, color:J.textPri, letterSpacing:'0.1px' }}>{h.v}</span>
              </div>
            ))}
          </div>
        </window.PageCard>
      </div>
    </window.PageContainer>
  );
}

function LiveMonitorCard({ label, value, sub, history, color, max }) {
  return (
    <div style={{
      borderRadius:12, padding:'14px 16px', position:'relative',
      background:'rgba(13,21,37,0.6)', border:`1px solid rgba(30,41,59,0.7)`,
      overflow:'hidden',
    }}>
      <div style={{ position:'absolute', top:0, left:14, right:14, height:1.5,
        background:`linear-gradient(90deg, transparent, ${color}, transparent)`, opacity:0.6 }} />

      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:8 }}>
        <div>
          <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, fontWeight:700,
            letterSpacing:'1.8px', color:J.textMut }}>{label}</div>
          <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:24, fontWeight:700,
            color, marginTop:4, lineHeight:1, letterSpacing:'0.4px',
            textShadow:`0 0 12px ${ca(color, 0.4)}` }}>{value}</div>
        </div>
        <div style={{ width:6, height:6, borderRadius:'50%', background:color,
          boxShadow:`0 0 5px ${color}`, animation:'j-blink 2s infinite' }} />
      </div>

      <window.LineChart values={history} color={color} height={50} max={max} />

      <div style={{ fontSize:10, color:J.textMut, marginTop:6, letterSpacing:'0.2px' }}>{sub}</div>
    </div>
  );
}

function BatRow({ label, value, color }) {
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center',
      padding:'4px 0', borderBottom:'1px solid rgba(255,255,255,0.04)' }}>
      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:9, color:J.textMut, letterSpacing:'0.4px' }}>{label}</span>
      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10.5, fontWeight:600, color, letterSpacing:'0.2px' }}>{value}</span>
    </div>
  );
}

function ThermalGauge({ value }) {
  const hot = value > 65;
  const color = hot ? J.red : value > 55 ? J.amber : J.cyan;
  // Half-circle gauge from 30°C to 85°C
  const pct = Math.min(1, Math.max(0, (value - 30) / 55));
  const r = 38;
  const c = Math.PI * r;
  return (
    <div style={{ position:'relative', width:96, height:60, display:'flex',
      alignItems:'flex-end', justifyContent:'center' }}>
      <svg width="96" height="60" viewBox="0 0 96 60">
        <path d={`M 10 56 A ${r} ${r} 0 0 1 86 56`} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="4" strokeLinecap="round"/>
        <path d={`M 10 56 A ${r} ${r} 0 0 1 86 56`} fill="none" stroke={color} strokeWidth="4" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - pct)}
          style={{ filter:`drop-shadow(0 0 3px ${color})`, transition:'all 0.6s' }} />
      </svg>
      <div style={{ position:'absolute', bottom:0, textAlign:'center' }}>
        <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:18, fontWeight:700, color }}>{value}°</div>
      </div>
    </div>
  );
}

Object.assign(window, { SystemPage });
