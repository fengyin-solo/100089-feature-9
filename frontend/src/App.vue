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
        <span class="head-user">
          <label class="identity-switch">
            当前身份
            <select :value="store.operator" @change="onIdentityChange">
              <option v-for="item in operators" :key="`${item.role}-${item.name}`" :value="item.name">
                {{ item.name }}（{{ item.role === 'supervisor' ? '值班负责人' : '理货人员' }}）
              </option>
            </select>
          </label>
          <button class="btn btn-sm" type="button" @click="toggleShift">交接班：{{ store.shiftLabel }}</button>
        </span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useSessionStore, OPERATORS } from '@/stores/session'

const store = useSessionStore()
const operators = OPERATORS

const SHIFTS = ['白班 08:00-20:00', '夜班 20:00-08:00']

function onIdentityChange(event: Event) {
  const name = (event.target as HTMLSelectElement).value
  const picked = OPERATORS.find((item) => item.name === name)
  if (picked) {
    store.setOperator(picked.name, picked.role)
  }
}

function toggleShift() {
  // 交接班只切班次：已提交的单据冻结可查，未提交的跟着归属理货人员走
  const current = SHIFTS.indexOf(store.shiftLabel)
  store.setShift(SHIFTS[(current + 1) % SHIFTS.length])
}

const navItems = [{ label: "运营概览", path: "/" }, { label: "泊位计划", path: "/berth" }, { label: "船舶档案", path: "/vessel" }, { label: "航次管理", path: "/voyage" }, { label: "岸桥作业", path: "/crane" }, { label: "装卸任务", path: "/loading" }, { label: "堆场管理", path: "/yard" }, { label: "集装箱档案", path: "/container" }, { label: "堆存记录", path: "/yardstore" }, { label: "闸口通行", path: "/gate" }, { label: "集卡调度", path: "/truck" }, { label: "理货作业", path: "/tally" }, { label: "残损登记", path: "/damage" }, { label: "单证处理", path: "/manifest" }, { label: "堆存计费", path: "/storage" }, { label: "引航拖轮", path: "/pilot" }, { label: "安全监督", path: "/safety" }, { label: "货主档案", path: "/customer" }, { label: "作业结算", path: "/settle" }]
</script>
