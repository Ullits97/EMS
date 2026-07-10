import type { PackageEconomics } from "../types";
import { dkk, dkkInterval, paybackYearsText } from "../format";

interface Props {
  packageEconomics: PackageEconomics;
  lifetimeYears: number;
}

// Interval throughout, like the battery's own StrategyEconomics: this
// includes the battery's dispatch strategy (price_optimized), so the same
// realism-factor uncertainty applies (SPEC §10.2).
export function PackageEconomicsCard({ packageEconomics, lifetimeYears }: Props) {
  const savingsText = dkkInterval(
    packageEconomics.annual_savings_dkk_low,
    packageEconomics.annual_savings_dkk_high,
  );
  const paybackText = paybackYearsText(
    packageEconomics.payback_years_low,
    packageEconomics.payback_years_high,
    `over ${lifetimeYears} år (batteriets levetid)`,
  );
  const npvText = dkkInterval(packageEconomics.npv_dkk, packageEconomics.npv_dkk_high);

  return (
    <div className="bc-headline">
      <div className="bc-stat">
        <span className="bc-stat-label">Samlet investering (solceller + batteri)</span>
        <span className="bc-stat-value">{dkk(packageEconomics.price_dkk_installed)}</span>
      </div>
      <div className="bc-stat">
        <span className="bc-stat-label">Gns. årlig besparelse ({lifetimeYears} år)</span>
        <span className="bc-stat-value">{savingsText}/år</span>
      </div>
      <div className="bc-stat">
        <span className="bc-stat-label">Tilbagebetalingstid (samlet)</span>
        <span className="bc-stat-value">{paybackText}</span>
      </div>
      <div className="bc-stat">
        <span className="bc-stat-label">Nutidsværdi (samlet)</span>
        <span className="bc-stat-value">{npvText}</span>
      </div>
    </div>
  );
}
