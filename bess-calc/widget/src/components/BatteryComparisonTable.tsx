import type { BatterySpec, SimulationResult } from "../types";
import { dkk } from "../format";

interface Alternative {
  product: BatterySpec;
  result: SimulationResult;
}

interface Props {
  alternatives: Alternative[];
  selectedName: string;
}

export function BatteryComparisonTable({ alternatives, selectedName }: Props) {
  const rows = [...alternatives].sort(
    (a, b) =>
      b.result.strategies.price_optimized.npv_dkk - a.result.strategies.price_optimized.npv_dkk,
  );
  const npvValues = rows.map((r) => r.result.strategies.price_optimized.npv_dkk);
  const minNpv = Math.min(...npvValues);
  const maxNpv = Math.max(...npvValues);
  const npvRange = maxNpv - minNpv;

  return (
    <div className="bc-table-wrap">
      <table className="bc-table">
        <thead>
          <tr>
            <th>Batteri</th>
            <th>Kapacitet</th>
            <th>Pris installeret</th>
            <th>Nutidsværdi (NPV)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ product, result }) => {
            const npv = result.strategies.price_optimized.npv_dkk;
            const isSelected = product.name === selectedName;
            return (
              <tr key={product.name} className={isSelected ? "bc-row-recommended" : undefined}>
                <td>
                  {product.name}
                  {isSelected ? <span className="bc-badge">Valgt</span> : null}
                </td>
                <td>{product.capacity_kwh} kWh</td>
                <td>{dkk(product.price_dkk_installed)}</td>
                <td>
                  {dkk(npv)}
                  <span className="bc-npv-bar-track">
                    <span
                      className="bc-npv-bar-fill"
                      style={{ width: `${npvRange > 0 ? ((npv - minNpv) / npvRange) * 100 : 100}%` }}
                    />
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
