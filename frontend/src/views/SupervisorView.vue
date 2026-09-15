<template>
  <el-card shadow="never">
    <template #header>
      <div class="head">
        <el-radio-group v-model="statusFilter" @change="load">
          <el-radio-button value="open">待处置</el-radio-button>
          <el-radio-button value="resolved">已处置</el-radio-button>
        </el-radio-group>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>
    </template>

    <el-table v-loading="loading" :data="escalations" stripe>
      <el-table-column label="对象" width="110">
        <template #default="{ row }">
          <el-tag :type="row.target_type === 'task' ? 'primary' : 'warning'">
            {{ row.target_type === 'task' ? '巡检任务' : '整改单' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="target_code" label="编号" width="190" />
      <el-table-column prop="target_title" label="事项" min-width="200" />
      <el-table-column label="升级原因" min-width="240">
        <template #default="{ row }">
          <div>{{ row.reason }}</div>
          <div class="muted">超期时点：{{ formatDateTime(row.overdue_at) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'open' ? 'danger' : 'success'">{{ row.status_label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="处置" width="220" fixed="right">
        <template #default="{ row }">
          <template v-if="canResolve">
            <el-button v-if="row.status === 'open'" size="small" type="primary" @click="resolve(row)">处置</el-button>
            <span v-else class="muted">{{ row.handle_note }}</span>
          </template>
          <el-button v-else size="small" @click="$router.push(`/tasks/${row.target_id}`)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { Refresh } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { apiListEscalations, apiResolveEscalation } from '../api';
import type { Escalation } from '../types/domain';
import { formatDateTime } from '../utils/format';
import { useAuth } from '../stores/auth';

const auth = useAuth();
const canResolve = computed(() => auth.isRole('supervisor'));
const statusFilter = ref<'open' | 'resolved'>('open');
const escalations = ref<Escalation[]>([]);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    escalations.value = await apiListEscalations(statusFilter.value);
  } finally {
    loading.value = false;
  }
}

async function resolve(row: Escalation) {
  const { value } = await ElMessageBox.prompt('请填写处置说明（如重新分派、延长期限等）', '处置升级单', {
    confirmButtonText: '确认处置',
    inputValidator: (v) => !!v?.trim() || '请填写处置说明',
  });
  await apiResolveEscalation(row.id, value.trim());
  ElMessage.success('已处置');
  load();
}

onMounted(load);
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; }
.muted { color: #9ca3af; font-size: 12px; }
</style>
