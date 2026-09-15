<template>
  <el-timeline>
    <el-timeline-item
      v-for="entry in entries" :key="entry.id"
      :type="colorOf(entry)" :timestamp="formatDateTime(entry.created_at)" placement="top"
    >
      <el-card shadow="never" class="timeline-card" :class="{ 'is-order': entry.target_type === 'rectification_order' }">
        <div class="timeline-head">
          <el-tag size="small" :type="entry.target_type === 'task' ? 'primary' : 'warning'" effect="plain">
            {{ entry.target_type === 'task' ? '任务' : '整改单' }}
          </el-tag>
          <span class="action">{{ entry.action_label }}</span>
          <span class="muted">{{ entry.target_code }}</span>
        </div>
        <div v-if="entry.detail" class="detail">{{ entry.detail }}</div>
        <div class="muted actor">操作人：{{ entry.actor_name || '系统' }}</div>
      </el-card>
    </el-timeline-item>
  </el-timeline>
</template>

<script setup lang="ts">
import type { TimelineEntry } from '../types/domain';
import { formatDateTime } from '../utils/format';

defineProps<{ entries: TimelineEntry[] }>();

function colorOf(e: TimelineEntry) {
  if (['close', 'submit_normal_close', 'recheck_pass', 'close_with_task'].includes(e.action)) return 'success';
  if (['recheck_reject', 'escalate'].includes(e.action)) return 'danger';
  if (['claim', 'reschedule', 'reassign', 'release_to_pool'].includes(e.action)) return 'warning';
  return 'primary';
}
</script>

<style scoped>
.timeline-card.is-order { border-left: 3px solid #f59e0b; }
.timeline-head { display: flex; align-items: center; gap: 8px; }
.action { font-weight: 600; color: #1f2937; }
.detail { margin: 6px 0 2px; color: #374151; font-size: 13px; }
.muted { color: #9ca3af; font-size: 12px; }
.actor { margin-top: 2px; }
</style>
