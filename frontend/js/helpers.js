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

export function showToast(message, type = "info") {
  const stack = document.getElementById("toast-stack");
  if (!stack) return;
  const toast = el("div", { class: `toast ${type}` }, [message]);
  stack.appendChild(toast);
  setTimeout(() => {
    toast.style.transition = "opacity .25s";
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 250);
  }, 3200);
}

export function mountModal(contentNode, onClose) {
  const backdrop = el("div", {
    class: "modal-backdrop",
    onclick: (event) => {
      if (event.target === backdrop) onClose?.();
    },
  });
  const modal = el("div", { class: "modal" }, [contentNode]);
  backdrop.appendChild(modal);
  document.body.appendChild(backdrop);
  return () => backdrop.remove();
}
