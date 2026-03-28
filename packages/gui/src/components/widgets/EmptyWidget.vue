<script setup lang="ts">
import { Sparkles } from 'lucide-vue-next'
</script>

<template>
  <div class="flex flex-col items-center justify-center h-full text-gray-400 p-8">
    <div class="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mb-4">
      <Sparkles class="w-8 h-8 text-gray-300" />
    </div>
    <h3 class="text-lg font-medium text-gray-500 mb-1">Workspace Ready</h3>
    <p class="text-sm text-center max-w-[200px]">
      Widgets will appear here when the agent uses tools
    </p>
  </div>
</template>
