// Funcoes utilitarias compartilhadas pelas views.

export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === undefined || value === null) continue;
    if (key === "class") node.className = value;
    else if (key === "html") node.innerHTML = value;
    else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key in node) {
      node[key] = value;
    } else {
      node.setAttribute(key, value);
    }
  }
  const list = Array.isArray(children) ? children : [children];
  for (const child of list) {
    if (child === undefined || child === null || child === false) continue;
    node.appendChild(typeof child === "string" || typeof child === "number" ? document.createTextNode(child) : child);
  }
  return node;
}

export function fmtPercent(value) {
  if (value === null || value === undefined) return "—";
  return `${(Number(value) * 100).toFixed(1)}%`;
}

export function fmtFrequencia(value) {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toFixed(1)}%`;
}

export function fmtNota(value) {
  if (value === null || value === undefined) return "—";
  return Number(value).toFixed(1);
}

export function fmtData(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("pt-BR");
}

export function fmtDataHora(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

const RISK_LABEL = { Baixo: "Baixo", Medio: "Médio", Alto: "Alto" };
const RISK_CLASS = { Baixo: "risk-baixo", Medio: "risk-medio", Alto: "risk-alto" };
const RISK_ICON = { Baixo: "●", Medio: "▲", Alto: "■" };

export function riskBadge(nivel) {
  const cls = RISK_CLASS[nivel] || "tone-neutral";
  const label = RISK_LABEL[nivel] || nivel || "—";
  const icon = RISK_ICON[nivel] || "";
  return el("span", { class: `badge ${cls}` }, [icon ? `${icon} ${label}` : label]);
}

const STATUS_LABEL = {
  Cadastrado: "Cadastrado",
  Cursando_Materia: "Cursando matéria",
  Regular: "Regular",
  Risco_Medio: "Risco médio",
  Risco_Alto: "Risco alto",
  Aprovado: "Aprovado",
  Reprovado: "Reprovado",
  Evadido: "Evadido",
};

export function statusLabel(status) {
  return STATUS_LABEL[status] || status || "—";
}

export function initials(nome) {
  if (!nome) return "?";
  const parts = nome.trim().split(/\s+/);
  const first = parts[0]?.[0] || "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase();
}

export function debounce(fn, wait = 250) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), wait);
  };
}

// Exibe uma notificacao temporaria. `options.onUndo`, se informado, adiciona
// um botao "Desfazer" que executa o callback e encerra o toast imediatamente.
export function showToast(message, type = "info", options = {}) {
  const { onUndo, undoLabel = "Desfazer", duration = onUndo ? 6000 : 3200 } = options;
  const stack = document.getElementById("toast-stack");
  if (!stack) return () => {};

  let timer = null;
  function dismiss() {
    clearTimeout(timer);
    toast.style.transition = "opacity .25s";
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 250);
  }

  const children = [el("span", {}, [message])];
  if (onUndo) {
    children.push(
      el(
        "button",
        {
          class: "toast-undo",
          type: "button",
          onclick: () => {
            onUndo();
            dismiss();
          },
        },
        [undoLabel]
      )
    );
  }

  const toast = el("div", { class: `toast ${type}`, role: "status" }, children);
  stack.appendChild(toast);
  timer = setTimeout(dismiss, duration);
  return dismiss;
}

// Modal acessivel: foco preso (Tab/Shift+Tab) dentro do dialogo, foco inicial
// no primeiro elemento focavel, Esc fecha, e o foco retorna ao elemento que
// abriu o modal quando ele e fechado.
export function mountModal(contentNode, onClose) {
  const previouslyFocused = document.activeElement;
  const titleNode = contentNode.querySelector("h3");
  const titleId = titleNode ? `modal-title-${Math.random().toString(36).slice(2, 9)}` : undefined;
  if (titleNode) titleNode.id = titleId;

  const backdrop = el("div", {
    class: "modal-backdrop",
    onclick: (event) => {
      if (event.target === backdrop) onClose?.();
    },
  });
  const modal = el(
    "div",
    {
      class: "modal",
      role: "dialog",
      "aria-modal": "true",
      "aria-labelledby": titleId,
      tabIndex: -1,
    },
    [contentNode]
  );
  backdrop.appendChild(modal);
  document.body.appendChild(backdrop);

  function focusableElements() {
    return Array.from(
      modal.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    );
  }

  const initialFocusables = focusableElements();
  (initialFocusables[0] || modal).focus();

  function onKeydown(event) {
    if (event.key === "Escape") {
      onClose?.();
      return;
    }
    if (event.key === "Tab") {
      const items = focusableElements();
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }
  document.addEventListener("keydown", onKeydown);

  return () => {
    document.removeEventListener("keydown", onKeydown);
    backdrop.remove();
    if (previouslyFocused && typeof previouslyFocused.focus === "function") {
      previouslyFocused.focus();
    }
  };
}

// Modal de confirmacao reutilizavel. Retorna uma Promise<boolean>: true se o
// usuario confirmou a acao, false se cancelou ou fechou (Esc/clique fora).
export function confirmModal(message, options = {}) {
  const { title = "Confirmar ação", confirmLabel = "Confirmar", danger = false } = options;
  return new Promise((resolve) => {
    function finish(result) {
      close();
      resolve(result);
    }
    const content = el("div", {}, [
      el("h3", {}, [title]),
      el("p", { class: "desc" }, [message]),
      el("div", { class: "form-actions" }, [
        el("button", { class: "btn btn-secondary", type: "button", onclick: () => finish(false) }, ["Cancelar"]),
        el(
          "button",
          { class: `btn ${danger ? "btn-danger" : "btn-primary"}`, type: "button", onclick: () => finish(true) },
          [confirmLabel]
        ),
      ]),
    ]);
    const close = mountModal(content, () => finish(false));
  });
}
