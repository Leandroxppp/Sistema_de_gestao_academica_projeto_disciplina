import { el, initials, showToast, mountModal, confirmModal } from "../helpers.js";
import { renderLoading, renderError } from "../layout.js";
import { api, getStoredUser, ApiError } from "../api.js";

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
  const usuarioLogado = getStoredUser();
  const refresh = () => renderUsuarios(container);

  const tableCard = el("div", { class: "card tight" }, [
    el("table", {}, [
      el("thead", {}, [
        el("tr", {}, [
          el("th", { scope: "col" }, ["Usuário"]),
          el("th", { scope: "col" }, ["Email"]),
          el("th", { scope: "col" }, ["Perfil"]),
          el("th", { scope: "col" }, ["Detalhe"]),
          el("th", { scope: "col" }, ["Status"]),
          el("th", { scope: "col" }, [""]),
        ]),
      ]),
      el(
        "tbody",
        {},
        usuarios.map((u) =>
          el("tr", { class: u.ativo === false ? "is-inactive" : "" }, [
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
            el("td", {}, [
              u.ativo === false
                ? el("span", { class: "badge tone-danger" }, ["Inativo"])
                : el("span", { class: "badge tone-success" }, ["Ativo"]),
            ]),
            el("td", {}, [buildRowActions(u, usuarioLogado, refresh)]),
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
          { class: "btn btn-primary", onclick: () => openUsuarioModal(null, refresh) },
          ["+ Novo usuário"]
        ),
      ]),
      tableCard,
    ])
  );
}

function buildRowActions(usuario, usuarioLogado, onChanged) {
  const isSelf = usuarioLogado && usuarioLogado.id === usuario.id;
  const editBtn = el(
    "button",
    { class: "btn btn-ghost btn-sm", type: "button", onclick: () => openUsuarioModal(usuario, onChanged) },
    ["Editar"]
  );

  if (isSelf) {
    return el("div", { class: "row-actions" }, [editBtn, el("span", { class: "badge tone-neutral" }, ["Você"])]);
  }

  const toggleBtn = el(
    "button",
    {
      class: `btn btn-sm ${usuario.ativo === false ? "btn-secondary" : "btn-danger"}`,
      type: "button",
      onclick: async () => {
        const ativando = usuario.ativo === false;
        const confirmado = await confirmModal(
          ativando
            ? `Reativar o acesso de "${usuario.nome}"?`
            : `Desativar o acesso de "${usuario.nome}"? Ele(a) nao podera mais fazer login.`,
          { title: ativando ? "Reativar usuário" : "Desativar usuário", confirmLabel: ativando ? "Reativar" : "Desativar", danger: !ativando }
        );
        if (!confirmado) return;
        try {
          if (ativando) {
            await api.atualizarUsuario(usuario.id, { ativo: true });
            showToast("Usuário reativado.", "success");
          } else {
            await api.desativarUsuario(usuario.id);
            showToast("Usuário desativado.", "success", {
              onUndo: async () => {
                try {
                  await api.atualizarUsuario(usuario.id, { ativo: true });
                  showToast("Usuário reativado.", "success");
                  onChanged();
                } catch (err) {
                  showToast(err instanceof ApiError ? err.message : "Erro ao desfazer.", "error");
                }
              },
            });
          }
          onChanged();
        } catch (err) {
          showToast(err instanceof ApiError ? err.message : "Erro ao atualizar usuário.", "error");
        }
      },
    },
    [usuario.ativo === false ? "Reativar" : "Desativar"]
  );

  return el("div", { class: "row-actions" }, [editBtn, toggleBtn]);
}

function openUsuarioModal(usuario, onSaved) {
  const isEdit = Boolean(usuario);
  const nomeInput = el("input", { placeholder: "Nome completo", value: usuario?.nome || "" });
  const emailInput = el("input", { type: "email", placeholder: "email@sigma.edu", value: usuario?.email || "" });
  const senhaInput = el("input", {
    type: "password",
    placeholder: isEdit ? "Deixe em branco para manter a senha atual" : "Senha inicial",
  });
  const perfilSelect = el(
    "select",
    { value: usuario?.perfil || "professor" },
    [
      el("option", { value: "professor" }, ["Professor"]),
      el("option", { value: "gestor" }, ["Gestor"]),
    ]
  );
  perfilSelect.value = usuario?.perfil || "professor";
  const detalheInput = el("input", {
    placeholder: "Ex.: Matemática (professor) ou Coordenador (gestor)",
    value: (usuario?.perfil === "gestor" ? usuario?.cargo : usuario?.especializacao) || "",
  });

  const errorBox = el("div", { class: "alert-banner", style: "display:none" }, [
    el("span", {}, ["⚠"]),
    el("span", { id: "usuario-form-error" }, [""]),
  ]);

  function setError(msg) {
    if (!msg) {
      errorBox.style.display = "none";
      return;
    }
    errorBox.style.display = "flex";
    errorBox.querySelector("#usuario-form-error").textContent = msg;
  }

  const submitBtn = el("button", { class: "btn btn-primary", type: "submit" }, [isEdit ? "Salvar" : "Cadastrar"]);

  const form = el(
    "form",
    {
      onsubmit: async (event) => {
        event.preventDefault();
        setError(null);
        if (!nomeInput.value.trim() || !emailInput.value.trim() || (!isEdit && !senhaInput.value)) {
          setError("Nome, email e senha são obrigatórios.");
          return;
        }
        submitBtn.disabled = true;
        submitBtn.textContent = isEdit ? "Salvando…" : "Cadastrando…";
        const perfil = perfilSelect.value;
        const payload = {
          nome: nomeInput.value.trim(),
          email: emailInput.value.trim(),
          perfil,
          especializacao: perfil === "professor" ? detalheInput.value.trim() || null : null,
          cargo: perfil === "gestor" ? detalheInput.value.trim() || null : null,
        };
        if (senhaInput.value) payload.senha = senhaInput.value;
        try {
          if (isEdit) {
            if (!senhaInput.value) delete payload.senha;
            await api.atualizarUsuario(usuario.id, payload);
            showToast("Usuário atualizado.", "success");
          } else {
            payload.senha = senhaInput.value;
            await api.criarUsuario(payload);
            showToast("Usuário cadastrado com sucesso.", "success");
          }
          close();
          onSaved();
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Erro ao salvar usuário.");
          submitBtn.disabled = false;
          submitBtn.textContent = isEdit ? "Salvar" : "Cadastrar";
        }
      },
    },
    [
      el("div", { class: "field" }, [el("label", {}, ["Nome"]), nomeInput]),
      el("div", { class: "field" }, [el("label", {}, ["Email"]), emailInput]),
      el("div", { class: "field" }, [el("label", {}, [isEdit ? "Nova senha (opcional)" : "Senha inicial"]), senhaInput]),
      el("div", { class: "field" }, [el("label", {}, ["Perfil"]), perfilSelect]),
      el("div", { class: "field" }, [el("label", {}, ["Especialização / cargo (opcional)"]), detalheInput]),
      errorBox,
      el("div", { class: "form-actions" }, [
        el("button", { class: "btn btn-secondary", type: "button", onclick: () => close() }, ["Cancelar"]),
        submitBtn,
      ]),
    ]
  );

  const content = el("div", {}, [el("h3", {}, [isEdit ? "Editar usuário" : "Novo usuário"]), form]);
  const close = mountModal(content, () => close());
}
