import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowUpRight, BarChart3, Check, CircleAlert, Clock3, Gauge, LockKeyhole, RefreshCw, ShieldCheck, SlidersHorizontal, Wifi } from 'lucide-react';
import './styles.css';

const API = { status: '/api/status', market: '/api/market', intelligence: '/api/intelligence' };
const jakarta = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Jakarta', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
const jakartaFull = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Jakarta', dateStyle: 'medium', timeStyle: 'medium' });
const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });

function formatTime(value) { return value ? jakarta.format(new Date(value)) : 'Unavailable'; }
function formatPrice(value) { return value == null || Number.isNaN(Number(value)) ? 'Unavailable' : number.format(Number(value)); }
function formatBytes(value) { if (value == null) return 'Unavailable'; const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']; let n = Number(value); let i = 0; while (n >= 1024 && i < units.length - 1) { n /= 1024; i += 1; } return `${n.toFixed(i ? 1 : 0)} ${units[i]}`; }
function chartGeometry(values) {
  const width = 320; const height = 180; const left = 42; const right = 10; const top = 14; const bottom = 34;
  const nums = values.map(Number).filter(Number.isFinite);
  if (nums.length < 2) return { nums, points: '', min: null, max: null, latest: null, width, height, left, right, top, bottom, range: 1 };
  const min = Math.min(...nums); const max = Math.max(...nums); const range = max - min || Math.max(Math.abs(max) * 0.05, 1);
  const points = nums.map((value, index) => `${left + (index / (nums.length - 1)) * (width - left - right)},${top + ((max - value) / range) * (height - top - bottom)}`).join(' ');
  return { nums, points, min, max, latest: nums.at(-1), width, height, left, right, top, bottom, range };
}
function LiveChart({ eyebrow, title, values, color = 'var(--green)', source, formatValue = formatPrice }) {
  const chart = chartGeometry(values);
  const gridYs = [0, 0.25, 0.5, 0.75, 1];
  const label = value => value == null ? 'Unavailable' : formatValue(value);
  return <article className="surface chart-card"><SectionHeading eyebrow={eyebrow} title={title} action={<Badge tone={chart.nums.length >= 2 ? 'green' : 'neutral'}>{chart.nums.length >= 2 ? 'SAMPLED' : 'WAITING'}</Badge>} /><div className="chart-summary"><div><span>Latest</span><strong>{label(chart.latest)}</strong></div><div><span>Minimum</span><strong>{label(chart.min)}</strong></div><div><span>Maximum</span><strong>{label(chart.max)}</strong></div><div><span>Samples</span><strong>{chart.nums.length}</strong></div></div><svg className="live-chart" viewBox="0 0 320 180" role="img" aria-label={title}>{gridYs.map((fraction) => { const y = chart.top + fraction * (chart.height - chart.top - chart.bottom); const value = chart.max == null ? null : chart.max - fraction * chart.range; return <g key={fraction}><line x1={chart.left} x2={chart.width - chart.right} y1={y} y2={y} className="chart-gridline" /><text x="2" y={y + 4} className="chart-axis-label">{label(value)}</text></g>; })}{chart.points && <polyline points={chart.points} style={{ stroke: color }} className="chart-line" />}{chart.nums.map((value, index) => { if (!chart.points) return null; const x = chart.left + (index / (chart.nums.length - 1)) * (chart.width - chart.left - chart.right); const y = chart.top + ((chart.max - value) / chart.range) * (chart.height - chart.top - chart.bottom); return <circle key={index} cx={x} cy={y} r="2.2" style={{ fill: color }}><title>{formatValue(value)}</title></circle>; })}<text x={chart.left} y={chart.height - 8} className="chart-axis-label">oldest</text><text x={chart.width - chart.right} y={chart.height - 8} textAnchor="end" className="chart-axis-label">latest</text></svg>{chart.nums.length < 2 && <div className="empty-inline">Waiting for a second verified sample. No placeholder line is shown.</div>}<SourceLine source={source ?? 'Live REST pool'} method="Sampled dashboard history" freshness={chart.nums.length ? 'current session' : 'waiting'} /></article>; }
function RangeHeatmap({ candles = [], yearly, levels = [] }) {
  const width = 360; const height = 250; const left = 48; const right = 78; const top = 16; const bottom = 28;
  const values = [...candles.flatMap(candle => [Number(candle.high), Number(candle.low)]), ...(yearly?.available ? [Number(yearly.value.high), Number(yearly.value.low)] : []), ...levels.map(level => Number(level.price))].filter(Number.isFinite);
  if (!values.length) return <div className="empty-state">No verified candle or level data.</div>;
  const domainHigh = Math.max(...values); const domainLow = Math.min(...values); const range = domainHigh - domainLow || 1;
  const y = price => top + ((domainHigh - Number(price)) / range) * (height - top - bottom);
  const x = index => left + (candles.length > 1 ? (index / (candles.length - 1)) * (width - left - right) : (width - left - right) / 2);
  const maxTouches = Math.max(1, ...levels.map(level => Number(level.touches) || 1));
  return <div className="range-heatmap-wrap"><div className="heatmap-legend"><span><i className="legend-candle" />BTC daily candles</span><span><i className="legend-resistance" />Resistance intensity</span><span><i className="legend-support" />Support intensity</span></div><svg className="range-heatmap" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="BTC candle range with support and resistance heatmap">{[0, .25, .5, .75, 1].map(fraction => { const price = domainHigh - fraction * range; const yy = top + fraction * (height - top - bottom); return <g key={fraction}><line x1={left} x2={width - right} y1={yy} y2={yy} className="chart-gridline" /><text x="2" y={yy + 4} className="chart-axis-label">{formatPrice(price)}</text></g>; })}{levels.map((level, index) => { const price = Number(level.price); const intensity = .16 + .62 * ((Number(level.touches) || 1) / maxTouches); const yy = y(price); const band = 2 + 4 * ((Number(level.touches) || 1) / maxTouches); const support = level.kind === 'support'; return <g key={`${level.kind}-${index}`}><rect x={left} y={yy - band} width={width - left - right} height={band * 2} fill={support ? 'var(--green)' : 'var(--red)'} opacity={intensity} /><line x1={left} x2={width - right} y1={yy} y2={yy} stroke={support ? 'var(--green)' : 'var(--red)'} strokeWidth="1" opacity=".95" /><text x={width - right + 5} y={yy + 3} className="heatmap-level-label">{formatPrice(price)}</text></g>; })}{candles.map((candle, index) => { const high = y(candle.high); const low = y(candle.low); const open = y(candle.open); const close = y(candle.close); const rising = Number(candle.close) >= Number(candle.open); const bodyTop = Math.min(open, close); const bodyHeight = Math.max(2, Math.abs(close - open)); return <g key={index}><line x1={x(index)} x2={x(index)} y1={high} y2={low} className="candle-wick" /><rect x={x(index) - 2.5} y={bodyTop} width="5" height={bodyHeight} className={rising ? 'candle-up' : 'candle-down'} /></g>; })}<text x={left} y={height - 8} className="chart-axis-label">oldest</text><text x={width - right} y={height - 8} textAnchor="end" className="chart-axis-label">latest</text></svg></div>;
}

function titleCase(value = '') { return value.replaceAll('_', ' '); }
function availability(value) { return value == null || value === '' ? 'Unavailable' : typeof value === 'object' ? JSON.stringify(value) : value; }

function Badge({ children, tone = 'neutral' }) { return <span className={`badge badge-${tone}`}>{children}</span>; }
function Metric({ label, value, detail, tone = '' }) { return <div className="metric"><span className="metric-label">{label}</span><strong className={tone}>{value}</strong>{detail && <span className="metric-detail">{detail}</span>}</div>; }
function SectionHeading({ eyebrow, title, action }) { return <div className="section-heading"><div><span className="section-eyebrow">{eyebrow}</span><h2>{title}</h2></div>{action}</div>; }
function SourceLine({ source = 'Unavailable', method = 'Not supplied', freshness = 'Unavailable' }) { return <div className="source-line"><span>Source: {source}</span><span>Method: {method}</span><span>Freshness: {freshness}</span></div>; }
function StatePill({ state }) { const tone = state === 'LIVE' ? 'green' : state === 'STALE' || state === 'REST FALLBACK' ? 'amber' : state === 'ERROR' ? 'red' : 'neutral'; return <Badge tone={tone}>{state}</Badge>; }
function IntelCard({ eyebrow, title, state = 'UNAVAILABLE', source, method, freshness, children }) { return <article className="surface intel-card"><SectionHeading eyebrow={eyebrow} title={title} action={<StatePill state={state} />} />{children ?? <div className="empty-state"><CircleAlert size={17} /><span>Data unavailable. No value rendered without a verified source.</span></div>}<SourceLine source={source} method={method} freshness={freshness} /></article>; }
function freshnessAge(value) { if (value == null || !Number.isFinite(Number(value))) return 'Unavailable'; const seconds = Math.max(0, Math.round(Number(value) / 1000)); if (seconds < 60) return `${seconds}s ago`; const minutes = Math.round(seconds / 60); if (minutes < 60) return `${minutes}m ago`; return `${Math.floor(minutes / 60)}h ${minutes % 60}m ago`; }
function freshnessTimestamp(value) { return value == null ? 'Unavailable' : `${jakartaFull.format(new Date(Number(value)))} WIB`; }
function FreshnessCard({ title, data }) { const state = data?.stale ? 'STALE' : data?.source_age_ms == null ? 'UNAVAILABLE' : 'CURRENT'; const tone = state === 'STALE' ? 'amber' : state === 'CURRENT' ? 'green' : 'red'; return <article className={`freshness-card freshness-${tone}`}><div className="freshness-heading"><strong>{title}</strong><Badge tone={tone}>{state}</Badge></div><div className="freshness-details"><span>Source age: <strong>{freshnessAge(data?.source_age_ms)}</strong></span><span>Request age: <strong>{freshnessAge(data?.request_age_ms)}</strong></span><span>Fetched: <strong>{freshnessTimestamp(data?.fetched_at_ms)}</strong></span><span>Source timestamp: <strong>{freshnessTimestamp(data?.source_updated_at_ms ?? data?.updated_at_ms)}</strong></span><span>Source: <strong>{data?.source ?? 'Unavailable'}</strong></span></div></article>; }
function FreshnessPanel({ intelligence }) { return <section className="freshness-grid" aria-label="Data freshness"><FreshnessCard title="Historical intelligence" data={intelligence?.freshness} /><FreshnessCard title="Order book" data={intelligence?.order_book_freshness} /></section>; }

function LevelList({ title, levels = [] }) { return <div className="level-list"><span className="metric-label">{title}</span>{levels.length ? levels.map((level, index) => <div className="level-row" key={`${title}-${index}`}><span>{formatPrice(level.price)}</span><strong>{level.touches} touches</strong></div>) : <div className="empty-inline">Unavailable</div>}</div>; }

function App() {
  const [status, setStatus] = useState(null);
  const [market, setMarket] = useState(null);
  const [intelligence, setIntelligence] = useState(null);
  const [health, setHealth] = useState(null);
  const [chartHistory, setChartHistory] = useState([]);
  const [history, setHistory] = useState([]);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [latency, setLatency] = useState(null);
  const [error, setError] = useState(null);
  const [streamConnected, setStreamConnected] = useState(false);
  const [streamError, setStreamError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastErrorAt, setLastErrorAt] = useState(null);
  const [rateLimited, setRateLimited] = useState(null);
  const lightBackoff = useRef(5000);
  const intelligenceBackoff = useRef(30000);

  async function fetchJson(endpoint) {
    const response = await fetch(endpoint, { cache: 'no-store' });
    if (response.ok) return response.json();
    const retryAfter = response.status === 429 ? Number(response.headers.get('Retry-After')) : null;
    const error = new Error(`${endpoint} request failed (${response.status})`);
    error.retryAfterMs = Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter * 1000 : null;
    error.rateLimited = response.status === 429;
    throw error;
  }

  function recordError(caught, endpoint) {
    const message = caught instanceof Error ? caught.message : 'Connection error';
    setError(message); setLastErrorAt(Date.now());
    if (caught?.rateLimited) setRateLimited({ endpoint, retryAfterMs: caught.retryAfterMs });
  }

  async function refreshLight() {
    const started = performance.now();
    try {
      const [statusResponse, marketResponse, healthResponse] = await Promise.all([fetchJson(API.status), fetchJson(API.market), fetchJson('/api/health')]);
      setStatus(statusResponse); setMarket(marketResponse); setHealth(healthResponse); setError(null); setRateLimited(null); setUpdatedAt(Date.now()); setLatency(Math.round(performance.now() - started));
      if (marketResponse?.ok && marketResponse.price != null) setHistory(previous => [...previous, Number(marketResponse.price)].slice(-32));
      lightBackoff.current = 5000;
      return 5000;
    } catch (caught) {
      recordError(caught, 'status/market/health');
      const delay = caught?.retryAfterMs ?? Math.min(lightBackoff.current * 2, 120000);
      lightBackoff.current = delay;
      return delay + Math.round(Math.random() * 1000);
    }
  }

  async function refreshIntelligence() {
    try {
      const intelligenceResponse = await fetchJson(API.intelligence);
      setIntelligence(intelligenceResponse); setRateLimited(null); intelligenceBackoff.current = 30000;
      const book = intelligenceResponse?.order_book;
      setChartHistory(previous => [...previous, { price: Number(market?.price), imbalance: Number(book?.imbalance), spread: Number(book?.spread) }].filter(item => Object.values(item).every(Number.isFinite)).slice(-48));
      return 30000;
    } catch (caught) {
      recordError(caught, 'intelligence');
      const delay = caught?.retryAfterMs ?? Math.min(intelligenceBackoff.current * 2, 300000);
      intelligenceBackoff.current = delay;
      return delay + Math.round(Math.random() * 2000);
    }
  }

  async function refresh() { setLoading(true); await Promise.all([refreshLight(), refreshIntelligence()]); setLoading(false); }

  useEffect(() => {
    let cancelled = false; let lightTimer; let intelligenceTimer;
    const scheduleLight = async () => { const delay = await refreshLight(); if (!cancelled) lightTimer = setTimeout(scheduleLight, delay); };
    const scheduleIntelligence = async () => { const delay = await refreshIntelligence(); if (!cancelled) intelligenceTimer = setTimeout(scheduleIntelligence, delay); };
    scheduleLight(); scheduleIntelligence();
    return () => { cancelled = true; clearTimeout(lightTimer); clearTimeout(intelligenceTimer); };
  }, []);
  useEffect(() => {
    setStreamConnected(false);
    setStreamError('Bitget SUSDT-FUTURES WebSocket is unavailable; rate-budgeted REST pooling remains active');
  }, []);

  const chartPoints = useMemo(() => {
    if (history.length < 2) return '';
    const min = Math.min(...history), max = Math.max(...history), range = max - min || 1;
    return history.map((value, index) => `${(index / (history.length - 1)) * 100},${92 - ((value - min) / range) * 78}`).join(' ');
  }, [history]);
  const live = Boolean(market?.ok); const runtimeSafety = status?.kill_switch?.runtime_state_available === true; const halted = runtimeSafety && status.kill_switch.halted === true;
  const validation = status?.validation ?? []; const strategies = status?.strategies ?? {};
  const feedState = error ? 'ERROR' : loading && !market ? 'LOADING' : streamConnected ? 'LIVE' : live ? 'REST FALLBACK' : 'UNAVAILABLE';
  const freshness = updatedAt ? `${Math.max(0, Math.round((Date.now() - updatedAt) / 1000))}s ago` : 'Unavailable';
  const rangeReady = market?.high24h != null && market?.low24h != null;
  const weekly = intelligence?.ranges?.weekly ?? []; const monthly = intelligence?.ranges?.monthly ?? []; const yearly = intelligence?.ranges?.yearly;
  const rsiData = intelligence?.rsi; const pivots = intelligence?.support_resistance; const smc = intelligence?.smc; const book = intelligence?.order_book; const liquidations = intelligence?.liquidations;
  const intelligenceFreshness = intelligence?.freshness?.freshness_ms != null ? `${Math.round(intelligence.freshness.freshness_ms / 1000)}s` : freshness;

  return <div className="app-shell">
    <aside className="rail"><div className="rail-brand"><div className="brand-glyph">A</div><div><span className="rail-kicker">Research</span><strong>ABDALGHONIY</strong></div></div><nav className="rail-nav" aria-label="Dashboard sections"><a className="active" href="#overview"><Activity size={16} />Overview</a><a href="#market"><BarChart3 size={16} />Market feed</a><a href="#intelligence"><Gauge size={16} />Intelligence</a><a href="#validation"><ShieldCheck size={16} />Validation</a><a href="#reports"><ArrowUpRight size={16} />Reports</a></nav><div className="rail-footer"><div className="rail-status"><span className={`status-light ${live ? '' : 'offline'}`} />{streamConnected ? 'Live socket' : live ? 'REST fallback' : 'Feed unavailable'}</div><span>v1 · paper</span></div></aside>
    <main className="content" id="overview">
      <header className="page-head"><div><div className="breadcrumb">ABDALGHONIY / MONITOR</div><h1>Research overview</h1><p>One screen for market state, safety posture, and evidence.</p></div><div className="head-actions"><Badge tone="green"><span className="status-light" />PAPER ONLY</Badge><button className="icon-button" onClick={refresh} aria-label="Refresh dashboard"><RefreshCw size={16} /></button></div></header>
      {error && <div className="notice notice-error"><CircleAlert size={16} />{error}{lastErrorAt && ` · last error ${formatTime(lastErrorAt)}`}</div>}
      {rateLimited && <div className="notice notice-warn"><Clock3 size={16} />Dashboard rate limited {rateLimited.endpoint}; backing off{rateLimited.retryAfterMs ? ` for ${Math.ceil(rateLimited.retryAfterMs / 1000)}s` : ''}. Exchange feeds are not being declared rate limited.</div>}
      {streamError && !error && <div className="notice notice-warn"><CircleAlert size={16} />{streamError}</div>}
      <section className="overview-grid"><article className="surface market-surface" id="market"><SectionHeading eyebrow="SUSDT-FUTURES · PUBLIC" title="Market pulse" action={<StatePill state={feedState} />} /><div className="market-main"><div><span className="instrument">{market?.symbol ?? 'SBTCSUSDT'}</span><div className="market-price">{formatPrice(market?.price)}</div><div className={`market-change ${Number(market?.change24h) < 0 ? 'negative' : ''}`}>{market?.change24h ? `${(Number(market.change24h) * 100).toFixed(2)}% 24h` : 'Waiting for feed'}</div></div><svg className="sparkline" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Recent price movement"><polyline points={chartPoints || '0,80 25,55 50,66 75,35 100,45'} /></svg></div><div className="market-foot"><div><span>24h high</span><strong>{formatPrice(market?.high24h)}</strong></div><div><span>24h low</span><strong>{formatPrice(market?.low24h)}</strong></div><div><span>Last tick</span><strong>{market?.ts ? formatTime(Number(market.ts)) : 'Unavailable'}</strong></div></div><SourceLine source={market?.source ?? 'Unavailable'} method={streamConnected ? 'Public WebSocket ticker' : 'REST snapshot'} freshness={freshness} /></article><article className="surface posture-surface"><SectionHeading eyebrow="GUARDRAILS" title="Safety posture" action={<Gauge size={18} className="muted-icon" />} /><div className="hero-state"><div className={`state-mark ${halted ? 'danger' : ''}`}>{halted ? <CircleAlert size={23} /> : <ShieldCheck size={23} />}</div><div><strong>{runtimeSafety ? (halted ? 'Halted' : 'Armed') : 'Policy only'}</strong><span>{runtimeSafety ? (halted ? 'New risk is blocked' : 'Runtime safety state active') : 'Runtime kill-switch state unavailable'}</span></div></div><div className="posture-list"><div><span>Live orders</span><Badge tone="green">Disabled</Badge></div><div><span>Hard stop</span><Badge tone="green">Required</Badge></div><div><span>Daily breaker</span><Badge tone="green">Enabled</Badge></div><div><span>Max leverage</span><strong>3×</strong></div></div></article></section>
      <section className="metrics-grid"><Metric label="System" value={status?.tests ?? 'Checking'} detail="offline suite" tone={status?.tests === 'passing' ? 'green' : 'amber'} /><Metric label="Connection" value={latency ? `${latency} ms` : 'Unavailable'} detail={updatedAt ? `updated ${formatTime(updatedAt)}` : 'waiting'} /><Metric label="Mode" value="Paper" detail="no live controls" tone="green" /><Metric label="Data source" value="Multi-exchange public" detail={intelligence?.freshness?.source ?? 'waiting'} /></section>
      <section className="charts-grid"><LiveChart eyebrow="REAL-TIME HISTORY" title="Price trend" values={chartHistory.map(item => item.price)} source={market?.source} /><LiveChart eyebrow="ORDER FLOW PROXY" title="Order-book imbalance" values={chartHistory.map(item => item.imbalance)} color="var(--amber)" source={intelligence?.freshness?.source} formatValue={value => Number(value).toFixed(3)} /><LiveChart eyebrow="MARKET QUALITY" title="Spread" values={chartHistory.map(item => item.spread)} color="var(--red)" source={intelligence?.freshness?.source} /></section>
      <section id="health" className="surface health-surface"><SectionHeading eyebrow="SYSTEM HEALTH" title="Service health" action={<Badge tone="green">READ ONLY</Badge>} /><div className="health-grid"><div><span>Status</span><strong>{health?.status ?? 'Unavailable'}</strong></div><div><span>Mode</span><strong>{health?.mode ?? 'Unavailable'}</strong></div><div><span>Data plane</span><strong>{health?.data_plane ?? 'Unavailable'}</strong></div><div><span>Live controls</span><strong>Disabled</strong></div></div><SourceLine source="Local service health" method="/api/health" freshness={health ? 'current' : 'waiting'} /></section>
      <FreshnessPanel intelligence={intelligence} />
      <section id="intelligence" className="intel-grid"><IntelCard eyebrow="STRUCTURE" title="Range map" state={weekly.length || monthly.length || yearly?.available ? feedState : 'UNAVAILABLE'} source={intelligence?.freshness?.source} method="Daily candles · calendar periods" freshness={intelligenceFreshness}>{weekly.length || monthly.length || yearly?.available ? <div className="range-detail"><RangeHeatmap candles={weekly} yearly={yearly} levels={pivots?.value ?? []} /><div className="range-periods"><div><span>Weekly high</span><strong>{weekly.at(-1) ? formatPrice(weekly.at(-1).high) : 'Unavailable'}</strong><small>{weekly.at(-1)?.start ?? ''} to {weekly.at(-1)?.end ?? ''}</small></div><div><span>Weekly low</span><strong>{weekly.at(-1) ? formatPrice(weekly.at(-1).low) : 'Unavailable'}</strong><small>{weekly.at(-1)?.candle_count ?? 0} observed candles</small></div><div><span>Monthly high</span><strong>{monthly.at(-1) ? formatPrice(monthly.at(-1).high) : 'Unavailable'}</strong><small>{monthly.at(-1)?.start ?? ''} to {monthly.at(-1)?.end ?? ''}</small></div><div><span>Monthly low</span><strong>{monthly.at(-1) ? formatPrice(monthly.at(-1).low) : 'Unavailable'}</strong><small>{monthly.at(-1)?.candle_count ?? 0} observed candles</small></div><div><span>Yearly high</span><strong>{yearly?.available ? formatPrice(yearly.value.high) : 'Unavailable'}</strong><small>{yearly?.available ? `${yearly.value.start} to ${yearly.value.end}` : yearly?.reason ?? 'Unavailable'}</small></div><div><span>Yearly low</span><strong>{yearly?.available ? formatPrice(yearly.value.low) : 'Unavailable'}</strong><small>{yearly?.available ? `${yearly.value.candle_count} observed candles` : yearly?.reason ?? 'Unavailable'}</small></div></div><div className="level-columns"><LevelList title="Resistance levels" levels={(pivots?.value ?? []).filter(level => level.kind === 'resistance')} /><LevelList title="Support levels" levels={(pivots?.value ?? []).filter(level => level.kind === 'support')} /></div></div> : null}</IntelCard><IntelCard eyebrow="MOMENTUM" title="RSI" state={rsiData?.available ? feedState : 'UNAVAILABLE'} source={intelligence?.freshness?.source} method="Wilder RSI(14) · daily candles" freshness={intelligenceFreshness}>{rsiData?.available ? <div className="health-list"><div><span>Value</span><strong>{rsiData.value}</strong></div><div><span>State</span><strong>{Number(rsiData.value) >= 70 ? 'Overbought' : Number(rsiData.value) <= 30 ? 'Oversold' : 'Neutral'}</strong></div></div> : null}</IntelCard><IntelCard eyebrow="SMART MONEY CONCEPTS" title="SMC structure" state={smc?.available ? feedState : 'UNAVAILABLE'} source={intelligence?.freshness?.source} method="Confirmed swing/BOS scan · daily candles" freshness={intelligenceFreshness}>{smc?.available ? <div className="health-list"><div><span>Events</span><strong>{smc.value.length}</strong></div><div><span>Latest</span><strong>{smc.value.at(-1)?.kind ?? 'Unavailable'}</strong></div></div> : null}</IntelCard><IntelCard eyebrow="LIQUIDITY" title="Order book" state={book?.status === 'ok' ? feedState : 'UNAVAILABLE'} source={intelligence?.freshness?.source} method="Public depth snapshot · top 20 levels" freshness={intelligenceFreshness}>{book?.status === 'ok' ? <div className="health-list"><div><span>Best bid / ask</span><strong>{formatPrice(book.best_bid)} / {formatPrice(book.best_ask)}</strong></div><div><span>Imbalance</span><strong>{Number(book.imbalance).toFixed(3)}</strong></div></div> : null}</IntelCard><IntelCard eyebrow="DERIVATIVES" title="Liquidation heatmap" state="UNAVAILABLE" source="Unavailable" method="No liquidation stream supplied" /><IntelCard eyebrow="OPERATIONS" title="Feed health" state={feedState} source={market?.source ?? 'Unavailable'} method={streamConnected ? 'WebSocket + REST fallback' : 'REST polling'} freshness={freshness}><div className="health-list"><div><span>Current state</span><strong>{feedState}</strong></div><div><span>Rate limit</span><strong>{availability(intelligence?.rate_limit ?? market?.rate_limit ?? status?.rate_limit)}</strong></div><div><span>Last update</span><strong>{updatedAt ? formatTime(updatedAt) : 'Unavailable'} WIB</strong></div></div></IntelCard></section>
      <section className="lower-grid" id="validation"><article className="surface validation-surface"><SectionHeading eyebrow="EVIDENCE" title="Validation ladder" action={<span className="section-note">{validation.filter(item => item.status === 'implemented' || item.status === 'implemented_live_public_readonly').length} of {validation.length} green</span>} /><div className="validation-list">{validation.map(item => { const green = item.status === 'implemented' || item.status === 'implemented_no_live_stream' || item.status === 'implemented_live_public_readonly'; const blocked = item.status.includes('blocked') || item.status === 'not_passed'; return <div className="validation-row" key={item.gate}><div className={`validation-icon ${green ? 'green' : blocked ? 'red' : 'amber'}`}>{green ? <Check size={14} /> : blocked ? <CircleAlert size={14} /> : <Clock3 size={14} />}</div><span>{titleCase(item.gate)}</span><em className={green ? 'green-text' : blocked ? 'red-text' : 'amber-text'}>{titleCase(item.status)}</em></div>; })}</div></article><article className="surface strategy-surface"><SectionHeading eyebrow="PAPER MODULES" title="Strategies" action={<SlidersHorizontal size={18} className="muted-icon" />} /><div className="strategy-list">{Object.entries(strategies).map(([name, mode]) => <div className="strategy-row" key={name}><div className="strategy-dot" /><span>{titleCase(name)}</span><Badge tone="green">{mode}</Badge></div>)}</div><div className="strategy-note"><LockKeyhole size={14} /> Execution path is intentionally unavailable.</div></article></section>
      <section className="surface reports-surface" id="reports"><SectionHeading eyebrow="SOURCE MATERIAL" title="Reports" action={<span className="section-note">Raw evidence, not projections</span>} /><div className="report-grid">{(status?.reports ?? []).map(path => <a href={path} key={path} className="report-link"><span>{path.split('/').pop()?.replace('.md', '')}</span><ArrowUpRight size={15} /></a>)}</div></section><footer className="page-footer"><span><Wifi size={13} /> Public telemetry · refreshes every 5 seconds</span><span>All times Asia/Jakarta · monitoring only</span></footer>
    </main>
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
