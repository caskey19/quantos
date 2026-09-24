import { useEffect, useRef, useState } from "react";
import { createChart, type IChartApi, type ISeriesApi } from "lightweight-charts";
import { getJson } from "./client";

const WORKSPACES = [
  ["command", "Command Center"],
  ["markets", "Markets"],
  ["charts", "Charts"],
  ["scanner", "Scanner"],
  ["research", "Research"],
  ["strategy", "Strategy Lab"],
  ["backtest", "Backtest"],
  ["paper", "Paper Trading"],
  ["live", "Live Trading"],
  ["positions", "Positions"],
  ["orders", "Orders"],
  ["risk", "Risk"],
  ["performance", "Performance"],
  ["ai", "AI Research"],
  ["data", "Data Health"],
  ["system", "System Health"],
  ["settings", "Settings"],
] as const;

type WorkspaceId = (typeof WORKSPACES)[number][0];

export function Workstation({ mode, live, recorded }: { mode: string; live: boolean; recorded: boolean }) {
  const [active, setActive] = useState<WorkspaceId>("command");
  return (
    <div className="app">
      <header className={live ? "banner live" : "banner"}>
        <div>
          {live ? "LIVE" : <span className="mode-pill">{mode.toUpperCase()}</span>} quant-os
        </div>
        <div>
          {live
            ? "REAL CAPITAL PATH OPEN"
            : recorded
              ? "RECORDED STUDY · LIVE SUBMISSION LOCKED"
              : "LIVE SUBMISSION LOCKED"}
        </div>
      </header>
      <nav className="nav">
        {WORKSPACES.map(([id, label]) => (
          <button key={id} className={active === id ? "active" : ""} onClick={() => setActive(id)}>
            {label}
          </button>
        ))}
      </nav>
      <main className="content">
        {active === "command" && <CommandCenter />}
        {active === "markets" && <JsonPanel title="Markets" path="/api/markets" />}
        {active === "charts" && <Charts />}
        {active === "scanner" && <Scanner />}
        {active === "research" && <Research />}
        {active === "strategy" && <Strategy />}
        {active === "backtest" && <Backtest />}
        {active === "paper" && <JsonPanel title="Paper" path="/api/session" />}
        {active === "live" && <LivePanel />}
        {active === "positions" && <Positions />}
        {active === "orders" && <Orders />}
        {active === "risk" && <RiskPanel />}
        {active === "performance" && <Performance />}
        {active === "ai" && <Research />}
        {active === "data" && <JsonPanel title="Data health" path="/api/data-health" />}
        {active === "system" && <JsonPanel title="System health" path="/api/system-health" />}
        {active === "settings" && <JsonPanel title="Checklist" path="/api/checklist" />}
      </main>
    </div>
  );
}

function CommandCenter() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    getJson("/api/command-center").then(setData).catch(() => setData(null));
  }, []);
  if (!data) return <p>Waiting for the local API.</p>;
  const account = data.account ?? {};
  const cards = [
    ["Mode", data.mode],
    ["Market", data.market_status],
    ["Equity", money(account.equity)],
    ["Cash", money(account.cash)],
    ["Buying power", money(account.buying_power)],
    ["Day P&L", money(account.day_pnl)],
    ["Week P&L", money(account.week_pnl)],
    ["Total P&L", money(account.total_pnl)],
    ["Drawdown", pct(account.drawdown)],
    ["Gross", money(data.exposure?.gross)],
    ["Net", money(data.exposure?.net)],
    ["Strategy", data.strategy_state],
    ["Regime", data.regime],
    ["Data", data.data_health],
    ["Broker", data.broker_connected ? "connected" : "down"],
    ["Kill", data.kill?.tripped ? data.kill.reason : "armed"],
  ];
  return (
    <div className="stack">
      <h1>Command Center</h1>
      <div className="grid">
        {cards.map(([label, value]) => (
          <div className="card" key={label}>
            <span>{label}</span>
            <strong>{String(value ?? "—")}</strong>
          </div>
        ))}
      </div>
      <div className="panel">
        <span className="muted">Hypothesis status: {data.hypothesis_status}. Research: {data.research_status}.</span>
        <p>Blocked orders and recent orders are listed from the operational store, not from a narrative model.</p>
      </div>
    </div>
  );
}

function Charts() {
  const ref = useRef<HTMLDivElement | null>(null);
  const [note, setNote] = useState("Loading fixture");
  useEffect(() => {
    let chart: IChartApi | null = null;
    let series: ISeriesApi<"Candlestick"> | null = null;
    getJson("/api/bars/L00")
      .then((payload) => {
        if (!ref.current) return;
        chart = createChart(ref.current, {
          layout: { background: { color: "#121821" }, textColor: "#d5dbe6" },
          grid: { vertLines: { color: "#243044" }, horzLines: { color: "#243044" } },
          height: 420,
        });
        series = chart.addCandlestickSeries();
        const volume = chart.addHistogramSeries({ priceScaleId: "vol", color: "#3d4f6a" });
        chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
        const bars = (payload.bars ?? []).map((bar: any) => ({
          time: bar.time,
          open: bar.open,
          high: bar.high,
          low: bar.low,
          close: bar.close,
        }));
        series.setData(bars);
        volume.setData((payload.bars ?? []).map((bar: any) => ({ time: bar.time, value: bar.volume })));
        setNote(payload.note ?? payload.source ?? "No bars");
      })
      .catch(() => setNote("Chart data is unavailable"));
    return () => chart?.remove();
  }, []);
  return (
    <div className="stack">
      <h1>Charts</h1>
      <div className="split">
        <div className="panel watch">
          <span className="muted">Watchlist</span>
          <button>L00 synthetic</button>
          <p className="muted">Symbol search and overlays attach once a market feed is configured. This view does not invent prices.</p>
        </div>
        <div>
          <div ref={ref} className="chart" />
          <p className="footer-note">
            {note}. Charting by{" "}
            <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">
              TradingView
            </a>{" "}
            Lightweight Charts, Apache 2.0.
          </p>
        </div>
      </div>
    </div>
  );
}

function Scanner() {
  const [data, setData] = useState<any>({ rows: [], columns: [], note: "" });
  useEffect(() => {
    getJson("/api/scanner").then(setData);
  }, []);
  return (
    <div className="stack">
      <h1>Scanner</h1>
      <p className="muted">{data.note}</p>
      <table>
        <thead>
          <tr>{(data.columns ?? []).map((column: string) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>
          {(data.rows ?? []).length === 0 ? (
            <tr><td colSpan={6}>No symbols. The scanner only shows reversal-program fields, and none are live.</td></tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

function Strategy() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    getJson("/api/strategy").then(setData);
  }, []);
  if (!data) return <p>Loading strategy record.</p>;
  return (
    <div className="stack">
      <h1>Strategy Lab</h1>
      <div className="panel">
        <div>State: {data.state}</div>
        <div>Hypothesis: {data.hypothesis_status}</div>
        <div>Version: {data.strategy_version}</div>
        <div>Trials counted: {data.n_trials}</div>
        <div>Plateau: {String(data.parameter_plateau)}</div>
        <h2>Rejection reasons</h2>
        <ul>{(data.rejection_reasons ?? []).map((reason: string) => <li key={reason}>{reason}</li>)}</ul>
      </div>
    </div>
  );
}

function Backtest() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    getJson("/api/backtest").then(setData);
  }, []);
  if (!data) return <p>Loading experiments.</p>;
  return (
    <div className="stack">
      <h1>Backtest</h1>
      <p className="muted">{data.note}</p>
      <table>
        <thead>
          <tr>
            <th>Experiment</th>
            <th>Model</th>
            <th>Sharpe</th>
            <th>Max DD</th>
            <th>Trades</th>
            <th>Result</th>
          </tr>
        </thead>
        <tbody>
          {(data.experiments ?? []).map((row: any) => (
            <tr key={row.experiment_id}>
              <td>{row.experiment_id}</td>
              <td>{row.cost_assumptions?.model}</td>
              <td>{number(row.metrics?.sharpe)}</td>
              <td>{pct(row.metrics?.max_drawdown)}</td>
              <td>{row.metrics?.trades}</td>
              <td>{row.result}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Research() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    getJson("/api/research").then(setData);
  }, []);
  if (!data) return <p>Loading research session.</p>;
  return (
    <div className="stack">
      <h1>AI Research</h1>
      <p className="muted">Promoted: {String(data.promoted)}. Claims are tagged. The skeptic can veto.</p>
      {(data.claims ?? []).map((claim: any, index: number) => (
        <div className="panel" key={index}>
          <span className="tag">{claim.kind}</span>
          <span className="tag">{claim.agent}</span>
          <div>{claim.statement}</div>
        </div>
      ))}
      <h2>Skeptic</h2>
      {(data.skeptic?.objections ?? []).map((claim: any, index: number) => (
        <div className="panel" key={`s${index}`}>
          <span className="tag">{claim.kind}</span>
          <div>{claim.statement}</div>
        </div>
      ))}
    </div>
  );
}

function LivePanel() {
  const [message, setMessage] = useState("Live submission is locked.");
  async function attempt() {
    if (import.meta.env.VITE_STATIC === "1") {
      setMessage("Live trading cannot be enabled through the API");
      return;
    }
    try {
      const response = await fetch("/api/live/enable", { method: "POST" });
      const payload = await response.json();
      setMessage(payload.detail ?? "Refused");
    } catch {
      setMessage("Live trading cannot be enabled through the API");
    }
  }
  return (
    <div className="stack">
      <h1>Live Trading</h1>
      <div className="panel">
        <p>This screen cannot create the unlock file, cannot raise capital limits, and cannot switch the process into live mode.</p>
        <button onClick={attempt}>Attempt to enable live</button>
        <p>{message}</p>
      </div>
    </div>
  );
}

function Positions() {
  const [data, setData] = useState<any>({ positions: [] });
  useEffect(() => {
    getJson("/api/positions").then(setData);
  }, []);
  return (
    <div className="stack">
      <h1>Positions</h1>
      <table>
        <thead><tr><th>Symbol</th><th>Qty</th><th>Avg</th><th>Notional</th></tr></thead>
        <tbody>
          {(data.positions ?? []).map((row: any) => (
            <tr key={row.symbol}><td>{row.symbol}</td><td>{row.qty}</td><td>{number(row.avg_price)}</td><td>{money(row.notional)}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Orders() {
  const [data, setData] = useState<any>({ orders: [], shadow: [] });
  useEffect(() => {
    getJson("/api/orders").then(setData);
  }, []);
  return (
    <div className="stack">
      <h1>Orders</h1>
      <table>
        <thead><tr><th>Id</th><th>Symbol</th><th>Side</th><th>State</th></tr></thead>
        <tbody>
          {(data.orders ?? []).map((row: any) => (
            <tr key={row.client_order_id}><td>{row.client_order_id}</td><td>{row.symbol}</td><td>{row.side}</td><td>{row.state}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RiskPanel() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    getJson("/api/risk").then(setData);
  }, []);
  if (!data) return <p>Loading risk.</p>;
  return (
    <div className="stack">
      <h1>Risk</h1>
      <div className="panel">Kill: {data.kill?.tripped ? data.kill.reason : "armed"} / {data.kill?.action}</div>
      <table>
        <tbody>
          {Object.entries(data.limits ?? {}).map(([key, value]) => (
            <tr key={key}><td>{key}</td><td>{String(value)}</td></tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Performance() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    getJson("/api/performance").then(setData);
  }, []);
  if (!data) return <p>Loading performance.</p>;
  return (
    <div className="stack">
      <h1>Performance</h1>
      <p className="muted">Market evidence: {String(data.real_market_evidence)}. Stress Sharpe is not a promotion.</p>
      <pre>{JSON.stringify(data.stress_sharpe_by_parameter ?? {}, null, 2)}</pre>
      <ul>{(data.rejection_reasons ?? []).map((reason: string) => <li key={reason}>{reason}</li>)}</ul>
    </div>
  );
}

function JsonPanel({ title, path }: { title: string; path: string }) {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    getJson(path).then(setData).catch((error) => setData({ error: String(error) }));
  }, [path]);
  return (
    <div className="stack">
      <h1>{title}</h1>
      <pre className="panel">{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}

function money(value: number | undefined) {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function pct(value: number | undefined) {
  if (value === undefined || value === null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

function number(value: number | undefined) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return "—";
  return Number(value).toFixed(2);
}
