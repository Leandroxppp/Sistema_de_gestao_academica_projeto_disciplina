// Cliente HTTP fino para a API do backend (app/api.py).
// Sem dependencias externas: usa fetch nativo do navegador.

const BASE_URL = ""; // mesma origem (backend serve o frontend em /app)
const TOKEN_KEY = "sigma_token";
const USER_KEY = "sigma_user";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function hasToken() {
  return Boolean(getToken());
}

export function getStoredUser() {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function setSession(token, usuario) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  if (usuario) localStorage.setItem(USER_KEY, JSON.stringify(usuario));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function request(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (networkError) {
    throw new ApiError(
      "Nao foi possivel conectar ao backend. Verifique se o servidor esta rodando (python run.py).",
      0
    );
  }

  let payload = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const message = (payload && payload.erro) || `Erro ${response.status}`;
    if (response.status === 401) {
      const hadSession = Boolean(getToken());
      clearSession();
      if (hadSession) {
        window.dispatchEvent(new CustomEvent("session-expired"));
      }
    }
    throw new ApiError(message, response.status);
  }
  return payload;
}

export const api = {
  login: (email, senha) => request("POST", "/auth/login", { email, senha }),
  logout: () => request("POST", "/auth/logout", {}),

  dashboard: () => request("GET", "/dashboard"),

  usuarios: () => request("GET", "/usuarios"),
  criarUsuario: (payload) => request("POST", "/usuarios", payload),

  materias: () => request("GET", "/materias"),
  criarMateria: (payload) => request("POST", "/materias", payload),

  alunos: () => request("GET", "/alunos"),
  criarAluno: (payload) => request("POST", "/alunos", payload),
  aluno: (id) => request("GET", `/alunos/${id}`),
  vincularMateria: (alunoId, materiaId) =>
    request("POST", `/alunos/${alunoId}/materias/${materiaId}`, {}),
  registrarDesempenho: (alunoId, payload) =>
    request("POST", `/alunos/${alunoId}/desempenhos`, payload),

  recalcularRiscos: () => request("POST", "/analises/recalcular", {}),

  alertas: () => request("GET", "/alertas"),

  relatorios: () => request("GET", "/relatorios"),
  criarRelatorio: (payload) => request("POST", "/relatorios", payload),
};
