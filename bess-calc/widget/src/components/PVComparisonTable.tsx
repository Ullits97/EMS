import type { PVProduct, SimulationResult } from "../types";
import { dkk } from "../format";

interface Alternative {
  product: PVProduct;
  result: SimulationResult;
}

interface Props {
  alternatives: Alternative[];
  selectedKwp: number;
}

// Ranked by the combined PV+battery package NPV (the battery is held fixed
// at the overall recommendation, so this shows "given that battery, which
// PV size is best") — the standalone PV-alone NPV is shown alongside as a
// second perspective, per the user's explicit ask to show both figures
// rather than picking just one.
export function PVComparisonTable({ alternatives, selectedKwp }: Props) {
  const packageNpv = (r: SimulationResult) => r.package_economics?.npv_dkk ?? 0;

  const rows = [...alternatives].sort((a, b) => packageNpv(b.result) - packageNpv(a.result));
  const npvValues = rows.map((r) => packageNpv(r.result));
  const minNpv = Math.min(...npvValues);
  const maxNpv = Math.max(...npvValues);
  const npvRange = maxNpv - minNpv;

  return (
    <div className="bc-table-wrap">
      <table className="bc-table">
        <thead>
          <tr>
            <th>Solcelleanlæg</th>
            <th>Kapacitet</th>
            <th>Pris installeret</th>
            <th>Nutidsværdi (samlet pakke)</th>
            <th>Nutidsværdi (solceller alene)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ product, result }) => {
            const npv = packageNpv(result);
            const isSelected = product.kwp === selectedKwp;
            return (
              <tr key={product.name} className={isSelected ? "bc-row-recommended" : undefined}>
                <td>
                  {product.name}
                  {isSelected ? <span className="bc-badge">Valgt</span> : null}
                </td>
                <td>{product.kwp} kWp</td>
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
                <td>{result.pv_economics ? dkk(result.pv_economics.npv_dkk) : "–"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
