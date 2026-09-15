<template>
  <el-table :data="tasks" stripe @row-click="(row: InspectionTask) => $emit('open', row.id)" class="row-click">
    <el-table-column prop="code" label="任务号" width="190" />
    <el-table-column label="名称/位置" min-width="220">
      <template #default="{ row }">
        <div class="strong">{{ row.title }}</div>
        <div class="muted">{{ row.building_name }} · {{ row.area_name }} · {{ row.period_label }}</div>
      </template>
    </el-table-column>
    <el-table-column label="状态" width="120">
      <template #default="{ row }">
        <el-tag :type="TASK_STATUS_TYPE[row.status as TaskStatus]">{{ row.status_label }}</el-tag>
        <el-tag v-if="row.overdue" type="danger" size="small" effect="plain" class="overdue-tag">超期</el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="assignee_name" label="负责人" width="110">
      <template #default="{ row }">{{ row.assignee_name || '待领取' }}</template>
    </el-table-column>
    <el-table-column label="期限" width="160">
      <template #default="{ row }">
        <span :class="{ 'text-danger': row.overdue }">{{ formatDateTime(row.due_at) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="整改" width="80">
      <template #default="{ row }">
        <el-badge v-if="row.open_order_count > 0" :value="row.open_order_count" type="danger" />
        <span v-else class="muted">—</span>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="200" fixed="right">
      <template #default="{ row }">
        <el-button size="small" @click.stop="$emit('open', row.id)">详情</el-button>
        <el-button
          v-if="canClaim(row)"
          size="small" type="primary" :loading="busyId === row.id"
          @click.stop="claim(row)"
        >领取</el-button>
        <el-tag v-else-if="!hideAction" size="small" type="info" plain>—</el-tag>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { apiClaimTask } from '../api';
import { TASK_STATUS_TYPE, type InspectionTask, type TaskStatus } from '../types/domain';
import { formatDateTime } from '../utils/format';

const props = defineProps<{
  tasks: InspectionTask[];
  hideAction?: boolean;
}>();
const emit = defineEmits<{
  (e: 'open', id: number): void;
  (e: 'changed'): void;
}>();

const busyId = ref<number | null>(null);

function canClaim(row: InspectionTask) {
  return row.status === 'pending' && !row.assignee_name;
}

async function claim(row: InspectionTask) {
  busyId.value = row.id;
  try {
    await apiClaimTask(row.id);
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
