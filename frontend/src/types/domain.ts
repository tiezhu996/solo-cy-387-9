// 业务领域类型定义，与后端序列化器字段保持一致。

export type Role = 'property' | 'inspector' | 'rectifier' | 'supervisor';

export interface User {
  id: number;
  username: string;
  name: string;
  role: Role;
  roleLabel: string;
  phone?: string;
  is_active: boolean;
}

export interface Building {
  id: number;
  code: string;
  name: string;
}

export interface Area {
  id: number;
  building: number;
  building_name: string;
  code: string;
  name: string;
  location?: string;
}

export type TaskStatus = 'pending' | 'claimed' | 'submitted' | 'returned' | 'done';

export interface InspectionTask {
  id: number;
  code: string;
  title: string;
  building_name: string;
  area_name: string;
  period: string;
  period_label: string;
  status: TaskStatus;
  status_label: string;
  assignee: number | null;
  assignee_name: string | null;
  scheduled_at: string;
  due_at: string;
  claimed_at: string | null;
  submitted_at: string | null;
  closed_at: string | null;
  created_at: string;
  open_order_count: number;
  overdue: boolean;
  checklist?: string[];
  publisher_name?: string | null;
  submission?: Submission | null;
}

export interface ItemResult {
  id?: number;
  name: string;
  result: 'normal' | 'issue';
  description?: string;
  photos?: string[];
}

export interface Submission {
  id: number;
  inspector_name: string;
  summary: string;
  created_at: string;
  items: ItemResult[];
}

export type OrderStatus =
  | 'pending' | 'processing' | 'submitted' | 'returned' | 'verified' | 'closed';

export interface Resolution {
  id: number;
  round: number;
  rectifier_name: string;
  note: string;
  photos: string[];
  created_at: string;
}

export interface Recheck {
  id: number;
  round: number;
  inspector_name: string;
  passed: boolean;
  note: string;
  created_at: string;
}

export interface RectificationOrder {
  id: number;
  code: string;
  task: number;
  task_code: string;
  task_title: string;
  source: string;
  source_label: string;
  source_item_name: string;
  issue_description: string;
  severity: string;
  severity_label: string;
  issue_photos: string[];
  assignee: number | null;
  assignee_name: string | null;
  status: OrderStatus;
  status_label: string;
  round: number;
  due_at: string;
  claimed_at: string | null;
  submitted_at: string | null;
  verified_at: string | null;
  closed_at: string | null;
  created_at: string;
  overdue: boolean;
  resolutions?: Resolution[];
  rechecks?: Recheck[];
}

export interface TimelineEntry {
  id: number;
  target_type: 'task' | 'rectification_order';
  target_id: number;
  target_code: string;
  action: string;
  action_label: string;
  from_status: string;
  to_status: string;
  actor_name: string;
  detail: string;
  created_at: string;
}

export interface Escalation {
  id: number;
  target_type: 'task' | 'rectification_order';
  target_id: number;
  target_code: string;
  target_title: string;
  level: string;
  reason: string;
  overdue_at: string | null;
  status: 'open' | 'resolved';
  status_label: string;
  handle_note: string;
  created_at: string;
  resolved_at: string | null;
}

export const TASK_STATUS_TYPE: Record<TaskStatus, 'info' | 'warning' | 'danger' | 'primary' | 'success'> = {
  pending: 'info',
  claimed: 'primary',
  submitted: 'danger',
  returned: 'warning',
  done: 'success',
};

export const ORDER_STATUS_TYPE: Record<OrderStatus, 'info' | 'warning' | 'danger' | 'primary' | 'success'> = {
  pending: 'info',
  processing: 'primary',
  submitted: 'warning',
  returned: 'danger',
  verified: 'success',
  closed: 'success',
};
