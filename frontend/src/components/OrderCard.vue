<template>
  <el-card class="order-card" shadow="never">
    <template #header>
      <div class="order-head">
        <div>
          <el-tag :type="ORDER_STATUS_TYPE[order.status]">{{ order.status_label }}</el-tag>
          <span class="order-code">{{ order.code }}</span>
          <el-tag size="small" type="info" effect="plain">第{{ order.round }}轮</el-tag>
          <el-tag v-if="order.overdue" size="small" type="danger" effect="plain">已超期</el-tag>
        </div>
        <div class="muted">整改期限：{{ formatDateTime(order.due_at) }} ｜ 负责人：{{ order.assignee_name || '待领取' }}</div>
      </div>
    </template>

    <el-descriptions :column="1" border size="small">
      <el-descriptions-item label="来源检查项">{{ order.source_item_name }}（{{ order.source_label }}）</el-descriptions-item>
      <el-descriptions-item label="问题描述">{{ order.issue_description }}</el-descriptions-item>
      <el-descriptions-item label="问题照片">
        <el-image
          v-for="(p, i) in order.issue_photos" :key="i" :src="p"
          :preview-src-list="order.issue_photos" :initial-index="i"
          fit="cover" class="thumb"
        />
        <span v-if="!order.issue_photos?.length" class="muted">无</span>
      </el-descriptions-item>
    </el-descriptions>

    <!-- 历轮整改与复验记录 -->
    <el-collapse v-if="order.resolutions?.length" class="history">
      <el-collapse-item :title="`整改/复验记录（${order.resolutions?.length || 0}）`" name="h">
        <el-timeline>
          <template v-for="r in order.resolutions" :key="`r${r.id}`">
            <el-timeline-item :timestamp="formatDateTime(r.created_at)" type="primary" placement="top">
              第{{ r.round }}轮整改 · {{ r.rectifier_name }}：{{ r.note }}
              <div v-if="r.photos.length" class="thumbs">
                <el-image v-for="(p, i) in r.photos" :key="i" :src="p" :preview-src-list="r.photos" :initial-index="i" fit="cover" class="thumb" />
              </div>
            </el-timeline-item>
          </template>
          <el-timeline-item
            v-for="c in order.rechecks" :key="`c${c.id}`"
            :timestamp="formatDateTime(c.created_at)" :type="c.passed ? 'success' : 'danger'" placement="top"
          >
            第{{ c.round }}轮复验 · {{ c.inspector_name }}：{{ c.passed ? '通过' : '驳回' }} {{ c.note }}
          </el-timeline-item>
        </el-timeline>
      </el-collapse-item>
    </el-collapse>

    <!-- 操作区 -->
    <div class="actions">
      <template v-if="role === 'rectifier'">
        <el-button v-if="['pending', 'returned'].includes(order.status) && !order.assignee"
          type="primary" :loading="busy" @click="claim">
          {{ order.status === 'returned' ? '承接驳回重做' : '领取整改单' }}
        </el-button>
        <template v-if="mine && ['processing', 'returned'].includes(order.status)">
          <el-input v-model="note" type="textarea" :rows="2" maxlength="500" show-word-limit
            placeholder="请描述整改处理情况" class="action-input" />
          <PhotoUploader v-model="photos" />
          <el-button type="primary" :loading="busy" @click="submitResolution">提交处理结果</el-button>
        </template>
      </template>

      <template v-if="role === 'inspector' && isTaskAssignee">
        <template v-if="order.status === 'submitted'">
          <el-input v-model="recheckNote" type="textarea" :rows="2" maxlength="500"
            placeholder="复验说明（驳回时必填）" class="action-input" />
          <el-button type="success" :loading="busy" @click="recheck(true)">复验通过</el-button>
          <el-button type="danger" plain :loading="busy" @click="recheck(false)">复验驳回</el-button>
        </template>
        <el-button v-if="order.status === 'verified'" type="success" :loading="busy" @click="close">关闭整改单</el-button>
      </template>

      <el-button v-if="role === 'property' && ['pending', 'processing', 'returned', 'submitted'].includes(order.status)"
        plain @click="reassignVisible = true">重新分派</el-button>
    </div>

    <el-dialog v-model="reassignVisible" title="重新分派整改单" width="420px">
      <el-select v-model="newRectifierId" placeholder="选择整改人" style="width: 100%">
        <el-option v-for="u in rectifiers" :key="u.id" :label="u.name" :value="u.id" />
      </el-select>
      <template #footer>
        <el-button @click="reassignVisible = false">取消</el-button>
        <el-button type="primary" @click="reassign">确认分派</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { ElMessage } from 'element-plus';
import {
  apiClaimOrder, apiCloseOrder, apiListUsers, apiReassignOrder,
  apiRecheckOrder, apiSubmitOrder,
} from '../api';
import { ORDER_STATUS_TYPE, type RectificationOrder, type Role, type User } from '../types/domain';
import { formatDateTime } from '../utils/format';
import PhotoUploader from './PhotoUploader.vue';

const props = defineProps<{
  order: RectificationOrder;
  role: Role;
  currentUserId: number | null;
  isTaskAssignee: boolean;
}>();
const emit = defineEmits<{ (e: 'changed'): void }>();

const busy = ref(false);
const note = ref('');
const photos = ref<string[]>([]);
const recheckNote = ref('');
const reassignVisible = ref(false);
const newRectifierId = ref<number | null>(null);
const rectifiers = ref<User[]>([]);

const mine = computed(() => props.order.assignee === props.currentUserId);

onMounted(async () => {
  if (props.role === 'property') rectifiers.value = (await apiListUsers('rectifier')).filter((u) => u.is_active);
});

async function run(fn: () => Promise<unknown>, okMsg: string) {
  busy.value = true;
  try {
    await fn();
    ElMessage.success(okMsg);
    emit('changed');
  } catch {
    // 统一错误提示
  } finally {
    busy.value = false;
  }
}

const claim = () => run(() => apiClaimOrder(props.order.id), '领取成功');
function submitResolution() {
  if (!note.value.trim()) {
    ElMessage.warning('请填写处理说明');
    return;
  }
  run(() => apiSubmitOrder(props.order.id, note.value.trim(), photos.value), '处理结果已提交，等待复验');
}
function recheck(passed: boolean) {
  if (!passed && !recheckNote.value.trim()) {
    ElMessage.warning('驳回时请填写复验说明');
    return;
  }
  run(() => apiRecheckOrder(props.order.id, passed, recheckNote.value.trim()), passed ? '复验通过' : '已驳回，进入新一轮整改');
}
const close = () => run(() => apiCloseOrder(props.order.id), '整改单已关闭');
async function reassign() {
  if (!newRectifierId.value) {
    ElMessage.warning('请选择整改人');
    return;
  }
  await run(() => apiReassignOrder(props.order.id, newRectifierId.value!), '重新分派成功');
  reassignVisible.value = false;
}
</script>

<style scoped>
.order-card { margin-bottom: 14px; }
.order-head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px; }
.order-code { font-weight: 700; margin: 0 8px; }
.muted { color: #9ca3af; font-size: 12px; }
.thumb { width: 72px; height: 72px; border-radius: 6px; margin-right: 6px; }
.thumbs { margin-top: 4px; }
.history { margin-top: 10px; }
.actions { margin-top: 12px; }
.action-input { margin-bottom: 8px; max-width: 520px; }
</style>
