<template>
  <el-card shadow="never">
    <template #header>
      <div class="head">
        <el-radio-group v-model="scope" @change="load">
          <el-radio-button value="mine">我的任务</el-radio-button>
          <el-radio-button value="pool">公共待领池</el-radio-button>
          <el-radio-button value="">全部</el-radio-button>
        </el-radio-group>
        <el-radio-group v-model="statusFilter" @change="load">
          <el-radio-button value="">全部状态</el-radio-button>
          <el-radio-button v-for="(label, key) in TASK_LABELS" :key="key" :value="key">{{ label }}</el-radio-button>
        </el-radio-group>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>
    </template>
    <el-table v-loading="loading" :data="filtered" stripe @row-click="(row: InspectionTask) => $router.push(`/tasks/${row.id}`)" class="row-click">
      <el-table-column prop="code" label="任务号" width="180" />
      <el-table-column label="名称/位置" min-width="220">
        <template #default="{ row }">
          <div class="strong">{{ row.title }}</div>
          <div class="muted">{{ row.building_name }} · {{ row.area_name }}</div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="130">
        <template #default="{ row }">
          <el-tag :type="TASK_STATUS_TYPE[row.status as TaskStatus]">{{ row.status_label }}</el-tag>
          <el-tag v-if="row.overdue" type="danger" size="small" effect="plain" class="ml4">超期</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="assignee_name" label="负责人" width="100">
        <template #default="{ row }">{{ row.assignee_name || '待领取' }}</template>
      </el-table-column>
      <el-table-column label="期限" width="160">
        <template #default="{ row }">
          <span :class="{ danger: row.overdue }">{{ formatDateTime(row.due_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click.stop="$router.push(`/tasks/${row.id}`)">进入</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { Refresh } from '@element-plus/icons-vue';
import { apiListTasks } from '../api';
import { TASK_STATUS_TYPE, type InspectionTask, type TaskStatus } from '../types/domain';
import { formatDateTime } from '../utils/format';

const TASK_LABELS: Record<string, string> = {
  pending: '待领取', claimed: '巡检中', submitted: '待整改', returned: '复验驳回', done: '已关闭',
};

const scope = ref<'mine' | 'pool' | ''>('mine');
const statusFilter = ref('');
const tasks = ref<InspectionTask[]>([]);
const loading = ref(false);

const filtered = computed(() =>
  statusFilter.value ? tasks.value.filter((t) => t.status === statusFilter.value) : tasks.value,
);

async function load() {
  loading.value = true;
  try {
    const params: Record<string, string> = {};
    if (scope.value) params.scope = scope.value;
    tasks.value = await apiListTasks(params);
  } finally {
    loading.value = false;
  }
}
onMounted(load);
</script>

<style scoped>
.head { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.row-click :deep(.el-table__row) { cursor: pointer; }
.strong { font-weight: 600; }
.muted { color: #9ca3af; font-size: 12px; }
.ml4 { margin-left: 4px; }
.danger { color: #dc2626; font-weight: 600; }
</style>
