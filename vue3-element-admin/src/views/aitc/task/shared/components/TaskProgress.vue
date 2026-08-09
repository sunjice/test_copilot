<template>
  <el-card class="mb-3">
    <div class="flex items-center gap-2 mb-4">
      <slot name="header-left" />
      <span class="text-lg font-bold">任务 #{{ taskId }} 明细</span>
      <slot name="header-right" />
    </div>

    <el-descriptions v-if="task" :column="4" border size="small" class="mb-4">
      <el-descriptions-item label="任务类型">
        <el-tag :type="taskTypeTag(task.task_type)" size="small">{{ taskTypeLabel(task.task_type) }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="项目">{{ task.project_name }}</el-descriptions-item>
      <el-descriptions-item label="套件" :span="2">{{ task.suite_name }}</el-descriptions-item>
      <el-descriptions-item label="模型">{{ task.model || '—' }}</el-descriptions-item>
      <el-descriptions-item label="创建人">{{ task.create_by || '—' }}</el-descriptions-item>
      <el-descriptions-item label="创建时间">{{ task.create_time || '—' }}</el-descriptions-item>
      <el-descriptions-item label="状态">
        <el-tag :type="statusTag(task.status)" size="small">{{ statusLabel(task.status) }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="进度">
        <el-progress
          :percentage="task.total_count ? Math.round(task.done_count / task.total_count * 100) : 0"
          :status="task.status === TaskStatusEnum.FAILED ? 'exception' : task.status === TaskStatusEnum.COMPLETED ? 'success' : undefined"
          :stroke-width="14"
        />
        <span class="text-xs text-gray-500">{{ task.done_count }} / {{ task.total_count }}</span>
      </el-descriptions-item>
      <el-descriptions-item label="Token 入">{{ task.input_tokens }}</el-descriptions-item>
      <el-descriptions-item label="Token 出">{{ task.output_tokens }}</el-descriptions-item>
      <el-descriptions-item v-if="task.error_msg" label="错误信息" :span="4">
        <span class="text-red-500">{{ task.error_msg }}</span>
      </el-descriptions-item>
    </el-descriptions>

    <div class="flex gap-2">
      <el-button
        v-if="task?.status === TaskStatusEnum.QUEUED || task?.status === TaskStatusEnum.RUNNING"
        type="danger"
        v-hasPerm="'aitc:task:stop'"
        @click="$emit('stop')"
      >
        停止任务
      </el-button>
      <el-button
        v-if="task?.status === TaskStatusEnum.COMPLETED"
        type="warning"
        v-hasPerm="'aitc:task:confirm'"
        @click="$emit('goReview')"
      >
        审核任务结果
      </el-button>
      <el-button
        v-if="task?.status === TaskStatusEnum.COMPLETED || task?.status === TaskStatusEnum.FAILED || task?.status === TaskStatusEnum.CONFIRMED || task?.status === TaskStatusEnum.STOPPED"
        type="danger"
        v-hasPerm="'aitc:task:create'"
        @click="$emit('rerun')"
      >
        重跑任务
      </el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import type { TaskVO } from "@/api/aitc/task";
import { TaskStatusEnum } from "@/enums/aitc";
import { taskTypeLabel, taskTypeTag, statusLabel, statusTag } from "../../../constants";

defineProps<{
  taskId: string;
  task: TaskVO | null;
}>();

defineEmits<{
  goReview: [];
  rerun: [];
  stop: [];
}>();
</script>
