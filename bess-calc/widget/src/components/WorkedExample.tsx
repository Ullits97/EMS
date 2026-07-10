import type { StrategyEconomics } from "../types";
import { dkk } from "../format";

interface Props {
  strategy: StrategyEconomics;
}

// Renders the year-1 savings figure as a derived calculation rather than an
// asserted number: baseline cost (no battery) minus cost with battery.
// baseline_cost_dkk is identical across year1/year1_upper by construction
// (the baseline scenario has no battery, so realism-scaling doesn't touch
// it) — a single point here is a factual input, not one of the intervals
// SPEC §10.2 requires for results.
export function WorkedExample({ strategy }: Props) {
  const baseline = strategy.year1.baseline_cost_dkk;
  const withBatteryLow = Math.min(
    strategy.year1.cost_with_battery_dkk,
    strategy.year1_upper.cost_with_battery_dkk,
  );
  const withBatteryHigh = Math.max(
    strategy.year1.cost_with_battery_dkk,
    strategy.year1_upper.cost_with_battery_dkk,
  );
  const savingsLow = baseline - withBatteryHigh;
  const savingsHigh = baseline - withBatteryLow;

  const withBatteryText =
    Math.abs(withBatteryHigh - withBatteryLow) < 50
      ? dkk(withBatteryLow)
      : `${dkk(withBatteryLow)} – ${dkk(withBatteryHigh)}`;
  const savingsText =
    Math.abs(savingsHigh - savingsLow) < 50
      ? dkk(savingsLow)
      : `${dkk(savingsLow)} – ${dkk(savingsHigh)}`;

  return (
    <div className="bc-worked-example">
      <div className="bc-worked-row">
        <span>Din elregning uden batteri (år 1)</span>
        <span>{dkk(baseline)}</span>
      </div>
      <div className="bc-worked-row">
        <span>Din elregning med batteri ({strategy.label_da}, år 1)</span>
        <span>{withBatteryText}</span>
      </div>
      <div className="bc-worked-row bc-worked-row--total">
        <span>= Besparelse år 1</span>
        <span>{savingsText}</span>
      </div>
    </div>
  );
}
