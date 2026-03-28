<script setup lang="ts">
import { ref } from 'vue'
import {
  Plus,
  MessageSquare,
  Settings,
  User,
  Bot,
  PanelRightClose,
  Paperclip,
  Send,
  X,
  LayoutGrid,
  Languages
} from 'lucide-vue-next'

// 模拟状态
const inputText = ref('')
const isWorkspaceOpen = ref(true)
const historyList = ref([
  { id: 1, title: '展示今天的deadline' },
  { id: 2, title: '早上好！请告诉我你有哪些工具' }
])
const quickSkills = ref(['General Assistant', 'Course Assistant', 'Deadline Manager'])
</script>

<template>
  <!-- 最外层容器：全屏高度，隐藏溢出，使用柔和的背景色区分层级 -->
  <div class="flex h-screen w-full bg-slate-50 text-slate-800 font-sans overflow-hidden">
    
    <!-- ================= 左侧边栏 (Sidebar) ================= -->
    <!-- 改进：增加内边距，按钮改为圆角，列表项增加呼吸感，弱化边框颜色 -->
    <aside class="w-64 bg-slate-50 border-r border-slate-200 flex flex-col flex-shrink-0">
      <!-- 顶部操作区 -->
      <div class="p-4">
        <button class="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white py-2.5 px-4 rounded-xl font-medium transition-colors shadow-sm active:scale-95">
          <Plus class="w-5 h-5" />
          <span>New Chat</span>
        </button>
      </div>

      <!-- 历史记录列表 -->
      <div class="flex-1 overflow-y-auto px-3">
        <div class="mb-6">
          <!-- 改进：弱化标题视觉比重 -->
          <h3 class="px-3 text-xs font-bold text-slate-400 tracking-wider mb-2 mt-2">TODAY</h3>
          <ul class="space-y-1">
            <li 
              v-for="item in historyList" 
              :key="item.id"
              class="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-slate-200/60 cursor-pointer text-[14px] text-slate-700 transition-colors group"
            >
              <!-- 改进：用更符合语义的消息图标代替复选框 -->
              <MessageSquare class="w-4 h-4 text-slate-400 group-hover:text-blue-500 flex-shrink-0" />
              <span class="truncate">{{ item.title }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- 底部用户信息 -->
      <div class="p-4 border-t border-slate-200 hover:bg-slate-100 cursor-pointer transition-colors flex items-center justify-between mt-auto">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold shadow-sm">
            U
          </div>
          <span class="text-sm font-medium text-slate-700">User Profile</span>
        </div>
        <Settings class="w-4 h-4 text-slate-400" />
      </div>
    </aside>

    <!-- ================= 中间主聊天区 (Main Chat) ================= -->
    <!-- 改进：背景设为纯白，与两侧的浅灰产生空间感 -->
    <main class="flex-1 flex flex-col relative min-w-0 bg-white">
      <!-- Header -->
      <header class="h-14 border-b border-slate-100 flex items-center justify-between px-6 flex-shrink-0">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-sm">
            <Bot class="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 class="text-[15px] font-bold text-slate-800 leading-tight">Student Management Agent</h2>
            <div class="flex items-center gap-1.5">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
              <span class="text-[11px] font-medium text-emerald-600">Online</span>
            </div>
          </div>
        </div>
        <button 
          @click="isWorkspaceOpen = !isWorkspaceOpen"
          class="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
        >
          <PanelRightClose class="w-5 h-5" />
        </button>
      </header>

      <!-- 聊天内容区 (空状态) -->
      <div class="flex-1 overflow-y-auto p-6 flex flex-col items-center justify-center pb-40">
        <div class="w-16 h-16 rounded-2xl bg-blue-50 flex items-center justify-center mb-6 shadow-sm border border-blue-100">
          <Bot class="w-8 h-8 text-blue-500" />
        </div>
        <h3 class="text-xl font-semibold text-slate-800 mb-3">How can I help you today?</h3>
        <p class="text-[14px] text-center max-w-md text-slate-500 leading-relaxed">
          Ask about courses, deadlines, campus policies, or type 
          <span class="text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded font-mono text-sm">@</span> 
          to select a specific AI skill.
        </p>
      </div>

      <!-- 底部输入区 -->
      <!-- 改进：增加渐变遮罩防止文字重叠，增加底部 padding 解决截断问题 -->
      <div class="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-white via-white to-transparent pt-12 pb-6 px-6">
        <div class="max-w-3xl mx-auto w-full">
          
          <!-- 快捷技能标签 -->
          <!-- 改进：增加 mb-3 拉开与输入框的距离，标签样式更圆润精致 -->
          <div class="flex flex-wrap gap-2 mb-3">
            <button 
              v-for="skill in quickSkills" 
              :key="skill"
              class="text-[12px] font-medium px-3 py-1.5 bg-slate-50 border border-slate-200 text-slate-600 rounded-full hover:bg-blue-50 hover:text-blue-600 hover:border-blue-200 transition-all shadow-sm"
            >
              @{{ skill }}
            </button>
          </div>

          <!-- 输入框主体 -->
          <!-- 改进：增加内边距，阴影更柔和，比例更协调 -->
          <div class="relative flex items-end gap-2 bg-white border border-slate-300 rounded-2xl shadow-sm focus-within:ring-4 focus-within:ring-blue-50 focus-within:border-blue-500 transition-all p-1.5">
            <button class="p-2.5 text-slate-400 hover:text-blue-600 hover:bg-slate-50 rounded-xl transition-colors flex-shrink-0 mb-0.5">
              <Paperclip class="w-5 h-5" />
            </button>
            
            <textarea 
              v-model="inputText"
              placeholder="Message Student Agent... (Type '@' to mention a specific skill)"
              rows="1"
              class="flex-1 max-h-32 py-3 text-[15px] resize-none outline-none bg-transparent text-slate-800 placeholder:text-slate-400 leading-relaxed"
            ></textarea>

            <button 
              class="p-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-all flex-shrink-0 shadow-sm mb-0.5"
              :class="!inputText ? 'opacity-50 cursor-not-allowed' : 'active:scale-95'"
            >
              <Send class="w-5 h-5 ml-0.5" />
            </button>
          </div>

          <!-- 免责声明 -->
          <!-- 改进：确保有足够的空间展示，不再被截断 -->
          <div class="text-center mt-3">
            <span class="text-[11px] text-slate-400">
              AI can make mistakes. Consider verifying important information.
            </span>
          </div>
        </div>
      </div>
    </main>

    <!-- ================= 右侧工作区 (Workspace) ================= -->
    <!-- 改进：背景色与左侧边栏呼应，统一视觉规范 -->
    <aside 
      v-if="isWorkspaceOpen"
      class="w-80 bg-slate-50 border-l border-slate-200 flex flex-col flex-shrink-0 relative"
    >
      <!-- Header -->
      <header class="h-14 border-b border-slate-200 flex items-center justify-between px-4">
        <h2 class="text-[14px] font-bold text-slate-800">Workspace</h2>
        <button 
          @click="isWorkspaceOpen = false"
          class="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-200 rounded-md transition-colors"
        >
          <X class="w-4 h-4" />
        </button>
      </header>

      <!-- 悬浮工具栏 (修复原图中尴尬的悬浮按钮) -->
      <!-- 改进：将其规整到一个半透明的药丸容器中，靠右对齐，不再显得杂乱 -->
      <div class="absolute right-4 top-20 flex flex-col gap-2 bg-white/80 backdrop-blur-sm p-1.5 rounded-2xl border border-slate-200 shadow-sm z-10">
        <button class="p-2 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-colors" title="Translate">
          <Languages class="w-4 h-4" />
        </button>
        <button class="p-2 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-xl transition-colors" title="Widgets">
          <LayoutGrid class="w-4 h-4" />
        </button>
        <button class="p-2 text-blue-600 bg-blue-50 rounded-xl transition-colors" title="AI Assistant">
          <Bot class="w-4 h-4" />
        </button>
      </div>

      <!-- 内容区 -->
      <div class="flex-1 flex flex-col items-center justify-center p-6 text-center">
        <div class="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center mb-4 border border-slate-200">
          <LayoutGrid class="w-6 h-6 text-slate-400" />
        </div>
        <h3 class="text-[15px] font-semibold text-slate-700 mb-1">Workspace Ready</h3>
        <p class="text-[13px] text-slate-500">
          Widgets will appear here when the agent uses tools.
        </p>
      </div>
    </aside>

  </div>
</template>

<style scoped>
/* 隐藏滚动条但保留滚动功能，让界面更清爽 */
::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 10px;
}
::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}
</style>