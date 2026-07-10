import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { BatterySpec, SimulationResult, StrategyEconomics } from "../types";

interface Props {
  result: SimulationResult;
  battery: BatterySpec;
  onBack: () => void;
}

// Validated categorical palette (dataviz reference slots 1-3); the widget
// draws its own light card surface, so light-mode values always apply.
const COLORS = {
  self_consumption: "#2a78d6",
  tariff: "#1baf7a",
  arbitrage: "#eda100",
};

const dkk = (v: number): string =>
  `${Math.round(v).toLocaleString("da-DK")} kr.`;

function savingsInterval(s: StrategyEconomics): string {
  const low = Math.round(s.annual_savings_dkk_low);
  const high = Math.round(s.annual_savings_dkk_high);
  if (Math.abs(high - low) < 50) return `ca. ${low.toLocaleString("da-DK")} kr./år`;
  return `${low.toLocaleString("da-DK")}–${high.toLocaleString("da-DK")} kr./år`;
}

const years = (v: number): string =>
  v.toLocaleString("da-DK", { maximumFractionDigits: 1 });

function paybackInterval(s: StrategyEconomics, lifetime: number): string {
  const { payback_years_low: low, payback_years_high: high } = s;
  if (low == null && high == null) return `over ${lifetime} år (batteriets levetid)`;
  if (low != null && high != null) {
    return Math.abs(high - low) < 0.3 ? `ca. ${years(low)} år` : `${years(low)}–${years(high)} år`;
  }
  return `${years((low ?? high) as number)} år eller mere`;
}

export function ResultStep({ result, battery, onBack }: Props) {
  const strategyB = result.strategies.price_optimized;
  const strategyA = result.strategies.self_consumption;
  const lifetime = battery.lifetime_years;

  const chartData = [strategyA, strategyB].map((s) => ({
    name: s.label_da,
    Egetforbrug: Math.max(Math.round(s.year1.savings_self_consumption_dkk), 0),
    Tarifbesparelse: Math.max(Math.round(s.year1.savings_tariff_avoidance_dkk), 0),
    Arbitrage: Math.max(Math.round(s.year1.savings_arbitrage_dkk), 0),
  }));

  return (
    <div className="bc-result">
      <button className="bc-back" onClick={onBack}>
        ← Ret indtastning
      </button>

      <div className="bc-headline">
        <div className="bc-stat">
          <span className="bc-stat-label">Besparelse med prisoptimeret styring</span>
          <span className="bc-stat-value">{savingsInterval(strategyB)}</span>
        </div>
        <div className="bc-stat">
          <span className="bc-stat-label">Tilbagebetalingstid</span>
          <span className="bc-stat-value">{paybackInterval(strategyB, lifetime)}</span>
        </div>
        <div className="bc-stat">
          <span className="bc-stat-label">
            Nutidsværdi efter {lifetime} år ({battery.name})
          </span>
          <span className="bc-stat-value">
            {dkk(strategyB.npv_dkk)}
            {strategyB.npv_dkk_high - strategyB.npv_dkk > 500
              ? ` til ${dkk(strategyB.npv_dkk_high)}`
              : ""}
          </span>
        </div>
      </div>

      <h3 className="bc-section-title">Hvor kommer besparelsen fra? (år 1)</h3>
      <div className="bc-chart">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 4, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e6e5e0" />
            <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#52514e" }} />
            <YAxis
              tickFormatter={(v: number) => v.toLocaleString("da-DK")}
              tick={{ fontSize: 12, fill: "#52514e" }}
              width={56}
              label={{
                value: "kr./år",
                angle: -90,
                position: "insideLeft",
                style: { fontSize: 12, fill: "#52514e" },
              }}
            />
            <Tooltip
              formatter={(value: number | string) => dkk(Number(value))}
              cursor={{ fill: "rgba(0,0,0,0.04)" }}
            />
            <Legend wrapperStyle={{ fontSize: 13 }} />
            <Bar
              dataKey="Egetforbrug"
              stackId="savings"
              isAnimationActive={false}
              fill={COLORS.self_consumption}
              stroke="#ffffff"
              strokeWidth={2}
            />
            <Bar
              dataKey="Tarifbesparelse"
              stackId="savings"
              isAnimationActive={false}
              fill={COLORS.tariff}
              stroke="#ffffff"
              strokeWidth={2}
            />
            <Bar
              dataKey="Arbitrage"
              stackId="savings"
              isAnimationActive={false}
              fill={COLORS.arbitrage}
              stroke="#ffffff"
              strokeWidth={2}
              radius={[4, 4, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <h3 className="bc-section-title">Standard vs. prisoptimeret styring</h3>
      <table className="bc-table">
        <thead>
          <tr>
            <th></th>
            <th>{strategyA.label_da}</th>
            <th>{strategyB.label_da}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Besparelse år 1</td>
            <td>{dkk(strategyA.year1.savings_total_dkk)}</td>
            <td>{dkk(strategyB.year1.savings_total_dkk)}</td>
          </tr>
          <tr>
            <td>Gns. årlig besparelse ({lifetime} år)</td>
            <td>{savingsInterval(strategyA)}</td>
            <td>{savingsInterval(strategyB)}</td>
          </tr>
          <tr>
            <td>Tilbagebetalingstid</td>
            <td>{paybackInterval(strategyA, lifetime)}</td>
            <td>{paybackInterval(strategyB, lifetime)}</td>
          </tr>
          <tr>
            <td>Nutidsværdi (NPV)</td>
            <td>{dkk(strategyA.npv_dkk)}</td>
            <td>{dkk(strategyB.npv_dkk)}</td>
          </tr>
        </tbody>
      </table>

      {/* Collapsible per SPEC §9, but open by default so the assumptions are
          visible without user interaction (SPEC §11 DoD). */}
      <details className="bc-assumptions" open>
        <summary>Forudsætninger</summary>
        <ul>
          {result.assumptions.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ul>
        <p className="bc-hint">
          Referenceår {result.reference_year} · motor v{result.engine_version}
        </p>
      </details>

      <p className="bc-disclaimer">{result.disclaimer}</p>
    </div>
  );
}
