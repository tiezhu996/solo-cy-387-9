<template>
  <el-dialog
    :model-value="visible" title="停用人员并交接待办" width="520px"
    @update:model-value="(v: boolean) => emit('update:visible', v)"
  >
    <el-alert type="warning" :closable="false" class="tip"
      :title="`停用「${user?.name || ''}」后，其名下未完成的${targetLabel}将在同一事务内交接，其他人员可继续处理；历史记录保留，重新启用不会自动拿回。`" />
    <el-radio-group v-model="mode" class="mode">
      <el-radio value="pool">退回公共待领池</el-radio>
      <el-radio value="takeover">指定接管人</el-radio>
    </el-radio-group>
    <el-select v-if="mode === 'takeover'" v-model="takeoverId"
      :placeholder="`选择${roleLabel}接管`" style="width: 100%">
      <el-option
        v-for="u in candidates" :key="u.id"
        :label="`${u.name}（${u.username}）`" :value="u.id"
      />
    </el-select>
    <p v-if="mode === 'pool'" class="hint">在办{{ targetLabel }}将被重置为可领取（保留期限与进度），挂起升级单一并解除。</p>
    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="danger" :loading="loading" @click="confirm">确认停用并交接</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { apiListUsers, apiSetUserActive } from '../api';
import type { User } from '../types/domain';

const props = defineProps<{ visible: boolean; user: User | null }>();
const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void;
  (e: 'done'): void;
}>();

const mode = ref<'pool' | 'takeover'>('pool');
const takeoverId = ref<number | null>(null);
const candidates = ref<User[]>([]);
const loading = ref(false);

const roleLabel = computed(() => props.user?.roleLabel || '人员');
const targetLabel = computed(() =>
  props.user?.role === 'inspector' ? '巡检任务' :
  props.user?.role === 'rectifier' ? '整改单' : '待办',
);

watch(
  () => props.visible,
  async (v) => {
    if (v && props.user) {
      mode.value = 'pool';
      takeoverId.value = null;
      candidates.value = (await apiListUsers(props.user.role)).filter(
        (u) => u.is_active && u.id !== props.user!.id,
      );
    }
  },
);

async function confirm() {
  if (mode.value === 'takeover' && !takeoverId.value) {
    ElMessage.warning('请选择接管人');
    return;
  }
  loading.value = true;
  try {
    const res = await apiSetUserActive(props.user!.id, false, mode.value === 'takeover' ? takeoverId.value! : undefined);
    const h = (res as unknown as { handoff?: { task_count: number; order_count: number; takeover: string | null } }).handoff;
    if (h) {
      ElMessage.success(
        `已停用，交接巡检任务 ${h.task_count} 个、整改单 ${h.order_count} 张` +
        (h.takeover ? `（接管人：${h.takeover}）` : '（已退回公共池）'),
      );
    } else {
      ElMessage.success('已停用');
    }
    emit('update:visible', false);
    emit('done');
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.tip { margin-bottom: 14px; }
.mode { margin-bottom: 12px; }
.hint { color: #9ca3af; font-size: 12px; margin-top: 8px; }
</style>
