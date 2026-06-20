// "Minhas Turmas": area do professor para ver somente as materias atribuidas
// a ele e lancar o desempenho (notas, frequencia, atividades) de toda a
// turma em uma unica tela, em vez de abrir aluno por aluno. Os relatorios e
// analises de risco continuam sendo gerados automaticamente a partir desses
// dados (MotorIA), sem nenhuma mudanca nessa parte.

import { el, fmtPercent, showToast } from "../helpers.js";
import { renderLoading, renderError } from "../layout.js";
import { api, getStoredUser, ApiError } from "../api.js";
import { navigate } from "../router.js";

export async function renderMinhasTurmas(container) {
  renderLoading(container);
  try {
    const materias = await api.materias();
    paintLista(container, materias);
  } catch (err) {
    renderError(container, err.message, () => renderMinhasTurmas(container));
  }
}

function paintLista(container, materias) {
  container.innerHTML = "";
  const usuario = getStoredUser();
  const minhas = materias.filter((m) => usuario && String(m.professor_id) === String(usuario.id));

  const content =
    minhas.length === 0
      ? el("div", { class: "card" }, [
          el("div", { class: "empty-state" }, [
            "Nenhuma turma atribuída a você ainda. Peça ao gestor para cadastrar a matéria e te atribuir como professor.",
          ]),
        ])
      : el("div", { class: "grid cols-3" }, minhas.map(buildTurmaCard));

  container.appendChild(
    el("div", {}, [
      el("div", { class: "view-header" }, [
        el("div", {}, [
          el("h2", {}, ["Minhas Turmas"]),
          el("p", { class: "desc" }, [`${minhas.length} turma(s) atribuída(s) a você.`]),
        ]),
      ]),
      content,
    ])
  );
}

function buildTurmaCard(materia) {
  return el("div", { class: "card" }, [
    el("div", { class: "card-title" }, [materia.nome]),
    el("div", { class: "metric-foot" }, [`${materia.carga_horaria}h · ${materia.semestre}`]),
    !materia.ativo ? el("span", { class: "badge tone-danger", style: "margin-top:8px;" }, ["Inativa"]) : null,
    el(
      "button",
      {
        class: "btn btn-primary btn-sm",
        style: "margin-top:14px;",
        type: "button",
        onclick: () => navigate(`/minhas-turmas/${materia.id}`),
      },
      ["Lançar notas"]
    ),
  ]);
}

export async function renderLancarNotas(container, params) {
  renderLoading(container);
  const materiaId = params.id;
  try {
    const [materias, alunosResp] = await Promise.all([
      api.materias(),
      api.alunos({ materiaId, pageSize: 100 }),
    ]);
    const materia = materias.find((m) => String(m.id) === String(materiaId));
    if (!materia) {
      renderError(container, "Turma não encontrada.", () => navigate("/minhas-turmas"));
      return;
    }
    paintLancarNotas(container, materia, alunosResp.itens);
  } catch (err) {
    renderError(container, err.message, () => renderLancarNotas(container, params));
  }
}

function paintLancarNotas(container, materia, alunos) {
  container.innerHTML = "";
  const inativa = !materia.ativo;

  const tableCard = el("div", { class: "card tight" }, [
    alunos.length === 0
      ? el("div", { class: "empty-state" }, ["Nenhum aluno vinculado a esta turma ainda."])
      : el("table", {}, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { scope: "col" }, ["Aluno"]),
              el("th", { scope: "col" }, ["Notas"]),
              el("th", { scope: "col" }, ["Frequência (%)"]),
              el("th", { scope: "col" }, ["Atividades"]),
              el("th", { scope: "col" }, [""]),
            ]),
          ]),
          el("tbody", {}, alunos.map((aluno) => buildLinhaAluno(aluno, materia, inativa))),
        ]),
  ]);

  container.appendChild(
    el("div", {}, [
      el("div", { class: "breadcrumb", onclick: () => navigate("/minhas-turmas") }, ["← Voltar para Minhas Turmas"]),
      el("div", { class: "view-header" }, [
        el("div", {}, [
          el("h2", { class: "mt-0" }, [materia.nome]),
          el("p", { class: "desc" }, [`${materia.carga_horaria}h · ${materia.semestre} · ${alunos.length} aluno(s)`]),
        ]),
      ]),
      inativa
        ? el("div", { class: "alert-banner", style: "margin-bottom:14px;" }, [
            el("span", {}, ["⚠"]),
            el("span", {}, [
              "Esta matéria está inativa. Peça ao gestor para reativá-la antes de lançar novos desempenhos.",
            ]),
          ])
        : null,
      el("p", { class: "desc" }, [
        "Lance as notas, a frequência e as atividades de cada aluno. Ao salvar, o sistema recalcula o risco e gera alertas e relatórios automaticamente.",
      ]),
      tableCard,
    ])
  );
}

function buildLinhaAluno(aluno, materia, inativa) {
  const notasInput = el("input", { placeholder: "Ex.: 8.0, 7.5", style: "width:120px;" });
  const frequenciaInput = el("input", {
    type: "number",
    min: "0",
    max: "100",
    step: "0.1",
    placeholder: "Ex.: 92",
    style: "width:90px;",
  });
  const entreguesInput = el("input", { type: "number", min: "0", step: "1", placeholder: "Entr.", style: "width:64px;" });
  const esperadasInput = el("input", { type: "number", min: "1", step: "1", placeholder: "Esp.", style: "width:64px;" });
  const feedback = el("div", { style: "font-size:12px; margin-top:4px;" });

  const submitBtn = el(
    "button",
    {
      class: "btn btn-primary btn-sm",
      type: "button",
      disabled: inativa,
      onclick: async () => {
        feedback.textContent = "";
        feedback.style.color = "";

        const notas = notasInput.value
          .split(/[,;]/)
          .map((n) => n.trim())
          .filter(Boolean)
          .map(Number);

        if (notas.length === 0 || notas.some((n) => Number.isNaN(n))) {
          feedback.textContent = "Informe ao menos uma nota válida.";
          feedback.style.color = "var(--danger)";
          return;
        }
        if (frequenciaInput.value === "") {
          feedback.textContent = "Informe a frequência.";
          feedback.style.color = "var(--danger)";
          return;
        }

        const payload = {
          materia_id: materia.id,
          notas,
          frequencia: Number(frequenciaInput.value),
          atividades_entregues: entreguesInput.value === "" ? undefined : Number(entreguesInput.value),
          atividades_esperadas: esperadasInput.value === "" ? undefined : Number(esperadasInput.value),
        };

        submitBtn.disabled = true;
        submitBtn.textContent = "Salvando…";
        try {
          const result = await api.registrarDesempenho(aluno.id, payload);
          showToast(`Desempenho de ${aluno.nome} registrado.`, "success");
          feedback.textContent = `${result.analise.nivel} (fator ${fmtPercent(result.analise.fator_risco)})`;
          notasInput.value = "";
          entreguesInput.value = "";
          esperadasInput.value = "";
        } catch (err) {
          feedback.textContent = err instanceof ApiError ? err.message : "Erro ao registrar desempenho.";
          feedback.style.color = "var(--danger)";
        } finally {
          submitBtn.disabled = inativa;
          submitBtn.textContent = "Salvar";
        }
      },
    },
    ["Salvar"]
  );

  return el("tr", {}, [
    el("td", {}, [
      el("strong", {}, [aluno.nome]),
      el("div", { class: "muted", style: "font-size:12px;" }, [aluno.matricula]),
    ]),
    el("td", {}, [notasInput]),
    el("td", {}, [frequenciaInput]),
    el("td", {}, [el("div", { style: "display:flex; gap:4px;" }, [entreguesInput, esperadasInput])]),
    el("td", {}, [submitBtn, feedback]),
  ]);
}
