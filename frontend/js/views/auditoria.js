import { el, fmtDataHora } from "../helpers.js";
import { renderLoading, renderError } from "../layout.js";
import { api } from "../api.js";

const PAGE_SIZE = 20;

const ACAO_LABEL = {
  criar: "Criação",
  atualizar: "Atualização",
  desativar: "Desativação",
  reativar: "Reativação",
  vincular_materia: "Vínculo de matéria",
  registrar_desempenho: "Registro de desempenho",
};

function acaoLabel(acao) {
  return ACAO_LABEL[acao] || acao || "—";
}

export async function renderAuditoria(container, params, page = 1) {
  renderLoading(container);
  try {
    const resultado = await api.auditoria({ page, pageSize: PAGE_SIZE });
    paint(container, resultado);
  } catch (err) {
    renderError(container, err.message, () => renderAuditoria(container, params, page));
  }
}

function paint(container, resultado) {
  container.innerHTML = "";
  const { itens, total, pagina, tamanho_pagina } = resultado;
  const totalPaginas = Math.max(1, Math.ceil(total / tamanho_pagina));

  const tableCard = el("div", { class: "card tight" }, [
    itens.length === 0
      ? el("div", { class: "empty-state" }, ["Nenhum registro de auditoria ainda."])
      : el("div", { style: "overflow-x:auto;" }, [
          el("table", {}, [
            el("thead", {}, [
              el("tr", {}, [
                el("th", { scope: "col" }, ["Quando"]),
                el("th", { scope: "col" }, ["Usuário"]),
                el("th", { scope: "col" }, ["Ação"]),
                el("th", { scope: "col" }, ["Entidade"]),
                el("th", { scope: "col" }, ["Detalhes"]),
              ]),
            ]),
            el(
              "tbody",
              {},
              itens.map((item) =>
                el("tr", {}, [
                  el("td", { class: "muted" }, [fmtDataHora(item.criado_em)]),
                  el("td", {}, [item.usuario_nome || "Sistema"]),
                  el("td", {}, [el("span", { class: "badge tone-neutral" }, [acaoLabel(item.acao)])]),
                  el("td", { class: "muted" }, [`${item.entidade} #${item.entidade_id}`]),
                  el("td", { class: "muted" }, [item.detalhes || "—"]),
                ])
              )
            ),
          ]),
        ]),
    itens.length > 0
      ? el("div", { class: "pagination" }, [
          el("span", {}, [`Página ${pagina} de ${totalPaginas} · ${total} registro(s)`]),
          el(
            "button",
            {
              class: "btn btn-secondary btn-sm",
              type: "button",
              disabled: pagina <= 1,
              onclick: () => renderAuditoria(container, null, pagina - 1),
            },
            ["Anterior"]
          ),
          el(
            "button",
            {
              class: "btn btn-secondary btn-sm",
              type: "button",
              disabled: pagina >= totalPaginas,
              onclick: () => renderAuditoria(container, null, pagina + 1),
            },
            ["Próxima"]
          ),
        ])
      : null,
  ]);

  container.appendChild(
    el("div", {}, [
      el("div", { class: "view-header" }, [
        el("div", {}, [
          el("h2", {}, ["Auditoria"]),
          el("p", { class: "desc" }, ["Histórico de ações realizadas no sistema."]),
        ]),
      ]),
      tableCard,
    ])
  );
}
