import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";

// Embed contract (SPEC §9):
//   <div id="bess-calc" data-tenant="demo" data-api="https://..."></div>
//   <script src=".../widget.js"></script>
function mount(): void {
  const host = document.getElementById("bess-calc");
  if (!host) {
    console.warn("bess-calc widget: no element with id=\"bess-calc\" found");
    return;
  }
  const tenant = host.dataset.tenant ?? "demo";
  const api = (host.dataset.api ?? "").replace(/\/$/, "");
  createRoot(host).render(
    <React.StrictMode>
      <App tenantId={tenant} apiBase={api} />
    </React.StrictMode>,
  );
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mount);
} else {
  mount();
}
