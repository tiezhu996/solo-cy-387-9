<template>
  <div class="login-page">
    <el-card class="login-card" shadow="always">
      <div class="brand">
        <h1>公共区域巡检整改闭环</h1>
        <p>发布 · 巡检 · 整改 · 复验 · 升级</p>
      </div>
      <el-form label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="登录名">
          <el-input v-model="username" placeholder="如 xunjian1" size="large" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" type="password" show-password placeholder="demo123456" size="large" @keyup.enter="handleLogin" />
        </el-form-item>
        <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="handleLogin">
          登 录
        </el-button>
      </el-form>

      <el-divider>演示账号（点击快捷登录，密码统一 demo123456）</el-divider>
      <div v-loading="accountsLoading" class="demo-accounts">
        <el-tag
          v-for="acc in accounts"
          :key="acc.id"
          class="demo-tag"
          :type="roleTagType(acc.role)"
          effect="plain"
          @click="quickLogin(acc.username)"
        >
          {{ acc.roleLabel }} · {{ acc.name }}
        </el-tag>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { apiDemoAccounts } from '../api';
import { useAuth } from '../stores/auth';
import type { Role, User } from '../types/domain';

const username = ref('');
const password = ref('demo123456');
const loading = ref(false);
const accounts = ref<User[]>([]);
const accountsLoading = ref(false);
const auth = useAuth();
const router = useRouter();
const route = useRoute();

onMounted(async () => {
  accountsLoading.value = true;
  try {
    accounts.value = await apiDemoAccounts();
  } finally {
    accountsLoading.value = false;
  }
});

function roleTagType(role: Role) {
  return ({ property: 'warning', inspector: 'primary', rectifier: 'success', supervisor: 'danger' } as const)[role];
}

function quickLogin(name: string) {
  username.value = name;
  handleLogin();
}

async function handleLogin() {
  if (!username.value) {
    ElMessage.warning('请输入登录名');
    return;
  }
  loading.value = true;
  try {
    const user = await auth.login(username.value.trim(), password.value);
    ElMessage.success(`欢迎，${user.name}`);
    router.replace((route.query.redirect as string) || '/workbench');
  } catch {
    // 错误提示已由请求封装统一弹出
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1d4ed8 0%, #0f766e 100%);
  padding: 24px;
}
.login-card {
  width: 460px;
  border-radius: 14px;
}
.brand {
  text-align: center;
  margin-bottom: 18px;
}
.brand h1 {
  font-size: 22px;
  color: #1f2937;
  margin: 0 0 6px;
}
.brand p {
  color: #6b7280;
  font-size: 13px;
  margin: 0;
}
.demo-accounts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}
.demo-tag {
  cursor: pointer;
  padding: 6px 10px;
}
</style>
