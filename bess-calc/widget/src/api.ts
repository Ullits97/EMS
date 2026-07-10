import type { SimulationRequest, SimulationResult, TenantCatalog } from "./types";

export class ApiClient {
  constructor(
    private baseUrl: string,
    private tenantId: string,
  ) {}

  async catalog(): Promise<TenantCatalog> {
    const resp = await fetch(
      `${this.baseUrl}/api/v1/tenants/${encodeURIComponent(this.tenantId)}/catalog`,
    );
    if (!resp.ok) throw new Error(`Katalog kunne ikke hentes (${resp.status})`);
    return resp.json();
  }

  async simulate(request: SimulationRequest): Promise<SimulationResult> {
    const resp = await fetch(`${this.baseUrl}/api/v1/simulate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: this.tenantId, request }),
    });
    if (!resp.ok) throw new Error(`Beregningen fejlede (${resp.status})`);
    return resp.json();
  }
}
