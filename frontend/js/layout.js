import { el, initials, showToast } from "./helpers.js";
import { api, clearSession, getStoredUser } from "./api.js";
import { navigate, currentPath } from "./router.js";

const NAV_ITEMS = [
  { path: "/dashboard", label: "Dashboard", icon: "▤" },
  { path: "/alunos", label: "Alunos", icon: "🎓" },
  { path: "/materias", label: "Matérias", icon: "📘" },
  { path: "/alertas", label: "Alertas", icon: "⚠" },
  { path: "/relatorios", label: "Relatórios", icon: "📄" },
  { path: "/usuarios", label: "Usuários", icon: "👥", gestorOnly: true },
];

const TITLES = {
  "/dashboard": "Dashboard",
  "/alunos": "Alunos",
  "/materias": "Matérias",
  "/alertas": "Alertas",
  "/relatorios": "Relatórios",
  "/usuarios": "Usuários",
};

function titleFor(path) {
  if (path.startsWith("/alunos/")) return "Detalhe do aluno";
  return TITLES[path] || "Sigma Acadêmico";
}

export function buildShell() {
  const app = document.getElementById("app");
  app.innerHTML = "";

  const usuario = getStoredUser();

  const sidebar = el("aside", { class: "sidebar" }, [
    el("div", { class: "sidebar-brand" }, [
      el("span", { html: "🟪" }),
      "Sigma Acadêmico",
    ]),
    el("nav", { class: "nav-group", id: "nav-group" }),
    el("div", { class: "nav-footer" }, [
      "Sistema de Gestão do Desempenho Estudantil",
    ]),
  ]);

  const navGroup = sidebar.querySelector("#nav-group");
  NAV_ITEMS.forEach((item) => {
    if (item.gestorOnly && usuario?.perfil !== "gestor") return;
    const link = el(
      "div",
      {
        class: "nav-link",
        "data-path": item.path,
        onclick: () => navigate(item.path),
      },
      [el("span", { class: "icon" }, [item.icon]), item.label]
    );
    navGroup.appendChild(link);
  });

  const topbar = el("header", { class: "topbar" }, [
    el("div", { class: "topbar-title", id: "view-title" }, [titleFor(currentPath())]),
    el("div", { class: "topbar-right" }, [
      el("div", { class: "user-chip" }, [
        el("div", { class: "avatar" }, [initials(usuario?.nome)]),
        el("div", {}, [
          el("div", {}, [usuario?.nome || "Usuário"]),
        ]),
        el("span", { class: "role-tag" }, [usuario?.perfil || ""]),
      ]),
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

  const shell = el("div", { class: "shell" }, [sidebar, topbar, main]);
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
  });
  const titleNode = document.getElementById("view-title");
  if (titleNode) titleNode.textContent = titleFor(path);
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
