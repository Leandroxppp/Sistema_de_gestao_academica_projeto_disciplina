import { el, showToast } from "../helpers.js";
import { renderLoading, renderError } from "../layout.js";
import { api, ApiError } from "../api.js";

// Campos do formulario de limiares de risco, agrupados por nivel. Os nomes
// (chave) precisam corresponder exatamente as chaves aceitas pelo backend em
// DEFAULT_RISCO_THRESHOLDS (app/services.py).
const CAMPOS_ALTO = [
  { chave: "alto_media", label: "Média mínima", hint: "Abaixo desse valor, a média já conta como risco Alto." },
  { chave: "alto_frequencia", label: "Frequência mínima (%)", hint: "Abaixo desse percentual, conta como risco Alto." },
  { chave: "alto_deficit_atividades", label: "Déficit de atividades (0–1)", hint: "Acima desse valor, conta como risco Alto." },
  { chave: "alto_fator", label: "Fator de risco (0–1)", hint: "Acima desse valor, conta como risco Alto." },
];

const CAMPOS_MEDIO = [
  { chave: "medio_media", label: "Média mínima", hint: "Abaixo desse valor (e acima do limiar Alto), conta como risco Médio." },
  { chave: "medio_frequencia", label: "Frequência mínima (%)", hint: "Abaixo desse percentual, conta como risco Médio." },
  { chave: "medio_deficit_atividades", label: "Déficit de atividades (0–1)", hint: "Acima desse valor, conta como risco Médio." },
  { chave: "medio_fator", label: "Fator de risco (0–1)", hint: "Acima desse valor, conta como risco Médio." },
];

export async function renderConfig(container) {
  renderLoading(container);
  try {
    const thresholds = await api.configRisco.obter();
    paint(container, thresholds);
  } catch (err) {
    renderError(container, err.message, () => renderConfig(container));
  }
}

function paint(container, thresholds) {
  container.innerHTML = "";

  const inputs = {};
  function buildCampo({ chave, label, hint }) {
    const input = el("input", {
      type: "number",
      step: "0.01",
      value: thresholds[chave] ?? "",
    });
    inputs[chave] = input;
    return el("div", { class: "field" }, [
      el("label", {}, [label]),
      input,
      el("div", { class: "hint" }, [hint]),
    ]);
  }

  const errorBox = el("div", { class: "alert-banner", style: "display:none" }, [
    el("span", {}, ["⚠"]),
    el("span", { id: "config-form-error" }, [""]),
  ]);

  function setError(msg) {
    if (!msg) {
      errorBox.style.display = "none";
      return;
    }
    errorBox.style.display = "flex";
    errorBox.querySelector("#config-form-error").textContent = msg;
  }

  const submitBtn = el("button", { class: "btn btn-primary", type: "submit" }, ["Salvar limiares"]);

  const form = el(
    "form",
    {
      onsubmit: async (event) => {
        event.preventDefault();
        setError(null);
        const payload = {};
        for (const chave of Object.keys(inputs)) {
          const valor = inputs[chave].value;
          if (valor === "") {
            setError("Todos os campos devem ser preenchidos.");
            return;
          }
          payload[chave] = Number(valor);
        }
        submitBtn.disabled = true;
        submitBtn.textContent = "Salvando…";
        try {
          const atualizado = await api.configRisco.atualizar(payload);
          showToast("Limiares de risco atualizados.", "success");
          paint(container, atualizado);
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Erro ao salvar limiares.");
          submitBtn.disabled = false;
          submitBtn.textContent = "Salvar limiares";
        }
      },
    },
    [
      el("div", { class: "card-title" }, ["Risco Alto"]),
      el("div", { class: "grid cols-2" }, CAMPOS_ALTO.map(buildCampo)),
      el("div", { class: "card-title", style: "margin-top:18px;" }, ["Risco Médio"]),
      el("div", { class: "grid cols-2" }, CAMPOS_MEDIO.map(buildCampo)),
      errorBox,
      el("div", { class: "form-actions" }, [submitBtn]),
    ]
  );

  container.appendChild(
    el("div", {}, [
      el("div", { class: "view-header" }, [
        el("div", {}, [
          el("h2", {}, ["Configurações"]),
          el("p", { class: "desc" }, [
            "Ajuste os limiares usados pelo motor de risco para classificar alunos como Baixo, Médio ou Alto risco. " +
              "Alterações se aplicam às próximas análises (registros de desempenho e recálculos).",
          ]),
        ]),
      ]),
      el("div", { class: "card" }, [form]),
    ])
  );
}
