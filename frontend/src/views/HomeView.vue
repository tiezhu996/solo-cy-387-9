<template>
  <main class="page">
    <section class="toolbar">
      <div>
        <h1>RentFind 租房平台</h1>
        <p>房源搜索、预约看房、合同管理和物业报修集中处理。</p>
      </div>
      <el-segmented v-model="mode" :options="['列表视图', '地图视图']" />
    </section>

    <section class="filters">
      <el-input v-model="region" placeholder="区域" />
      <el-input-number v-model="maxRent" :min="1000" :step="500" />
      <el-select v-model="layout" placeholder="户型">
        <el-option label="全部" value="全部" />
        <el-option label="一室一厅" value="一室一厅" />
        <el-option label="两室一厅" value="两室一厅" />
        <el-option label="三室两厅" value="三室两厅" />
      </el-select>
    </section>

    <section v-if="mode === '地图视图'" class="map-panel">高德地图区域：按经纬度展示房源点位，当前示例加载 {{ filtered.length }} 套房源。</section>
    <section class="grid">
      <PropertyCard v-for="item in filtered" :key="item.id" :item="item" />
    </section>

    <section class="repair">
      <h2>物业报修</h2>
      <el-select v-model="faultType">
        <el-option label="水电" value="水电" />
        <el-option label="门锁" value="门锁" />
        <el-option label="管道" value="管道" />
        <el-option label="家电" value="家电" />
        <el-option label="其他" value="其他" />
      </el-select>
      <el-input v-model="description" placeholder="描述故障情况" />
      <el-button type="success" @click="submitRepair">提交工单</el-button>
      <span>{{ notice }}</span>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import PropertyCard from '../components/PropertyCard.vue';
import { createRepair, getProperties } from '../api/client';
import type { PropertyItem } from '../types/domain';

const properties = ref<PropertyItem[]>([]);
const mode = ref('列表视图');
const region = ref('');
const maxRent = ref(7000);
const layout = ref('全部');
const faultType = ref('水电');
const description = ref('');
const notice = ref('等待提交');

onMounted(async () => {
  properties.value = await getProperties();
});

const filtered = computed(() => properties.value.filter((item) => {
  const hitRegion = !region.value || item.region.includes(region.value);
  const hitRent = item.rent <= maxRent.value;
  const hitLayout = layout.value === '全部' || item.layout === layout.value;
  return hitRegion && hitRent && hitLayout;
}));

async function submitRepair() {
  const ticket = await createRepair({ faultType: faultType.value, description: description.value });
  notice.value = `工单 ${ticket.id} 已提交：${ticket.status}`;
}
</script>
