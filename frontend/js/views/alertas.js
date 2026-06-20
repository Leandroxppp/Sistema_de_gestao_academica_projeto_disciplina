import { el, riskBadge, fmtDataHora } from "../helpers.js";
import { renderLoading, renderError } from "../layout.js";
import { api } from "../api.js";
import { navigate } from "../router.js";

export async function renderAlertas(container) {
  renderLoading(container);
  try {
    const alertas = await api.alertas();
    paint(container, alertas);
  } catch (err) {
    renderError(container, err.message, () => renderAlertas(container));
  }
}

function paint(container, alertas) {
  container.innerHTML = "";
  const ativos = alertas.filter((a) => a.ativo);
  const resolvidos = alertas.filter((a) => !a.ativo);

  function table(list) {
    if (list.length === 0) {
      return el("div", { class: "empty-state" }, ["Nenhum alerta nesta categoria."]);
    }
    return el("table", {}, [
      el("thead", {}, [
        el("tr", {}, [
          el("th", { scope: "col" }, ["Aluno"]),
          el("th", { scope: "col" }, ["Mensagem"]),
          el("th", { scope: "col" }, ["Nível"]),
          el("th", { scope: "col" }, ["Criado em"]),
          list === resolvidos ? el("th", { scope: "col" }, ["Resolvido em"]) : null,
        ]),
      ]),
      el(
        "tbody",
        {},
        list.map((alerta) =>
          el(
            "tr",
            {
              class: "clickable",
              tabIndex: 0,
              role: "button",
              "aria-label": `Ver detalhes de ${alerta.aluno_nome}`,
              onclick: () => navigate(`/alunos/${alerta.aluno_id}`),
              onkeydown: (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  navigate(`/alunos/${alerta.aluno_id}`);
                }
              },
            },
            [
              el("td", {}, [el("strong", {}, [alerta.aluno_nome]), el("div", { class: "muted", style: "font-size:11.5px;" }, [alerta.matricula])]),
              el("td", {}, [alerta.mensagem]),
              el("td", {}, [riskBadge(alerta.nivel_risco)]),
              el("td", { class: "muted" }, [fmtDataHora(alerta.criado_em)]),
              list === resolvidos ? el("td", { class: "muted" }, [fmtDataHora(alerta.resolvido_em)]) : null,
            ]
          )
        )
      ),
    ]);
  }

  container.appendChild(
    el("div", {}, [
      el("div", { class: "view-header" }, [
        el("div", {}, [
          el("h2", {}, ["Alertas"]),
          el("p", { class: "desc" }, [`${ativos.length} alerta(s) ativo(s) de ${alertas.length} no total.`]),
        ]),
      ]),
      el("div", { class: "card tight" }, [table(ativos)]),
      resolvidos.length > 0
        ? el("div", { style: "margin-top:18px;" }, [
            el("div", { class: "section-title" }, ["Histórico resolvido"]),
            el("div", { class: "card tight" }, [table(resolvidos)]),
          ])
        : null,
    ])
  );
}
