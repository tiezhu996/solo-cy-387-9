// 统一 API 请求封装：自动携带 Token、解包 {success,data,error}、401 跳登录。
import { ElMessage } from 'element-plus';

const API_BASE = '/api';
const TOKEN_KEY = 'patrolloop_token';

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || '';
}
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

interface ApiEnvelope<T> {
  success: boolean;
  code: string;
  data: T;
  error: string | null;
}

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  // 是否静默错误（由调用方自行处理提示）
  silent?: boolean;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Token ${token}`;
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method || 'GET',
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', '网络连接失败，请确认后端服务已启动');
  }

  let payload: ApiEnvelope<T>;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError(response.status, 'BAD_RESPONSE', '服务器返回格式异常');
  }

  if (!response.ok || !payload.success) {
    const error = new ApiError(response.status, payload.code, payload.error || '请求失败');
    if (response.status === 401) {
      clearToken();
      if (location.hash !== '#/login') location.hash = '#/login';
    }
    if (!options.silent) ElMessage.error(error.message);
    throw error;
  }
  return payload.data;
}

export async function uploadPhoto(file: File): Promise<{ url: string; name: string }> {
  const form = new FormData();
  form.append('file', file);
  const response = await fetch(`${API_BASE}/photos/`, {
    method: 'POST',
    headers: { Authorization: `Token ${getToken()}` },
    body: form,
  });
  const payload = await response.json();
  if (!response.ok || !payload.success) {
    throw new ApiError(response.status, payload.code, payload.error || '照片上传失败');
  }
  return payload.data;
}
