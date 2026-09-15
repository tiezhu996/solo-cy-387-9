<template>
  <div class="photo-uploader">
    <el-upload
      :file-list="fileList"
      list-type="picture-card"
      :http-request="customUpload"
      :on-remove="handleRemove"
      :on-preview="handlePreview"
      accept="image/*"
      multiple
    >
      <el-icon><Plus /></el-icon>
    </el-upload>
    <el-dialog v-model="previewVisible" title="照片预览" width="520px">
      <img :src="previewUrl" alt="预览" style="width: 100%" />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import { Plus } from '@element-plus/icons-vue';
import type { UploadFile, UploadFiles, UploadRequestOptions } from 'element-plus';
import { ElMessage } from 'element-plus';
import { uploadPhoto } from '../api/client';

const props = defineProps<{ modelValue: string[] }>();
const emit = defineEmits<{ (e: 'update:modelValue', value: string[]): void }>();

const fileList = ref<UploadFiles>([]);
const previewVisible = ref(false);
const previewUrl = ref('');

// 外部值（如驳回后重新整改带入）变化时同步
watch(
  () => props.modelValue,
  (urls) => {
    fileList.value = (urls || []).map((url, index) => ({
      name: `照片${index + 1}`,
      url,
      status: 'success',
      uid: index,
    })) as UploadFiles;
  },
  { immediate: true },
);

async function customUpload(options: UploadRequestOptions) {
  try {
    const { url } = await uploadPhoto(options.file as File);
    const next = [...props.modelValue, url];
    emit('update:modelValue', next);
    options.onSuccess?.({ url });
  } catch (e) {
    ElMessage.error('照片上传失败');
    options.onError?.(e as never);
  }
}

function handleRemove(_file: UploadFile, files: UploadFiles) {
  emit('update:modelValue', files.map((f) => f.url || '').filter(Boolean));
}

function handlePreview(file: UploadFile) {
  previewUrl.value = file.url || '';
  previewVisible.value = true;
}
</script>
