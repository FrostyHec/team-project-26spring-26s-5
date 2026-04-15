<script setup lang="ts">
/**
 * ComposeEditor — WangEditor v5 rich-text wrapper (vanilla JS API; no editor-for-vue).
 */
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { createEditor, createToolbar } from '@wangeditor/editor'
import type { IDomEditor, IEditorConfig, IToolbarConfig } from '@wangeditor/editor'
import '@wangeditor/editor/dist/css/style.css'

interface Props {
  modelValue: string
  placeholder?: string
}

const props = withDefaults(defineProps<Props>(), {
  placeholder: 'Write your message...',
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const toolbarRef = ref<HTMLDivElement>()
const editorRef = ref<HTMLDivElement>()
let editorInstance: IDomEditor | null = null

onMounted(() => {
  const toolbarConfig: Partial<IToolbarConfig> = {}
  const editorConfig: Partial<IEditorConfig> = {
    placeholder: props.placeholder,
    onChange(editor) {
      emit('update:modelValue', editor.getHtml())
    },
  }
  editorInstance = createEditor({
    selector: editorRef.value!,
    html: props.modelValue ?? '',
    config: editorConfig,
    mode: 'default',
  })
  createToolbar({
    editor: editorInstance,
    selector: toolbarRef.value!,
    config: toolbarConfig,
    mode: 'default',
  })
})

watch(
  () => props.modelValue,
  (val) => {
    if (editorInstance && editorInstance.getHtml() !== val) {
      editorInstance.setHtml(val ?? '')
    }
  },
)

onBeforeUnmount(() => {
  editorInstance?.destroy()
  editorInstance = null
})
</script>

<template>
  <div class="border border-gray-300 rounded-lg overflow-hidden">
    <div ref="toolbarRef" class="border-b border-gray-200" />
    <div ref="editorRef" class="min-h-48 max-h-80 overflow-y-auto" />
  </div>
</template>
