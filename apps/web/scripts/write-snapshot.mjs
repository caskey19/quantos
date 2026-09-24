import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(webRoot, "../..");

function readJson(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function readYamlMap(path, section) {
  const lines = readFileSync(path, "utf8").split(/\r?\n/);
  const values = {};
  let inSection = section === undefined;
  for (const line of lines) {
    if (!line.trim() || line.trim().startsWith("#")) continue;
    if (!line.startsWith(" ") && !line.startsWith("\t")) {
      inSection = section === undefined ? true : line.startsWith(`${section}:`);
      continue;
    }
    if (!inSection) continue;
    const trimmed = line.trim();
    const split = trimmed.indexOf(":");
    if (split < 0) continue;
    const key = trimmed.slice(0, split).trim();
    let value = trimmed.slice(split + 1).trim().replace(/^["']|["']$/g, "");
    if (value === "true") value = true;
    else if (value === "false") value = false;
    else if (value !== "" && !Number.isNaN(Number(value))) value = Number(value);
    values[key] = value;
  }
  return values;
}

const study = readJson(resolve(repoRoot, "research/results/reversal_study.json"));
const chart = readJson(resolve(repoRoot, "research/results/chart_fixture.json"));
const checklist = readYamlMap(resolve(repoRoot, "config/live_authorization.yml"), "items");
const limits = readYamlMap(resolve(repoRoot, "config/risk_limits.yml"));
const dataVersion = study.experiments?.[0]?.data_version ?? "synthetic";

const account = {
  equity: 100000,
  cash: 100000,
  buying_power: 100000,
  day_pnl: 0,
  week_pnl: 0,
  total_pnl: 0,
  drawdown: 0,
  gross_exposure: 0,
  net_exposure: 0,
  peak_equity: 100000,
};

const kill = { tripped: false, reason: null, action: "stop_new", detail: "" };

const research = {
  promoted: false,
  claims: [
    {
      agent: "research",
      kind: "hypothesis",
      statement:
        "Liquid names with weak recent residual returns might outperform strong names over 1 to 5 sessions after costs.",
      refs: ["Jegadeesh 1990", "Lehmann 1990"],
    },
    {
      agent: "quant",
      kind: "fact",
      statement: `Pre-registered trial count is ${study.n_trials}. The sealed window was not opened.`,
      refs: ["config/sealed_window.yml"],
    },
    {
      agent: "data",
      kind: "fact",
      statement:
        "This run used a synthetic panel. IEX and SIP market data were not ingested. Survivorship is unresolved.",
      refs: [dataVersion],
    },
    {
      agent: "ml",
      kind: "fact",
      statement: "The linear baseline is stored and not promoted. No model sits on the order path.",
      refs: [],
    },
    {
      agent: "execution",
      kind: "statistical_evidence",
      statement: "Optimistic, expected, and stress fills were all recorded. Promotion looks at the stress model only.",
      refs: [],
    },
    {
      agent: "news",
      kind: "fact",
      statement: "News is outside the selected program and was not used as a feature.",
      refs: [],
    },
    {
      agent: "code_review",
      kind: "fact",
      statement: "Reversal features use past pct_change only. Forward labels live in a separate module.",
      refs: [],
    },
    {
      agent: "risk",
      kind: "hypothesis",
      statement: "A short book can lose more than the gross budget if spreads gap. Hard loss limits stay in force.",
      refs: [],
    },
  ],
  skeptic: {
    veto: true,
    objections: [
      {
        agent: "skeptic",
        kind: "fact",
        statement: "There is no market evidence in this artifact. Promotion is refused.",
        refs: [],
      },
      {
        agent: "skeptic",
        kind: "statistical_evidence",
        statement: "Stress-model validation Sharpe is not positive, so costs or the plant dominate.",
        refs: [],
      },
      {
        agent: "skeptic",
        kind: "hypothesis",
        statement: "A single parameter cell is not a plateau. Isolated winners are treated as overfit.",
        refs: [],
      },
      {
        agent: "skeptic",
        kind: "speculation",
        statement:
          "Published reversal profits have often been bid-ask bounce. That remains the leading alternative explanation.",
        refs: ["Jegadeesh and Titman microstructure papers", "Avramov, Chordia, Goyal"],
      },
    ],
  },
};

const snapshot = {
  "/api/session": {
    mode: "paper",
    live_locked: true,
    recorded: true,
    live: {
      mode: "paper",
      live_submission_allowed: false,
      reason: "Live trading is disabled: TRADING_MODE is not live; unlock file absent or phrase mismatch",
      checklist,
      unlock_present: false,
    },
    broker: "none",
    paper_broker: true,
  },
  "/api/checklist": {
    mode: "paper",
    live_submission_allowed: false,
    reason: "Live trading is disabled: TRADING_MODE is not live; unlock file absent or phrase mismatch",
    checklist,
    unlock_present: false,
  },
  "/api/command-center": {
    mode: "paper",
    live_locked: true,
    market_status: "recorded study",
    account,
    exposure: { gross: 0, net: 0 },
    positions: [],
    strategy_state: study.state,
    hypothesis_status: study.hypothesis_status,
    regime: "unvalidated",
    kill,
    broker_connected: false,
    data_health: "synthetic",
    research_status: study.promotion,
    blocked: [],
    recent_orders: [],
  },
  "/api/orders": { orders: [], shadow: [] },
  "/api/strategy": study,
  "/api/research": research,
  "/api/backtest": {
    experiments: study.experiments ?? [],
    stress: (study.experiments ?? []).filter((row) => row.cost_assumptions?.model === "stress"),
    note: "Figures are synthetic until a market-data study is stored.",
    real_market_evidence: study.real_market_evidence ?? false,
  },
  "/api/risk": { limits, kill, blocked: [] },
  "/api/performance": {
    real_market_evidence: false,
    best_stress_parameter: study.best_stress_parameter,
    stress_sharpe_by_parameter: study.stress_sharpe_by_parameter,
    rejection_reasons: study.rejection_reasons,
  },
  "/api/scanner": {
    rows: [],
    columns: ["symbol", "residual", "spread_bps", "dollar_volume", "regime", "excluded"],
    note: "Scanner stays empty until market data for the reversal program is ingested.",
  },
  "/api/markets": {
    feed: "none",
    note: "No market session is connected. This page is the recorded study, not a running broker.",
  },
  "/api/bars/L00": {
    ...chart,
    requested: "L00",
    note: "Synthetic fixture. Not a market price.",
  },
  "/api/data-health": {
    trustworthy: false,
    reason: "No raw market dataset has been ingested. Synthetic research output is labeled synthetic.",
    survivorship: "unresolved",
    feed: "unconfigured",
  },
  "/api/system-health": {
    process: { note: "GitHub Pages static record. No trading process is running." },
    database_ms: null,
    latency: {},
    broker_connected: false,
    alerts: [],
    kill,
  },
  "/api/positions": { positions: [], exposure: { gross: 0, net: 0 } },
};

const outDir = resolve(webRoot, "public");
mkdirSync(outDir, { recursive: true });
writeFileSync(resolve(outDir, "snapshot.json"), JSON.stringify(snapshot));
