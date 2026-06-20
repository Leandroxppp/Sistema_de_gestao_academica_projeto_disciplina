import { el, showToast, mountModal, confirmModal, fmtNota, fmtFrequencia, riskBadge } from "../helpers.js";
import { renderLoading, renderError } from "../layout.js";
import { api, getStoredUser, ApiError } from "../api.js";

export async function renderMaterias(container) {
  renderLoading(container);
  try {
    const usuario = getStoredUser();
    const isGestor = usuario?.perfil === "gestor";
    const [materias, usuarios, comparativo] = await Promise.all([
      api.materias(),
      api.usuarios(),
      isGestor ? api.comparativoMaterias() : Promise.resolve(null),
    ]);
    paint(container, materias, usuarios, comparativo);
  } catch (err) {
    renderError(container, err.message, () => renderMaterias(container));
  }
}

function paint(container, materias, usuarios, comparativo) {
  container.innerHTML = "";
  const usuario = getStoredUser();
  const isGestor = usuario?.perfil === "gestor";
  // Apenas professores ativos podem ser escolhidos para novas materias/edicoes.
  const professoresAtivos = usuarios.filter((u) => u.perfil === "professor" && u.ativo !== false);
  const refresh = () => renderMaterias(container);

  const headerActions = [];
  if (isGestor) {
    headerActions.push(
      el(
        "button",
        { class: "btn btn-primary", onclick: () => openMateriaModal(null, professoresAtivos, refresh) },
        ["+ Nova matéria"]
      )
    );
  }

  const tableCard = el("div", { class: "card tight" }, [
    materias.length === 0
      ? el("div", { class: "empty-state" }, ["Nenhuma matéria cadastrada."])
      : el("table", {}, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { scope: "col" }, ["Matéria"]),
              el("th", { scope: "col" }, ["Carga horária"]),
              el("th", { scope: "col" }, ["Semestre"]),
              el("th", { scope: "col" }, ["Professor"]),
              el("th", { scope: "col" }, ["Status"]),
              isGestor ? el("th", { scope: "col" }, [""]) : null,
            ]),
          ]),
          el(
            "tbody",
            {},
            materias.map((m) =>
              el("tr", { class: !m.ativo ? "is-inactive" : "" }, [
                el("td", {}, [el("strong", {}, [m.nome])]),
                el("td", { class: "muted" }, [`${m.carga_horaria}h`]),
                el("td", { class: "muted" }, [m.semestre]),
                el("td", {}, [m.professor_nome || "—"]),
                el("td", {}, [
                  !m.ativo
                    ? el("span", { class: "badge tone-danger" }, ["Inativa"])
                    : el("span", { class: "badge tone-success" }, ["Ativa"]),
                ]),
                isGestor ? el("td", {}, [buildRowActions(m, professoresAtivos, refresh)]) : null,
              ])
            )
          ),
        ]),
  ]);

  container.appendChild(
    el("div", {}, [
      el("div", { class: "view-header" }, [
        el("div", {}, [
          el("h2", {}, ["Matérias"]),
          el("p", { class: "desc" }, [`${materias.length} matéria(s) cadastrada(s).`]),
        ]),
      ]),
      el("div", { class: "toolbar" }, headerActions),
      tableCard,
      buildComparativoSection(comparativo),
    ])
  );
}

function buildComparativoSection(comparativo) {
  if (!comparativo) return null;

  if (comparativo.length === 0) {
    return el("div", { style: "margin-top:24px;" }, [
      el("div", { class: "section-title" }, ["Comparativo entre turmas da mesma matéria"]),
      el("div", { class: "card" }, [
        el("div", { class: "empty-state" }, [
          "Nenhuma matéria tem turmas com professores diferentes para comparar ainda.",
        ]),
      ]),
    ]);
  }

  return el("div", { style: "margin-top:24px;" }, [
    el("div", { class: "section-title" }, ["Comparativo entre turmas da mesma matéria"]),
    el("p", { class: "desc" }, [
      "Quando a mesma matéria é ministrada por professores diferentes, comparamos os indicadores de risco de cada turma para destacar onde os alunos estão indo melhor ou pior.",
    ]),
    ...comparativo.map(buildComparativoGroupCard),
  ]);
}

function buildComparativoGroupCard(grupo) {
  return el("div", { class: "card tight", style: "margin-top:12px;" }, [
    el("div", { style: "padding:16px 18px 0;" }, [el("div", { class: "card-title" }, [grupo.materia_nome])]),
    el("table", {}, [
      el("thead", {}, [
        el("tr", {}, [
          el("th", { scope: "col" }, ["Professor"]),
          el("th", { scope: "col" }, ["Semestre"]),
          el("th", { scope: "col" }, ["Alunos"]),
          el("th", { scope: "col" }, ["Média"]),
          el("th", { scope: "col" }, ["Frequência"]),
          el("th", { scope: "col" }, ["Risco"]),
          el("th", { scope: "col" }, [""]),
        ]),
      ]),
      el(
        "tbody",
        {},
        grupo.turmas.map((turma) => {
          let indicador = null;
          if (turma.materia_id === grupo.destaque_materia_id) {
            indicador = el("span", { class: "badge tone-success" }, ["🌟 Destaque"]);
          } else if (turma.materia_id === grupo.atencao_materia_id) {
            indicador = el("span", { class: "badge tone-danger" }, ["⚠ Atenção"]);
          }
          return el("tr", {}, [
            el("td", {}, [turma.professor_nome || "—"]),
            el("td", { class: "muted" }, [turma.semestre]),
            el("td", { class: "muted" }, [String(turma.total_alunos)]),
            el("td", {}, [turma.media_geral != null ? fmtNota(turma.media_geral) : "—"]),
            el("td", {}, [turma.frequencia_media != null ? fmtFrequencia(turma.frequencia_media) : "—"]),
            el("td", {}, [
              turma.nivel_risco ? riskBadge(turma.nivel_risco) : el("span", { class: "metric-foot" }, ["Sem dados"]),
            ]),
            el("td", {}, [indicador]),
          ]);
        })
      ),
    ]),
  ]);
}

function buildRowActions(materia, professoresAtivos, onChanged) {
  const editBtn = el(
    "button",
    { class: "btn btn-ghost btn-sm", type: "button", onclick: () => openMateriaModal(materia, professoresAtivos, onChanged) },
    ["Editar"]
  );
  const toggleBtn = el(
    "button",
    {
      class: `btn btn-sm ${!materia.ativo ? "btn-secondary" : "btn-danger"}`,
      type: "button",
      onclick: async () => {
        const ativando = !materia.ativo;
        const confirmado = await confirmModal(
          ativando
            ? `Reativar a matéria "${materia.nome}"?`
            : `Desativar a matéria "${materia.nome}"? Não será possível vincular novos alunos ou registrar desempenho enquanto estiver inativa.`,
          {
            title: ativando ? "Reativar matéria" : "Desativar matéria",
            confirmLabel: ativando ? "Reativar" : "Desativar",
            danger: !ativando,
          }
        );
        if (!confirmado) return;
        try {
          if (ativando) {
            await api.atualizarMateria(materia.id, { ativo: true });
            showToast("Matéria reativada.", "success");
          } else {
            await api.desativarMateria(materia.id);
            showToast("Matéria desativada.", "success", {
              onUndo: async () => {
                try {
                  await api.atualizarMateria(materia.id, { ativo: true });
                  showToast("Matéria reativada.", "success");
                  onChanged();
                } catch (err) {
                  showToast(err instanceof ApiError ? err.message : "Erro ao desfazer.", "error");
                }
              },
            });
          }
          onChanged();
        } catch (err) {
          showToast(err instanceof ApiError ? err.message : "Erro ao atualizar matéria.", "error");
        }
      },
    },
    [!materia.ativo ? "Reativar" : "Desativar"]
  );
  return el("div", { class: "row-actions" }, [editBtn, toggleBtn]);
}

function openMateriaModal(materia, professoresAtivos, onSaved) {
  const isEdit = Boolean(materia);
  const nomeInput = el("input", { placeholder: "Ex.: Estrutura de Dados", value: materia?.nome || "" });
  const cargaInput = el("input", {
    type: "number",
    min: "1",
    placeholder: "Ex.: 80",
    value: materia?.carga_horaria ?? "",
  });
  const semestreInput = el("input", { placeholder: "Ex.: 2026.2", value: materia?.semestre || "" });
  const professorSelect = el("select", {}, [
    el("option", { value: "" }, ["Sem professor definido"]),
    ...professoresAtivos.map((p) => el("option", { value: p.id }, [p.nome])),
  ]);
  professorSelect.value = materia?.professor_id ? String(materia.professor_id) : "";

  const errorBox = el("div", { class: "alert-banner", style: "display:none" }, [
    el("span", {}, ["⚠"]),
    el("span", { id: "materia-form-error" }, [""]),
  ]);

  function setError(msg) {
    if (!msg) {
      errorBox.style.display = "none";
      return;
    }
    errorBox.style.display = "flex";
    errorBox.querySelector("#materia-form-error").textContent = msg;
  }

  const submitBtn = el("button", { class: "btn btn-primary", type: "submit" }, [isEdit ? "Salvar" : "Cadastrar"]);

  const form = el(
    "form",
    {
      onsubmit: async (event) => {
        event.preventDefault();
        setError(null);
        if (!nomeInput.value.trim() || !cargaInput.value || !semestreInput.value.trim()) {
          setError("Nome, carga horária e semestre são obrigatórios.");
          return;
        }
        submitBtn.disabled = true;
        submitBtn.textContent = isEdit ? "Salvando…" : "Cadastrando…";
        try {
          const payload = {
            nome: nomeInput.value.trim(),
            carga_horaria: Number(cargaInput.value),
            semestre: semestreInput.value.trim(),
            professor_id: professorSelect.value || null,
          };
          if (isEdit) {
            await api.atualizarMateria(materia.id, payload);
            showToast("Matéria atualizada.", "success");
          } else {
            await api.criarMateria(payload);
            showToast("Matéria cadastrada com sucesso.", "success");
          }
          close();
          onSaved();
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Erro ao salvar matéria.");
          submitBtn.disabled = false;
          submitBtn.textContent = isEdit ? "Salvar" : "Cadastrar";
        }
      },
    },
    [
      el("div", { class: "field" }, [el("label", {}, ["Nome"]), nomeInput]),
      el("div", { class: "field-row" }, [
        el("div", { class: "field" }, [el("label", {}, ["Carga horária"]), cargaInput]),
        el("div", { class: "field" }, [el("label", {}, ["Semestre"]), semestreInput]),
      ]),
      el("div", { class: "field" }, [el("label", {}, ["Professor"]), professorSelect]),
      errorBox,
      el("div", { class: "form-actions" }, [
        el("button", { class: "btn btn-secondary", type: "button", onclick: () => close() }, ["Cancelar"]),
        submitBtn,
      ]),
    ]
  );

  const content = el("div", {}, [el("h3", {}, [isEdit ? "Editar matéria" : "Nova matéria"]), form]);
  const close = mountModal(content, () => close());
}
