import { useEffect, useMemo, useState } from "react";
import { ApiClient } from "./api";
import { InputStep, type InputValues } from "./components/InputStep";
import { ResultStep } from "./components/ResultStep";
import { mapPostcode } from "./postcode";
import type {
  BatterySpec,
  PVProduct,
  PVSpec,
  SimulationRequest,
  SimulationResult,
  TenantCatalog,
} from "./types";

interface Props {
  tenantId: string;
  apiBase: string;
}

type Alternative = { product: BatterySpec; result: SimulationResult };
type PvAlternative = { product: PVProduct; result: SimulationResult };

type Phase =
  | { step: "input" }
  | { step: "loading" }
  | {
      step: "result";
      result: SimulationResult;
      battery: BatterySpec;
      alternatives: Alternative[] | null;
      pvAlternatives: PvAlternative[] | null;
    }
  | { step: "error"; message: string };

function buildRequest(
  values: InputValues,
  battery: BatterySpec,
  pv: PVSpec | null,
): SimulationRequest {
  const site = mapPostcode(values.postcode)!;
  return {
    battery,
    pv,
    consumption: { annual_kwh: values.annualKwh, profile: values.profile },
    site: { price_area: site.price_area, dso: site.dso },
    scenario: { tax_scenario: "low_2026_27" },
  };
}

interface PvCandidate {
  product: PVProduct | null;
  spec: PVSpec | null;
}

function batteryCandidates(values: InputValues, catalog: TenantCatalog): BatterySpec[] {
  if (values.batteryName === "auto") return catalog.products;
  const catalogBattery = catalog.products.find((p) => p.name === values.batteryName);
  if (!catalogBattery) throw new Error("Ukendt batterimodel");
  return [
    values.batteryPriceDkk != null
      ? { ...catalogBattery, price_dkk_installed: values.batteryPriceDkk }
      : catalogBattery,
  ];
}

// values.pvName is undefined in the free-form fallback mode (no PV catalog
// configured for this tenant), "auto" to sweep the whole PV catalog, or a
// specific catalog product name — mirrors batteryCandidates above.
function pvCandidates(values: InputValues, catalog: TenantCatalog): PvCandidate[] {
  if (!values.hasPv) return [{ product: null, spec: null }];

  if (values.pvName == null) {
    return [
      {
        product: null,
        spec: {
          kwp: values.pvKwp,
          orientation: values.pvOrientation,
          tilt_deg: 35,
          price_dkk_installed: values.pvPriceDkk ?? null,
        },
      },
    ];
  }

  if (values.pvName === "auto") {
    return catalog.pv_products.map((product) => ({
      product,
      spec: {
        kwp: product.kwp,
        orientation: values.pvOrientation,
        tilt_deg: 35,
        price_dkk_installed: product.price_dkk_installed,
      },
    }));
  }

  const product = catalog.pv_products.find((p) => p.name === values.pvName);
  if (!product) throw new Error("Ukendt solcelleanlæg");
  return [
    {
      product,
      spec: {
        kwp: product.kwp,
        orientation: values.pvOrientation,
        tilt_deg: 35,
        price_dkk_installed: values.pvPriceDkk ?? product.price_dkk_installed,
      },
    },
  ];
}

// Ranks a combination by the combined PV+battery investment when a priced
// PV is part of it, else falls back to the battery-only NPV (unchanged
// behavior when there's no priced PV in the picture).
function metric(result: SimulationResult): number {
  return result.package_economics?.npv_dkk ?? result.strategies.price_optimized.npv_dkk;
}

export function App({ tenantId, apiBase }: Props) {
  const client = useMemo(() => new ApiClient(apiBase, tenantId), [apiBase, tenantId]);
  const [catalog, setCatalog] = useState<TenantCatalog | null>(null);
  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>({ step: "input" });

  useEffect(() => {
    client
      .catalog()
      .then(setCatalog)
      .catch((err: Error) => setCatalogError(err.message));
  }, [client]);

  const brandColor = catalog?.branding.primary_color ?? "#1d7a5f";

  async function onSubmit(values: InputValues): Promise<void> {
    if (!catalog) return;
    setPhase({ step: "loading" });
    try {
      const batteries = batteryCandidates(values, catalog);
      const pvs = pvCandidates(values, catalog);
      const combos = batteries.flatMap((battery) => pvs.map((pv) => ({ battery, pv })));

      if (combos.length === 1) {
        const { battery, pv } = combos[0];
        const result = await client.simulate(buildRequest(values, battery, pv.spec));
        setPhase({ step: "result", result, battery, alternatives: null, pvAlternatives: null });
        return;
      }

      const runs = await Promise.all(
        combos.map(async (combo) => ({
          ...combo,
          result: await client.simulate(buildRequest(values, combo.battery, combo.pv.spec)),
        })),
      );
      const best = runs.reduce((a, b) => (metric(b.result) > metric(a.result) ? b : a));

      // Two separate 1D comparisons rather than a full N×M grid: each
      // dimension held at the overall winner's choice for the other.
      const alternatives =
        batteries.length > 1
          ? runs
              .filter((r) => r.pv.spec === best.pv.spec)
              .map((r) => ({ product: r.battery, result: r.result }))
          : null;
      const pvAlternatives =
        values.pvName === "auto"
          ? runs
              .filter((r) => r.battery === best.battery)
              .map((r) => ({ product: r.pv.product!, result: r.result }))
          : null;

      setPhase({
        step: "result",
        result: best.result,
        battery: best.battery,
        alternatives,
        pvAlternatives,
      });
    } catch (err) {
      setPhase({ step: "error", message: (err as Error).message });
    }
  }

  return (
    <div className="bc-root" style={{ ["--bc-primary" as string]: brandColor }}>
      <header className="bc-header">
        {catalog?.branding.logo_url ? (
          <img className="bc-logo" src={catalog.branding.logo_url} alt={catalog.branding.name} />
        ) : null}
        <div>
          <h2 className="bc-title">Batteriberegner</h2>
          <p className="bc-subtitle">
            {catalog ? catalog.branding.name : "Indlæser…"} · Beregn din besparelse med et
            hjemmebatteri
          </p>
        </div>
      </header>

      {catalogError ? (
        <p className="bc-error">Kunne ikke kontakte beregningstjenesten: {catalogError}</p>
      ) : null}

      {phase.step === "input" && catalog ? (
        <InputStep
          products={catalog.products}
          pvProducts={catalog.pv_products}
          onSubmit={onSubmit}
        />
      ) : null}

      {phase.step === "loading" ? (
        <div className="bc-loading" role="status">
          <div className="bc-spinner" aria-hidden="true" />
          <p>Simulerer et helt år kvarter for kvarter…</p>
        </div>
      ) : null}

      {phase.step === "error" ? (
        <div>
          <p className="bc-error">{phase.message}</p>
          <button className="bc-button" onClick={() => setPhase({ step: "input" })}>
            Prøv igen
          </button>
        </div>
      ) : null}

      {phase.step === "result" && catalog ? (
        <ResultStep
          result={phase.result}
          battery={phase.battery}
          alternatives={phase.alternatives}
          pvAlternatives={phase.pvAlternatives}
          branding={catalog.branding}
          leadsEnabled={catalog.leads_enabled}
          onSubmitLead={async (contact) => {
            await client.submitLead(contact, phase.result.input_echo, phase.result);
          }}
          onBack={() => setPhase({ step: "input" })}
        />
      ) : null}
    </div>
  );
}
