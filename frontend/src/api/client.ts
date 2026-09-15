import type { PropertyItem, RepairTicket } from '../types/domain';

const API_BASE = '/api';

export async function getProperties(): Promise<PropertyItem[]> {
  const response = await fetch(`${API_BASE}/properties/`);
  if (!response.ok) throw new Error('房源加载失败');
  return response.json();
}

export async function createRepair(ticket: Pick<RepairTicket, 'faultType' | 'description'>): Promise<RepairTicket> {
  const response = await fetch(`${API_BASE}/repairs/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(ticket),
  });
  if (!response.ok) throw new Error('报修提交失败');
  return response.json();
}
