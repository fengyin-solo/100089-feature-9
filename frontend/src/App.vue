<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">港口集装箱作业调度平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向船舶靠泊、集装箱装卸、堆场堆存、闸口进出与理货结算的一体化港口作业调度后台。</span>
        <div class="head-session">
          <span v-if="session.currentShift" class="shift-pill">
            当前班次：{{ session.currentShift.label }} · 值班负责人 {{ session.currentShift.lead_name }}
          </span>
          <label class="identity-pick">
            <span>当班身份</span>
            <select :value="session.operatorId" @change="onIdentityChange">
              <option v-for="operator in session.operators" :key="operator.id" :value="operator.id">
                {{ operator.name }}（{{ operator.role_label }}）
              </option>
            </select>
          </label>
          <button
            v-if="session.isCurrentLead"
            class="btn primary handover-btn"
            type="button"
            :disabled="handing"
            @click="onHandover"
          >
            {{ handing ? '交接中…' : `交接班 → ${session.nextShift?.label ?? ''}` }}
          </button>
        </div>
      </header>
      <p v-if="session.lastMessage" class="session-msg ok">{{ session.lastMessage }}</p>
      <p v-if="session.lastError" class="session-msg error">{{ session.lastError }}</p>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const handing = ref(false)

const navItems = [{ label: "运营概览", path: "/" }, { label: "泊位计划", path: "/berth" }, { label: "船舶档案", path: "/vessel" }, { label: "航次管理", path: "/voyage" }, { label: "岸桥作业", path: "/crane" }, { label: "装卸任务", path: "/loading" }, { label: "堆场管理", path: "/yard" }, { label: "集装箱档案", path: "/container" }, { label: "堆存记录", path: "/yardstore" }, { label: "闸口通行", path: "/gate" }, { label: "集卡调度", path: "/truck" }, { label: "理货作业", path: "/tally" }, { label: "残损登记", path: "/damage" }, { label: "单证处理", path: "/manifest" }, { label: "堆存计费", path: "/storage" }, { label: "引航拖轮", path: "/pilot" }, { label: "安全监督", path: "/safety" }, { label: "货主档案", path: "/customer" }, { label: "作业结算", path: "/settle" }]

function onIdentityChange(event: Event) {
  const target = event.target as HTMLSelectElement
  session.selectOperator(target.value)
  session.lastError = ''
  session.lastMessage = ''
}

async function onHandover() {
  handing.value = true
  try {
    await session.handover()
  } finally {
    handing.value = false
  }
}
</script>

<style scoped>
.head-session {
  display: flex;
  align-items: center;
  gap: 12px;
}
.shift-pill {
  font-size: 12px;
  color: #0b5cad;
  background: #e8f1fd;
  border: 1px solid #bcd6f6;
  border-radius: 999px;
  padding: 3px 10px;
}
.identity-pick {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.identity-pick select {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 13px;
}
.handover-btn {
  padding: 5px 12px;
}
.session-msg {
  margin: 8px 0 0;
  font-size: 12px;
}
.session-msg.ok {
  color: #067647;
}
.session-msg.error {
  color: #b42318;
}
</style>
