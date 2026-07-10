import { useState } from "react";
import { mapPostcode } from "../postcode";
import type { BatterySpec } from "../types";

export interface InputValues {
  postcode: number;
  annualKwh: number;
  profile: string;
  hasPv: boolean;
  pvKwp: number;
  pvOrientation: "S" | "SE_SW" | "E_W";
  batteryName: string; // product name or "auto"
}

interface Props {
  products: BatterySpec[];
  onSubmit: (values: InputValues) => void;
}

const HOUSEHOLD_PRESETS = [
  { label: "Lejlighed (2.000 kWh/år)", kwh: 2000, profile: "base" },
  { label: "Hus uden elbil/varmepumpe (4.500 kWh/år)", kwh: 4500, profile: "base" },
  { label: "Hus med elbil (8.000 kWh/år)", kwh: 8000, profile: "base_ev" },
  { label: "Hus med varmepumpe (9.000 kWh/år)", kwh: 9000, profile: "base_hp" },
  { label: "Hus med elbil og varmepumpe (12.500 kWh/år)", kwh: 12500, profile: "base_ev_hp" },
];

export function InputStep({ products, onSubmit }: Props) {
  const [postcodeText, setPostcodeText] = useState("");
  const [presetIndex, setPresetIndex] = useState(1);
  const [customKwh, setCustomKwh] = useState<string>("");
  const [hasPv, setHasPv] = useState(false);
  const [pvKwp, setPvKwp] = useState("6");
  const [pvOrientation, setPvOrientation] = useState<"S" | "SE_SW" | "E_W">("S");
  const [batteryName, setBatteryName] = useState("auto");

  const postcode = parseInt(postcodeText, 10);
  const site = Number.isFinite(postcode) ? mapPostcode(postcode) : null;
  const postcodeInvalid = postcodeText.length === 4 && !site;

  const preset = HOUSEHOLD_PRESETS[presetIndex];
  const annualKwh = customKwh ? parseFloat(customKwh) : preset.kwh;
  const kwp = parseFloat(pvKwp);

  const valid =
    site !== null &&
    annualKwh > 0 &&
    annualKwh < 100000 &&
    (!hasPv || (kwp > 0 && kwp <= 50));

  function submit(e: React.FormEvent): void {
    e.preventDefault();
    if (!valid) return;
    onSubmit({
      postcode,
      annualKwh,
      profile: preset.profile,
      hasPv,
      pvKwp: kwp,
      pvOrientation,
      batteryName,
    });
  }

  return (
    <form className="bc-form" onSubmit={submit}>
      <div className="bc-field">
        <label className="bc-label" htmlFor="bc-postcode">
          Postnummer
        </label>
        <input
          id="bc-postcode"
          className="bc-input"
          inputMode="numeric"
          maxLength={4}
          placeholder="fx 8000"
          value={postcodeText}
          onChange={(e) => setPostcodeText(e.target.value.replace(/\D/g, ""))}
        />
        {site ? <p className="bc-hint">Netområde: {site.label}</p> : null}
        {postcodeInvalid ? <p className="bc-error">Ukendt postnummer.</p> : null}
      </div>

      <div className="bc-field">
        <label className="bc-label" htmlFor="bc-household">
          Husstandstype
        </label>
        <select
          id="bc-household"
          className="bc-input"
          value={presetIndex}
          onChange={(e) => {
            setPresetIndex(parseInt(e.target.value, 10));
            setCustomKwh("");
          }}
        >
          {HOUSEHOLD_PRESETS.map((p, i) => (
            <option key={p.label} value={i}>
              {p.label}
            </option>
          ))}
        </select>
      </div>

      <div className="bc-field">
        <label className="bc-label" htmlFor="bc-kwh">
          Årsforbrug (kWh) — valgfrit, overstyrer husstandstypen
        </label>
        <input
          id="bc-kwh"
          className="bc-input"
          inputMode="numeric"
          placeholder={String(preset.kwh)}
          value={customKwh}
          onChange={(e) => setCustomKwh(e.target.value.replace(/\D/g, ""))}
        />
      </div>

      <div className="bc-field">
        <label className="bc-check">
          <input
            type="checkbox"
            checked={hasPv}
            onChange={(e) => setHasPv(e.target.checked)}
          />{" "}
          Jeg har (eller får) solceller
        </label>
      </div>

      {hasPv ? (
        <div className="bc-row">
          <div className="bc-field">
            <label className="bc-label" htmlFor="bc-kwp">
              Solcelleanlæg (kWp)
            </label>
            <input
              id="bc-kwp"
              className="bc-input"
              inputMode="decimal"
              value={pvKwp}
              onChange={(e) => setPvKwp(e.target.value.replace(/[^0-9.,]/g, "").replace(",", "."))}
            />
          </div>
          <div className="bc-field">
            <label className="bc-label" htmlFor="bc-orient">
              Orientering
            </label>
            <select
              id="bc-orient"
              className="bc-input"
              value={pvOrientation}
              onChange={(e) => setPvOrientation(e.target.value as "S" | "SE_SW" | "E_W")}
            >
              <option value="S">Syd</option>
              <option value="SE_SW">Sydøst/Sydvest</option>
              <option value="E_W">Øst/Vest</option>
            </select>
          </div>
        </div>
      ) : null}

      <div className="bc-field">
        <label className="bc-label" htmlFor="bc-battery">
          Batteri
        </label>
        <select
          id="bc-battery"
          className="bc-input"
          value={batteryName}
          onChange={(e) => setBatteryName(e.target.value)}
        >
          <option value="auto">Anbefal størrelse (bedste økonomi)</option>
          {products.map((p) => (
            <option key={p.name} value={p.name}>
              {p.name} — {p.capacity_kwh} kWh ·{" "}
              {p.price_dkk_installed.toLocaleString("da-DK")} kr. installeret
            </option>
          ))}
        </select>
      </div>

      <button className="bc-button" type="submit" disabled={!valid}>
        Beregn besparelse
      </button>
    </form>
  );
}
