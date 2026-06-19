import { el, showToast } from "../helpers.js";
import { api, setSession, ApiError } from "../api.js";

export function renderLogin(onSuccess) {
  const app = document.getElementById("app");
  app.innerHTML = "";

  let submitting = false;

  const emailInput = el("input", {
    type: "email",
    placeholder: "seu.email@sigma.edu",
    required: true,
    value: "",
    id: "login-email",
  });
  const senhaInput = el("input", {
    type: "password",
    placeholder: "••••••••",
    required: true,
    id: "login-senha",
  });
  const errorBox = el("div", { class: "alert-banner", style: "display:none" }, [
    el("span", {}, ["⚠"]),
    el("span", { id: "login-error-text" }, [""]),
  ]);
  const submitBtn = el("button", { class: "btn btn-primary", type: "submit", style: "width:100%; justify-content:center;" }, [
    "Entrar",
  ]);

  function setError(message) {
    if (!message) {
      errorBox.style.display = "none";
      return;
    }
    errorBox.style.display = "flex";
    errorBox.querySelector("#login-error-text").textContent = message;
  }

  function fillDemo(perfil) {
    if (perfil === "gestor") {
      emailInput.value = "gestor@sigma.edu";
      senhaInput.value = "gestor123";
    } else {
      emailInput.value = "professor@sigma.edu";
      senhaInput.value = "professor123";
    }
  }

  const form = el(
    "form",
    {
      onsubmit: async (event) => {
        event.preventDefault();
        if (submitting) return;
        setError(null);
        const email = emailInput.value.trim();
        const senha = senhaInput.value;
        if (!email || !senha) {
          setError("Informe email e senha.");
          return;
        }
        submitting = true;
        submitBtn.disabled = true;
        submitBtn.textContent = "Entrando…";
        try {
          const result = await api.login(email, senha);
          setSession(result.token, result.usuario);
          showToast(`Bem-vindo(a), ${result.usuario.nome.split(" ")[0]}!`, "success");
          onSuccess();
        } catch (err) {
          if (err instanceof ApiError) {
            setError(err.message);
          } else {
            setError("Erro inesperado ao entrar.");
          }
        } finally {
          submitting = false;
          submitBtn.disabled = false;
          submitBtn.textContent = "Entrar";
        }
      },
    },
    [
      el("div", { class: "field" }, [el("label", {}, ["Email"]), emailInput]),
      el("div", { class: "field" }, [el("label", {}, ["Senha"]), senhaInput]),
      errorBox,
      submitBtn,
    ]
  );

  const card = el("div", { class: "auth-card" }, [
    el("div", { class: "auth-brand" }, [
      el("div", { class: "auth-logo" }, ["S"]),
      el("h1", {}, ["Sigma Acadêmico"]),
    ]),
    el("p", { class: "subtitle" }, ["Gestão do desempenho estudantil — entre para continuar"]),
    form,
    el("div", { class: "demo-hint" }, [
      el("div", {}, [
        "Usuários de demonstração: ",
        el("button", { type: "button", onclick: () => fillDemo("professor") }, ["professor"]),
        " · ",
        el("button", { type: "button", onclick: () => fillDemo("gestor") }, ["gestor"]),
      ]),
    ]),
  ]);

  app.appendChild(el("div", { class: "auth-screen" }, [card]));
}
