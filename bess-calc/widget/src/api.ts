import type { LeadContact, SimulationRequest, SimulationResult, TenantCatalog } from "./types";

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

  async submitLead(
    contact: LeadContact,
    request: SimulationRequest,
    result: SimulationResult,
  ): Promise<{ id: number }> {
    const resp = await fetch(
      `${this.baseUrl}/api/v1/tenants/${encodeURIComponent(this.tenantId)}/leads`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ contact, request, result }),
      },
    );
    if (!resp.ok) throw new Error(`Kunne ikke sende oplysningerne (${resp.status})`);
    return resp.json();
  }
}
