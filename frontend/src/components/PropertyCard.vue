<template>
  <el-card shadow="hover" class="property-card">
    <template #header>
      <div class="card-header">
        <strong>{{ item.community }}</strong>
        <el-tag>{{ item.status }}</el-tag>
      </div>
    </template>
    <p>{{ item.region }} · {{ item.layout }} · {{ item.area }}㎡</p>
    <p class="rent">¥{{ item.rent }}/月，押金 ¥{{ item.deposit }}</p>
    <div class="facility-list">
      <el-tag v-for="facility in item.facilities" :key="facility" size="small">{{ facility }}</el-tag>
    </div>
    <el-button type="primary" class="full">预约看房</el-button>
  </el-card>
</template>

<script setup lang="ts">
import type { PropertyItem } from '../types/domain';

defineProps<{ item: PropertyItem }>();
</script>
