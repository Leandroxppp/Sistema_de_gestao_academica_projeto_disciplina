import { el, fmtDataHora, showToast, mountModal } from "../helpers.js";
import { renderLoading, renderError } from "../layout.js";
import { api, ApiError } from "../api.js";

const TIPOS = [
  { value: "desempenho", label: "Desempenho" },
  { value: "risco", label: "Risco e evasão" },
  { value: "turma", label: "Turma / matéria" },
];

export async function renderRelatorios(container) {
  renderLoading(container);
  try {
    const relatorios = await api.relatorios();
    paint(container, relatorios);
  } catch (err) {
    renderError(container, err.message, () => renderRelatorios(container));
  }
}

function paint(container, relatorios) {
  container.innerHTML = "";

  const tableCard = el("div", { class: "card tight" }, [
    relatorios.length === 0
      ? el("div", { class: "empty-state" }, ["Nenhum relatório gerado ainda."])
      : el("table", {}, [
          el("thead", {}, [
            el("tr", {}, [
              el("th", { scope: "col" }, ["Título"]),
              el("th", { scope: "col" }, ["Tipo"]),
              el("th", { scope: "col" }, ["Criado por"]),
              el("th", { scope: "col" }, ["Criado em"]),
              el("th", { scope: "col" }, [""]),
            ]),
          ]),
          el(
            "tbody",
            {},
            relatorios.map((r) =>
              el("tr", {}, [
                el("td", {}, [el("strong", {}, [r.titulo])]),
                el("td", {}, [el("span", { class: "badge tone-neutral" }, [r.tipo])]),
                el("td", { class: "muted" }, [r.criado_por_nome || "—"]),
                el("td", { class: "muted" }, [fmtDataHora(r.criado_em)]),
                el("td", {}, [
                  el("div", { class: "row-actions" }, [
                    el("button", { class: "btn btn-ghost btn-sm", onclick: () => openViewModal(r) }, ["Ver conteúdo"]),
                    el("button", { class: "btn btn-secondary btn-sm", onclick: () => baixarRelatorio(r) }, ["Baixar"]),
                  ]),
                ]),
              ])
            )
          ),
        ]),
  ]);

  container.appendChild(
    el("div", {}, [
      el("div", { class: "view-header" }, [
        el("div", {}, [
          el("h2", {}, ["Relatórios"]),
          el("p", { class: "desc" }, [`${relatorios.length} relatório(s) gerado(s).`]),
        ]),
        el(
          "button",
          { class: "btn btn-primary", onclick: () => openCreateModal(() => renderRelatorios(container)) },
          ["+ Novo relatório"]
        ),
      ]),
      tableCard,
    ])
  );
}

function baixarRelatorio(relatorio) {
  let conteudo = relatorio.conteudo;
  let extensao = "txt";
  let mime = "text/plain";
  try {
    conteudo = JSON.stringify(JSON.parse(relatorio.conteudo), null, 2);
    extensao = "json";
    mime = "application/json";
  } catch {
    // conteudo nao e JSON, mantem como texto puro
  }

  const nomeArquivo = `${slugify(relatorio.titulo) || "relatorio"}-${relatorio.id}.${extensao}`;
  const blob = new Blob([conteudo], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nomeArquivo;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function slugify(texto) {
  return (texto || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(new RegExp("[\\u0300-\\u036f]", "g"), "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function openViewModal(relatorio) {
  let conteudo = relatorio.conteudo;
  try {
    conteudo = JSON.stringify(JSON.parse(relatorio.conteudo), null, 2);
  } catch {
    // conteudo nao e JSON, mantem como texto puro
  }
  const content = el("div", {}, [
    el("h3", {}, [relatorio.titulo]),
    el("div", { style: "background:var(--surface-2); padding:14px 16px; border-radius:8px; font-family:inherit; font-size:14px; line-height:1.6; max-height:50vh; overflow:auto; white-space:pre-wrap;" }, [
      conteudo,
    ]),
    el("div", { class: "form-actions" }, [
      el("button", { class: "btn btn-secondary", onclick: () => close() }, ["Fechar"]),
    ]),
  ]);
  const close = mountModal(content, () => close());
}

function openCreateModal(onCreated) {
  const tituloInput = el("input", { placeholder: "Ex.: Relatório semestral de risco" });
  const tipoSelect = el("select", {}, TIPOS.map((t) => el("option", { value: t.value }, [t.label])));
  const conteudoInput = el("textarea", { placeholder: "Deixe em branco para gerar automaticamente a partir do dashboard atual." });
  const errorBox = el("div", { class: "alert-banner", style: "display:none" }, [
    el("span", {}, ["⚠"]),
    el("span", { id: "create-relatorio-error" }, [""]),
  ]);

  function setError(msg) {
    if (!msg) {
      errorBox.style.display = "none";
      return;
    }
    errorBox.style.display = "flex";
    errorBox.querySelector("#create-relatorio-error").textContent = msg;
  }

  const submitBtn = el("button", { class: "btn btn-primary", type: "submit" }, ["Gerar relatório"]);

  const form = el(
    "form",
    {
      onsubmit: async (event) => {
        event.preventDefault();
        setError(null);
        submitBtn.disabled = true;
        submitBtn.textContent = "Gerando…";
        try {
          await api.criarRelatorio({
            titulo: tituloInput.value.trim() || undefined,
            tipo: tipoSelect.value,
            conteudo: conteudoInput.value.trim() || undefined,
          });
          showToast("Relatório gerado com sucesso.", "success");
          close();
          onCreated();
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Erro ao gerar relatório.");
          submitBtn.disabled = false;
          submitBtn.textContent = "Gerar relatório";
        }
      },
    },
    [
      el("div", { class: "field" }, [el("label", {}, ["Título (opcional)"]), tituloInput]),
      el("div", { class: "field" }, [el("label", {}, ["Tipo"]), tipoSelect]),
      el("div", { class: "field" }, [el("label", {}, ["Conteúdo (opcional)"]), conteudoInput]),
      errorBox,
      el("div", { class: "form-actions" }, [
        el("button", { class: "btn btn-secondary", type: "button", onclick: () => close() }, ["Cancelar"]),
        submitBtn,
      ]),
    ]
  );

  const content = el("div", {}, [el("h3", {}, ["Novo relatório"]), form]);
  const close = mountModal(content, () => close());
}
