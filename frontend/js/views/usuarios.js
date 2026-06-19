import { el, initials, showToast, mountModal } from "../helpers.js";
import { renderLoading, renderError } from "../layout.js";
import { api, ApiError } from "../api.js";

export async function renderUsuarios(container) {
  renderLoading(container);
  try {
    const usuarios = await api.usuarios();
    paint(container, usuarios);
  } catch (err) {
    renderError(container, err.message, () => renderUsuarios(container));
  }
}

function paint(container, usuarios) {
  container.innerHTML = "";

  const tableCard = el("div", { class: "card tight" }, [
    el("table", {}, [
      el("thead", {}, [
        el("tr", {}, [
          el("th", {}, ["Usuário"]),
          el("th", {}, ["Email"]),
          el("th", {}, ["Perfil"]),
          el("th", {}, ["Detalhe"]),
        ]),
      ]),
      el(
        "tbody",
        {},
        usuarios.map((u) =>
          el("tr", {}, [
            el(
              "td",
              {},
              [
                el("div", { style: "display:flex; align-items:center; gap:10px;" }, [
                  el("div", { class: "avatar" }, [initials(u.nome)]),
                  el("strong", {}, [u.nome]),
                ]),
              ]
            ),
            el("td", { class: "muted" }, [u.email]),
            el("td", {}, [el("span", { class: `badge ${u.perfil === "gestor" ? "tone-primary" : "tone-neutral"}` }, [u.perfil])]),
            el("td", { class: "muted" }, [u.perfil === "professor" ? u.especializacao || "—" : u.cargo || "—"]),
          ])
        )
      ),
    ]),
  ]);

  container.appendChild(
    el("div", {}, [
      el("div", { class: "view-header" }, [
        el("div", {}, [
          el("h2", {}, ["Usuários"]),
          el("p", { class: "desc" }, [`${usuarios.length} usuário(s) cadastrado(s). Acesso restrito ao gestor.`]),
        ]),
        el(
          "button",
          { class: "btn btn-primary", onclick: () => openCreateUsuarioModal(() => renderUsuarios(container)) },
          ["+ Novo usuário"]
        ),
      ]),
      tableCard,
    ])
  );
}

function openCreateUsuarioModal(onCreated) {
  const nomeInput = el("input", { placeholder: "Nome completo" });
  const emailInput = el("input", { type: "email", placeholder: "email@sigma.edu" });
  const senhaInput = el("input", { type: "password", placeholder: "Senha inicial" });
  const perfilSelect = el("select", {}, [
    el("option", { value: "professor" }, ["Professor"]),
    el("option", { value: "gestor" }, ["Gestor"]),
  ]);
  const detalheInput = el("input", { placeholder: "Ex.: Matemática (professor) ou Coordenador (gestor)" });

  const errorBox = el("div", { class: "alert-banner", style: "display:none" }, [
    el("span", {}, ["⚠"]),
    el("span", { id: "create-usuario-error" }, [""]),
  ]);

  function setError(msg) {
    if (!msg) {
      errorBox.style.display = "none";
      return;
    }
    errorBox.style.display = "flex";
    errorBox.querySelector("#create-usuario-error").textContent = msg;
  }

  const submitBtn = el("button", { class: "btn btn-primary", type: "submit" }, ["Cadastrar"]);

  const form = el(
    "form",
    {
      onsubmit: async (event) => {
        event.preventDefault();
        setError(null);
        if (!nomeInput.value.trim() || !emailInput.value.trim() || !senhaInput.value) {
          setError("Nome, email e senha são obrigatórios.");
          return;
        }
        submitBtn.disabled = true;
        submitBtn.textContent = "Cadastrando…";
        const perfil = perfilSelect.value;
        try {
          await api.criarUsuario({
            nome: nomeInput.value.trim(),
            email: emailInput.value.trim(),
            senha: senhaInput.value,
            perfil,
            especializacao: perfil === "professor" ? detalheInput.value.trim() || undefined : undefined,
            cargo: perfil === "gestor" ? detalheInput.value.trim() || undefined : undefined,
          });
          showToast("Usuário cadastrado com sucesso.", "success");
          close();
          onCreated();
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Erro ao cadastrar usuário.");
          submitBtn.disabled = false;
          submitBtn.textContent = "Cadastrar";
        }
      },
    },
    [
      el("div", { class: "field" }, [el("label", {}, ["Nome"]), nomeInput]),
      el("div", { class: "field" }, [el("label", {}, ["Email"]), emailInput]),
      el("div", { class: "field" }, [el("label", {}, ["Senha inicial"]), senhaInput]),
      el("div", { class: "field" }, [el("label", {}, ["Perfil"]), perfilSelect]),
      el("div", { class: "field" }, [el("label", {}, ["Especialização / cargo (opcional)"]), detalheInput]),
      errorBox,
      el("div", { class: "form-actions" }, [
        el("button", { class: "btn btn-secondary", type: "button", onclick: () => close() }, ["Cancelar"]),
        submitBtn,
      ]),
    ]
  );

  const content = el("div", {}, [el("h3", {}, ["Novo usuário"]), form]);
  const close = mountModal(content, () => close());
}
