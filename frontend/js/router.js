// Roteador hash simples (#/rota/:param), sem dependencias externas.

const routes = [];
let notFoundHandler = () => {};

export function resetRoutes() {
  routes.length = 0;
}

export function registerRoute(pattern, handler) {
  const paramNames = [];
  const regexStr = pattern
    .replace(/:[a-zA-Z_]+/g, (match) => {
      paramNames.push(match.slice(1));
      return "([^/]+)";
    });
  const regex = new RegExp(`^${regexStr}$`);
  routes.push({ regex, paramNames, handler });
}

export function setNotFound(handler) {
  notFoundHandler = handler;
}

export function navigate(path) {
  if (window.location.hash.slice(1) === path) {
    resolveRoute();
  } else {
    window.location.hash = path;
  }
}

export function currentPath() {
  const hash = window.location.hash.slice(1);
  return hash || "/dashboard";
}

function resolveRoute() {
  const path = currentPath();
  for (const route of routes) {
    const match = route.regex.exec(path);
    if (match) {
      const params = {};
      route.paramNames.forEach((name, index) => {
        params[name] = decodeURIComponent(match[index + 1]);
      });
      route.handler(params);
      return;
    }
  }
  notFoundHandler();
}

export function startRouter() {
  window.addEventListener("hashchange", resolveRoute);
  resolveRoute();
}
