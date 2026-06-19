import { el, fmtPercent, riskBadge, statusLabel, debounce, showToast, mountModal } from "../helpers.js";
import { renderLoading, renderError } from "../layout.js";
import { api, getStoredUser, ApiError } from "../api.js";
import { navigate } from "../router.js";

export async function renderAlunos(container) {
  renderLoading(container);
  try {
    const alunos = await api.alunos();
    paint(container, alunos);
  } catch (err) {
    renderError(container, err.message, () => renderAlunos(container));
  }
}

function paint(container, alunos) {
  container.innerHTML = "";
  const usuario = getStoredUser();
  const isGestor = usuario?.perfil === "gestor";

  let filtered = alunos;

  const tableWrap = el("div", { class: "card tight" });

  function renderTable(list) {
    tableWrap.innerHTML = "";
    if (list.length === 0) {
      tableWrap.appendChild(el("div", { class: "empty-state" }, ["Nenhum aluno encontrado."]));
      return;
    }
    tableWrap.appendChild(
      el("table", {}, [
        el("thead", {}, [
          el("tr", {}, [
            el("th", {}, ["Aluno"]),
            el("th", {}, ["Matrícula"]),
            el("th", {}, ["Status"]),
            el("th", {}, ["Risco"]),
            el("th", {}, ["Fator de risco"]),
            el("th", {}, ["Matérias"]),
          ]),
        ]),
        el(
          "tbody",
          {},
          list.map((aluno) =>
            el(
              "tr",
              { class: "clickable", onclick: () => navigate(`/alunos/${aluno.id}`) },
              [
                el("td", {}, [el("strong", {}, [aluno.nome])]),
                el("td", { class: "muted" }, [aluno.matricula]),
                el("td", {}, [statusLabel(aluno.status)]),
                el("td", {}, [riskBadge(aluno.status_risco)]),
                el("td", {}, [fmtPercent(aluno.fator_risco)]),
                el("td", { class: "muted" }, [String(aluno.materias?.length ?? 0)]),
              ]
            )
          )
        ),
      ])
    );
  }

  const searchInput = el("input", {
    class: "search-input",
    placeholder: "Buscar por nome ou matrícula…",
    oninput: debounce((event) => {
      const term = event.target.value.trim().toLowerCase();
      filtered = !term
        ? alunos
        : alunos.filter(
            (aluno) =>
              aluno.nome.toLowerCase().includes(term) || aluno.matricula.toLowerCase().includes(term)
          );
      renderTable(filtered);
    }, 200),
  });

  const headerActions = [searchInput];
  if (isGestor) {
    headerActions.push(
      el(
        "button",
        { class: "btn btn-primary", onclick: () => openCreateAlunoModal(() => renderAlunos(container)) },
        ["+ Novo aluno"]
      )
    );
  }

  container.appendChild(
    el("div", {}, [
      el("div", { class: "view-header" }, [
        el("div", {}, [
          el("h2", {}, ["Alunos"]),
          el("p", { class: "desc" }, [`${alunos.length} aluno(s) cadastrado(s).`]),
        ]),
      ]),
      el("div", { class: "toolbar" }, headerActions),
      tableWrap,
    ])
  );

  renderTable(filtered);
}

function openCreateAlunoModal(onCreated) {
  const nomeInput = el("input", { placeholder: "Nome completo" });
  const matriculaInput = el("input", { placeholder: "Ex.: 2026010" });
  const emailInput = el("input", { type: "email", placeholder: "email@sigma.edu" });
  const errorBox = el("div", { class: "alert-banner", style: "display:none" }, [
    el("span", {}, ["⚠"]),
    el("span", { id: "create-aluno-error" }, [""]),
  ]);

  function setError(msg) {
    if (!msg) {
      errorBox.style.display = "none";
      return;
    }
    errorBox.style.display = "flex";
    errorBox.querySelector("#create-aluno-error").textContent = msg;
  }

  const submitBtn = el("button", { class: "btn btn-primary", type: "submit" }, ["Cadastrar"]);

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
        submitBtn.textContent = "Cadastrando…";
        try {
          await api.criarAluno({
            nome: nomeInput.value.trim(),
            matricula: matriculaInput.value.trim(),
            email: emailInput.value.trim() || undefined,
          });
          showToast("Aluno cadastrado com sucesso.", "success");
          close();
          onCreated();
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Erro ao cadastrar aluno.");
          submitBtn.disabled = false;
          submitBtn.textContent = "Cadastrar";
        }
      },
    },
    [
      el("div", { class: "field" }, [el("label", {}, ["Nome"]), nomeInput]),
      el("div", { class: "field" }, [el("label", {}, ["Matrícula"]), matriculaInput]),
      el("div", { class: "field" }, [el("label", {}, ["Email (opcional)"]), emailInput]),
      errorBox,
      el("div", { class: "form-actions" }, [
        el("button", { class: "btn btn-secondary", type: "button", onclick: () => close() }, ["Cancelar"]),
        submitBtn,
      ]),
    ]
  );

  const content = el("div", {}, [el("h3", {}, ["Novo aluno"]), form]);
  const close = mountModal(content, () => close());
}
