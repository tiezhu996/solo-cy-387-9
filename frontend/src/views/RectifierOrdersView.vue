<template>
  <el-card shadow="never">
    <template #header>
      <div class="head">
        <el-radio-group v-model="scope" @change="load">
          <el-radio-button value="mine">我的整改单</el-radio-button>
          <el-radio-button value="pool">待领取</el-radio-button>
          <el-radio-button value="">全部</el-radio-button>
        </el-radio-group>
        <el-radio-group v-model="statusFilter" @change="load">
          <el-radio-button value="">全部状态</el-radio-button>
          <el-radio-button v-for="(label, key) in ORDER_LABELS" :key="key" :value="key">{{ label }}</el-radio-button>
        </el-radio-group>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>
    </template>
    <el-table v-loading="loading" :data="filtered" stripe @row-click="(row: RectificationOrder) => $router.push(`/tasks/${row.task}`)" class="row-click">
      <el-table-column prop="code" label="整改单号" width="180" />
      <el-table-column label="问题/来源" min-width="240">
        <template #default="{ row }">
          <div class="strong">{{ row.issue_description }}</div>
          <div class="muted">{{ row.task_code }} · {{ row.source_item_name }} · 第{{ row.round }}轮</div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="ORDER_STATUS_TYPE[row.status as OrderStatus]">{{ row.status_label }}</el-tag>
          <el-tag v-if="row.overdue" type="danger" size="small" effect="plain" class="ml4">超期</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="assignee_name" label="负责人" width="100">
        <template #default="{ row }">{{ row.assignee_name || '待领取' }}</template>
      </el-table-column>
      <el-table-column label="整改期限" width="160">
        <template #default="{ row }">
          <span :class="{ danger: row.overdue }">{{ formatDateTime(row.due_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click.stop="$router.push(`/tasks/${row.task}`)">处理</el-button>
          <el-button
            v-if="!row.assignee && ['pending', 'returned'].includes(row.status)"
            size="small" type="primary" :loading="busyId === row.id"
            @click.stop="claim(row)"
          >{{ row.status === 'returned' ? '承接重做' : '领取' }}</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { Refresh } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { apiClaimOrder, apiListOrders } from '../api';
import { ORDER_STATUS_TYPE, type OrderStatus, type RectificationOrder } from '../types/domain';
import { formatDateTime } from '../utils/format';

const ORDER_LABELS: Record<string, string> = {
  pending: '待整改', processing: '整改中', submitted: '待复验',
  returned: '复验驳回', verified: '复验通过', closed: '已关闭',
};

const scope = ref<'mine' | 'pool' | ''>('mine');
const statusFilter = ref('');
const orders = ref<RectificationOrder[]>([]);
const loading = ref(false);
const busyId = ref<number | null>(null);

async function claim(row: RectificationOrder) {
  busyId.value = row.id;
  try {
    await apiClaimOrder(row.id);
    ElMessage.success('领取成功');
    await load();
  } catch {
    // 409 已统一提示
  } finally {
    busyId.value = null;
  }
}

const filtered = computed(() =>
  statusFilter.value ? orders.value.filter((o) => o.status === statusFilter.value) : orders.value,
);

async function load() {
  loading.value = true;
  try {
    const params: Record<string, string> = {};
    if (scope.value) params.scope = scope.value;
    orders.value = await apiListOrders(params);
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
