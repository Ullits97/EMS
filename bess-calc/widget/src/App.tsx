import { useEffect, useMemo, useState } from "react";
import { ApiClient } from "./api";
import { InputStep, type InputValues } from "./components/InputStep";
import { ResultStep } from "./components/ResultStep";
import { mapPostcode } from "./postcode";
import type { BatterySpec, SimulationRequest, SimulationResult, TenantCatalog } from "./types";

interface Props {
  tenantId: string;
  apiBase: string;
}

type Phase =
  | { step: "input" }
  | { step: "loading" }
  | { step: "result"; result: SimulationResult; battery: BatterySpec }
  | { step: "error"; message: string };

function buildRequest(values: InputValues, battery: BatterySpec): SimulationRequest {
  const site = mapPostcode(values.postcode)!;
  return {
    battery,
    pv: values.hasPv
      ? { kwp: values.pvKwp, orientation: values.pvOrientation, tilt_deg: 35 }
      : null,
    consumption: { annual_kwh: values.annualKwh, profile: values.profile },
    site: { price_area: site.price_area, dso: site.dso },
    scenario: { tax_scenario: "low_2026_27" },
  };
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
      if (values.batteryName === "auto") {
        // "Anbefal størrelse": sweep the catalog, pick the best headline NPV.
        const results = await Promise.all(
          catalog.products.map(async (product) => ({
            product,
            result: await client.simulate(buildRequest(values, product)),
          })),
        );
        const best = results.reduce((a, b) =>
          b.result.strategies.price_optimized.npv_dkk >
          a.result.strategies.price_optimized.npv_dkk
            ? b
            : a,
        );
        setPhase({ step: "result", result: best.result, battery: best.product });
      } else {
        const battery = catalog.products.find((p) => p.name === values.batteryName);
        if (!battery) throw new Error("Ukendt batterimodel");
        const result = await client.simulate(buildRequest(values, battery));
        setPhase({ step: "result", result, battery });
      }
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
        <InputStep products={catalog.products} onSubmit={onSubmit} />
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

      {phase.step === "result" ? (
        <ResultStep
          result={phase.result}
          battery={phase.battery}
          onBack={() => setPhase({ step: "input" })}
        />
      ) : null}
    </div>
  );
}
