import { el, fmtPercent, riskBadge, statusLabel, debounce, showToast, mountModal } from "../helpers.js";
import { renderLoading, renderError } from "../layout.js";
import { api, getStoredUser, ApiError } from "../api.js";
import { navigate } from "../router.js";

const PAGE_SIZE = 10;
const RISCOS = [
  { value: "", label: "Todos os riscos" },
  { value: "Baixo", label: "Risco baixo" },
  { value: "Medio", label: "Risco médio" },
  { value: "Alto", label: "Risco alto" },
];

// Estado dos filtros/paginação fica fora da funcao de render para que
// recarregar a pagina (apos importar, criar aluno etc.) preserve a posicao
// em que o usuario estava.
const state = { termo: "", risco: "", pagina: 1 };

export async function renderAlunos(container) {
  await carregar(container);
}

async function carregar(container) {
  renderLoading(container);
  try {
    const resultado = await api.alunos({ page: state.pagina, pageSize: PAGE_SIZE, termo: state.termo, risco: state.risco });
    paint(container, resultado);
  } catch (err) {
    renderError(container, err.message, () => carregar(container));
  }
}

function paint(container, resultado) {
  container.innerHTML = "";
  const usuario = getStoredUser();
  const isGestor = usuario?.perfil === "gestor";
  const { itens, total, pagina, tamanho_pagina } = resultado;
  const totalPaginas = Math.max(1, Math.ceil(total / tamanho_pagina));

  const tableWrap = el("div", { class: "card tight" }, [
    itens.length === 0
      ? el("div", { class: "empty-state" }, ["Nenhum aluno encontrado."])
      : el("table", {}, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { scope: "col" }, ["Aluno"]),
              el("th", { scope: "col" }, ["Matrícula"]),
              el("th", { scope: "col" }, ["Status"]),
              el("th", { scope: "col" }, ["Risco"]),
              el("th", { scope: "col" }, ["Fator de risco"]),
              el("th", { scope: "col" }, ["Matérias"]),
            ]),
          ]),
          el(
            "tbody",
            {},
            itens.map((aluno) =>
              el(
                "tr",
                {
                  class: `clickable${aluno.ativo === 0 ? " is-inactive" : ""}`,
                  tabIndex: 0,
                  role: "button",
                  "aria-label": `Ver detalhes de ${aluno.nome}`,
                  onclick: () => navigate(`/alunos/${aluno.id}`),
                  onkeydown: (event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      navigate(`/alunos/${aluno.id}`);
                    }
                  },
                },
                [
                  el("td", {}, [
                    el("strong", {}, [aluno.nome]),
                    aluno.ativo === 0
                      ? el("span", { class: "badge tone-danger", style: "margin-left:6px;" }, ["Inativo"])
                      : null,
                  ]),
                  el("td", { class: "muted" }, [aluno.matricula]),
                  el("td", {}, [statusLabel(aluno.status)]),
                  el("td", {}, [riskBadge(aluno.status_risco)]),
                  el("td", {}, [fmtPercent(aluno.fator_risco)]),
                  el("td", { class: "muted" }, [String(aluno.materias?.length ?? 0)]),
                ]
              )
            )
          ),
        ]),
  ]);

  const paginationWrap = el("div", { class: "pagination" });
  if (itens.length > 0) {
    paginationWrap.appendChild(el("span", {}, [`${total} aluno(s) · Página ${pagina} de ${totalPaginas}`]));
    paginationWrap.appendChild(
      el(
        "button",
        {
          class: "btn btn-secondary btn-sm",
          type: "button",
          disabled: pagina <= 1,
          onclick: () => {
            state.pagina -= 1;
            carregar(container);
          },
        },
        ["‹ Anterior"]
      )
    );
    paginationWrap.appendChild(
      el(
        "button",
        {
          class: "btn btn-secondary btn-sm",
          type: "button",
          disabled: pagina >= totalPaginas,
          onclick: () => {
            state.pagina += 1;
            carregar(container);
          },
        },
        ["Próxima ›"]
      )
    );
  }

  const searchInput = el("input", {
    class: "search-input",
    placeholder: "Buscar por nome ou matrícula…",
    "aria-label": "Buscar aluno por nome ou matrícula",
    value: state.termo,
    oninput: debounce((event) => {
      state.termo = event.target.value.trim();
      state.pagina = 1;
      carregar(container);
    }, 300),
  });

  const riscoSelect = el(
    "select",
    {
      class: "filter-select",
      "aria-label": "Filtrar por nível de risco",
      onchange: (event) => {
        state.risco = event.target.value;
        state.pagina = 1;
        carregar(container);
      },
    },
    RISCOS.map((r) => el("option", { value: r.value }, [r.label]))
  );
  riscoSelect.value = state.risco;

  const headerActions = [searchInput, riscoSelect];
  if (isGestor) {
    headerActions.push(
      el(
        "button",
        { class: "btn btn-secondary", type: "button", onclick: () => openImportCsvModal(() => carregar(container)) },
        ["Importar CSV"]
      )
    );
    headerActions.push(
      el(
        "button",
        { class: "btn btn-primary", onclick: () => openCreateAlunoModal(() => carregar(container)) },
        ["+ Novo aluno"]
      )
    );
  }

  container.appendChild(
    el("div", {}, [
      el("div", { class: "view-header" }, [
        el("div", {}, [
          el("h2", {}, ["Alunos"]),
          el("p", { class: "desc" }, [`${total} aluno(s) cadastrado(s).`]),
        ]),
      ]),
      el("div", { class: "toolbar" }, headerActions),
      tableWrap,
      paginationWrap,
    ])
  );
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

function openImportCsvModal(onImported) {
  const fileInput = el("input", { type: "file", accept: ".csv,text/csv" });
  const hint = el("p", { class: "hint" }, [
    "Cabeçalho esperado: nome,matricula,email. Linhas com matrícula duplicada ou campos vazios são reportadas como erro, sem interromper a importação.",
  ]);
  const errorBox = el("div", { class: "alert-banner", style: "display:none" }, [
    el("span", {}, ["⚠"]),
    el("span", { id: "import-csv-error" }, [""]),
  ]);

  function setError(msg) {
    if (!msg) {
      errorBox.style.display = "none";
      return;
    }
    errorBox.style.display = "flex";
    errorBox.querySelector("#import-csv-error").textContent = msg;
  }

  const submitBtn = el("button", { class: "btn btn-primary", type: "submit" }, ["Importar"]);

  const form = el(
    "form",
    {
      onsubmit: async (event) => {
        event.preventDefault();
        setError(null);
        const file = fileInput.files?.[0];
        if (!file) {
          setError("Selecione um arquivo CSV.");
          return;
        }
        submitBtn.disabled = true;
        submitBtn.textContent = "Importando…";
        try {
          const texto = await file.text();
          const resultado = await api.importarAlunosCsv(texto);
          close();
          showImportResultModal(resultado);
          onImported();
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Erro ao importar CSV.");
          submitBtn.disabled = false;
          submitBtn.textContent = "Importar";
        }
      },
    },
    [
      el("div", { class: "field" }, [el("label", {}, ["Arquivo CSV"]), fileInput]),
      hint,
      errorBox,
      el("div", { class: "form-actions" }, [
        el("button", { class: "btn btn-secondary", type: "button", onclick: () => close() }, ["Cancelar"]),
        submitBtn,
      ]),
    ]
  );

  const content = el("div", {}, [el("h3", {}, ["Importar alunos via CSV"]), form]);
  const close = mountModal(content, () => close());
}

function showImportResultModal(resultado) {
  const { importados, total_linhas, erros } = resultado;
  const content = el("div", {}, [
    el("h3", {}, ["Resultado da importação"]),
    el("div", { class: "alert-banner success" }, [
      el("span", {}, ["✓"]),
      `${importados} de ${total_linhas} linha(s) importada(s) com sucesso.`,
    ]),
    erros && erros.length > 0
      ? el("div", {}, [
          el("p", { class: "desc" }, [`${erros.length} erro(s):`]),
          el(
            "ul",
            { style: "margin:0 0 12px; padding-left:18px; font-size:12.5px; color:var(--text-muted); max-height:200px; overflow:auto;" },
            erros.map((e) => el("li", {}, [`Linha ${e.linha}: ${e.motivo}`]))
          ),
        ])
      : null,
    el("div", { class: "form-actions" }, [
      el("button", { class: "btn btn-primary", type: "button", onclick: () => close() }, ["Fechar"]),
    ]),
  ]);
  const close = mountModal(content, () => close());
}
