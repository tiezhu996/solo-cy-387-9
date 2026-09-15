<template>
  <el-dialog
    :model-value="visible" title="发布巡检任务" width="640px"
    @update:model-value="(v: boolean) => emit('update:visible', v)" @open="loadMeta"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="92px">
      <el-form-item label="任务名称" prop="title">
        <el-input v-model="form.title" placeholder="如 A栋一层大堂日巡检" />
      </el-form-item>
      <el-row :gutter="12">
        <el-col :span="12">
          <el-form-item label="楼栋" prop="building_id">
            <el-select v-model="form.building_id" placeholder="选择楼栋" style="width: 100%" @change="onBuildingChange">
              <el-option v-for="b in buildings" :key="b.id" :label="b.name" :value="b.id" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="区域" prop="area_id">
            <el-select v-model="form.area_id" placeholder="选择区域" style="width: 100%">
              <el-option v-for="a in areas" :key="a.id" :label="a.name" :value="a.id" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>
      <el-row :gutter="12">
        <el-col :span="8">
          <el-form-item label="周期" prop="period">
            <el-select v-model="form.period" style="width: 100%">
              <el-option label="每日" value="daily" />
              <el-option label="每周" value="weekly" />
              <el-option label="每月" value="monthly" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="计划时间" prop="scheduled_at">
            <el-date-picker v-model="form.scheduled_at" type="datetime" placeholder="选择时间" style="width: 100%" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="巡检期限" prop="due_at">
            <el-date-picker v-model="form.due_at" type="datetime" placeholder="选择时间" style="width: 100%" />
          </el-form-item>
        </el-col>
      </el-row>
      <el-form-item label="直接指派">
        <el-select v-model="form.assignee_id" clearable placeholder="不指派则进入公共池待领取" style="width: 100%">
          <el-option v-for="i in inspectors" :key="i.id" :label="i.name" :value="i.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="检查项" prop="checklist">
        <div style="width: 100%">
          <el-tag v-for="(item, idx) in form.checklist" :key="idx" closable class="check-tag" @close="form.checklist.splice(idx, 1)">
            {{ item }}
          </el-tag>
          <el-input
            v-if="inputVisible" ref="inputRef" v-model="inputValue" size="small"
            style="width: 160px" @keyup.enter="addCheck" @blur="addCheck"
          />
          <el-button v-else size="small" @click="showInput">+ 添加检查项</el-button>
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">发布</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { nextTick, reactive, ref } from 'vue';
import type { FormInstance, FormRules } from 'element-plus';
import { ElMessage } from 'element-plus';
import { apiAreas, apiBuildings, apiListUsers, apiPublishTask } from '../api';
import { toIso } from '../utils/format';
import type { Area, Building, User } from '../types/domain';

const props = defineProps<{ visible: boolean }>();
const emit = defineEmits<{
  (e: 'update:visible', v: boolean): void;
  (e: 'published'): void;
}>();

const formRef = ref<FormInstance>();
const buildings = ref<Building[]>([]);
const areas = ref<Area[]>([]);
const inspectors = ref<User[]>([]);
const saving = ref(false);

const form = reactive({
  title: '',
  building_id: null as number | null,
  area_id: null as number | null,
  period: 'daily',
  scheduled_at: null as Date | null,
  due_at: null as Date | null,
  assignee_id: null as number | null,
  checklist: [] as string[],
});

const rules: FormRules = {
  title: [{ required: true, message: '请输入任务名称' }],
  building_id: [{ required: true, message: '请选择楼栋' }],
  area_id: [{ required: true, message: '请选择区域' }],
  scheduled_at: [{ required: true, message: '请选择计划时间' }],
  due_at: [{ required: true, message: '请选择巡检期限' }],
};

const inputVisible = ref(false);
const inputValue = ref('');
const inputRef = ref();

async function loadMeta() {
  const [b, allAreas, users] = await Promise.all([
    apiBuildings(),
    apiAreas(),
    apiListUsers('inspector'),
  ]);
  buildings.value = b;
  areas.value = allAreas;
  inspectors.value = users.filter((u) => u.is_active);
}

function onBuildingChange() {
  form.area_id = null;
}

function showInput() {
  inputVisible.value = true;
  nextTick(() => inputRef.value?.focus());
}
function addCheck() {
  const v = inputValue.value.trim();
  if (v && !form.checklist.includes(v)) form.checklist.push(v);
  inputVisible.value = false;
  inputValue.value = '';
}

async function submit() {
  await formRef.value?.validate();
  if (form.checklist.length === 0) {
    ElMessage.warning('请至少添加一个检查项');
    return;
  }
  saving.value = true;
  try {
    await apiPublishTask({
      title: form.title,
      building_id: form.building_id!,
      area_id: form.area_id!,
      period: form.period,
      scheduled_at: toIso(form.scheduled_at),
      due_at: toIso(form.due_at),
      checklist: form.checklist,
      assignee_id: form.assignee_id,
    });
    ElMessage.success('巡检任务已发布');
    emit('update:visible', false);
    emit('published');
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.check-tag { margin: 0 8px 8px 0; }
</style>
