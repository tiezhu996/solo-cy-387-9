// 按后端接口聚合的 API 调用。
import { request } from './client';
import type {
  Area,
  Building,
  Escalation,
  InspectionTask,
  ItemResult,
  RectificationOrder,
  TimelineEntry,
  User,
} from '../types/domain';

// ---- 认证 / 用户 ----
export const apiLogin = (username: string, password: string) =>
  request<{ token: string; user: User }>('/auth/login/', {
    method: 'POST',
    body: { username, password },
    silent: true,
  });
export const apiLogout = () => request('/auth/logout/', { method: 'POST' });
export const apiMe = () => request<User>('/auth/me/');
export const apiDemoAccounts = () => request<User[]>('/auth/demo-accounts/');
export const apiListUsers = (role?: string) =>
  request<User[]>(`/users/${role ? `?role=${role}` : ''}`);
export const apiSetUserActive = (id: number, isActive: boolean, takeoverUserId?: number) =>
  request<User>(`/users/${id}/active/`, {
    method: 'POST',
    body: isActive
      ? { is_active: true }
      : { is_active: false, ...(takeoverUserId ? { takeover_user_id: takeoverUserId } : {}) },
  });

// ---- 组织 ----
export const apiBuildings = () => request<Building[]>('/buildings/');
export const apiAreas = (buildingId?: number) =>
  request<Area[]>(`/areas/${buildingId ? `?building=${buildingId}` : ''}`);

// ---- 巡检任务 ----
export interface PublishPayload {
  title: string;
  building_id: number;
  area_id: number;
  period: string;
  scheduled_at: string;
  due_at: string;
  checklist: string[];
  assignee_id?: number | null;
}
export const apiListTasks = (params: Record<string, string> = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request<InspectionTask[]>(`/tasks/${qs ? `?${qs}` : ''}`);
};
export const apiTask = (id: number) => request<InspectionTask>(`/tasks/${id}/`);
export const apiPublishTask = (payload: PublishPayload) =>
  request<InspectionTask>('/tasks/', { method: 'POST', body: payload });
export const apiClaimTask = (id: number) =>
  request<InspectionTask>(`/tasks/${id}/claim/`, { method: 'POST' });
export const apiSubmitTask = (id: number, items: ItemResult[], summary: string) =>
  request<InspectionTask>(`/tasks/${id}/submit/`, { method: 'POST', body: { items, summary } });
export const apiCloseTask = (id: number) =>
  request<InspectionTask>(`/tasks/${id}/close/`, { method: 'POST' });
export const apiRescheduleTask = (id: number, scheduled_at: string, due_at: string) =>
  request<InspectionTask>(`/tasks/${id}/reschedule/`, {
    method: 'POST',
    body: { scheduled_at, due_at },
  });
export const apiReassignTask = (id: number, userId: number | null) =>
  request<InspectionTask>(`/tasks/${id}/reassign/`, {
    method: 'POST',
    body: userId ? { user_id: userId } : { to_pool: true },
  });
export const apiTaskTimeline = (id: number) =>
  request<TimelineEntry[]>(`/tasks/${id}/timeline/`);

// ---- 整改单 ----
export const apiListOrders = (params: Record<string, string> = {}) => {
  const qs = new URLSearchParams(params).toString();
  return request<RectificationOrder[]>(`/orders/${qs ? `?${qs}` : ''}`);
};
export const apiOrder = (id: number) => request<RectificationOrder>(`/orders/${id}/`);
export const apiClaimOrder = (id: number) =>
  request<RectificationOrder>(`/orders/${id}/claim/`, { method: 'POST' });
export const apiSubmitOrder = (id: number, note: string, photos: string[]) =>
  request<RectificationOrder>(`/orders/${id}/submit/`, {
    method: 'POST',
    body: { note, photos },
  });
export const apiRecheckOrder = (id: number, passed: boolean, note: string) =>
  request<RectificationOrder>(`/orders/${id}/recheck/`, {
    method: 'POST',
    body: { passed, note },
  });
export const apiCloseOrder = (id: number) =>
  request<RectificationOrder>(`/orders/${id}/close/`, { method: 'POST' });
export const apiReassignOrder = (id: number, userId: number) =>
  request<RectificationOrder>(`/orders/${id}/reassign/`, {
    method: 'POST',
    body: { user_id: userId },
  });

// ---- 超期升级 ----
export const apiListEscalations = (status = 'open') =>
  request<Escalation[]>(`/escalations/?status=${status}`);
export const apiResolveEscalation = (id: number, note: string) =>
  request<{ id: number; status: string }>(`/escalations/${id}/resolve/`, {
    method: 'POST',
    body: { note },
  });
