// Backend address; override with VITE_API_URL when it is not on localhost
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const TOKEN_KEY = 'token';
const USER_KEY = 'user';

// --- Session: token and current user kept in localStorage ---
export const getToken = () => localStorage.getItem(TOKEN_KEY);

export const getUser = () => {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY));
  } catch {
    return null;
  }
};

export const saveSession = (token, user) => {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
};

export const clearSession = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};

export const isAdmin = (user) => user?.role === 'admin';

// --- Requests ---
export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

// FastAPI sends "detail" as a string, or as a list of validation errors
const describe = (detail, fallback) => {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ');
  }
  return fallback;
};

/**
 * Call the API with the stored token.
 * `body` is sent as JSON; pass `form` instead for form-encoded data, or
 * `files` (a FormData) to upload files: the browser sets its content type.
 * On 401 the session is cleared and the user is sent to the login page.
 */
export async function api(path, { method = 'GET', body, form, files } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let payload;
  if (files) {
    payload = files;
  } else if (form) {
    payload = new URLSearchParams(form);
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
  } else if (body !== undefined) {
    payload = JSON.stringify(body);
    headers['Content-Type'] = 'application/json';
  }

  let response;
  try {
    response = await fetch(API_URL + path, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, 'Сервер недоступен');
  }

  if (response.status === 401 && path !== '/auth/login') {
    clearSession();
    window.location.assign('/login');
    throw new ApiError(401, 'Сессия истекла');
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(response.status, describe(data?.detail, `Ошибка ${response.status}`));
  }
  return data;
}

export const login = async (username, password) => {
  const data = await api('/auth/login', { method: 'POST', form: { username, password } });
  saveSession(data.access_token, data.user);
  return data.user;
};
