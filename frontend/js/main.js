import { getStoredUser, clearSession } from "./api.js";
import { renderLogin } from "./views/login.js";
import { buildShell, setActiveNav } from "./layout.js";
import { registerRoute, resetRoutes, setNotFound, startRouter, navigate, currentPath } from "./router.js";
import { renderDashboard } from "./views/dashboard.js";
import { renderAlunos } from "./views/alunos.js";
import { renderAlunoDetail } from "./views/aluno-detail.js";
import { renderMaterias } from "./views/materias.js";
import { renderAlertas } from "./views/alertas.js";
import { renderRelatorios } from "./views/relatorios.js";
import { renderUsuarios } from "./views/usuarios.js";
import { showToast } from "./helpers.js";

function isAuthenticated() {
  return Boolean(getStoredUser() && localStorage.getItem("sigma_token"));
}

function showLoginScreen() {
  renderLogin(() => {
    window.location.hash = "#/dashboard";
    startApp();
  });
}

function guardedView(renderFn, { gestorOnly = false } = {}) {
  return (params) => {
    const usuario = getStoredUser();
    if (gestorOnly && usuario?.perfil !== "gestor") {
      navigate("/dashboard");
      return;
    }
    const { viewRoot } = ensureShellMounted();
    setActiveNav(currentPath());
    renderFn(viewRoot, params);
  };
}

let shellMounted = false;
let viewRootRef = null;

function ensureShellMounted() {
  if (!shellMounted) {
    const shell = buildShell();
    viewRootRef = shell.viewRoot;
    shellMounted = true;
  }
  return { viewRoot: viewRootRef };
}

function registerRoutes() {
  resetRoutes();
  registerRoute("/dashboard", guardedView(renderDashboard));
  registerRoute("/alunos", guardedView(renderAlunos));
  registerRoute("/alunos/:id", guardedView(renderAlunoDetail));
  registerRoute("/materias", guardedView(renderMaterias));
  registerRoute("/alertas", guardedView(renderAlertas));
  registerRoute("/relatorios", guardedView(renderRelatorios));
  registerRoute("/usuarios", guardedView(renderUsuarios, { gestorOnly: true }));
  registerRoute("/login", () => {
    shellMounted = false;
    showLoginScreen();
  });
  setNotFound(() => navigate("/dashboard"));
}

function startApp() {
  shellMounted = false;
  registerRoutes();
  startRouter();
}

window.addEventListener("session-expired", () => {
  shellMounted = false;
  showToast("Sua sessão expirou. Faça login novamente.", "error");
  showLoginScreen();
});

function boot() {
  if (isAuthenticated()) {
    startApp();
  } else {
    clearSession();
    showLoginScreen();
  }
}

boot();
