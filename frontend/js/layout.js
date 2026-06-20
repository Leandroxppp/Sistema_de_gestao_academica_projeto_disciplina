import { el, initials, showToast, mountModal } from "./helpers.js";
import { api, clearSession, getStoredUser, ApiError } from "./api.js";
import { navigate, currentPath } from "./router.js";
import { getTheme, toggleTheme } from "./theme.js";

const NAV_ITEMS = [
  { path: "/dashboard", label: "Dashboard", icon: "▤" },
  { path: "/alunos", label: "Alunos", icon: "🎓" },
  { path: "/materias", label: "Matérias", icon: "📘" },
  { path: "/minhas-turmas", label: "Minhas Turmas", icon: "📝", professorOnly: true },
  { path: "/alertas", label: "Alertas", icon: "⚠" },
  { path: "/relatorios", label: "Relatórios", icon: "📄" },
  { path: "/usuarios", label: "Usuários", icon: "👥", gestorOnly: true },
  { path: "/auditoria", label: "Auditoria", icon: "🕓", gestorOnly: true },
  { path: "/config", label: "Configurações", icon: "⚙", gestorOnly: true },
];

const TITLES = {
  "/dashboard": "Dashboard",
  "/alunos": "Alunos",
  "/materias": "Matérias",
  "/minhas-turmas": "Minhas Turmas",
  "/alertas": "Alertas",
  "/relatorios": "Relatórios",
  "/usuarios": "Usuários",
  "/auditoria": "Auditoria",
  "/config": "Configurações",
};

function titleFor(path) {
  if (path.startsWith("/alunos/")) return "Detalhe do aluno";
  if (path.startsWith("/minhas-turmas/")) return "Lançar notas";
  return TITLES[path] || "Sigma Acadêmico";
}

// Listener de Esc para o drawer mobile da sidebar. Mantido em escopo de
// modulo para garantir que cada chamada a buildShell() remova o listener
// anterior antes de registrar um novo (evita acumular handlers).
let activeSidebarCloser = null;

export function buildShell() {
  const app = document.getElementById("app");
  app.innerHTML = "";

  if (activeSidebarCloser) {
    document.removeEventListener("keydown", activeSidebarCloser);
    activeSidebarCloser = null;
  }

  const usuario = getStoredUser();

  const sidebar = el("aside", { class: "sidebar", id: "sidebar" }, [
    el("div", { class: "sidebar-brand" }, [
      el("span", { html: "🟪" }),
      "Sigma Acadêmico",
    ]),
    el("nav", { class: "nav-group", id: "nav-group" }),
    el("div", { class: "nav-footer" }, [
      "Sistema de Gestão do Desempenho Estudantil",
    ]),
  ]);

  const overlay = el("div", { class: "sidebar-overlay", id: "sidebar-overlay", onclick: () => closeSidebar() });

  function openSidebar() {
    sidebar.classList.add("open");
    overlay.classList.add("visible");
    activeSidebarCloser = (event) => {
      if (event.key === "Escape") closeSidebar();
    };
    document.addEventListener("keydown", activeSidebarCloser);
  }

  function closeSidebar() {
    sidebar.classList.remove("open");
    overlay.classList.remove("visible");
    if (activeSidebarCloser) {
      document.removeEventListener("keydown", activeSidebarCloser);
      activeSidebarCloser = null;
    }
  }

  function toggleSidebar() {
    if (sidebar.classList.contains("open")) closeSidebar();
    else openSidebar();
  }

  const navGroup = sidebar.querySelector("#nav-group");
  NAV_ITEMS.forEach((item) => {
    if (item.gestorOnly && usuario?.perfil !== "gestor") return;
    if (item.professorOnly && usuario?.perfil !== "professor") return;
    const link = el(
      "div",
      {
        class: "nav-link",
        "data-path": item.path,
        tabIndex: 0,
        role: "link",
        onclick: () => {
          navigate(item.path);
          closeSidebar();
        },
        onkeydown: (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            navigate(item.path);
            closeSidebar();
          }
        },
      },
      [el("span", { class: "icon" }, [item.icon]), item.label]
    );
    navGroup.appendChild(link);
  });

  const menuToggle = el(
    "button",
    {
      class: "menu-toggle",
      type: "button",
      "aria-label": "Abrir menu de navegação",
      onclick: () => toggleSidebar(),
    },
    ["☰"]
  );

  const themeBtn = el(
    "button",
    {
      class: "btn-theme",
      type: "button",
      "aria-label": "Alternar tema claro/escuro",
      onclick: () => {
        const next = toggleTheme();
        themeBtn.textContent = next === "dark" ? "☀" : "🌙";
      },
    },
    [getTheme() === "dark" ? "☀" : "🌙"]
  );

  const topbar = el("header", { class: "topbar" }, [
    el("div", { class: "topbar-left", style: "display:flex; align-items:center; gap:12px;" }, [
      menuToggle,
      el("div", { class: "topbar-title", id: "view-title" }, [titleFor(currentPath())]),
    ]),
    el("div", { class: "topbar-right" }, [
      themeBtn,
      el(
        "div",
        {
          class: "user-chip",
          style: "cursor:pointer;",
          tabIndex: 0,
          role: "button",
          "aria-label": "Minha conta",
          onclick: () => openMinhaContaModal(),
          onkeydown: (event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              openMinhaContaModal();
            }
          },
        },
        [
          el("div", { class: "avatar" }, [initials(usuario?.nome)]),
          el("div", {}, [
            el("div", {}, [usuario?.nome || "Usuário"]),
          ]),
          el("span", { class: "role-tag" }, [usuario?.perfil || ""]),
        ]
      ),
      el(
        "button",
        {
          class: "btn-logout",
          onclick: async () => {
            try {
              await api.logout();
            } catch {
              // mesmo se a chamada falhar, encerramos a sessao localmente
            }
            clearSession();
            showToast("Sessão finalizada.", "info");
            window.location.hash = "";
            navigate("/login");
          },
        },
        ["Sair"]
      ),
    ]),
  ]);

  const main = el("main", { class: "main", id: "view-root" });

  const shell = el("div", { class: "shell" }, [sidebar, overlay, topbar, main]);
  app.appendChild(shell);

  return { viewRoot: main, viewTitle: topbar.querySelector("#view-title"), navGroup };
}

export function setActiveNav(path) {
  const root = document.querySelector(".nav-group");
  if (!root) return;
  root.querySelectorAll(".nav-link").forEach((link) => {
    const linkPath = link.getAttribute("data-path");
    const active = path === linkPath || (linkPath !== "/dashboard" && path.startsWith(linkPath));
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  const titleNode = document.getElementById("view-title");
  if (titleNode) titleNode.textContent = titleFor(path);
}

function openMinhaContaModal() {
  const usuario = getStoredUser();

  const senhaAtualInput = el("input", { type: "password", autocomplete: "current-password", required: true });
  const novaSenhaInput = el("input", { type: "password", autocomplete: "new-password", required: true });
  const confirmarInput = el("input", { type: "password", autocomplete: "new-password", required: true });

  const errorBox = el("div", { class: "alert-banner", style: "display:none" }, [
    el("span", {}, ["⚠"]),
    el("span", { id: "senha-form-error" }, [""]),
  ]);

  function setError(msg) {
    if (!msg) {
      errorBox.style.display = "none";
      return;
    }
    errorBox.style.display = "flex";
    errorBox.querySelector("#senha-form-error").textContent = msg;
  }

  const submitBtn = el("button", { class: "btn btn-primary", type: "submit" }, ["Alterar senha"]);

  const form = el(
    "form",
    {
      onsubmit: async (event) => {
        event.preventDefault();
        setError(null);
        if (novaSenhaInput.value.length < 6) {
          setError("A nova senha deve ter ao menos 6 caracteres.");
          return;
        }
        if (novaSenhaInput.value !== confirmarInput.value) {
          setError("A confirmação não corresponde à nova senha.");
          return;
        }
        submitBtn.disabled = true;
        submitBtn.textContent = "Alterando…";
        try {
          await api.alterarSenha(senhaAtualInput.value, novaSenhaInput.value);
          showToast("Senha alterada com sucesso.", "success");
          close();
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Erro ao alterar senha.");
          submitBtn.disabled = false;
          submitBtn.textContent = "Alterar senha";
        }
      },
    },
    [
      el("div", { class: "field" }, [el("label", {}, ["Senha atual"]), senhaAtualInput]),
      el("div", { class: "field" }, [el("label", {}, ["Nova senha"]), novaSenhaInput]),
      el("div", { class: "field" }, [el("label", {}, ["Confirmar nova senha"]), confirmarInput]),
      errorBox,
      el("div", { class: "form-actions" }, [
        el("button", { class: "btn btn-secondary", type: "button", onclick: () => close() }, ["Cancelar"]),
        submitBtn,
      ]),
    ]
  );

  const content = el("div", {}, [
    el("h3", {}, ["Minha conta"]),
    el("p", { class: "desc" }, [`${usuario?.nome || "Usuário"} · ${usuario?.email || ""}`]),
    form,
  ]);
  const close = mountModal(content, () => close());
}

export function renderLoading(container) {
  container.innerHTML = "";
  container.appendChild(
    el("div", { class: "loading-wrap" }, [el("div", { class: "spinner" })])
  );
}

export function renderError(container, message, retry) {
  container.innerHTML = "";
  container.appendChild(
    el("div", { class: "card" }, [
      el("div", { class: "alert-banner" }, [el("span", {}, ["⚠"]), message]),
      retry ? el("button", { class: "btn btn-secondary", onclick: retry }, ["Tentar novamente"]) : null,
    ])
  );
}
