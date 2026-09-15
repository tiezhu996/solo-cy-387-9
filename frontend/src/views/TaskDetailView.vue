<template>
  <div v-loading="loading">
    <el-page-header content="任务详情" @back="$router.back()" class="page-head" />

    <template v-if="task">
      <el-card shadow="never" class="block">
        <div class="task-head">
          <div>
            <el-tag :type="TASK_STATUS_TYPE[task.status]" size="large">{{ task.status_label }}</el-tag>
            <el-tag v-if="task.overdue" type="danger" effect="dark" class="ml8">已超期</el-tag>
            <span class="task-title">{{ task.title }}</span>
            <span class="muted">{{ task.code }}</span>
          </div>
          <div class="head-actions">
            <!-- 巡检员操作 -->
            <template v-if="role === 'inspector'">
              <el-button
                v-if="['pending', 'submitted', 'returned'].includes(task.status) && !task.assignee"
                type="primary" :loading="busy" @click="claim"
              >{{ task.status === 'pending' ? '领取任务' : '领取并接管复验' }}</el-button>
              <el-button v-if="isMine && task.status === 'claimed'" type="primary" @click="submitVisible = true">提交巡检结果</el-button>
              <el-button v-if="isMine && allVerified" type="success" :loading="busy" @click="closeTask">闭环关闭</el-button>
            </template>
            <!-- 物业操作 -->
            <template v-if="role === 'property' && task.status !== 'done'">
              <el-button @click="rescheduleVisible = true">改期</el-button>
              <el-button type="warning" plain @click="reassignVisible = true">重新分派</el-button>
            </template>
            <el-button @click="load">刷新</el-button>
          </div>
        </div>

        <el-descriptions :column="3" border size="small" class="desc">
          <el-descriptions-item label="楼栋/区域">{{ task.building_name }} · {{ task.area_name }}</el-descriptions-item>
          <el-descriptions-item label="周期">{{ task.period_label }}</el-descriptions-item>
          <el-descriptions-item label="当前负责人">{{ task.assignee_name || '公共池待领取' }}</el-descriptions-item>
          <el-descriptions-item label="计划时间">{{ formatDateTime(task.scheduled_at) }}</el-descriptions-item>
          <el-descriptions-item label="巡检期限">{{ formatDateTime(task.due_at) }}</el-descriptions-item>
          <el-descriptions-item label="发布人">{{ task.publisher_name || '—' }}</el-descriptions-item>
          <el-descriptions-item label="检查项" :span="3">
            <el-tag v-for="(c, i) in task.checklist" :key="i" size="small" class="check-tag">{{ c }}</el-tag>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 巡检提交结果 -->
        <el-divider content-position="left">现场巡检结果</el-divider>
        <template v-if="task.submission">
          <p class="muted">提交人：{{ task.submission.inspector_name }} · {{ formatDateTime(task.submission.created_at) }}
            <span v-if="task.submission.summary"> · {{ task.submission.summary }}</span>
          </p>
          <el-table :data="task.submission.items" size="small" border>
            <el-table-column prop="name" label="检查项" min-width="160" />
            <el-table-column label="结果" width="100">
              <template #default="{ row }">
                <el-tag :type="row.result === 'normal' ? 'success' : 'danger'">
                  {{ row.result === 'normal' ? '正常' : '异常' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="问题描述" min-width="200" />
            <el-table-column label="照片" width="160">
              <template #default="{ row }">
                <el-image v-for="(p, i) in row.photos" :key="i" :src="p" :preview-src-list="row.photos"
                  :initial-index="i" fit="cover" class="thumb" />
                <span v-if="!row.photos?.length" class="muted">—</span>
              </template>
            </el-table-column>
          </el-table>
        </template>
        <el-empty v-else description="尚未提交巡检结果" :image-size="60" />
      </el-card>

      <!-- 整改单 -->
      <el-card shadow="never" class="block">
        <template #header><span class="card-title">整改单（{{ orders.length }}）— 复验通过后才能关闭</span></template>
        <el-empty v-if="!orders.length" description="无整改单" :image-size="60" />
        <OrderCard
          v-for="o in orders" :key="o.id" :order="o"
          :role="role" :current-user-id="user?.id || null" :is-task-assignee="isMine"
          @changed="load"
        />
      </el-card>

      <!-- 闭环时间线 -->
      <el-card shadow="never" class="block">
        <template #header><span class="card-title">闭环状态历史（刷新后完整保留）</span></template>
        <TimelineView :entries="timeline" />
      </el-card>
    </template>

    <!-- 提交巡检 -->
    <SubmitInspectionDialog v-if="task" v-model:visible="submitVisible" :task="task" @submitted="load" />

    <!-- 改期 -->
    <el-dialog v-model="rescheduleVisible" title="任务改期" width="460px">
      <el-form label-position="top">
        <el-form-item label="计划巡检时间"><el-date-picker v-model="rescheduleForm.scheduled_at" type="datetime" style="width: 100%" /></el-form-item>
        <el-form-item label="巡检期限"><el-date-picker v-model="rescheduleForm.due_at" type="datetime" style="width: 100%" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rescheduleVisible = false">取消</el-button>
        <el-button type="primary" @click="reschedule">确认改期</el-button>
      </template>
    </el-dialog>

    <!-- 重新分派 -->
    <el-dialog v-model="reassignVisible" title="重新分派" width="460px">
      <el-radio-group v-model="assignMode" class="assign-mode">
        <el-radio value="user">分派给巡检员</el-radio>
        <el-radio value="pool">退回公共待领池</el-radio>
      </el-radio-group>
      <el-select v-if="assignMode === 'user'" v-model="newInspectorId" placeholder="选择巡检员" style="width: 100%">
        <el-option v-for="u in inspectors" :key="u.id" :label="u.name" :value="u.id" />
      </el-select>
      <template #footer>
        <el-button @click="reassignVisible = false">取消</el-button>
        <el-button type="primary" @click="reassign">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  apiClaimTask, apiCloseTask, apiListOrders, apiListUsers,
  apiReassignTask, apiRescheduleTask, apiTask, apiTaskTimeline,
} from '../api';
import { TASK_STATUS_TYPE, type InspectionTask, type RectificationOrder, type Role, type TimelineEntry, type User } from '../types/domain';
import { formatDateTime, toIso } from '../utils/format';
import { useAuth } from '../stores/auth';
import OrderCard from '../components/OrderCard.vue';
import TimelineView from '../components/TimelineView.vue';
import SubmitInspectionDialog from '../components/SubmitInspectionDialog.vue';

const props = defineProps<{ id: string }>();
const auth = useAuth();
const user = computed(() => auth.state.user);
const role = computed<Role>(() => auth.state.user!.role);

const loading = ref(false);
const busy = ref(false);
const task = ref<InspectionTask | null>(null);
const orders = ref<RectificationOrder[]>([]);
const timeline = ref<TimelineEntry[]>([]);
const inspectors = ref<User[]>([]);

const submitVisible = ref(false);
const rescheduleVisible = ref(false);
const reassignVisible = ref(false);
const assignMode = ref<'user' | 'pool'>('user');
const newInspectorId = ref<number | null>(null);
const rescheduleForm = reactive({ scheduled_at: null as Date | null, due_at: null as Date | null });

const isMine = computed(() => !!task.value && task.value.assignee === user.value?.id);
const allVerified = computed(() => orders.value.length > 0 && orders.value.every((o) => ['verified', 'closed'].includes(o.status)));

async function load() {
  loading.value = true;
  try {
    const id = Number(props.id);
    const [t, os, tl] = await Promise.all([
      apiTask(id),
      apiListOrders({ task: String(id) }),
      apiTaskTimeline(id),
    ]);
    task.value = t;
    orders.value = os;
    timeline.value = tl;
  } finally {
    loading.value = false;
  }
}

async function run(fn: () => Promise<unknown>, msg: string) {
  busy.value = true;
  try {
    await fn();
    ElMessage.success(msg);
    await load();
  } catch {
    // 统一提示
  } finally {
    busy.value = false;
  }
}

const claim = () => run(() => apiClaimTask(Number(props.id)), '领取成功');
const closeTask = () =>
  ElMessageBox.confirm('所有整改单已复验通过，确认关闭该巡检任务？', '闭环关闭', { type: 'warning' })
    .then(() => run(() => apiCloseTask(Number(props.id)), '任务已闭环关闭'))
    .catch(() => undefined);

function openReschedule() {
  if (task.value) {
    rescheduleForm.scheduled_at = new Date(task.value.scheduled_at);
    rescheduleForm.due_at = new Date(task.value.due_at);
  }
}
async function reschedule() {
  if (!rescheduleForm.scheduled_at || !rescheduleForm.due_at) {
    ElMessage.warning('请选择时间');
    return;
  }
  await run(
    () => apiRescheduleTask(Number(props.id), toIso(rescheduleForm.scheduled_at), toIso(rescheduleForm.due_at)),
    '改期成功',
  );
  rescheduleVisible.value = false;
}
async function reassign() {
  if (assignMode.value === 'user' && !newInspectorId.value) {
    ElMessage.warning('请选择巡检员');
    return;
  }
  await run(
    () => apiReassignTask(Number(props.id), assignMode.value === 'user' ? newInspectorId.value : null),
    assignMode.value === 'user' ? '重新分派成功' : '已退回公共待领池',
  );
  reassignVisible.value = false;
}

onMounted(async () => {
  await load();
  openReschedule();
  if (role.value === 'property') inspectors.value = (await apiListUsers('inspector')).filter((u) => u.is_active);
});
</script>

<style scoped>
.page-head { margin-bottom: 14px; }
.block { margin-bottom: 16px; }
.task-head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }
.task-title { font-size: 18px; font-weight: 700; margin-left: 8px; color: #1f2937; }
.muted { color: #9ca3af; font-size: 12px; }
.ml8 { margin-left: 8px; }
.desc { margin-top: 6px; }
.check-tag { margin: 2px 6px 2px 0; }
.card-title { font-weight: 600; }
.thumb { width: 60px; height: 60px; border-radius: 4px; margin-right: 6px; }
.assign-mode { margin-bottom: 12px; }
</style>
