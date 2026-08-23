import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowUpRight, BarChart3, Check, CircleAlert, Clock3, Gauge, LockKeyhole, RefreshCw, ShieldCheck, SlidersHorizontal, Wifi } from 'lucide-react';
import './styles.css';

const API = { status: '/api/status', market: '/api/market' };
const jakarta = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Jakarta', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });

function formatTime(value) { return jakarta.format(value ? new Date(value) : new Date()); }
function formatPrice(value) { return value == null ? '—' : number.format(Number(value)); }
function titleCase(value) { return value.replaceAll('_', ' '); }

function Badge({ children, tone = 'neutral' }) { return <span className={`badge badge-${tone}`}>{children}</span>; }
function Metric({ label, value, detail, tone = '' }) { return <div className="metric"><span className="metric-label">{label}</span><strong className={tone}>{value}</strong>{detail && <span className="metric-detail">{detail}</span>}</div>; }
function SectionHeading({ eyebrow, title, action }) { return <div className="section-heading"><div><span className="section-eyebrow">{eyebrow}</span><h2>{title}</h2></div>{action}</div>; }

function App() {
  const [status, setStatus] = useState(null);
  const [market, setMarket] = useState(null);
  const [history, setHistory] = useState([]);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [latency, setLatency] = useState(null);
  const [error, setError] = useState(null);

  async function refresh() {
    const started = performance.now();
    try {
      const [statusResponse, marketResponse] = await Promise.all([
        fetch(API.status, { cache: 'no-store' }).then(r => r.json()),
        fetch(API.market, { cache: 'no-store' }).then(r => r.json()),
      ]);
      setStatus(statusResponse); setMarket(marketResponse); setError(null); setUpdatedAt(Date.now()); setLatency(Math.round(performance.now() - started));
      if (marketResponse?.ok) setHistory(previous => [...previous, Number(marketResponse.price)].slice(-32));
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Connection error'); }
  }
  useEffect(() => { refresh(); const timer = setInterval(refresh, 5000); return () => clearInterval(timer); }, []);

  const chartPoints = useMemo(() => {
    if (history.length < 2) return '';
    const min = Math.min(...history), max = Math.max(...history), range = max - min || 1;
    return history.map((value, index) => `${(index / (history.length - 1)) * 100},${92 - ((value - min) / range) * 78}`).join(' ');
  }, [history]);

  const live = Boolean(market?.ok); const halted = Boolean(status?.kill_switch?.halted);
  const validation = status?.validation ?? [];
  const strategies = status?.strategies ?? {};

  return <div className="app-shell">
    <aside className="rail">
      <div className="rail-brand"><div className="brand-glyph">A</div><div><span className="rail-kicker">Research</span><strong>ABDALGHONIY</strong></div></div>
      <nav className="rail-nav" aria-label="Dashboard sections">
        <a className="active" href="#overview"><Activity size={16} />Overview</a>
        <a href="#market"><BarChart3 size={16} />Market feed</a>
        <a href="#validation"><ShieldCheck size={16} />Validation</a>
        <a href="#reports"><ArrowUpRight size={16} />Reports</a>
      </nav>
      <div className="rail-footer"><div className="rail-status"><span className={`status-light ${live ? '' : 'offline'}`} />{live ? 'Live demo feed' : 'Feed unavailable'}</div><span>v1 · paper</span></div>
    </aside>

    <main className="content" id="overview">
      <header className="page-head"><div><div className="breadcrumb">ABDALGHONIY / MONITOR</div><h1>Research overview</h1><p>One screen for market state, safety posture, and evidence.</p></div><div className="head-actions"><Badge tone="green"><span className="status-light" />PAPER ONLY</Badge><button className="icon-button" onClick={refresh} aria-label="Refresh dashboard"><RefreshCw size={16} /></button></div></header>

      {error && <div className="notice notice-error"><CircleAlert size={16} />{error}</div>}

      <section className="overview-grid">
        <article className="surface market-surface" id="market"><SectionHeading eyebrow="SUSDT-FUTURES · PUBLIC" title="Market pulse" action={<Badge tone={live ? 'green' : 'red'}>{live ? 'CONNECTED' : 'OFFLINE'}</Badge>} /><div className="market-main"><div><span className="instrument">{market?.symbol ?? 'SBTCSUSDT'}</span><div className="market-price">{formatPrice(market?.price)}</div><div className={`market-change ${Number(market?.change24h) < 0 ? 'negative' : ''}`}>{market?.change24h ? `${(Number(market.change24h) * 100).toFixed(2)}% 24h` : 'Waiting for feed'}</div></div><svg className="sparkline" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Recent price movement"><polyline points={chartPoints || '0,80 25,55 50,66 75,35 100,45'} /></svg></div><div className="market-foot"><div><span>24h high</span><strong>{formatPrice(market?.high24h)}</strong></div><div><span>24h low</span><strong>{formatPrice(market?.low24h)}</strong></div><div><span>Last tick</span><strong>{market?.ts ? formatTime(Number(market.ts)) : '—'}</strong></div></div></article>
        <article className="surface posture-surface"><SectionHeading eyebrow="GUARDRAILS" title="Safety posture" action={<Gauge size={18} className="muted-icon" />} /><div className="hero-state"><div className={`state-mark ${halted ? 'danger' : ''}`}>{halted ? <CircleAlert size={23} /> : <ShieldCheck size={23} />}</div><div><strong>{halted ? 'Halted' : 'Armed'}</strong><span>{halted ? 'New risk is blocked' : 'Paper risk controls active'}</span></div></div><div className="posture-list"><div><span>Live orders</span><Badge tone="green">Disabled</Badge></div><div><span>Hard stop</span><Badge tone="green">Required</Badge></div><div><span>Daily breaker</span><Badge tone="green">Enabled</Badge></div><div><span>Max leverage</span><strong>3×</strong></div></div></article>
      </section>

      <section className="metrics-grid"><Metric label="System" value={status?.tests ?? 'Checking'} detail="offline suite" tone={status?.tests === 'passing' ? 'green' : 'amber'} /><Metric label="Connection" value={latency ? `${latency} ms` : '—'} detail={updatedAt ? `updated ${formatTime(updatedAt)}` : 'waiting'} /><Metric label="Mode" value="Paper" detail="no live controls" tone="green" /><Metric label="Data source" value="Bitget" detail="public demo ticker" /></section>

      <section className="lower-grid" id="validation"><article className="surface validation-surface"><SectionHeading eyebrow="EVIDENCE" title="Validation ladder" action={<span className="section-note">{validation.filter(item => item.status === 'implemented').length} of {validation.length} green</span>} /><div className="validation-list">{validation.map(item => { const green = item.status === 'implemented' || item.status === 'implemented_no_live_stream'; const blocked = item.status.includes('blocked') || item.status === 'not_passed'; return <div className="validation-row" key={item.gate}><div className={`validation-icon ${green ? 'green' : blocked ? 'red' : 'amber'}`}>{green ? <Check size={14} /> : blocked ? <CircleAlert size={14} /> : <Clock3 size={14} />}</div><span>{titleCase(item.gate)}</span><em className={green ? 'green-text' : blocked ? 'red-text' : 'amber-text'}>{titleCase(item.status)}</em></div>; })}</div></article><article className="surface strategy-surface"><SectionHeading eyebrow="PAPER MODULES" title="Strategies" action={<SlidersHorizontal size={18} className="muted-icon" />} /><div className="strategy-list">{Object.entries(strategies).map(([name, mode]) => <div className="strategy-row" key={name}><div className="strategy-dot" /><span>{titleCase(name)}</span><Badge tone="green">{mode}</Badge></div>)}</div><div className="strategy-note"><LockKeyhole size={14} /> Execution path is intentionally unavailable.</div></article></section>

      <section className="surface reports-surface" id="reports"><SectionHeading eyebrow="SOURCE MATERIAL" title="Reports" action={<span className="section-note">Raw evidence, not projections</span>} /><div className="report-grid">{(status?.reports ?? []).map(path => <a href={path} key={path} className="report-link"><span>{path.split('/').pop()?.replace('.md', '')}</span><ArrowUpRight size={15} /></a>)}</div></section>
      <footer className="page-footer"><span><Wifi size={13} /> Public telemetry · refreshes every 5 seconds</span><span>All times Asia/Jakarta · monitoring only</span></footer>
    </main>
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
