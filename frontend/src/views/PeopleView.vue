<template>
  <el-tabs v-model="tab" class="tabs">
    <el-tab-pane label="人员管理" name="people">
      <el-card shadow="never">
        <template #header>
          <div class="head">
            <span>人员（停用后无法登录，待办需重新分派；历史记录保留）</span>
            <el-button type="primary" @click="openCreate">新增人员</el-button>
          </div>
        </template>
        <el-table v-loading="loading" :data="users" stripe>
          <el-table-column prop="username" label="登录名" width="140" />
          <el-table-column prop="name" label="姓名" width="120" />
          <el-table-column label="角色" width="120">
            <template #default="scope">
              <el-tag :type="roleType(scope.row.role)">{{ scope.row.roleLabel }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="phone" label="电话" width="160" />
          <el-table-column label="状态" width="100">
            <template #default="scope">
              <el-tag :type="scope.row.is_active ? 'success' : 'info'">
                {{ scope.row.is_active ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="scope">
              <el-button
                size="small"
                :type="scope.row.is_active ? 'danger' : 'success'"
                plain
                @click="toggleActive(scope.row)"
              >
                {{ scope.row.is_active ? '停用' : '启用' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-tab-pane>

    <el-tab-pane label="楼栋 / 区域" name="org">
      <el-row :gutter="14">
        <el-col :span="10">
          <el-card shadow="never">
            <template #header>
              <div class="head">
                <span>楼栋</span>
                <el-button type="primary" size="small" @click="addBuilding">新增</el-button>
              </div>
            </template>
            <el-table
              :data="buildings"
              size="small"
              highlight-current-row
              @row-click="selectBuilding"
            >
              <el-table-column prop="code" label="编号" width="90" />
              <el-table-column prop="name" label="名称" />
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="14">
          <el-card shadow="never">
            <template #header>
              <div class="head">
                <span>区域{{ areaTitle }}</span>
                <el-button
                  type="primary"
                  size="small"
                  :disabled="!currentBuilding"
                  @click="addArea"
                >新增区域</el-button>
              </div>
            </template>
            <el-table :data="areas" size="small">
              <el-table-column prop="code" label="编号" width="100" />
              <el-table-column prop="name" label="名称" />
              <el-table-column prop="location" label="位置" />
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </el-tab-pane>
  </el-tabs>

  <el-dialog v-model="createVisible" title="新增人员" width="420px">
    <el-form :model="createForm" label-width="80px">
      <el-form-item label="登录名">
        <el-input v-model="createForm.username" />
      </el-form-item>
      <el-form-item label="姓名">
        <el-input v-model="createForm.name" />
      </el-form-item>
      <el-form-item label="角色">
        <el-select v-model="createForm.role" style="width: 100%">
          <el-option label="巡检员" value="inspector" />
          <el-option label="整改人" value="rectifier" />
          <el-option label="主管" value="supervisor" />
          <el-option label="物业管理员" value="property" />
        </el-select>
      </el-form-item>
      <el-form-item label="电话">
        <el-input v-model="createForm.phone" />
      </el-form-item>
      <el-form-item label="初始密码">
        <el-input v-model="createForm.password" placeholder="默认 123456" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createVisible = false">取消</el-button>
      <el-button type="primary" @click="createUser">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { request } from '../api/client';
import { apiAreas, apiBuildings, apiListUsers, apiSetUserActive } from '../api';
import type { Area, Building, Role, User } from '../types/domain';

const tab = ref('people');
const loading = ref(false);
const users = ref<User[]>([]);
const buildings = ref<Building[]>([]);
const areas = ref<Area[]>([]);
const allAreas = ref<Area[]>([]);
const currentBuilding = ref<Building | null>(null);
const createVisible = ref(false);
const createForm = reactive({
  username: '',
  name: '',
  role: 'inspector' as Role,
  phone: '',
  password: '',
});

const areaTitle = computed(() =>
  currentBuilding.value ? '（' + currentBuilding.value.name + '）' : '',
);

function roleType(role: Role) {
  const map: Record<Role, 'warning' | 'primary' | 'success' | 'danger'> = {
    property: 'warning',
    inspector: 'primary',
    rectifier: 'success',
    supervisor: 'danger',
  };
  return map[role];
}

async function loadUsers() {
  loading.value = true;
  try {
    users.value = await apiListUsers();
  } finally {
    loading.value = false;
  }
}

async function loadOrg() {
  const [b, a] = await Promise.all([apiBuildings(), apiAreas()]);
  buildings.value = b;
  allAreas.value = a;
  if (!currentBuilding.value && b.length) selectBuilding(b[0]);
  filterAreas();
}

function selectBuilding(b: Building) {
  currentBuilding.value = b;
  filterAreas();
}

function filterAreas() {
  areas.value = currentBuilding.value
    ? allAreas.value.filter((x) => x.building === currentBuilding.value!.id)
    : [];
}

async function toggleActive(row: User) {
  const action = row.is_active ? '停用' : '启用';
  await ElMessageBox.confirm('确认' + action + '「' + row.name + '」？', action + '人员', {
    type: 'warning',
  });
  await apiSetUserActive(row.id, !row.is_active);
  ElMessage.success('已' + action);
  loadUsers();
}

function openCreate() {
  Object.assign(createForm, {
    username: '',
    name: '',
    role: 'inspector',
    phone: '',
    password: '',
  });
  createVisible.value = true;
}

async function createUser() {
  if (!createForm.username || !createForm.name) {
    ElMessage.warning('登录名和姓名必填');
    return;
  }
  await request('/users/', { method: 'POST', body: { ...createForm } });
  ElMessage.success('人员已创建');
  createVisible.value = false;
  loadUsers();
}

async function addBuilding() {
  const result = await ElMessageBox.prompt('楼栋名称', '新增楼栋', {
    inputValidator: (v) => !!v?.trim() || '请输入名称',
  });
  const code = 'B' + (Date.now() % 100000);
  await request('/buildings/', { method: 'POST', body: { code, name: result.value } });
  ElMessage.success('楼栋已新增');
  loadOrg();
}

async function addArea() {
  const result = await ElMessageBox.prompt('区域名称', '新增区域', {
    inputValidator: (v) => !!v?.trim() || '请输入名称',
  });
  await request('/areas/', {
    method: 'POST',
    body: {
      building: currentBuilding.value!.id,
      code: 'A' + (Date.now() % 100000),
      name: result.value,
      location: '',
    },
  });
  ElMessage.success('区域已新增');
  loadOrg();
}

onMounted(() => {
  loadUsers();
  loadOrg();
});
</script>

<style scoped>
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tabs {
  min-height: 400px;
}
</style>
