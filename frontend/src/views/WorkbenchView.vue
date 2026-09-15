<template>
  <div v-loading="loading">
    <el-row :gutter="16" class="stat-row">
      <el-col v-for="card in cards" :key="card.label" :span="6">
        <el-card shadow="hover" class="stat-card" @click="card.to && router.push(card.to)">
          <div class="stat-label">{{ card.label }}</div>
          <div class="stat-value" :style="{ color: card.color }">{{ card.value }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>{{ listTitle }}</span>
          <div>
            <el-button v-if="isRole('property')" type="primary" :icon="Plus" @click="publishVisible = true">发布巡检任务</el-button>
            <el-button :icon="Refresh" @click="load">刷新</el-button>
          </div>
        </div>
      </template>
      <TaskTable v-if="role !== 'rectifier'" :tasks="tasks" @changed="load" @open="openTask" />
      <OrderTable v-else :orders="orders" @changed="load" @openTask="openTask" />
    </el-card>

    <PublishTaskDialog v-model:visible="publishVisible" @published="load" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { Plus, Refresh } from '@element-plus/icons-vue';
import { apiListEscalations, apiListOrders, apiListTasks } from '../api';
import { useAuth } from '../stores/auth';
import type { Escalation, InspectionTask, RectificationOrder } from '../types/domain';
import TaskTable from '../components/TaskTable.vue';
import OrderTable from '../components/OrderTable.vue';
import PublishTaskDialog from '../components/PublishTaskDialog.vue';

const auth = useAuth();
const router = useRouter();
const isRole = auth.isRole;
const loading = ref(false);
const tasks = ref<InspectionTask[]>([]);
const orders = ref<RectificationOrder[]>([]);
const escalations = ref<Escalation[]>([]);
const publishVisible = ref(false);

const role = computed(() => auth.state.user?.role);

const cards = computed(() => {
  const t = tasks.value;
  if (role.value === 'inspector') {
    return [
      { label: '待领取（公共池）', value: tasks.value.filter((x) => x.status === 'pending').length, color: '#0ea5e9', to: '/tasks' },
      { label: '我的巡检中', value: t.filter((x) => x.assignee === auth.state.user?.id && (x.status === 'claimed')).length, color: '#2563eb', to: '/tasks' },
      { label: '待我复验', value: orders.value.filter((o) => o.status === 'submitted').length, color: '#d97706', to: '/tasks' },
      { label: '驳回重改中', value: t.filter((x) => x.status === 'returned').length, color: '#dc2626', to: '/tasks' },
    ];
  }
  if (role.value === 'rectifier') {
    return [
      { label: '待领取整改单', value: orders.value.filter((o) => o.status === 'pending').length, color: '#0ea5e9', to: '/orders' },
      { label: '我的整改中', value: orders.value.filter((o) => o.assignee === auth.state.user?.id && ['processing', 'returned'].includes(o.status)).length, color: '#2563eb', to: '/orders' },
      { label: '待复验', value: orders.value.filter((o) => o.status === 'submitted').length, color: '#d97706', to: '/orders' },
      { label: '已闭环', value: orders.value.filter((o) => o.status === 'closed').length, color: '#16a34a', to: '/orders' },
    ];
  }
  if (role.value === 'supervisor') {
    return [
      { label: '待处置升级', value: escalations.value.length, color: '#dc2626', to: '/escalations' },
      { label: '进行中任务', value: tasks.value.filter((x) => x.status !== 'done').length, color: '#2563eb' },
      { label: '已关闭任务', value: tasks.value.filter((x) => x.status === 'done').length, color: '#16a34a' },
      { label: '今日超期', value: tasks.value.filter((x) => x.overdue).length, color: '#ea580c' },
    ];
  }
  // property
  return [
    { label: '全部任务', value: tasks.value.length, color: '#2563eb' },
    { label: '待领取', value: tasks.value.filter((x) => x.status === 'pending').length, color: '#0ea5e9' },
    { label: '进行中', value: tasks.value.filter((x) => ['claimed', 'submitted', 'returned'].includes(x.status)).length, color: '#d97706' },
    { label: '已关闭', value: tasks.value.filter((x) => x.status === 'done').length, color: '#16a34a' },
  ];
});

const listTitle = computed(() => {
  if (role.value === 'rectifier') return '我相关的整改任务';
  if (role.value === 'supervisor') return '全部巡检任务（只读总览）';
  return '巡检任务列表';
});

async function load() {
  loading.value = true;
  try {
    const [t, o, e] = await Promise.all([
      role.value === 'inspector' ? apiListTasks() : apiListTasks(),
      role.value === 'inspector' || role.value === 'rectifier' ? apiListOrders({}) : Promise.resolve([]),
      role.value === 'supervisor' ? apiListEscalations('open') : Promise.resolve([]),
    ]);
    tasks.value = t;
    orders.value = o;
    escalations.value = e;
  } finally {
    loading.value = false;
  }
}

function openTask(id: number) {
  router.push(`/tasks/${id}`);
}

onMounted(load);
</script>

<style scoped>
.stat-row { margin-bottom: 16px; }
.stat-card { cursor: pointer; }
.stat-label { color: #6b7280; font-size: 13px; }
.stat-value { font-size: 30px; font-weight: 700; margin-top: 6px; }
.card-header { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
</style>
