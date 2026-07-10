import type { PVEconomics } from "../types";
import { dkk, years } from "../format";

interface Props {
  pvEconomics: PVEconomics | null;
  lifetimeYears: number;
}

// Single-point figures throughout: unlike battery/package economics, there is
// no dispatch strategy to blend here (no battery involved), so there is no
// realism-factor uncertainty band to express as an interval — see
// WorkedExample for the same reasoning applied to baseline_cost_dkk.
export function PVEconomicsCard({ pvEconomics, lifetimeYears }: Props) {
  if (!pvEconomics) {
    return (
      <div className="bc-callout bc-callout--warning">
        <span className="bc-callout-icon" aria-hidden="true">
          i
        </span>
        <span>
          Angiv installeret pris for solcelleanlægget i formularen for at se, om solceller
          alene betaler sig, uafhængigt af batteriet.
        </span>
      </div>
    );
  }

  const paybackText =
    pvEconomics.payback_years != null
      ? `${years(pvEconomics.payback_years)} år`
      : `over ${lifetimeYears} år (eller aldrig)`;

  return (
    <div className="bc-worked-example">
      <div className="bc-worked-row">
        <span>Elregning uden anlæg (år 1)</span>
        <span>{dkk(pvEconomics.cost_without_pv_dkk_year1)}</span>
      </div>
      <div className="bc-worked-row">
        <span>Elregning med kun solceller (år 1)</span>
        <span>{dkk(pvEconomics.cost_with_pv_only_dkk_year1)}</span>
      </div>
      <div className="bc-worked-row bc-worked-row--total">
        <span>= Besparelse år 1</span>
        <span>{dkk(pvEconomics.savings_dkk_year1)}</span>
      </div>
      <div className="bc-worked-row">
        <span>Gns. årlig besparelse ({lifetimeYears} år)</span>
        <span>{dkk(pvEconomics.savings_dkk_avg)}</span>
      </div>
      <div className="bc-worked-row">
        <span>Tilbagebetalingstid</span>
        <span>{paybackText}</span>
      </div>
      <div className="bc-worked-row">
        <span>Nutidsværdi (NPV)</span>
        <span>{dkk(pvEconomics.npv_dkk)}</span>
      </div>
    </div>
  );
}
