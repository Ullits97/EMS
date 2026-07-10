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
import type { BatterySpec, Branding, SimulationResult, StrategyEconomics } from "../types";
import { dkk, dkkInterval, paybackYearsText } from "../format";
import { assumptionSeverity, hasSyntheticWarning, unverifiedNotes } from "../assumptions";
import { WorkedExample } from "./WorkedExample";
import { BatteryComparisonTable } from "./BatteryComparisonTable";
import { PVEconomicsCard } from "./PVEconomicsCard";
import { SystemComparisonTable } from "./SystemComparisonTable";
import { PackageEconomicsCard } from "./PackageEconomicsCard";
import { ContactCta } from "./ContactCta";

interface Alternative {
  product: BatterySpec;
  result: SimulationResult;
}

interface Props {
  result: SimulationResult;
  battery: BatterySpec;
  alternatives: Alternative[] | null;
  branding: Branding;
  onBack: () => void;
}

// Validated categorical palette (dataviz reference slots 1-3); the widget
// draws its own light card surface, so light-mode values always apply.
const COLORS = {
  self_consumption: "#2a78d6",
  tariff: "#1baf7a",
  arbitrage: "#eda100",
};

const DSO_LABELS: Record<string, string> = {
  n1: "N1",
  radius: "Radius",
  cerius: "Cerius",
};

function savingsInterval(s: StrategyEconomics): string {
  const low = Math.round(s.annual_savings_dkk_low);
  const high = Math.round(s.annual_savings_dkk_high);
  if (Math.abs(high - low) < 50) return `ca. ${low.toLocaleString("da-DK")} kr./år`;
  return `${low.toLocaleString("da-DK")}–${high.toLocaleString("da-DK")} kr./år`;
}

function year1Interval(s: StrategyEconomics): string {
  return dkkInterval(
    Math.min(s.year1.savings_total_dkk, s.year1_upper.savings_total_dkk),
    Math.max(s.year1.savings_total_dkk, s.year1_upper.savings_total_dkk),
  );
}

function paybackInterval(s: StrategyEconomics, lifetime: number): string {
  return paybackYearsText(
    s.payback_years_low,
    s.payback_years_high,
    `over ${lifetime} år (batteriets levetid)`,
  );
}

export function ResultStep({ result, battery, alternatives, branding, onBack }: Props) {
  const strategyB = result.strategies.price_optimized;
  const strategyA = result.strategies.self_consumption;
  const lifetime = battery.lifetime_years;

  const chartData = [strategyA, strategyB].map((s) => ({
    name: s.label_da,
    Egetforbrug: Math.max(Math.round(s.year1.savings_self_consumption_dkk), 0),
    Tarifbesparelse: Math.max(Math.round(s.year1.savings_tariff_avoidance_dkk), 0),
    Arbitrage: Math.max(Math.round(s.year1.savings_arbitrage_dkk), 0),
  }));

  const syntheticWarning = hasSyntheticWarning(result.assumptions);
  const unverified = unverifiedNotes(result.assumptions);
  const echo = result.input_echo;

  return (
    <div className="bc-result">
      <div className="bc-result-actions">
        <button className="bc-back" onClick={onBack}>
          ← Ret indtastning
        </button>
        <button className="bc-print-button" onClick={() => window.print()}>
          Udskriv resultat
        </button>
      </div>

      {syntheticWarning ? (
        <div className="bc-callout bc-callout--critical">
          <span className="bc-callout-icon" aria-hidden="true">
            ⚠
          </span>
          <span>
            {syntheticWarning}{" "}
            <a className="bc-callout-link" href="#bc-forudsaetninger">
              Se alle forudsætninger nedenfor.
            </a>
          </span>
        </div>
      ) : unverified.length > 0 ? (
        <div className="bc-callout bc-callout--warning">
          <span className="bc-callout-icon" aria-hidden="true">
            ⚠
          </span>
          <span>
            Nogle satser i beregningen er endnu ikke verificeret.{" "}
            <a className="bc-callout-link" href="#bc-forudsaetninger">
              Se alle forudsætninger nedenfor.
            </a>
          </span>
        </div>
      ) : null}

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

      <h3 className="bc-section-title">Sådan hænger tallene sammen (år 1)</h3>
      <WorkedExample strategy={strategyB} />

      {echo.pv ? (
        <>
          <h3 className="bc-section-title">Giver solceller alene mening?</h3>
          <PVEconomicsCard pvEconomics={result.pv_economics} lifetimeYears={lifetime} />

          <h3 className="bc-section-title">Ingen anlæg vs. kun solceller vs. solceller + batteri</h3>
          <SystemComparisonTable
            costWithoutPv={result.cost_without_pv_dkk_year1}
            strategyB={strategyB}
          />
        </>
      ) : null}

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
      <p className="bc-chart-caption">
        Bjælken for '{strategyB.label_da}' svarer til tallene ovenfor.
      </p>

      {alternatives && alternatives.length > 1 ? (
        <>
          <h3 className="bc-section-title">Sammenligning af batteristørrelser (nutidsværdi)</h3>
          <BatteryComparisonTable alternatives={alternatives} selectedName={battery.name} />
        </>
      ) : null}

      {result.package_economics ? (
        <>
          <h3 className="bc-section-title">Samlet pakke-økonomi (solceller + batteri)</h3>
          <PackageEconomicsCard
            packageEconomics={result.package_economics}
            lifetimeYears={lifetime}
          />
        </>
      ) : null}

      <h3 className="bc-section-title">Standard vs. prisoptimeret styring</h3>
      <div className="bc-table-wrap">
        <table className="bc-table">
          <thead>
            <tr>
              <th></th>
              <th>{strategyA.label_da}</th>
              <th>
                {strategyB.label_da}
                <span className="bc-badge">Anbefalet</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Besparelse år 1</td>
              <td>{year1Interval(strategyA)}</td>
              <td>{year1Interval(strategyB)}</td>
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
      </div>

      <details className="bc-details">
        <summary>Dine indtastninger</summary>
        <dl>
          <dt>Elområde</dt>
          <dd>
            {echo.site.price_area} · netselskab {DSO_LABELS[echo.site.dso] ?? echo.site.dso}
          </dd>
          <dt>Forbrug</dt>
          <dd>
            {echo.consumption.annual_kwh.toLocaleString("da-DK")} kWh/år (profil "
            {echo.consumption.profile}")
          </dd>
          <dt>Solceller</dt>
          <dd>
            {echo.pv
              ? `${echo.pv.kwp} kWp, orientering ${echo.pv.orientation}` +
                (echo.pv.price_dkk_installed
                  ? ` · ${echo.pv.price_dkk_installed.toLocaleString("da-DK")} kr. installeret`
                  : "")
              : "Ingen solceller"}
          </dd>
          <dt>Batteri</dt>
          <dd>
            {battery.name} — {battery.capacity_kwh} kWh ·{" "}
            {battery.price_dkk_installed.toLocaleString("da-DK")} kr. installeret
          </dd>
          <dt>Afgiftsscenarie</dt>
          <dd>{echo.scenario.tax_scenario}</dd>
        </dl>
      </details>

      <details className="bc-details" id="bc-forudsaetninger" open>
        <summary>Forudsætninger</summary>
        <ul>
          {result.assumptions.map((a) => {
            const severity = assumptionSeverity(a);
            const className =
              severity === "critical"
                ? "bc-assumption--critical"
                : severity === "warning"
                  ? "bc-assumption--warning"
                  : undefined;
            return (
              <li key={a} className={className}>
                {a}
              </li>
            );
          })}
        </ul>
        <p className="bc-hint">
          Referenceår {result.reference_year} · motor v{result.engine_version}
        </p>
      </details>

      <p className="bc-disclaimer">{result.disclaimer}</p>

      <ContactCta branding={branding} />
    </div>
  );
}
