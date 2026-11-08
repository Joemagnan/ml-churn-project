// Servie par l'API (/ui/) : appels sur la même origine.
// Servie par Nginx (docker-compose, port 8080) : appels via le proxy /api/.
const API_BASE = window.location.pathname.startsWith("/ui") ? "" : "/api";
const FIELDS = ["age", "anciennete", "revenu", "nb_reclamations", "montant_mensuel", "retards_paiement"];

const form = document.getElementById("predict-form");
const button = document.getElementById("predict-btn");
const resultBox = document.getElementById("result");
const errorBox = document.getElementById("error");

async function loadStatus() {
  const badge = document.getElementById("api-status");
  try {
    const health = await fetch(`${API_BASE}/health`);
    const body = await health.json();
    badge.textContent = `API : ${body.status}`;
    badge.className = `badge ${health.ok ? "badge-up" : "badge-down"}`;
    const info = await (await fetch(`${API_BASE}/model/info`)).json();
    document.getElementById("model-info").textContent = `Modèle : ${info.model} v${info.version}`;
  } catch (err) {
    badge.textContent = "API : injoignable";
    badge.className = "badge badge-down";
  }
}

function showError(message) {
  resultBox.hidden = true;
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function formatValidationError(detail) {
  if (!Array.isArray(detail)) return String(detail);
  return detail.map((d) => `${d.loc[d.loc.length - 1]} : ${d.msg}`).join(" | ");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {};
  for (const field of FIELDS) {
    const raw = document.getElementById(field).value;
    if (raw === "") return showError(`Le champ ${field} est obligatoire.`);
    payload[field] = Number(raw);
  }

  button.disabled = true;
  button.textContent = "Calcul…";
  try {
    const response = await fetch(`${API_BASE}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Client-ID": "web-ui" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      return showError(`Erreur ${response.status} : ${formatValidationError(body.detail)}`);
    }
    errorBox.hidden = true;
    const percent = (body.probability * 100).toFixed(1);
    document.getElementById("result-label").textContent = body.prediction;
    document.getElementById("result-proba").textContent = `${percent} %`;
    document.getElementById("result-bar").style.width = `${percent}%`;
    document.getElementById("result-version").textContent = body.model_version;
    document.getElementById("result-duration").textContent = body.duration_ms;
    resultBox.className = `result ${body.prediction === "CHURN" ? "churn" : "no-churn"}`;
    resultBox.hidden = false;
  } catch (err) {
    showError("Impossible de joindre l'API de prédiction.");
  } finally {
    button.disabled = false;
    button.textContent = "Prédire";
  }
});

loadStatus();
