import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowUpRight, BarChart3, Check, CircleAlert, Clock3, Gauge, LockKeyhole, RefreshCw, ShieldCheck, SlidersHorizontal, Wifi } from 'lucide-react';
import './styles.css';

const API = { status: '/api/status', market: '/api/market', intelligence: '/api/intelligence' };
const jakarta = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Jakarta', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });

function formatTime(value) { return value ? jakarta.format(new Date(value)) : 'Unavailable'; }
function formatPrice(value) { return value == null || Number.isNaN(Number(value)) ? 'Unavailable' : number.format(Number(value)); }
function titleCase(value = '') { return value.replaceAll('_', ' '); }
function availability(value) { return value == null || value === '' ? 'Unavailable' : typeof value === 'object' ? JSON.stringify(value) : value; }

function Badge({ children, tone = 'neutral' }) { return <span className={`badge badge-${tone}`}>{children}</span>; }
function Metric({ label, value, detail, tone = '' }) { return <div className="metric"><span className="metric-label">{label}</span><strong className={tone}>{value}</strong>{detail && <span className="metric-detail">{detail}</span>}</div>; }
function SectionHeading({ eyebrow, title, action }) { return <div className="section-heading"><div><span className="section-eyebrow">{eyebrow}</span><h2>{title}</h2></div>{action}</div>; }
function SourceLine({ source = 'Unavailable', method = 'Not supplied', freshness = 'Unavailable' }) { return <div className="source-line"><span>Source: {source}</span><span>Method: {method}</span><span>Freshness: {freshness}</span></div>; }
function StatePill({ state }) { const tone = state === 'LIVE' ? 'green' : state === 'STALE' ? 'amber' : state === 'ERROR' ? 'red' : 'neutral'; return <Badge tone={tone}>{state}</Badge>; }
function IntelCard({ eyebrow, title, state = 'UNAVAILABLE', source, method, freshness, children }) { return <article className="surface intel-card"><SectionHeading eyebrow={eyebrow} title={title} action={<StatePill state={state} />} />{children ?? <div className="empty-state"><CircleAlert size={17} /><span>Data unavailable. No value rendered without a verified source.</span></div>}<SourceLine source={source} method={method} freshness={freshness} /></article>; }

function App() {
  const [status, setStatus] = useState(null);
  const [market, setMarket] = useState(null);
  const [intelligence, setIntelligence] = useState(null);
  const [history, setHistory] = useState([]);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [latency, setLatency] = useState(null);
  const [error, setError] = useState(null);
  const [streamConnected, setStreamConnected] = useState(false);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    const started = performance.now();
    setLoading(true);
    try {
      const [statusResponse, marketResponse, intelligenceResponse] = await Promise.all([
        fetch(API.status, { cache: 'no-store' }).then(r => { if (!r.ok) throw new Error(`Status request failed (${r.status})`); return r.json(); }),
        fetch(API.market, { cache: 'no-store' }).then(r => { if (!r.ok) throw new Error(`Market request failed (${r.status})`); return r.json(); }),
        fetch(API.intelligence, { cache: 'no-store' }).then(r => { if (!r.ok) throw new Error(`Intelligence request failed (${r.status})`); return r.json(); }),
      ]);
      setStatus(statusResponse); setMarket(marketResponse); setIntelligence(intelligenceResponse); setError(null); setUpdatedAt(Date.now()); setLatency(Math.round(performance.now() - started));
      if (marketResponse?.ok && marketResponse.price != null) setHistory(previous => [...previous, Number(marketResponse.price)].slice(-32));
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Connection error'); }
    finally { setLoading(false); }
  }
  useEffect(() => { refresh(); const timer = setInterval(refresh, 5000); return () => clearInterval(timer); }, []);
  useEffect(() => {
    let socket;
    try {
      socket = new WebSocket('wss://ws.bitget.com/v2/ws/public');
      socket.onopen = () => { setStreamConnected(true); socket.send(JSON.stringify({ op: 'subscribe', args: [{ instType: 'mc', channel: 'ticker', instId: 'SBTCSUSDT' }] })); };
      socket.onmessage = event => {
        try {
          const payload = JSON.parse(event.data); const tick = payload?.data?.[0];
          if (!tick?.lastPr) return;
          const next = { ok: true, source: 'Bitget public WebSocket · SUSDT-FUTURES', symbol: tick.instId || 'SBTCSUSDT', price: tick.lastPr, change24h: tick.change24h, high24h: tick.high24h, low24h: tick.low24h, ts: tick.ts };
          setMarket(next); setHistory(previous => [...previous, Number(next.price)].slice(-32)); setUpdatedAt(Date.now()); setError(null);
        } catch { /* ignore protocol heartbeat frames */ }
      };
      socket.onerror = () => setStreamConnected(false); socket.onclose = () => setStreamConnected(false);
    } catch { setStreamConnected(false); }
    return () => socket?.close();
  }, []);

  const chartPoints = useMemo(() => {
    if (history.length < 2) return '';
    const min = Math.min(...history), max = Math.max(...history), range = max - min || 1;
    return history.map((value, index) => `${(index / (history.length - 1)) * 100},${92 - ((value - min) / range) * 78}`).join(' ');
  }, [history]);
  const live = Boolean(market?.ok); const halted = Boolean(status?.kill_switch?.halted);
  const validation = status?.validation ?? []; const strategies = status?.strategies ?? {};
  const feedState = error ? 'ERROR' : loading && !market ? 'LOADING' : streamConnected ? 'LIVE' : live ? 'STALE' : 'UNAVAILABLE';
  const freshness = updatedAt ? `${Math.max(0, Math.round((Date.now() - updatedAt) / 1000))}s ago` : 'Unavailable';
  const rangeReady = market?.high24h != null && market?.low24h != null;
  const weekly = intelligence?.ranges?.weekly ?? []; const monthly = intelligence?.ranges?.monthly ?? [];
  const rsiData = intelligence?.rsi; const pivots = intelligence?.support_resistance; const smc = intelligence?.smc; const book = intelligence?.order_book; const liquidations = intelligence?.liquidations;
  const intelligenceFreshness = intelligence?.freshness?.freshness_ms != null ? `${Math.round(intelligence.freshness.freshness_ms / 1000)}s` : freshness;

  return <div className="app-shell">
    <aside className="rail"><div className="rail-brand"><div className="brand-glyph">A</div><div><span className="rail-kicker">Research</span><strong>ABDALGHONIY</strong></div></div><nav className="rail-nav" aria-label="Dashboard sections"><a className="active" href="#overview"><Activity size={16} />Overview</a><a href="#market"><BarChart3 size={16} />Market feed</a><a href="#intelligence"><Gauge size={16} />Intelligence</a><a href="#validation"><ShieldCheck size={16} />Validation</a><a href="#reports"><ArrowUpRight size={16} />Reports</a></nav><div className="rail-footer"><div className="rail-status"><span className={`status-light ${live ? '' : 'offline'}`} />{streamConnected ? 'Live socket' : live ? 'REST fallback' : 'Feed unavailable'}</div><span>v1 · paper</span></div></aside>
    <main className="content" id="overview">
      <header className="page-head"><div><div className="breadcrumb">ABDALGHONIY / MONITOR</div><h1>Research overview</h1><p>One screen for market state, safety posture, and evidence.</p></div><div className="head-actions"><Badge tone="green"><span className="status-light" />PAPER ONLY</Badge><button className="icon-button" onClick={refresh} aria-label="Refresh dashboard"><RefreshCw size={16} /></button></div></header>
      {error && <div className="notice notice-error"><CircleAlert size={16} />{error}</div>}
      <section className="overview-grid"><article className="surface market-surface" id="market"><SectionHeading eyebrow="SUSDT-FUTURES · PUBLIC" title="Market pulse" action={<StatePill state={feedState} />} /><div className="market-main"><div><span className="instrument">{market?.symbol ?? 'SBTCSUSDT'}</span><div className="market-price">{formatPrice(market?.price)}</div><div className={`market-change ${Number(market?.change24h) < 0 ? 'negative' : ''}`}>{market?.change24h ? `${(Number(market.change24h) * 100).toFixed(2)}% 24h` : 'Waiting for feed'}</div></div><svg className="sparkline" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Recent price movement"><polyline points={chartPoints || '0,80 25,55 50,66 75,35 100,45'} /></svg></div><div className="market-foot"><div><span>24h high</span><strong>{formatPrice(market?.high24h)}</strong></div><div><span>24h low</span><strong>{formatPrice(market?.low24h)}</strong></div><div><span>Last tick</span><strong>{market?.ts ? formatTime(Number(market.ts)) : 'Unavailable'}</strong></div></div><SourceLine source={market?.source ?? 'Unavailable'} method={streamConnected ? 'Public WebSocket ticker' : 'REST snapshot'} freshness={freshness} /></article><article className="surface posture-surface"><SectionHeading eyebrow="GUARDRAILS" title="Safety posture" action={<Gauge size={18} className="muted-icon" />} /><div className="hero-state"><div className={`state-mark ${halted ? 'danger' : ''}`}>{halted ? <CircleAlert size={23} /> : <ShieldCheck size={23} />}</div><div><strong>{halted ? 'Halted' : 'Armed'}</strong><span>{halted ? 'New risk is blocked' : 'Paper risk controls active'}</span></div></div><div className="posture-list"><div><span>Live orders</span><Badge tone="green">Disabled</Badge></div><div><span>Hard stop</span><Badge tone="green">Required</Badge></div><div><span>Daily breaker</span><Badge tone="green">Enabled</Badge></div><div><span>Max leverage</span><strong>3×</strong></div></div></article></section>
      <section className="metrics-grid"><Metric label="System" value={status?.tests ?? 'Checking'} detail="offline suite" tone={status?.tests === 'passing' ? 'green' : 'amber'} /><Metric label="Connection" value={latency ? `${latency} ms` : 'Unavailable'} detail={updatedAt ? `updated ${formatTime(updatedAt)}` : 'waiting'} /><Metric label="Mode" value="Paper" detail="no live controls" tone="green" /><Metric label="Data source" value="Bitget" detail="public demo ticker" /></section>
      <section id="intelligence" className="intel-grid"><IntelCard eyebrow="STRUCTURE" title="Weekly / monthly ranges" state={weekly.length || monthly.length ? feedState : 'UNAVAILABLE'} source={intelligence?.freshness?.source} method="Daily candles · calendar periods" freshness={intelligenceFreshness}>{weekly.length || monthly.length ? <div className="health-list"><div><span>Weekly observed</span><strong>{weekly.length} periods</strong></div><div><span>Monthly observed</span><strong>{monthly.length} periods</strong></div><div><span>Pivot support / resistance</span><strong>{pivots?.available ? pivots.value.length : 'Unavailable'}</strong></div></div> : null}</IntelCard><IntelCard eyebrow="MOMENTUM" title="RSI" state={rsiData?.available ? feedState : 'UNAVAILABLE'} source={intelligence?.freshness?.source} method="Wilder RSI(14) · daily candles" freshness={intelligenceFreshness}>{rsiData?.available ? <div className="health-list"><div><span>Value</span><strong>{rsiData.value}</strong></div><div><span>State</span><strong>{Number(rsiData.value) >= 70 ? 'Overbought' : Number(rsiData.value) <= 30 ? 'Oversold' : 'Neutral'}</strong></div></div> : null}</IntelCard><IntelCard eyebrow="SMART MONEY CONCEPTS" title="SMC structure" state={smc?.available ? feedState : 'UNAVAILABLE'} source={intelligence?.freshness?.source} method="Confirmed swing/BOS scan · daily candles" freshness={intelligenceFreshness}>{smc?.available ? <div className="health-list"><div><span>Events</span><strong>{smc.value.length}</strong></div><div><span>Latest</span><strong>{smc.value.at(-1)?.kind ?? 'Unavailable'}</strong></div></div> : null}</IntelCard><IntelCard eyebrow="LIQUIDITY" title="Order book" state={book?.status === 'ok' ? feedState : 'UNAVAILABLE'} source={intelligence?.freshness?.source} method="Public depth snapshot · top 20 levels" freshness={intelligenceFreshness}>{book?.status === 'ok' ? <div className="health-list"><div><span>Best bid / ask</span><strong>{formatPrice(book.best_bid)} / {formatPrice(book.best_ask)}</strong></div><div><span>Imbalance</span><strong>{Number(book.imbalance).toFixed(3)}</strong></div></div> : null}</IntelCard><IntelCard eyebrow="DERIVATIVES" title="Liquidation heatmap" state="UNAVAILABLE" source="Unavailable" method="No liquidation stream supplied" /><IntelCard eyebrow="OPERATIONS" title="Feed health" state={feedState} source={market?.source ?? 'Unavailable'} method={streamConnected ? 'WebSocket + REST fallback' : 'REST polling'} freshness={freshness}><div className="health-list"><div><span>Current state</span><strong>{feedState}</strong></div><div><span>Rate limit</span><strong>{availability(intelligence?.rate_limit ?? market?.rate_limit ?? status?.rate_limit)}</strong></div><div><span>Last update</span><strong>{updatedAt ? formatTime(updatedAt) : 'Unavailable'} WIB</strong></div></div></IntelCard></section>
      <section className="lower-grid" id="validation"><article className="surface validation-surface"><SectionHeading eyebrow="EVIDENCE" title="Validation ladder" action={<span className="section-note">{validation.filter(item => item.status === 'implemented').length} of {validation.length} green</span>} /><div className="validation-list">{validation.map(item => { const green = item.status === 'implemented' || item.status === 'implemented_no_live_stream'; const blocked = item.status.includes('blocked') || item.status === 'not_passed'; return <div className="validation-row" key={item.gate}><div className={`validation-icon ${green ? 'green' : blocked ? 'red' : 'amber'}`}>{green ? <Check size={14} /> : blocked ? <CircleAlert size={14} /> : <Clock3 size={14} />}</div><span>{titleCase(item.gate)}</span><em className={green ? 'green-text' : blocked ? 'red-text' : 'amber-text'}>{titleCase(item.status)}</em></div>; })}</div></article><article className="surface strategy-surface"><SectionHeading eyebrow="PAPER MODULES" title="Strategies" action={<SlidersHorizontal size={18} className="muted-icon" />} /><div className="strategy-list">{Object.entries(strategies).map(([name, mode]) => <div className="strategy-row" key={name}><div className="strategy-dot" /><span>{titleCase(name)}</span><Badge tone="green">{mode}</Badge></div>)}</div><div className="strategy-note"><LockKeyhole size={14} /> Execution path is intentionally unavailable.</div></article></section>
      <section className="surface reports-surface" id="reports"><SectionHeading eyebrow="SOURCE MATERIAL" title="Reports" action={<span className="section-note">Raw evidence, not projections</span>} /><div className="report-grid">{(status?.reports ?? []).map(path => <a href={path} key={path} className="report-link"><span>{path.split('/').pop()?.replace('.md', '')}</span><ArrowUpRight size={15} /></a>)}</div></section><footer className="page-footer"><span><Wifi size={13} /> Public telemetry · refreshes every 5 seconds</span><span>All times Asia/Jakarta · monitoring only</span></footer>
    </main>
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
