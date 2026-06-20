import {
  el,
  fmtPercent,
  fmtFrequencia,
  fmtNota,
  fmtData,
  fmtDataHora,
  riskBadge,
  statusLabel,
  initials,
  showToast,
  mountModal,
  confirmModal,
} from "../helpers.js";
import { renderLoading, renderError } from "../layout.js";
import { sparkline } from "../charts.js";
import { api, getStoredUser, ApiError } from "../api.js";
import { navigate } from "../router.js";

const STATUS_VALUES = [
  "Cadastrado",
  "Cursando_Materia",
  "Regular",
  "Risco_Medio",
  "Risco_Alto",
  "Aprovado",
  "Reprovado",
  "Evadido",
];

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
  const inativo = aluno.ativo === 0;

  const refresh = () => renderAlunoDetail(container, { id: aluno.id });

  const headerRight = [riskBadge(aluno.status_risco)];
  if (inativo) headerRight.unshift(el("span", { class: "badge tone-danger" }, ["Inativo"]));
  if (isGestor) {
    headerRight.push(
      el(
        "button",
        { class: "btn btn-ghost btn-sm", type: "button", onclick: () => openAlunoModal(aluno, refresh) },
        ["Editar"]
      )
    );
    headerRight.push(
      el(
        "button",
        {
          class: `btn btn-sm ${inativo ? "btn-secondary" : "btn-danger"}`,
          type: "button",
          onclick: async () => {
            const confirmado = await confirmModal(
              inativo
                ? `Reativar o cadastro de "${aluno.nome}"?`
                : `Desativar o cadastro de "${aluno.nome}"? Não será possível vincular matérias ou registrar desempenho enquanto estiver inativo.`,
              {
                title: inativo ? "Reativar aluno" : "Desativar aluno",
                confirmLabel: inativo ? "Reativar" : "Desativar",
                danger: !inativo,
              }
            );
            if (!confirmado) return;
            try {
              if (inativo) {
                await api.atualizarAluno(aluno.id, { ativo: true });
                showToast("Aluno reativado.", "success");
              } else {
                await api.desativarAluno(aluno.id);
                showToast("Aluno desativado.", "success", {
                  onUndo: async () => {
                    try {
                      await api.atualizarAluno(aluno.id, { ativo: true });
                      showToast("Aluno reativado.", "success");
                      refresh();
                    } catch (err) {
                      showToast(err instanceof ApiError ? err.message : "Erro ao desfazer.", "error");
                    }
                  },
                });
              }
              refresh();
            } catch (err) {
              showToast(err instanceof ApiError ? err.message : "Erro ao atualizar aluno.", "error");
            }
          },
        },
        [inativo ? "Reativar" : "Desativar"]
      )
    );
  }

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
      el("div", { style: "display:flex; gap:8px; align-items:center;" }, headerRight),
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
    isGestor && !inativo ? buildVincularForm(aluno, todasMaterias, refresh) : null,
    isGestor && inativo
      ? el("div", { class: "metric-foot", style: "margin-top:10px;" }, ["Reative o aluno para vincular novas matérias."])
      : null,
  ]);

  const desempenhoForm = buildDesempenhoForm(aluno, refresh, inativo);

  const historicoCard = el("div", { class: "card tight" }, [
    el("div", { style: "padding:18px 18px 0;" }, [el("div", { class: "card-title" }, ["Histórico de desempenho"])]),
    aluno.desempenhos.length === 0
      ? el("div", { class: "empty-state" }, ["Nenhum desempenho registrado ainda."])
      : el("table", {}, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { scope: "col" }, ["Data"]),
              el("th", { scope: "col" }, ["Matéria"]),
              el("th", { scope: "col" }, ["Notas"]),
              el("th", { scope: "col" }, ["Frequência"]),
              el("th", { scope: "col" }, ["Atividades"]),
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

  const intervencoesCard = buildIntervencoesCard(aluno, refresh);

  container.appendChild(
    el("div", {}, [
      header,
      summaryCards,
      el("div", { class: "two-col", style: "margin-top:16px;" }, [
        el("div", {}, [historicoCard]),
        el("div", { style: "display:flex; flex-direction:column; gap:16px;" }, [desempenhoForm, materiasCard]),
      ]),
      el("div", { style: "margin-top:16px;" }, [intervencoesCard]),
    ])
  );
}

const INTERVENCAO_TIPO_LABEL = {
  Contato: "Contato",
  Reuniao: "Reunião",
  Encaminhamento: "Encaminhamento",
  Outro: "Outro",
};
const INTERVENCAO_TIPOS = Object.keys(INTERVENCAO_TIPO_LABEL);

function buildIntervencoesCard(aluno, onDone) {
  const intervencoes = aluno.intervencoes || [];

  const tabela =
    intervencoes.length === 0
      ? el("div", { class: "metric-foot", style: "margin-top:8px;" }, ["Nenhuma ação registrada ainda."])
      : el("table", { style: "margin-top:10px;" }, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { scope: "col" }, ["Tipo"]),
              el("th", { scope: "col" }, ["Descrição"]),
              el("th", { scope: "col" }, ["Status"]),
              el("th", { scope: "col" }, ["Responsável"]),
              el("th", { scope: "col" }, ["Quando"]),
              el("th", { scope: "col" }, [""]),
            ]),
          ]),
          el(
            "tbody",
            {},
            intervencoes.map((i) => {
              const isPendente = i.status === "Pendente";
              return el("tr", {}, [
                el("td", {}, [INTERVENCAO_TIPO_LABEL[i.tipo] || i.tipo]),
                el("td", { class: "muted" }, [i.descricao || "—"]),
                el("td", {}, [
                  el("span", { class: `badge ${isPendente ? "tone-warning" : "tone-success"}` }, [i.status]),
                ]),
                el("td", { class: "muted" }, [i.responsavel_nome || "—"]),
                el("td", { class: "muted" }, [
                  isPendente ? fmtDataHora(i.criado_em) : `Concluída em ${fmtDataHora(i.resolvido_em)}`,
                ]),
                el("td", {}, [
                  isPendente
                    ? el(
                        "button",
                        {
                          class: "btn btn-ghost btn-sm",
                          type: "button",
                          onclick: async () => {
                            try {
                              await api.atualizarIntervencao(i.id, { status: "Concluída" });
                              showToast("Ação marcada como concluída.", "success");
                              onDone();
                            } catch (err) {
                              showToast(err instanceof ApiError ? err.message : "Erro ao atualizar ação.", "error");
                            }
                          },
                        },
                        ["Concluir"]
                      )
                    : null,
                ]),
              ]);
            })
          ),
        ]);

  const tipoSelect = el(
    "select",
    {},
    INTERVENCAO_TIPOS.map((t) => el("option", { value: t }, [INTERVENCAO_TIPO_LABEL[t]]))
  );
  const descricaoInput = el("input", { placeholder: "Detalhes da ação (opcional)" });
  const errorBox = el("div", { class: "alert-banner", style: "display:none" }, [
    el("span", {}, ["⚠"]),
    el("span", { id: "intervencao-form-error" }, [""]),
  ]);

  function setError(msg) {
    if (!msg) {
      errorBox.style.display = "none";
      return;
    }
    errorBox.style.display = "flex";
    errorBox.querySelector("#intervencao-form-error").textContent = msg;
  }

  const submitBtn = el("button", { class: "btn btn-secondary btn-sm", type: "submit" }, ["Registrar ação"]);
  const form = el(
    "form",
    {
      style: "margin-top:14px;",
      onsubmit: async (event) => {
        event.preventDefault();
        setError(null);
        submitBtn.disabled = true;
        try {
          await api.criarIntervencao(aluno.id, {
            tipo: tipoSelect.value,
            descricao: descricaoInput.value.trim() || undefined,
          });
          showToast("Ação registrada.", "success");
          descricaoInput.value = "";
          onDone();
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Erro ao registrar ação.");
          submitBtn.disabled = false;
        }
      },
    },
    [
      el("div", { class: "field-row" }, [
        el("div", { class: "field" }, [el("label", {}, ["Tipo de ação"]), tipoSelect]),
        el("div", { class: "field" }, [el("label", {}, ["Descrição"]), descricaoInput]),
      ]),
      errorBox,
      el("div", { class: "form-actions" }, [submitBtn]),
    ]
  );

  return el("div", { class: "card" }, [
    el("div", { class: "card-title" }, ["Plano de ação"]),
    el("p", { class: "desc", style: "margin-top:2px;" }, [
      "Registre e acompanhe ações de acompanhamento para este aluno (contato com responsável, reunião, encaminhamento etc.).",
    ]),
    tabela,
    form,
  ]);
}

function buildVincularForm(aluno, todasMaterias, onDone) {
  const linkedIds = new Set(aluno.materias.map((m) => m.id));
  // Soh materias ativas e ainda nao vinculadas podem ser oferecidas aqui.
  const disponiveis = todasMaterias.filter((m) => !linkedIds.has(m.id) && m.ativo !== 0);
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

function buildDesempenhoForm(aluno, onDone, inativo) {
  if (inativo) {
    return el("div", { class: "card" }, [
      el("div", { class: "card-title" }, ["Registrar novo desempenho"]),
      el("div", { class: "metric-foot", style: "margin-top:8px;" }, [
        "Aluno inativo. Reative o cadastro para registrar novos desempenhos.",
      ]),
    ]);
  }

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

function openAlunoModal(aluno, onSaved) {
  const nomeInput = el("input", { placeholder: "Nome completo", value: aluno.nome || "" });
  const matriculaInput = el("input", { placeholder: "Ex.: 2026010", value: aluno.matricula || "" });
  const emailInput = el("input", { type: "email", placeholder: "email@sigma.edu", value: aluno.email || "" });
  const statusSelect = el("select", {}, STATUS_VALUES.map((v) => el("option", { value: v }, [statusLabel(v)])));
  statusSelect.value = aluno.status;

  const errorBox = el("div", { class: "alert-banner", style: "display:none" }, [
    el("span", {}, ["⚠"]),
    el("span", { id: "aluno-form-error" }, [""]),
  ]);

  function setError(msg) {
    if (!msg) {
      errorBox.style.display = "none";
      return;
    }
    errorBox.style.display = "flex";
    errorBox.querySelector("#aluno-form-error").textContent = msg;
  }

  const submitBtn = el("button", { class: "btn btn-primary", type: "submit" }, ["Salvar"]);

  const form = el(
    "form",
    {
      onsubmit: async (event) => {
        event.preventDefault();
        setError(null);
        if (!nomeInput.value.trim() || !matriculaInput.value.trim()) {
          setError("Nome e matrícula são obrigatórios.");
          return;
        }
        submitBtn.disabled = true;
        submitBtn.textContent = "Salvando…";
        try {
          await api.atualizarAluno(aluno.id, {
            nome: nomeInput.value.trim(),
            matricula: matriculaInput.value.trim(),
            email: emailInput.value.trim() || null,
            status: statusSelect.value,
          });
          showToast("Aluno atualizado.", "success");
          close();
          onSaved();
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Erro ao salvar aluno.");
          submitBtn.disabled = false;
          submitBtn.textContent = "Salvar";
        }
      },
    },
    [
      el("div", { class: "field" }, [el("label", {}, ["Nome"]), nomeInput]),
      el("div", { class: "field" }, [el("label", {}, ["Matrícula"]), matriculaInput]),
      el("div", { class: "field" }, [el("label", {}, ["Email (opcional)"]), emailInput]),
      el("div", { class: "field" }, [el("label", {}, ["Status acadêmico"]), statusSelect]),
      errorBox,
      el("div", { class: "form-actions" }, [
        el("button", { class: "btn btn-secondary", type: "button", onclick: () => close() }, ["Cancelar"]),
        submitBtn,
      ]),
    ]
  );

  const content = el("div", {}, [el("h3", {}, ["Editar aluno"]), form]);
  const close = mountModal(content, () => close());
}
