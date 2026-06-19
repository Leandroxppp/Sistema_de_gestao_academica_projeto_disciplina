import { el, showToast, mountModal } from "../helpers.js";
import { renderLoading, renderError } from "../layout.js";
import { api, getStoredUser, ApiError } from "../api.js";

export async function renderMaterias(container) {
  renderLoading(container);
  try {
    const [materias, usuarios] = await Promise.all([api.materias(), api.usuarios()]);
    paint(container, materias, usuarios);
  } catch (err) {
    renderError(container, err.message, () => renderMaterias(container));
  }
}

function paint(container, materias, usuarios) {
  container.innerHTML = "";
  const usuario = getStoredUser();
  const isGestor = usuario?.perfil === "gestor";
  const professores = usuarios.filter((u) => u.perfil === "professor");

  const headerActions = [];
  if (isGestor) {
    headerActions.push(
      el(
        "button",
        { class: "btn btn-primary", onclick: () => openCreateMateriaModal(professores, () => renderMaterias(container)) },
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
              el("th", {}, ["Matéria"]),
              el("th", {}, ["Carga horária"]),
              el("th", {}, ["Semestre"]),
              el("th", {}, ["Professor"]),
            ]),
          ]),
          el(
            "tbody",
            {},
            materias.map((m) =>
              el("tr", {}, [
                el("td", {}, [el("strong", {}, [m.nome])]),
                el("td", { class: "muted" }, [`${m.carga_horaria}h`]),
                el("td", { class: "muted" }, [m.semestre]),
                el("td", {}, [m.professor_nome || "—"]),
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
    ])
  );
}

function openCreateMateriaModal(professores, onCreated) {
  const nomeInput = el("input", { placeholder: "Ex.: Estrutura de Dados" });
  const cargaInput = el("input", { type: "number", min: "1", placeholder: "Ex.: 80" });
  const semestreInput = el("input", { placeholder: "Ex.: 2026.2" });
  const professorSelect = el(
    "select",
    {},
    [
      el("option", { value: "" }, ["Sem professor definido"]),
      ...professores.map((p) => el("option", { value: p.id }, [p.nome])),
    ]
  );
  const errorBox = el("div", { class: "alert-banner", style: "display:none" }, [
    el("span", {}, ["⚠"]),
    el("span", { id: "create-materia-error" }, [""]),
  ]);

  function setError(msg) {
    if (!msg) {
      errorBox.style.display = "none";
      return;
    }
    errorBox.style.display = "flex";
    errorBox.querySelector("#create-materia-error").textContent = msg;
  }

  const submitBtn = el("button", { class: "btn btn-primary", type: "submit" }, ["Cadastrar"]);

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
        submitBtn.textContent = "Cadastrando…";
        try {
          await api.criarMateria({
            nome: nomeInput.value.trim(),
            carga_horaria: Number(cargaInput.value),
            semestre: semestreInput.value.trim(),
            professor_id: professorSelect.value || undefined,
          });
          showToast("Matéria cadastrada com sucesso.", "success");
          close();
          onCreated();
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Erro ao cadastrar matéria.");
          submitBtn.disabled = false;
          submitBtn.textContent = "Cadastrar";
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

  const content = el("div", {}, [el("h3", {}, ["Nova matéria"]), form]);
  const close = mountModal(content, () => close());
}
