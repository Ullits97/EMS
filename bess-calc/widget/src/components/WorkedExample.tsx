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
  const withBattery = strategy.year1.cost_with_battery_dkk;
  const withBatteryUpper = strategy.year1_upper.cost_with_battery_dkk;
  const costLow = Math.min(withBattery, withBatteryUpper);
  const costHigh = Math.max(withBattery, withBatteryUpper);
  // When the interval collapses, show the headline (year1) cost/savings pair
  // together — never a cost from one variant paired with savings derived
  // from the other, which would make baseline - shown_cost != shown_savings.
  const collapsed = Math.abs(costHigh - costLow) < 50;

  const withBatteryText = collapsed
    ? dkk(withBattery)
    : `${dkk(costLow)} – ${dkk(costHigh)}`;
  const savingsText = collapsed
    ? dkk(baseline - withBattery)
    : `${dkk(baseline - costHigh)} – ${dkk(baseline - costLow)}`;

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
