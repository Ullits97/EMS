import type { StrategyEconomics } from "../types";
import { dkk } from "../format";

interface Props {
  costWithoutPv: number;
  strategyB: StrategyEconomics;
}

// Three-tier waterfall: shows the marginal value of adding a battery on top
// of solar, vs. having no system at all. Needs no PV price — pure cost
// comparison, so it's shown whenever PV is present regardless of whether an
// installed price was entered.
export function SystemComparisonTable({ costWithoutPv, strategyB }: Props) {
  const rows = [
    { label: "Ingen anlæg", cost: costWithoutPv },
    { label: "Kun solceller", cost: strategyB.year1.baseline_cost_dkk },
    { label: "Solceller + batteri", cost: strategyB.year1.cost_with_battery_dkk },
  ];

  return (
    <div className="bc-table-wrap">
      <table className="bc-table">
        <thead>
          <tr>
            <th></th>
            <th>Elregning (år 1)</th>
            <th>Besparelse vs. ingen anlæg</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <td>{r.label}</td>
              <td>{dkk(r.cost)}</td>
              <td>{dkk(costWithoutPv - r.cost)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
