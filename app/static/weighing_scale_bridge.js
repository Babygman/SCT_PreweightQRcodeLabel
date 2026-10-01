(() => {
  "use strict";

  const config = document.getElementById("scale-bridge-config");
  const forms = [...document.querySelectorAll("[data-scale-weighing-form]")];
  if (!config || forms.length === 0) return;

  const baseUrl = config.dataset.baseUrl;
  const messages = JSON.parse(config.dataset.messages);
  let activeForm = null;
  let activeContext = null;
  let contextReady = Promise.resolve();
  let timer = null;

  const bridgeRequest = async (path, options = {}) => {
    const response = await fetch(`${baseUrl}${path}`, {
      cache: "no-store",
      ...options,
      headers: {"Content-Type": "application/json", ...(options.headers || {})},
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(payload.error || "BRIDGE_UNAVAILABLE");
      error.payload = payload;
      throw error;
    }
    return payload;
  };

  const contextFor = (form, state = null) => ({
    material: form.dataset.material,
    production_order: form.dataset.productionOrder,
    formula_item: form.dataset.formulaItem,
    station: form.dataset.station,
    scale: state?.scale_identity?.scale_code || null,
  });

  const contextsMatch = (expected, actual) => Object.keys(expected).every(
    (key) => String(actual?.[key] ?? "") === String(expected[key] ?? ""),
  );

  const reasonFor = (state, context) => {
    if (!contextsMatch(context, state.context)) return "CONTEXT_MISMATCH";
    return state.save_block_reason || null;
  };

  const show = (form, state = null, overrideReason = null) => {
    const connected = Boolean(state?.connected);
    const reason = overrideReason || (state && activeContext ? reasonFor(state, activeContext) : "BRIDGE_UNAVAILABLE");
    form.querySelector("[data-scale-connection]").textContent = connected ? messages.connected : messages.disconnected;
    form.querySelector("[data-scale-stability]").textContent = state ? (state.stable ? messages.stable : messages.unstable) : "—";
    form.querySelector("[data-scale-gross]").textContent = state?.gross ?? "—";
    form.querySelector("[data-scale-tare]").textContent = state?.tare ?? "—";
    form.querySelector("[data-scale-actual]").textContent = state?.actual ?? "—";
    form.querySelectorAll("[data-scale-unit]").forEach((unit) => { unit.textContent = state?.unit ?? "—"; });
    form.querySelector("[data-scale-reason]").textContent = reason ? (messages[reason] || messages.BRIDGE_UNAVAILABLE) : "";
    const weight = form.querySelector(".actual-weight");
    weight.value = !reason && state?.actual ? state.actual : "";
    form.querySelector(".save-weighing").disabled = Boolean(reason) || !(Number(weight.value) > 0);
  };

  const refresh = async () => {
    if (!activeForm) return;
    try {
      const state = await bridgeRequest("/status");
      const nextContext = contextFor(activeForm, state);
      if (!activeContext || !contextsMatch(nextContext, activeContext)) {
        activeContext = nextContext;
        const updated = await bridgeRequest("/context", {method: "POST", body: JSON.stringify(activeContext)});
        show(activeForm, updated);
      } else {
        show(activeForm, state);
      }
    } catch (_error) {
      show(activeForm, null, "BRIDGE_UNAVAILABLE");
    }
  };

  const activate = (form) => {
    if (activeForm === form) return contextReady;
    if (activeForm) show(activeForm, null, "CONTEXT_MISMATCH");
    activeForm = form;
    activeContext = null;
    contextReady = refresh();
    return contextReady;
  };

  forms.forEach((form) => {
    form.addEventListener("focusin", () => activate(form));
    form.addEventListener("click", () => activate(form));
    form.querySelector(".capture-tare").addEventListener("click", async () => {
      await activate(form);
      try {
        const state = await bridgeRequest("/tare/capture", {method: "POST", body: "{}"});
        show(form, state);
      } catch (error) {
        show(form, error.payload?.state || null, error.message);
      }
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      await activate(form);
      form.querySelector(".save-weighing").disabled = true;
      try {
        const state = await bridgeRequest("/status");
        const expected = contextFor(form, state);
        const reason = reasonFor(state, expected);
        if (reason || !state.actual || !(Number(state.actual) > 0)) {
          show(form, state, reason || "FINAL_CHECK_FAILED");
          return;
        }
        form.querySelector(".actual-weight").value = state.actual;
        HTMLFormElement.prototype.submit.call(form);
      } catch (_error) {
        show(form, null, "FINAL_CHECK_FAILED");
      }
    });
  });

  void activate(forms[0]);
  timer = window.setInterval(refresh, 500);
  window.addEventListener("pagehide", () => window.clearInterval(timer), {once: true});
})();
