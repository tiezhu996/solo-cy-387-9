<template>
  <el-table :data="orders" stripe @row-click="(row: RectificationOrder) => $emit('openTask', row.task)" class="row-click">
    <el-table-column prop="code" label="整改单号" width="190" />
    <el-table-column label="问题/来源" min-width="240">
      <template #default="{ row }">
        <div class="strong">{{ row.issue_description }}</div>
        <div class="muted">{{ row.task_code }} · 来源：{{ row.source_label }} · {{ row.source_item_name }}</div>
      </template>
    </el-table-column>
    <el-table-column label="状态" width="110">
      <template #default="{ row }">
        <el-tag :type="ORDER_STATUS_TYPE[row.status as OrderStatus]">{{ row.status_label }}</el-tag>
        <el-tag v-if="row.overdue" type="danger" size="small" effect="plain" class="overdue-tag">超期</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="轮次" width="70">
      <template #default="{ row }">第{{ row.round }}轮</template>
    </el-table-column>
    <el-table-column prop="assignee_name" label="负责人" width="110">
      <template #default="{ row }">{{ row.assignee_name || '待领取' }}</template>
    </el-table-column>
    <el-table-column label="整改期限" width="160">
      <template #default="{ row }">
        <span :class="{ 'text-danger': row.overdue }">{{ formatDateTime(row.due_at) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="220" fixed="right">
      <template #default="{ row }">
        <el-button size="small" @click.stop="$emit('openTask', row.task)">查看任务</el-button>
        <el-button
          v-if="canClaim(row)"
          size="small" type="primary" :loading="busyId === row.id"
          @click.stop="claim(row)"
        >{{ row.status === 'returned' ? '承接重做' : '领取' }}</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { apiClaimOrder } from '../api';
import { ORDER_STATUS_TYPE, type OrderStatus, type RectificationOrder, type Role } from '../types/domain';
import { formatDateTime } from '../utils/format';

const props = defineProps<{ orders: RectificationOrder[]; viewerRole?: Role | '' }>();
const emit = defineEmits<{
  (e: 'openTask', taskId: number): void;
  (e: 'changed'): void;
}>();

const busyId = ref<number | null>(null);
function canClaim(row: RectificationOrder) {
  return props.viewerRole === 'rectifier'
    && !row.assignee
    && ['pending', 'returned'].includes(row.status);
}
async function claim(row: RectificationOrder) {
  busyId.value = row.id;
  try {
    await apiClaimOrder(row.id);
    ElMessage.success('领取成功');
    emit('changed');
  } catch {
    // 409 已统一提示
  } finally {
    busyId.value = null;
  }
}
</script>

<style scoped>
.row-click :deep(.el-table__row) { cursor: pointer; }
.strong { font-weight: 600; color: #1f2937; }
.muted { color: #9ca3af; font-size: 12px; }
.overdue-tag { margin-left: 4px; }
.text-danger { color: #dc2626; font-weight: 600; }
</style>
