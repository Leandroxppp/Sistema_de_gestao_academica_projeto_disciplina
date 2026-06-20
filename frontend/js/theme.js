// Modo claro/escuro com persistencia em localStorage.
// Sem dependencias externas: usa apenas o atributo data-theme no <html>.

const THEME_KEY = "sigma_theme";

export function getTheme() {
  return localStorage.getItem(THEME_KEY) || "light";
}

export function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
}

export function setTheme(theme) {
  localStorage.setItem(THEME_KEY, theme);
  applyTheme(theme);
}

// Deve ser chamado o mais cedo possivel (antes de montar a UI) para evitar
// o flash do tema errado durante o carregamento da pagina.
export function initTheme() {
  applyTheme(getTheme());
}

export function toggleTheme() {
  const next = getTheme() === "dark" ? "light" : "dark";
  setTheme(next);
  return next;
}
