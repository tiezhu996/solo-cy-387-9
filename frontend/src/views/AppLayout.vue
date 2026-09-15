<template>
  <el-container class="app-shell">
    <el-aside width="220px" class="sidebar">
      <div class="logo">巡检整改闭环</div>
      <el-menu :default-active="activeMenu" router class="menu" background-color="#0f2e4d" text-color="#c7d6e5" active-text-color="#ffd04b">
        <el-menu-item index="/workbench">
          <el-icon><Monitor /></el-icon><span>工作台</span>
        </el-menu-item>
        <el-menu-item v-if="isRole('property')" index="/people">
          <el-icon><UserFilled /></el-icon><span>人员管理</span>
        </el-menu-item>
        <el-menu-item v-if="isRole('inspector')" index="/tasks">
          <el-icon><Search /></el-icon><span>巡检任务</span>
        </el-menu-item>
        <el-menu-item v-if="isRole('rectifier')" index="/orders">
          <el-icon><Tools /></el-icon><span>整改单</span>
        </el-menu-item>
        <el-menu-item v-if="isRole('supervisor') || isRole('property')" index="/escalations">
          <el-icon><Warning /></el-icon><span>超期升级台</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-title">{{ roleTitle }}工作台</div>
        <div class="header-right">
          <el-tag :type="roleTagType" effect="dark">{{ user?.roleLabel }}</el-tag>
          <span class="user-name">{{ user?.name }}</span>
          <el-button link type="primary" @click="handleLogout">退出登录</el-button>
        </div>
      </el-header>
      <el-main class="main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { Monitor, UserFilled, Search, Tools, Warning } from '@element-plus/icons-vue';
import { useAuth } from '../stores/auth';
import type { Role } from '../types/domain';

const auth = useAuth();
const router = useRouter();
const route = useRoute();
const user = computed(() => auth.state.user);
const isRole = (...roles: Role[]) => auth.isRole(...roles);
const activeMenu = computed(() => route.path.startsWith('/tasks/') ? '/tasks' : route.path);

const roleTitle = computed(() => `${user.value?.roleLabel || ''} `);
const roleTagType = computed(() => {
  const map: Record<Role, 'warning' | 'primary' | 'success' | 'danger'> = {
    property: 'warning', inspector: 'primary', rectifier: 'success', supervisor: 'danger',
  };
  return user.value ? map[user.value.role] : 'primary';
});

async function handleLogout() {
  await auth.logout();
  router.replace('/login');
}
</script>

<style scoped>
.app-shell { min-height: 100vh; }
.sidebar { background: #0f2e4d; }
.logo {
  color: #fff; font-size: 17px; font-weight: 700; text-align: center;
  padding: 20px 10px; border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.menu { border-right: none; }
.header {
  background: #fff; display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid #e5e7eb;
}
.header-title { font-size: 16px; font-weight: 600; color: #1f2937; }
.header-right { display: flex; align-items: center; gap: 10px; }
.user-name { color: #374151; font-size: 14px; }
.main { background: #f3f5f8; padding: 18px; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
