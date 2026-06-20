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

function buildQuery(params = {}) {
  const usp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    usp.set(key, value);
  }
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
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
  atualizarUsuario: (id, payload) => request("PATCH", `/usuarios/${id}`, payload),
  desativarUsuario: (id) => request("DELETE", `/usuarios/${id}`),

  materias: () => request("GET", "/materias"),
  criarMateria: (payload) => request("POST", "/materias", payload),
  atualizarMateria: (id, payload) => request("PATCH", `/materias/${id}`, payload),
  desativarMateria: (id) => request("DELETE", `/materias/${id}`),

  alunos: ({ page = 1, pageSize = 10, termo, risco, materiaId } = {}) =>
    request("GET", `/alunos${buildQuery({ page, page_size: pageSize, termo, risco, materia_id: materiaId })}`),
  importarAlunosCsv: (csvTexto) => request("POST", "/alunos/importar", { csv: csvTexto }),
  criarAluno: (payload) => request("POST", "/alunos", payload),
  aluno: (id) => request("GET", `/alunos/${id}`),
  atualizarAluno: (id, payload) => request("PATCH", `/alunos/${id}`, payload),
  desativarAluno: (id) => request("DELETE", `/alunos/${id}`),
  vincularMateria: (alunoId, materiaId) =>
    request("POST", `/alunos/${alunoId}/materias/${materiaId}`, {}),
  registrarDesempenho: (alunoId, payload) =>
    request("POST", `/alunos/${alunoId}/desempenhos`, payload),

  recalcularRiscos: () => request("POST", "/analises/recalcular", {}),

  alertas: () => request("GET", "/alertas"),

  relatorios: () => request("GET", "/relatorios"),
  criarRelatorio: (payload) => request("POST", "/relatorios", payload),

  auditoria: ({ page = 1, pageSize = 20 } = {}) =>
    request("GET", `/auditoria${buildQuery({ page, page_size: pageSize })}`),

  intervencoes: (alunoId) => request("GET", `/alunos/${alunoId}/intervencoes`),
  criarIntervencao: (alunoId, payload) =>
    request("POST", `/alunos/${alunoId}/intervencoes`, payload),
  atualizarIntervencao: (intervencaoId, payload) =>
    request("PATCH", `/intervencoes/${intervencaoId}`, payload),

  alterarSenha: (senhaAtual, novaSenha) =>
    request("POST", "/auth/senha", { senha_atual: senhaAtual, nova_senha: novaSenha }),

  configRisco: {
    obter: () => request("GET", "/config/risco"),
    atualizar: (payload) => request("PATCH", "/config/risco", payload),
  },

  comparativoMaterias: () => request("GET", "/materias/comparativo"),
};
