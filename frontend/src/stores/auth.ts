// 全局登录态：模块级单例 reactive，刷新页面后用持久化 Token 拉取 /me 恢复。
import { reactive } from 'vue';
import { apiLogin, apiLogout, apiMe } from '../api';
import { clearToken, getToken, setToken } from '../api/client';
import type { Role, User } from '../types/domain';

interface AuthState {
  user: User | null;
  initialized: boolean;
  loading: boolean;
}

const state = reactive<AuthState>({ user: null, initialized: false, loading: false });

export function useAuth() {
  async function login(username: string, password: string) {
    const { token, user } = await apiLogin(username, password);
    setToken(token);
    state.user = user;
    return user;
  }

  async function logout() {
    try {
      await apiLogout();
    } catch {
      // 忽略退出登录的网络错误
    }
    clearToken();
    state.user = null;
  }

  // 刷新页面后恢复会话
  async function restore() {
    if (state.initialized) return state.user;
    if (!getToken()) {
      state.initialized = true;
      return null;
    }
    state.loading = true;
    try {
      state.user = await apiMe();
    } catch {
      clearToken();
      state.user = null;
    } finally {
      state.loading = false;
      state.initialized = true;
    }
    return state.user;
  }

  return {
    state,
    login,
    logout,
    restore,
    isRole: (...roles: Role[]) => !!state.user && roles.includes(state.user.role),
  };
}
