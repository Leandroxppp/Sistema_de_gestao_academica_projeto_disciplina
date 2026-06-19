import { el, fmtPercent, fmtFrequencia, fmtNota, fmtData, fmtDataHora, riskBadge, statusLabel, initials, showToast } from "../helpers.js";
import { renderLoading, renderError } from "../layout.js";
import { sparkline } from "../charts.js";
import { api, getStoredUser, ApiError } from "../api.js";
import { navigate } from "../router.js";

export async function renderAlunoDetail(container, params) {
  renderLoading(container);
  const alunoId = params.id;
  try {
    const [aluno, materias] = await Promise.all([api.aluno(alunoId), api.materias()]);
    paint(container, aluno, materias);
  } catch (err) {
    renderError(container, err.message, () => renderAlunoDetail(container, params));
  }
}

function paint(container, aluno, todasMaterias) {
  container.innerHTML = "";
  const usuario = getStoredUser();
  const isGestor = usuario?.perfil === "gestor";

  const refresh = () => renderAlunoDetail(container, { id: aluno.id });

  const header = el("div", {}, [
    el("div", { class: "breadcrumb", onclick: () => navigate("/alunos") }, ["← Voltar para Alunos"]),
    el("div", { class: "view-header" }, [
      el("div", { style: "display:flex; align-items:center; gap:14px;" }, [
        el("div", { class: "avatar", style: "width:46px; height:46px; font-size:15px;" }, [initials(aluno.nome)]),
        el("div", {}, [
          el("h2", { class: "mt-0" }, [aluno.nome]),
          el("p", { class: "desc" }, [`Matrícula ${aluno.matricula}${aluno.email ? " · " + aluno.email : ""}`]),
        ]),
      ]),
      el("div", { style: "display:flex; gap:8px; align-items:center;" }, [riskBadge(aluno.status_risco)]),
    ]),
  ]);

  const notasHistorico = [...aluno.desempenhos]
    .slice()
    .reverse()
    .flatMap((d) => d.notas);

  const summaryCards = el("div", { class: "grid cols-3" }, [
    el("div", { class: "card" }, [
      el("div", { class: "card-title" }, ["Status acadêmico"]),
      el("div", { class: "metric-value", style: "font-size:18px;" }, [statusLabel(aluno.status)]),
      el("div", { class: "metric-foot" }, [`Fator de risco: ${fmtPercent(aluno.fator_risco)}`]),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card-title" }, ["Última análise"]),
      aluno.ultima_analise
        ? el("div", {}, [
            el("div", { style: "margin:4px 0;" }, [riskBadge(aluno.ultima_analise.nivel_risco)]),
            el("div", { class: "metric-foot" }, [aluno.ultima_analise.mensagem]),
          ])
        : el("div", { class: "metric-foot" }, ["Nenhuma análise registrada ainda."]),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "card-title" }, ["Histórico de notas"]),
      notasHistorico.length > 0
        ? sparkline(notasHistorico)
        : el("div", { class: "metric-foot" }, ["Sem notas registradas."]),
    ]),
  ]);

  const materiasCard = el("div", { class: "card" }, [
    el("div", { class: "card-title" }, ["Matérias vinculadas"]),
    aluno.materias.length === 0
      ? el("div", { class: "metric-foot", style: "margin-top:8px;" }, ["Nenhuma matéria vinculada."])
      : el(
          "div",
          { style: "display:flex; flex-wrap:wrap; gap:6px; margin-top:10px;" },
          aluno.materias.map((materia) => el("span", { class: "badge tone-primary" }, [materia.nome]))
        ),
    isGestor ? buildVincularForm(aluno, todasMaterias, refresh) : null,
  ]);

  const desempenhoForm = buildDesempenhoForm(aluno, refresh);

  const historicoCard = el("div", { class: "card tight" }, [
    el("div", { style: "padding:18px 18px 0;" }, [el("div", { class: "card-title" }, ["Histórico de desempenho"])]),
    aluno.desempenhos.length === 0
      ? el("div", { class: "empty-state" }, ["Nenhum desempenho registrado ainda."])
      : el("table", {}, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", {}, ["Data"]),
              el("th", {}, ["Matéria"]),
              el("th", {}, ["Notas"]),
              el("th", {}, ["Frequência"]),
              el("th", {}, ["Atividades"]),
            ]),
          ]),
          el(
            "tbody",
            {},
            aluno.desempenhos.map((d) =>
              el("tr", {}, [
                el("td", { class: "muted" }, [fmtData(d.data_referencia)]),
                el("td", {}, [d.materia_nome || "—"]),
                el(
                  "td",
                  {},
                  [el("div", { style: "display:flex; gap:4px;" }, d.notas.map((n) => el("span", { class: "notas-pill" }, [fmtNota(n)])))]
                ),
                el("td", {}, [fmtFrequencia(d.frequencia)]),
                el("td", { class: "muted" }, [
                  d.atividades_entregues != null && d.atividades_esperadas != null
                    ? `${d.atividades_entregues}/${d.atividades_esperadas}`
                    : "—",
                ]),
              ])
            )
          ),
        ]),
  ]);

  container.appendChild(
    el("div", {}, [
      header,
      summaryCards,
      el("div", { class: "two-col", style: "margin-top:16px;" }, [
        el("div", {}, [historicoCard]),
        el("div", { style: "display:flex; flex-direction:column; gap:16px;" }, [desempenhoForm, materiasCard]),
      ]),
    ])
  );
}

function buildVincularForm(aluno, todasMaterias, onDone) {
  const linkedIds = new Set(aluno.materias.map((m) => m.id));
  const disponiveis = todasMaterias.filter((m) => !linkedIds.has(m.id));
  if (disponiveis.length === 0) return null;

  const select = el(
    "select",
    {},
    disponiveis.map((m) => el("option", { value: m.id }, [m.nome]))
  );
  const btn = el(
    "button",
    {
      class: "btn btn-secondary btn-sm",
      type: "button",
      onclick: async () => {
        btn.disabled = true;
        try {
          await api.vincularMateria(aluno.id, select.value);
          showToast("Matéria vinculada.", "success");
          onDone();
        } catch (err) {
          showToast(err instanceof ApiError ? err.message : "Erro ao vincular matéria.", "error");
          btn.disabled = false;
        }
      },
    },
    ["Vincular"]
  );

  return el("div", { style: "margin-top:14px; display:flex; gap:8px;" }, [select, btn]);
}

function buildDesempenhoForm(aluno, onDone) {
  const materiaSelect = el(
    "select",
    {},
    [
      el("option", { value: "" }, ["Geral (sem matéria específica)"]),
      ...aluno.materias.map((m) => el("option", { value: m.id }, [m.nome])),
    ]
  );
  const notasInput = el("input", { placeholder: "Ex.: 8.0, 7.5, 9.0", required: true });
  const frequenciaInput = el("input", { type: "number", min: "0", max: "100", step: "0.1", placeholder: "Ex.: 92", required: true });
  const entreguesInput = el("input", { type: "number", min: "0", step: "1", placeholder: "Opcional" });
  const esperadasInput = el("input", { type: "number", min: "1", step: "1", placeholder: "Opcional" });
  const dataInput = el("input", { type: "date", value: new Date().toISOString().slice(0, 10) });

  const errorBox = el("div", { class: "alert-banner", style: "display:none" }, [el("span", {}, ["⚠"]), el("span", { id: "perf-error" }, [""])]);
  const resultBox = el("div", { style: "display:none" });

  function setError(msg) {
    if (!msg) {
      errorBox.style.display = "none";
      return;
    }
    errorBox.style.display = "flex";
    errorBox.querySelector("#perf-error").textContent = msg;
  }

  const submitBtn = el("button", { class: "btn btn-primary", type: "submit" }, ["Registrar desempenho"]);

  const form = el(
    "form",
    {
      onsubmit: async (event) => {
        event.preventDefault();
        setError(null);
        resultBox.style.display = "none";

        const notas = notasInput.value
          .split(/[,;]/)
          .map((n) => n.trim())
          .filter(Boolean)
          .map(Number);

        if (notas.length === 0 || notas.some((n) => Number.isNaN(n))) {
          setError("Informe ao menos uma nota válida, separadas por vírgula.");
          return;
        }
        if (frequenciaInput.value === "") {
          setError("Informe a frequência.");
          return;
        }

        const payload = {
          materia_id: materiaSelect.value || undefined,
          notas,
          frequencia: Number(frequenciaInput.value),
          atividades_entregues: entreguesInput.value === "" ? undefined : Number(entreguesInput.value),
          atividades_esperadas: esperadasInput.value === "" ? undefined : Number(esperadasInput.value),
          data_referencia: dataInput.value || undefined,
        };

        submitBtn.disabled = true;
        submitBtn.textContent = "Registrando…";
        try {
          const result = await api.registrarDesempenho(aluno.id, payload);
          showToast("Desempenho registrado.", "success");
          resultBox.style.display = "block";
          resultBox.innerHTML = "";
          resultBox.appendChild(
            el("div", { class: "alert-banner success", style: "margin-top:8px;" }, [
              el("span", {}, ["✓"]),
              el("span", {}, [`Análise: ${result.analise.nivel} (fator ${fmtPercent(result.analise.fator_risco)}) — ${result.analise.mensagem}`]),
            ])
          );
          notasInput.value = "";
          entreguesInput.value = "";
          esperadasInput.value = "";
          setTimeout(onDone, 900);
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Erro ao registrar desempenho.");
        } finally {
          submitBtn.disabled = false;
          submitBtn.textContent = "Registrar desempenho";
        }
      },
    },
    [
      el("div", { class: "field" }, [el("label", {}, ["Matéria"]), materiaSelect]),
      el("div", { class: "field" }, [
        el("label", {}, ["Notas"]),
        notasInput,
        el("div", { class: "hint" }, ["Separe múltiplas notas por vírgula."]),
      ]),
      el("div", { class: "field-row" }, [
        el("div", { class: "field" }, [el("label", {}, ["Frequência (%)"]), frequenciaInput]),
        el("div", { class: "field" }, [el("label", {}, ["Data"]), dataInput]),
      ]),
      el("div", { class: "field-row" }, [
        el("div", { class: "field" }, [el("label", {}, ["Atividades entregues"]), entreguesInput]),
        el("div", { class: "field" }, [el("label", {}, ["Atividades esperadas"]), esperadasInput]),
      ]),
      errorBox,
      resultBox,
      el("div", { class: "form-actions" }, [submitBtn]),
    ]
  );

  return el("div", { class: "card" }, [el("div", { class: "card-title" }, ["Registrar novo desempenho"]), form]);
}
