<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ChevronDown } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    label: string
    buttonClass?: string
    menuClass?: string
    menuAlign?: 'left' | 'right'
    menuPlacement?: 'top' | 'bottom'
  }>(),
  {
    buttonClass: '',
    menuClass: '',
    menuAlign: 'left',
    menuPlacement: 'bottom',
  },
)

const dropdownOpen = ref(false)
const dropdownRef = ref<HTMLElement | null>(null)

const menuPositionClass = computed(() => {
  const alignClass = props.menuAlign === 'right' ? 'right-0' : 'left-0'
  const placementClass = props.menuPlacement === 'top' ? 'bottom-full mb-1' : 'top-full mt-1'
  return `${alignClass} ${placementClass}`
})

function toggleDropdown(): void {
  dropdownOpen.value = !dropdownOpen.value
}

function closeDropdown(): void {
  dropdownOpen.value = false
}

function onClickOutside(event: MouseEvent): void {
  const target = event.target
  if (!(target instanceof Node)) return
  if (dropdownRef.value && !dropdownRef.value.contains(target)) {
    closeDropdown()
  }
}

onMounted(() => {
  document.addEventListener('click', onClickOutside, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside, true)
})

defineExpose({ closeDropdown })
</script>

<template>
  <div ref="dropdownRef" class="relative">
    <button
      data-testid="menu-dropdown-trigger"
      class="flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm font-semibold text-gray-800 transition-colors hover:text-blue-600"
      :class="props.buttonClass"
      @click="toggleDropdown"
    >
      <slot name="label">{{ props.label }}</slot>
      <ChevronDown class="h-4 w-4 transition-transform" :class="{ 'rotate-180': dropdownOpen }" />
    </button>

    <div
      v-show="dropdownOpen"
      class="absolute z-20 min-w-[11rem] rounded-lg border border-gray-200 bg-white py-1 shadow-lg"
      :class="[menuPositionClass, props.menuClass]"
    >
      <slot :close-dropdown="closeDropdown" />
    </div>
  </div>
</template>
