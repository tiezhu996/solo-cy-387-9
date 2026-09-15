<template>
  <el-dialog
    :model-value="visible" title="提交巡检结果" width="720px"
    @update:model-value="(v: boolean) => emit('update:visible', v)"
  >
    <el-alert type="info" :closable="false" class="tip"
      title="逐项填写检查结果；选择「异常」时必须描述问题，提交后将自动生成整改单并保留来源。" />
    <el-form label-position="top">
      <el-form-item label="总体说明">
        <el-input v-model="summary" type="textarea" :rows="2" maxlength="500" show-word-limit placeholder="可补充总体情况（选填）" />
      </el-form-item>

      <el-card v-for="(item, idx) in items" :key="item.name" shadow="never" class="item-card">
        <div class="item-head">
          <span class="item-name">{{ idx + 1 }}. {{ item.name }}</span>
          <el-radio-group v-model="item.result">
            <el-radio-button label="normal">正常</el-radio-button>
            <el-radio-button label="issue">异常</el-radio-button>
          </el-radio-group>
        </div>
        <template v-if="item.result === 'issue'">
          <el-input v-model="item.description" type="textarea" :rows="2" maxlength="500"
            placeholder="请描述现场问题（必填）" class="issue-input" />
          <PhotoUploader v-model="item.photos" />
        </template>
      </el-card>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="submit">提交巡检结果</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { apiSubmitTask } from '../api';
import type { InspectionTask, ItemResult } from '../types/domain';
import PhotoUploader from './PhotoUploader.vue';

const props = defineProps<{ visible: boolean; task: InspectionTask }>();
const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void;
  (e: 'submitted'): void;
}>();

const summary = ref('');
const submitting = ref(false);
const items = reactive<Array<{ name: string; result: 'normal' | 'issue'; description: string; photos: string[] }>>([]);

watch(
  () => props.visible,
  (v) => {
    if (v) {
      summary.value = props.task.submission?.summary || '';
      items.splice(0, items.length,
        ...(props.task.checklist || []).map((name) => ({ name, result: 'normal' as const, description: '', photos: [] })));
    }
  },
);

async function submit() {
  const badIssue = items.find((i) => i.result === 'issue' && !i.description.trim());
  if (badIssue) {
    ElMessage.warning(`检查项「${badIssue.name}」为异常，请填写问题描述`);
    return;
  }
  if (!items.length) {
    ElMessage.warning('没有可提交的检查项');
    return;
  }
  submitting.value = true;
  try {
    const payload: ItemResult[] = items.map((i) =>
      i.result === 'issue'
        ? { name: i.name, result: 'issue', description: i.description.trim(), photos: i.photos }
        : { name: i.name, result: 'normal' },
    );
    await apiSubmitTask(props.task.id, payload, summary.value.trim());
    ElMessage.success('巡检结果已提交');
    emit('update:visible', false);
    emit('submitted');
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.tip { margin-bottom: 12px; }
.item-card { margin-bottom: 10px; }
.item-head { display: flex; justify-content: space-between; align-items: center; }
.item-name { font-weight: 600; color: #1f2937; }
.issue-input { margin: 10px 0; }
</style>
