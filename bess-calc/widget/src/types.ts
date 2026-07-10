// Mirrors the engine's pydantic models (engine/src/besscalc/models.py).

export interface BatterySpec {
  name: string;
  capacity_kwh: number;
  power_kw: number;
  roundtrip_efficiency: number;
  depth_of_discharge: number;
  calendar_degradation_pct_yr: number;
  cycle_life: number;
  lifetime_years: number;
  price_dkk_installed: number;
}

export interface PVSpec {
  kwp: number;
  orientation: "S" | "SE_SW" | "E_W";
  tilt_deg?: number;
  price_dkk_installed?: number | null;
}

export interface SimulationRequest {
  battery: BatterySpec;
  pv: PVSpec | null;
  consumption: { annual_kwh: number; profile: string };
  site: { price_area: "DK1" | "DK2"; dso: string };
  scenario: { tax_scenario: string };
}

export interface SavingsBreakdown {
  savings_self_consumption_dkk: number;
  savings_arbitrage_dkk: number;
  savings_tariff_avoidance_dkk: number;
  savings_total_dkk: number;
  baseline_cost_dkk: number;
  cost_with_battery_dkk: number;
}

export interface StrategyEconomics {
  strategy: string;
  label_da: string;
  year1: SavingsBreakdown;
  year1_upper: SavingsBreakdown;
  lifetime: SavingsBreakdown;
  lifetime_upper: SavingsBreakdown;
  annual_savings_dkk_low: number;
  annual_savings_dkk_high: number;
  payback_years_low: number | null;
  payback_years_high: number | null;
  npv_dkk: number;
  npv_dkk_high: number;
}

export interface PVEconomics {
  price_dkk_installed: number;
  cost_without_pv_dkk_year1: number;
  cost_with_pv_only_dkk_year1: number;
  savings_dkk_year1: number;
  savings_dkk_avg: number;
  payback_years: number | null;
  npv_dkk: number;
}

export interface PackageEconomics {
  price_dkk_installed: number;
  annual_savings_dkk_low: number;
  annual_savings_dkk_high: number;
  payback_years_low: number | null;
  payback_years_high: number | null;
  npv_dkk: number;
  npv_dkk_high: number;
}

export interface SimulationResult {
  strategies: Record<string, StrategyEconomics>;
  reference_year: number;
  assumptions: string[];
  disclaimer: string;
  engine_version: string;
  input_echo: SimulationRequest;
  cost_without_pv_dkk_year1: number;
  pv_economics: PVEconomics | null;
  package_economics: PackageEconomics | null;
}

export interface Branding {
  name: string;
  logo_url: string;
  primary_color: string;
  secondary_color: string;
  contact_phone?: string | null;
  contact_email?: string | null;
  cta_text?: string | null;
  cta_url?: string | null;
}

export interface TenantCatalog {
  tenant_id: string;
  branding: Branding;
  products: BatterySpec[];
}
