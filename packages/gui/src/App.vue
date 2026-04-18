<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { RouterView } from 'vue-router'
import DeadlineAlarmModal from '@/components/DeadlineAlarmModal.vue'
import { useNotificationPoller } from '@/composables/useNotificationPoller'

const poller = useNotificationPoller()
onMounted(() => poller.start())
onUnmounted(() => poller.stop())
</script>

<template>
  <RouterView />
  <DeadlineAlarmModal />
</template>

<style scoped></style>
