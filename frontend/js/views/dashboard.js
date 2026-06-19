import { el, fmtPercent, fmtDataHora, riskBadge, showToast } from "../helpers.js";
import { renderLoading, renderError } from "../layout.js";
import { donutChart, riskColors, legendDot } from "../charts.js";
import { api } from "../api.js";
import { navigate } from "../router.js";

export async function renderDashboard(container) {
  renderLoading(container);
  try {
    const data = await api.dashboard();
    paint(container, data);
  } catch (err) {
    renderError(container, err.message, () => renderDashboard(container));
  }
}

function paint(container, data) {
  container.innerHTML = "";
  const { indicadores, distribuicao_risco, alertas, previsoes_recentes } = data;

  const cards = el("div", { class: "grid cols-4" }, [
    metricCard("Total de alunos", indicadores.total_alunos, "🎓", "var(--primary)", "var(--primary-soft)"),
    metricCard("Alunos em risco", indicadores.alunos_em_risco, "⚠", "var(--warning)", "var(--warning-soft)"),
    metricCard("Alertas ativos", indicadores.alertas_ativos, "🔔", "var(--danger)", "var(--danger-soft)"),
    metricCard("Fator de risco médio", fmtPercent(indicadores.fator_risco_medio), "📊", "var(--success)", "var(--success-soft)"),
  ]);

  const recalcBtn = el(
    "button",
    {
      class: "btn btn-secondary btn-sm",
      onclick: async (event) => {
        const btn = event.currentTarget;
        btn.disabled = true;
        btn.textContent = "Recalculando…";
        try {
          const result = await api.recalcularRiscos();
          showToast(`Riscos recalculados para ${result.total} aluno(s).`, "success");
          renderDashboard(container);
        } catch (err) {
          showToast(err.message, "error");
          btn.disabled = false;
          btn.textContent = "Recalcular riscos";
        }
      },
    },
    ["Recalcular riscos"]
  );

  const distCard = el("div", { class: "card" }, [
    el("div", { class: "card-title" }, ["Distribuição de risco", recalcBtn]),
    el("div", { style: "display:flex; align-items:center; gap:24px; margin-top:10px; flex-wrap:wrap;" }, [
      donutChart(distribuicao_risco),
      el(
        "div",
        { style: "display:flex; flex-direction:column; gap:8px; font-size:13px;" },
        Object.entries(distribuicao_risco).map(([key, value]) =>
          el("div", { style: "display:flex; align-items:center;" }, [
            legendDot(riskColors[key] || "#94a3b8"),
            `${key === "Medio" ? "Médio" : key}: `,
            el("strong", { style: "margin-left:4px;" }, [String(value)]),
          ])
        )
      ),
    ]),
  ]);

  const alertasCard = el("div", { class: "card tight" }, [
    el("div", { style: "padding:18px 18px 0;" }, [
      el("div", { class: "card-title" }, [
        "Alertas ativos recentes",
        el("a", { style: "font-size:12px; cursor:pointer; color:var(--primary);", onclick: () => navigate("/alertas") }, ["ver todos"]),
      ]),
    ]),
    alertas.length === 0
      ? el("div", { class: "empty-state" }, ["Nenhum alerta ativo no momento."])
      : el(
          "div",
          {},
          alertas.slice(0, 6).map((alerta) =>
            el("div", { class: "list-row" }, [
              el("div", { class: "list-row-main" }, [
                el("div", { class: "list-row-title" }, [alerta.aluno_nome]),
                el("div", { class: "list-row-sub" }, [alerta.mensagem]),
              ]),
              riskBadge(alerta.nivel_risco),
            ])
          )
        ),
  ]);

  const previsoesCard = el("div", { class: "card tight" }, [
    el("div", { style: "padding:18px 18px 0;" }, [el("div", { class: "card-title" }, ["Previsões recentes do motor de risco"])]),
    previsoes_recentes.length === 0
      ? el("div", { class: "empty-state" }, ["Nenhuma análise registrada ainda."])
      : el(
          "table",
          {},
          [
            el("thead", {}, [
              el("tr", {}, [
                el("th", {}, ["Aluno"]),
                el("th", {}, ["Nível"]),
                el("th", {}, ["Fator de risco"]),
                el("th", {}, ["Média"]),
                el("th", {}, ["Frequência"]),
                el("th", {}, ["Quando"]),
              ]),
            ]),
            el(
              "tbody",
              {},
              previsoes_recentes.map((analise) =>
                el("tr", {}, [
                  el("td", {}, [analise.aluno_nome]),
                  el("td", {}, [riskBadge(analise.nivel_risco)]),
                  el("td", {}, [fmtPercent(analise.fator_risco)]),
                  el("td", {}, [Number(analise.media_notas).toFixed(1)]),
                  el("td", {}, [`${Number(analise.frequencia).toFixed(1)}%`]),
                  el("td", { class: "muted" }, [fmtDataHora(analise.criado_em)]),
                ])
              )
            ),
          ]
        ),
  ]);

  container.appendChild(
    el("div", {}, [
      el("div", { class: "view-header" }, [
        el("div", {}, [
          el("h2", {}, ["Visão geral"]),
          el("p", { class: "desc" }, ["Indicadores consolidados de desempenho e risco acadêmico."]),
        ]),
      ]),
      cards,
      el("div", { class: "two-col", style: "margin-top:16px;" }, [previsoesCard, distCard]),
      el("div", { style: "margin-top:16px;" }, [alertasCard]),
    ])
  );
}

function metricCard(title, value, icon, color, soft) {
  return el("div", { class: "card" }, [
    el("div", { style: "display:flex; justify-content:space-between; align-items:flex-start;" }, [
      el("div", {}, [
        el("div", { class: "card-title" }, [title]),
        el("div", { class: "metric-value" }, [String(value)]),
      ]),
      el("div", { class: "metric-icon", style: `background:${soft}; color:${color};` }, [icon]),
    ]),
  ]);
}
