import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Activity, ArrowUpRight, BarChart3, Check, CircleAlert, Clock3, Gauge, LockKeyhole, RefreshCw, ShieldCheck, SlidersHorizontal, Wifi } from 'lucide-react';
import './styles.css';

const API = { status: '/api/status', market: '/api/market', intelligence: '/api/intelligence' };
const LIGHT_POLL_MS = 8000;
const INTELLIGENCE_POLL_MS = 30000;
const MAX_LIGHT_BACKOFF_MS = 120000;
const MAX_INTELLIGENCE_BACKOFF_MS = 300000;
const jakarta = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Jakarta', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
const jakartaFull = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Jakarta', dateStyle: 'medium', timeStyle: 'medium' });
const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });

function formatTime(value) { return value ? jakarta.format(new Date(value)) : 'Unavailable'; }
function formatPrice(value) { return value == null || Number.isNaN(Number(value)) ? 'Unavailable' : number.format(Number(value)); }
function formatBytes(value) { if (value == null) return 'Unavailable'; const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']; let n = Number(value); let i = 0; while (n >= 1024 && i < units.length - 1) { n /= 1024; i += 1; } return `${n.toFixed(i ? 1 : 0)} ${units[i]}`; }
function chartGeometry(values) {
  const width = 320; const height = 180; const left = 42; const right = 10; const top = 14; const bottom = 34;
  const nums = values.map(Number).filter(Number.isFinite);
  if (nums.length < 2) return { nums, points: '', min: nums[0] ?? null, max: nums[0] ?? null, latest: nums.at(-1) ?? null, width, height, left, right, top, bottom, range: 1 };
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

function distanceFromPrice(level, price) { const value = Number(level?.price); const current = Number(price); return Number.isFinite(value) && Number.isFinite(current) ? ((value - current) / current) * 100 : null; }
function levelStrength(level) { const touches = Number(level?.touches) || 0; return touches >= 4 ? 'Strong' : touches >= 2 ? 'Medium' : 'Weak'; }
function PriorityLevels({ pivots, price }) {
  const levels = (pivots?.value ?? []).map(level => ({ ...level, distance: distanceFromPrice(level, price) })).filter(level => level.distance != null);
  const resistance = levels.filter(level => level.distance > 0).sort((a, b) => a.distance - b.distance).slice(0, 4);
  const support = levels.filter(level => level.distance < 0).sort((a, b) => Math.abs(a.distance) - Math.abs(b.distance)).slice(0, 4);
  const rows = (items, kind) => items.length ? items.map((level, index) => <div className="priority-level" key={`${kind}-${level.price}-${index}`}><div><strong>{formatPrice(level.price)}</strong><span>{Math.abs(level.distance).toFixed(2)}% {kind === 'resistance' ? 'above' : 'below'} · {level.touches} touches</span></div><Badge tone={levelStrength(level) === 'Strong' ? 'green' : levelStrength(level) === 'Medium' ? 'amber' : 'neutral'}>{levelStrength(level)}</Badge></div>) : <div className="empty-inline">No verified {kind} near current price.</div>;
  return <div className="priority-levels"><div className="priority-column"><span className="metric-label">Nearest resistance</span>{rows(resistance, 'resistance')}</div><div className="priority-column"><span className="metric-label">Nearest support</span>{rows(support, 'support')}</div><details className="all-levels"><summary>Show all {levels.length} verified levels</summary><div className="all-levels-list">{levels.sort((a, b) => Math.abs(a.distance) - Math.abs(b.distance)).map((level, index) => <span key={`${level.kind}-${level.price}-${index}`}><b>{level.kind}</b> {formatPrice(level.price)} · {Math.abs(level.distance).toFixed(2)}% · {level.touches} touches</span>)}</div></details></div>;
}
function TimeframeStrip({ data }) { return <div className="timeframe-strip">{['1H', '4H', '1D'].map(key => { const item = data?.[key]; const bias = item?.smc?.bias ?? 'unavailable'; return <div key={key}><span>{key}</span><strong>{bias}</strong><small>{item?.rsi?.value ?? 'No RSI'} RSI · {item?.available ? freshnessAge(item.freshness?.source_age_ms) : 'unavailable'}</small></div>; })}</div>; }
function ConfidenceBlock({ rsiData, smc, book, freshness, liquidations }) { const evidence = [{ label: 'Daily structure available', good: smc?.available === true }, { label: 'Momentum context available', good: rsiData?.available === true }, { label: 'Public order book available', good: book?.status === 'ok' }, { label: 'Historical source within policy', good: freshness?.stale === false }, { label: 'Liquidation evidence available', good: liquidations?.status === 'ok' }]; const score = evidence.filter(item => item.good).length; const level = score >= 5 ? 'High' : score >= 3 ? 'Medium' : 'Low'; return <div className="confidence-block"><div className="confidence-heading"><span>Explainable research confidence</span><Badge tone={level === 'High' ? 'green' : level === 'Medium' ? 'amber' : 'red'}>{level}</Badge></div><div className="confidence-evidence">{evidence.map(item => <span key={item.label} className={item.good ? 'good' : 'missing'}>{item.good ? '✓' : '×'} {item.label}</span>)}</div></div>; }
function ScenarioMap({ pivots, price, smc, rsiData }) { const levels = (pivots?.value ?? []).map(level => ({ ...level, distance: distanceFromPrice(level, price) })).filter(level => level.distance != null); const above = levels.filter(level => level.distance > 0).sort((a, b) => a.distance - b.distance)[0]; const below = levels.filter(level => level.distance < 0).sort((a, b) => Math.abs(a.distance) - Math.abs(b.distance))[0]; return <div className="scenario-map"><div className="scenario-heading"><span>Scenario map</span><small>Research conditions, not orders</small></div><div className="scenario-grid"><div className="scenario bullish"><Badge tone="green">Continuation</Badge><strong>{above ? `Acceptance above ${formatPrice(above.price)}` : 'Higher resistance acceptance'}</strong><span>{smc?.bias === 'bullish' ? 'Structure supports continuation.' : 'Requires bullish structure confirmation.'}</span></div><div className="scenario bearish"><Badge tone="red">Reversal</Badge><strong>{below ? `Close below ${formatPrice(below.price)}` : 'Break nearest support'}</strong><span>{rsiData?.zone === 'overbought' ? 'RSI rollover would strengthen this case.' : 'Requires bearish structure confirmation.'}</span></div></div></div>; }
function DecisionCockpit({ market, intelligence, rsiData, smc, pivots, book }) {
  const price = market?.price;
  const rsiValue = Number(rsiData?.value);
  const smcBias = smc?.bias ?? 'unavailable';
  const stance = smcBias === 'bullish' && rsiValue >= 70 ? 'Bullish, extended' : smcBias === 'bullish' ? 'Bullish structure' : smcBias === 'bearish' ? 'Bearish structure' : 'Insufficient evidence';
  const stanceTone = stance.startsWith('Bullish') ? 'green' : stance.startsWith('Bearish') ? 'red' : 'amber';
  const latest = smc?.latest;
  return <section className="decision-cockpit surface"><div className="decision-main"><span className="section-eyebrow">RESEARCH DECISION COCKPIT · {intelligence?.freshness?.kind ?? 'PUBLIC DATA'}</span><div className="decision-price"><strong>{formatPrice(price)}</strong><span>{market?.symbol ?? 'SBTCSUSDT'}</span></div><div className="stance-row"><Badge tone={stanceTone}>{stance}</Badge><span>Paper research only · no execution path</span></div></div><div className="decision-evidence"><div><span>RSI 14 · daily</span><strong>{rsiData?.value ?? 'Unavailable'}</strong><small>{rsiData?.zone ?? 'No context'}</small></div><div><span>Structure</span><strong>{smcBias}</strong><small>{latest?.kind?.replaceAll('_', ' ') ?? 'No confirmed event'}</small></div><div><span>Order book</span><strong>{book?.imbalance != null ? Number(book.imbalance).toFixed(3) : 'Unavailable'}</strong><small>{book?.status === 'ok' ? 'public depth' : 'unavailable'}</small></div></div><div className="decision-note"><span>Decision guardrail</span><strong>{rsiValue >= 70 ? 'Do not treat overbought RSI as an isolated short signal.' : smcBias === 'bullish' ? 'Wait for level and momentum confirmation before any research conclusion.' : 'No stance until structure and source freshness are sufficient.'}</strong></div><PriorityLevels pivots={pivots} price={price} /><TimeframeStrip data={intelligence?.multi_timeframe} /><ConfidenceBlock rsiData={rsiData} smc={smc} book={book} freshness={intelligence?.freshness} liquidations={intelligence?.liquidations} /><ScenarioMap pivots={pivots} price={price} smc={smc} rsiData={rsiData} /></section>;
}
function RsiCard({ data, freshness }) { const value = Number(data?.value); const fill = Number.isFinite(value) ? `${Math.max(0, Math.min(100, value))}%` : '0%'; return <article className="surface research-card rsi-card"><SectionHeading eyebrow="MOMENTUM · DAILY" title="RSI 14" action={<Badge tone={data?.zone === 'overbought' ? 'amber' : data?.zone === 'oversold' ? 'red' : 'green'}>{data?.zone ?? 'UNAVAILABLE'}</Badge>} /><div className="rsi-value">{data?.value ?? 'Unavailable'}</div><div className="rsi-gauge"><span style={{ width: fill }} /></div><div className="rsi-zones"><span>Oversold 0-30</span><span>Neutral 30-70</span><span>Overbought 70-100</span></div><div className="interpretation"><span>Research interpretation</span><strong>{data?.interpretation ?? data?.reason ?? 'No verified RSI context.'}</strong></div><SourceLine source={freshness?.source} method="Wilder RSI(14) · daily candles" freshness={freshness ? freshnessAge(freshness.source_age_ms) : 'Unavailable'} /></article>; }
function SmcCard({ data, freshness }) { const events = data?.recent_events ?? []; return <article className="surface research-card smc-card"><SectionHeading eyebrow="MARKET STRUCTURE · DAILY" title="SMC structure" action={<Badge tone={data?.bias === 'bullish' ? 'green' : data?.bias === 'bearish' ? 'red' : 'neutral'}>{data?.bias ?? 'UNAVAILABLE'}</Badge>} /><div className="smc-summary"><div><span>Confirmed events</span><strong>{data?.event_count ?? 0}</strong></div><div><span>Latest event</span><strong>{data?.latest?.kind?.replaceAll('_', ' ') ?? 'Unavailable'}</strong></div><div><span>Event price</span><strong>{formatPrice(data?.latest?.price)}</strong></div></div><div className="smc-timeline">{events.length ? events.slice().reverse().map((event, index) => <div className="smc-event" key={`${event.kind}-${event.index}-${index}`}><div className={`smc-dot ${event.kind.includes('BULLISH') ? 'bullish' : 'bearish'}`} /><div><strong>{event.kind.replaceAll('_', ' ')}</strong><span>{formatPrice(event.price)} · {event.timestamp_ms ? freshnessTimestamp(event.timestamp_ms) : `candle ${event.index}`}</span><small>{event.explanation}</small></div></div>) : <div className="empty-state">No confirmed structure event.</div>}</div><SourceLine source={freshness?.source} method="Confirmed swing / BOS scan · daily candles" freshness={freshness ? freshnessAge(freshness.source_age_ms) : 'Unavailable'} /></article>; }
function OrderBookCard({ book, freshness }) { const imbalance = Number(book?.imbalance); const fill = Number.isFinite(imbalance) ? `${Math.min(100, Math.max(0, (imbalance + 1) * 50))}%` : '0%'; return <article className="surface research-card order-card"><SectionHeading eyebrow="LIQUIDITY · PUBLIC" title="Order book" action={<StatePill state={book?.status === 'ok' ? 'REST FALLBACK' : 'UNAVAILABLE'} />} /><div className="book-quote"><div><span>Best bid</span><strong>{formatPrice(book?.best_bid)}</strong></div><div><span>Best ask</span><strong>{formatPrice(book?.best_ask)}</strong></div><div><span>Spread</span><strong>{formatPrice(book?.spread)}</strong></div></div><div className="imbalance-meter"><div><span>Bid / ask imbalance</span><strong>{Number.isFinite(imbalance) ? imbalance.toFixed(3) : 'Unavailable'}</strong></div><div className="imbalance-track"><span style={{ width: fill }} /></div></div><SourceLine source={freshness?.source ?? 'Unavailable'} method="Public depth snapshot · top 20 levels" freshness={freshness ? freshnessAge(freshness.source_age_ms) : 'Unavailable'} /></article>; }
function LiquidationCard({ data }) { return <article className="surface research-card liquidation-card"><SectionHeading eyebrow="DERIVATIVES · PUBLIC" title="Liquidation heatmap" action={<Badge tone="neutral">UNAVAILABLE</Badge>} /><div className="unavailable-panel"><CircleAlert size={18} /><strong>No reliable public liquidation stream</strong><span>This panel is excluded from the research stance. It is not estimated from candles, trades, or order-book imbalance.</span><small>Reason: {data?.error ?? 'No source supplied'}</small></div><SourceLine source="None" method="Fail-closed public data policy" freshness="Unavailable" /></article>; }

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
  const latestMarketPrice = useRef(null);

  async function fetchJson(endpoint) {
    const response = await fetch(endpoint, { cache: 'no-store' });
    if (response.ok) return response.json();
    const retryAfterHeader = response.status === 429 ? response.headers.get('Retry-After') : null;
    const retryAfterSeconds = retryAfterHeader && /^\d+$/.test(retryAfterHeader.trim()) ? Number(retryAfterHeader) : null;
    const retryAfterDate = retryAfterHeader && retryAfterSeconds == null ? Date.parse(retryAfterHeader) : NaN;
    const retryAfterMs = retryAfterSeconds != null
      ? retryAfterSeconds * 1000
      : Number.isFinite(retryAfterDate) ? Math.max(0, retryAfterDate - Date.now()) : null;
    const error = new Error(`${endpoint} request failed (${response.status})`);
    error.retryAfterMs = retryAfterMs;
    error.rateLimited = response.status === 429;
    throw error;
  }

  function recordError(caught, endpoint) {
    const message = caught instanceof Error ? caught.message : 'Connection error';
    setError({ endpoint, message }); setLastErrorAt(Date.now());
    if (caught?.rateLimited) setRateLimited({ endpoint, retryAfterMs: caught.retryAfterMs });
  }

  function clearEndpointStatus(endpoint) {
    setError(previous => previous?.endpoint === endpoint ? null : previous);
    setRateLimited(previous => previous?.endpoint === endpoint ? null : previous);
  }

  function applyMarket(marketResponse) {
    setMarket(marketResponse);
    latestMarketPrice.current = marketResponse?.ok && marketResponse.price != null ? Number(marketResponse.price) : null;
    if (marketResponse?.ok && marketResponse.price != null) setHistory(previous => [...previous, Number(marketResponse.price)].slice(-32));
  }

  function applyIntelligence(intelligenceResponse) {
    setIntelligence(intelligenceResponse);
    const book = intelligenceResponse?.order_book;
    setChartHistory(previous => [...previous, { price: latestMarketPrice.current, imbalance: Number(book?.imbalance), spread: Number(book?.spread) }].filter(item => Object.values(item).every(Number.isFinite)).slice(-48));
  }

  async function refreshEndpoint(endpoint, name, onSuccess) {
    try {
      const response = await fetchJson(endpoint);
      onSuccess(response);
      clearEndpointStatus(name);
      setUpdatedAt(Date.now());
      setLoading(false);
      return { ok: true };
    } catch (caught) {
      recordError(caught, name);
      return { ok: false, error: caught };
    }
  }

  async function refresh() {
    const started = performance.now();
    setLoading(true);
    await Promise.all([
      refreshEndpoint(API.status, 'status', setStatus),
      refreshEndpoint(API.market, 'market', applyMarket),
      refreshEndpoint('/api/health', 'health', setHealth),
      refreshEndpoint(API.intelligence, 'intelligence', applyIntelligence),
    ]);
    setLatency(Math.round(performance.now() - started));
    setLoading(false);
  }

  useEffect(() => {
    let cancelled = false;
    const jobs = [
      { endpoint: API.status, name: 'status', onSuccess: setStatus, base: LIGHT_POLL_MS, max: MAX_LIGHT_BACKOFF_MS, delay: LIGHT_POLL_MS, timer: null },
      { endpoint: API.market, name: 'market', onSuccess: applyMarket, base: LIGHT_POLL_MS, max: MAX_LIGHT_BACKOFF_MS, delay: LIGHT_POLL_MS, timer: null },
      { endpoint: '/api/health', name: 'health', onSuccess: setHealth, base: LIGHT_POLL_MS, max: MAX_LIGHT_BACKOFF_MS, delay: LIGHT_POLL_MS, timer: null },
      { endpoint: API.intelligence, name: 'intelligence', onSuccess: applyIntelligence, base: INTELLIGENCE_POLL_MS, max: MAX_INTELLIGENCE_BACKOFF_MS, delay: INTELLIGENCE_POLL_MS, timer: null },
    ];
    const schedule = async job => {
      const result = await refreshEndpoint(job.endpoint, job.name, job.onSuccess);
      if (result.ok) job.delay = job.base;
      else job.delay = result.error?.retryAfterMs ?? Math.min(job.delay * 2, job.max);
      if (!cancelled) job.timer = setTimeout(() => schedule(job), job.delay + Math.round(Math.random() * 1000));
    };
    jobs.forEach(schedule);
    return () => { cancelled = true; jobs.forEach(job => clearTimeout(job.timer)); };
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
      {error && <div className="notice notice-error"><CircleAlert size={16} />{error.message}{lastErrorAt && ` · last error ${formatTime(lastErrorAt)}`}</div>}
      {rateLimited && <div className="notice notice-warn"><Clock3 size={16} />Dashboard rate limited {rateLimited.endpoint}; backing off{rateLimited.retryAfterMs ? ` for ${Math.ceil(rateLimited.retryAfterMs / 1000)}s` : ''}. Exchange feeds are not being declared rate limited.</div>}
      {streamError && !error && <div className="notice notice-warn"><CircleAlert size={16} />{streamError}</div>}
      <section className="overview-grid"><article className="surface market-surface" id="market"><SectionHeading eyebrow="SUSDT-FUTURES · PUBLIC" title="Market pulse" action={<StatePill state={feedState} />} /><div className="market-main"><div><span className="instrument">{market?.symbol ?? 'SBTCSUSDT'}</span><div className="market-price">{formatPrice(market?.price)}</div><div className={`market-change ${Number(market?.change24h) < 0 ? 'negative' : ''}`}>{market?.change24h ? `${(Number(market.change24h) * 100).toFixed(2)}% 24h` : 'Waiting for feed'}</div></div><svg className="sparkline" viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="Recent price movement"><polyline points={chartPoints || '0,80 25,55 50,66 75,35 100,45'} /></svg></div><div className="market-foot"><div><span>24h high</span><strong>{formatPrice(market?.high24h)}</strong></div><div><span>24h low</span><strong>{formatPrice(market?.low24h)}</strong></div><div><span>Last tick</span><strong>{market?.ts ? formatTime(Number(market.ts)) : 'Unavailable'}</strong></div></div><SourceLine source={market?.source ?? 'Unavailable'} method={streamConnected ? 'Public WebSocket ticker' : 'REST snapshot'} freshness={freshness} /></article><article className="surface posture-surface"><SectionHeading eyebrow="GUARDRAILS" title="Safety posture" action={<Gauge size={18} className="muted-icon" />} /><div className="hero-state"><div className={`state-mark ${halted ? 'danger' : ''}`}>{halted ? <CircleAlert size={23} /> : <ShieldCheck size={23} />}</div><div><strong>{runtimeSafety ? (halted ? 'Halted' : 'Armed') : 'Policy only'}</strong><span>{runtimeSafety ? (halted ? 'New risk is blocked' : 'Runtime safety state active') : 'Runtime kill-switch state unavailable'}</span></div></div><div className="posture-list"><div><span>Live orders</span><Badge tone="green">Disabled</Badge></div><div><span>Hard stop</span><Badge tone="green">Required</Badge></div><div><span>Daily breaker</span><Badge tone="green">Enabled</Badge></div><div><span>Max leverage</span><strong>3×</strong></div></div></article></section>
      <section className="metrics-grid"><Metric label="System" value={status?.tests ?? 'Checking'} detail="offline suite" tone={status?.tests === 'passing' ? 'green' : 'amber'} /><Metric label="Connection" value={latency ? `${latency} ms` : 'Unavailable'} detail={updatedAt ? `updated ${formatTime(updatedAt)}` : 'waiting'} /><Metric label="Mode" value="Paper" detail="no live controls" tone="green" /><Metric label="Data source" value="Multi-exchange public" detail={intelligence?.freshness?.source ?? 'waiting'} /></section>
      <section className="charts-grid"><LiveChart eyebrow="REAL-TIME HISTORY" title="Price trend" values={chartHistory.map(item => item.price)} source={market?.source} /><LiveChart eyebrow="ORDER FLOW PROXY" title="Order-book imbalance" values={chartHistory.map(item => item.imbalance)} color="var(--amber)" source={intelligence?.freshness?.source} formatValue={value => Number(value).toFixed(3)} /><LiveChart eyebrow="MARKET QUALITY" title="Spread" values={chartHistory.map(item => item.spread)} color="var(--red)" source={intelligence?.freshness?.source} /></section>
      <section id="health" className="surface health-surface"><SectionHeading eyebrow="SYSTEM HEALTH" title="Service health" action={<Badge tone="green">READ ONLY</Badge>} /><div className="health-grid"><div><span>Status</span><strong>{health?.status ?? 'Unavailable'}</strong></div><div><span>Mode</span><strong>{health?.mode ?? 'Unavailable'}</strong></div><div><span>Data plane</span><strong>{health?.data_plane ?? 'Unavailable'}</strong></div><div><span>Live controls</span><strong>Disabled</strong></div></div><SourceLine source="Local service health" method="/api/health" freshness={health ? 'current' : 'waiting'} /></section>
      <FreshnessPanel intelligence={intelligence} />
      <DecisionCockpit market={market} intelligence={intelligence} rsiData={rsiData} smc={smc} pivots={pivots} book={book} />
      <section id="intelligence" className="redesigned-intelligence"><div className="section-divider"><div><span className="section-eyebrow">DECISION EVIDENCE</span><h2>Intelligence panels</h2></div><span className="section-note">Prioritized inputs, expandable detail, honest unavailable states</span></div><div className="research-grid research-grid-top"><RsiCard data={rsiData} freshness={intelligence?.freshness} /><SmcCard data={smc} freshness={intelligence?.freshness} /></div><div className="research-grid research-grid-bottom"><OrderBookCard book={book} freshness={intelligence?.order_book_freshness} /><LiquidationCard data={liquidations} /></div></section>
      <section id="legacy-intelligence" className="intel-grid"><IntelCard eyebrow="STRUCTURE" title="Range map" state={weekly.length || monthly.length || yearly?.available ? feedState : 'UNAVAILABLE'} source={intelligence?.freshness?.source} method="Daily candles · calendar periods" freshness={intelligenceFreshness}>{weekly.length || monthly.length || yearly?.available ? <div className="range-detail"><RangeHeatmap candles={weekly} yearly={yearly} levels={pivots?.value ?? []} /><div className="range-periods"><div><span>Weekly high</span><strong>{weekly.at(-1) ? formatPrice(weekly.at(-1).high) : 'Unavailable'}</strong><small>{weekly.at(-1)?.start ?? ''} to {weekly.at(-1)?.end ?? ''}</small></div><div><span>Weekly low</span><strong>{weekly.at(-1) ? formatPrice(weekly.at(-1).low) : 'Unavailable'}</strong><small>{weekly.at(-1)?.candle_count ?? 0} observed candles</small></div><div><span>Monthly high</span><strong>{monthly.at(-1) ? formatPrice(monthly.at(-1).high) : 'Unavailable'}</strong><small>{monthly.at(-1)?.start ?? ''} to {monthly.at(-1)?.end ?? ''}</small></div><div><span>Monthly low</span><strong>{monthly.at(-1) ? formatPrice(monthly.at(-1).low) : 'Unavailable'}</strong><small>{monthly.at(-1)?.candle_count ?? 0} observed candles</small></div><div><span>Yearly high</span><strong>{yearly?.available ? formatPrice(yearly.value.high) : 'Unavailable'}</strong><small>{yearly?.available ? `${yearly.value.start} to ${yearly.value.end}` : yearly?.reason ?? 'Unavailable'}</small></div><div><span>Yearly low</span><strong>{yearly?.available ? formatPrice(yearly.value.low) : 'Unavailable'}</strong><small>{yearly?.available ? `${yearly.value.candle_count} observed candles` : yearly?.reason ?? 'Unavailable'}</small></div></div><div className="level-columns"><LevelList title="Resistance levels" levels={(pivots?.value ?? []).filter(level => level.kind === 'resistance')} /><LevelList title="Support levels" levels={(pivots?.value ?? []).filter(level => level.kind === 'support')} /></div></div> : null}</IntelCard><IntelCard eyebrow="MOMENTUM" title="RSI" state={rsiData?.available ? feedState : 'UNAVAILABLE'} source={intelligence?.freshness?.source} method="Wilder RSI(14) · daily candles" freshness={intelligenceFreshness}>{rsiData?.available ? <div className="health-list"><div><span>Value</span><strong>{rsiData.value}</strong></div><div><span>State</span><strong>{Number(rsiData.value) >= 70 ? 'Overbought' : Number(rsiData.value) <= 30 ? 'Oversold' : 'Neutral'}</strong></div></div> : null}</IntelCard><IntelCard eyebrow="SMART MONEY CONCEPTS" title="SMC structure" state={smc?.available ? feedState : 'UNAVAILABLE'} source={intelligence?.freshness?.source} method="Confirmed swing/BOS scan · daily candles" freshness={intelligenceFreshness}>{smc?.available ? <div className="health-list"><div><span>Events</span><strong>{smc.value.length}</strong></div><div><span>Latest</span><strong>{smc.value.at(-1)?.kind ?? 'Unavailable'}</strong></div></div> : null}</IntelCard><IntelCard eyebrow="LIQUIDITY" title="Order book" state={book?.status === 'ok' ? feedState : 'UNAVAILABLE'} source={intelligence?.freshness?.source} method="Public depth snapshot · top 20 levels" freshness={intelligenceFreshness}>{book?.status === 'ok' ? <div className="health-list"><div><span>Best bid / ask</span><strong>{formatPrice(book.best_bid)} / {formatPrice(book.best_ask)}</strong></div><div><span>Imbalance</span><strong>{Number(book.imbalance).toFixed(3)}</strong></div></div> : null}</IntelCard><IntelCard eyebrow="DERIVATIVES" title="Liquidation heatmap" state="UNAVAILABLE" source="Unavailable" method="No liquidation stream supplied" /><IntelCard eyebrow="OPERATIONS" title="Feed health" state={feedState} source={market?.source ?? 'Unavailable'} method={streamConnected ? 'WebSocket + REST fallback' : 'REST polling'} freshness={freshness}><div className="health-list"><div><span>Current state</span><strong>{feedState}</strong></div><div><span>Rate limit</span><strong>{availability(intelligence?.rate_limit ?? market?.rate_limit ?? status?.rate_limit)}</strong></div><div><span>Last update</span><strong>{updatedAt ? formatTime(updatedAt) : 'Unavailable'} WIB</strong></div></div></IntelCard></section>
      <section className="lower-grid" id="validation"><article className="surface validation-surface"><SectionHeading eyebrow="EVIDENCE" title="Validation ladder" action={<span className="section-note">{validation.filter(item => item.status === 'implemented' || item.status === 'implemented_live_public_readonly').length} of {validation.length} green</span>} /><div className="validation-list">{validation.map(item => { const green = item.status === 'implemented' || item.status === 'implemented_no_live_stream' || item.status === 'implemented_live_public_readonly'; const blocked = item.status.includes('blocked') || item.status === 'not_passed'; return <div className="validation-row" key={item.gate}><div className={`validation-icon ${green ? 'green' : blocked ? 'red' : 'amber'}`}>{green ? <Check size={14} /> : blocked ? <CircleAlert size={14} /> : <Clock3 size={14} />}</div><span>{titleCase(item.gate)}</span><em className={green ? 'green-text' : blocked ? 'red-text' : 'amber-text'}>{titleCase(item.status)}</em></div>; })}</div></article><article className="surface strategy-surface"><SectionHeading eyebrow="PAPER MODULES" title="Strategies" action={<SlidersHorizontal size={18} className="muted-icon" />} /><div className="strategy-list">{Object.entries(strategies).map(([name, mode]) => <div className="strategy-row" key={name}><div className="strategy-dot" /><span>{titleCase(name)}</span><Badge tone="green">{mode}</Badge></div>)}</div><div className="strategy-note"><LockKeyhole size={14} /> Execution path is intentionally unavailable.</div></article></section>
      <section className="surface reports-surface" id="reports"><SectionHeading eyebrow="SOURCE MATERIAL" title="Reports" action={<span className="section-note">Raw evidence, not projections</span>} /><div className="report-grid">{(status?.reports ?? []).map(path => <a href={path} key={path} className="report-link"><span>{path.split('/').pop()?.replace('.md', '')}</span><ArrowUpRight size={15} /></a>)}</div></section><footer className="page-footer"><span><Wifi size={13} /> Public telemetry · market/status ~8s · intelligence ~30s</span><span>All times Asia/Jakarta · monitoring only</span></footer>
    </main>
  </div>;
}

createRoot(document.getElementById('root')).render(<App />);
