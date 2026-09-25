<template>
  <section class="page" data-module="tally">
    <header class="page-head">
      <div>
        <h2>理货作业管理</h2>
        <p class="page-desc">
          理货单按理货人员归属：只能改本人未提交的单据，他人单据只读并标明归属；
          提交后锁定，需值班负责人退回整改（记录时间与理由）。当前：{{ store.operator }}（{{ store.roleLabel }}）· {{ store.shiftLabel }}
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记理货单</button>
        <button class="btn" type="button" @click="exportRows">导出理货作业清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>理货单号</span>
        <input v-model="filters.keyword" placeholder="按理货单号检索" />
      </label>
      <label class="filter-item">
        <span>理货状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <label class="filter-item filter-check">
        <input v-model="filters.mine" type="checkbox" />
        <span>只看归属我的</span>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>归属与锁定</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] || '—' }}</td>
          <td>
            <span v-if="row.is_owner" class="tag tag-mine">我的单</span>
            <span v-else class="tag tag-other">他人单 · {{ row.owner_name }}</span>
            <span v-if="row.locked" class="tag tag-locked">已提交锁定</span>
            <span v-else-if="!row.is_owner" class="tag tag-readonly">只读</span>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openView(row)">查看</button>
            <button v-if="row.can_edit" class="link" type="button" @click="openEdit(row)">编辑</button>
            <button
              v-if="row.can_edit && row.status === '待理货'"
              class="link"
              type="button"
              @click="runAction('开始理货', row)"
            >
              开始理货
            </button>
            <button
              v-if="row.can_submit && row.status === '理货中'"
              class="link link-warn"
              type="button"
              @click="runAction('提交复核', row)"
            >
              提交复核
            </button>
            <button
              v-if="row.can_confirm"
              class="link"
              type="button"
              @click="runAction('确认完成', row)"
            >
              确认完成
            </button>
            <button
              v-if="row.can_return"
              class="link link-danger"
              type="button"
              @click="openReturn(row)"
            >
              退回整改
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无符合条件的理货单，可先登记理货单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条理货作业记录 · 未提交单据跟随归属理货人员，交接班不转移</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="okMessage" class="ok-text">{{ okMessage }}</span>
    </footer>

    <!-- 登记 / 编辑理货单 -->
    <div v-if="formVisible" class="modal-mask" @click.self="closeForm">
      <div class="modal">
        <h3 class="modal-title">{{ formMode === 'create' ? '登记理货单' : `编辑理货单 ${form.理货单号}` }}</h3>
        <p class="modal-tip">
          单据归属理货人员：<strong>{{ store.operator }}</strong>；理货方式与箱量录入提交前可随时修改。
        </p>
        <div class="form-grid">
          <label class="form-item">
            <span>理货单号 *</span>
            <input v-model="form.理货单号" :disabled="formMode === 'edit'" placeholder="如 TALL-0101" />
          </label>
          <label class="form-item">
            <span>关联航次 *</span>
            <input v-model="form.关联航次" placeholder="如 VOYA-0008" />
          </label>
          <label class="form-item">
            <span>理货方式 *</span>
            <select v-model="form.理货方式">
              <option value="" disabled>请选择理货方式</option>
              <option v-for="m in tallyMethods" :key="m" :value="m">{{ m }}</option>
            </select>
          </label>
          <label class="form-item">
            <span>理货箱量</span>
            <input v-model="form.理货箱量" placeholder="按实际理货箱数录入" />
          </label>
          <label class="form-item">
            <span>残损箱数</span>
            <input v-model="form.残损箱数" placeholder="无残损可留空或填 0" />
          </label>
        </div>
        <div class="modal-foot">
          <button class="btn" type="button" @click="closeForm">取消</button>
          <button class="btn primary" type="button" @click="submitForm">保存</button>
        </div>
      </div>
    </div>

    <!-- 退回整改：负责人必填理由 -->
    <div v-if="returnVisible" class="modal-mask" @click.self="closeReturn">
      <div class="modal">
        <h3 class="modal-title">退回整改 · {{ returnTarget?.理货单号 }}</h3>
        <p class="modal-tip">
          当前状态「{{ returnTarget?.status }}」已锁定，退回后归属人
          <strong>{{ returnTarget?.owner_name }}</strong> 可修改并重新提交，原录入内容保留。
        </p>
        <label class="form-item">
          <span>退回理由 *</span>
          <textarea v-model="returnReason" rows="4" placeholder="请说明退回原因，将与退回时间一并记入单据审计记录"></textarea>
        </label>
        <div class="modal-foot">
          <button class="btn" type="button" @click="closeReturn">取消</button>
          <button class="btn danger" type="button" @click="confirmReturn">确认退回</button>
        </div>
      </div>
    </div>

    <!-- 查看明细：所有人可看，含提交时间与退回记录 -->
    <div v-if="viewVisible" class="modal-mask" @click.self="closeView">
      <div class="modal modal-wide">
        <h3 class="modal-title">理货单明细 · {{ viewRow?.理货单号 }}</h3>
        <table class="detail-table">
          <tbody>
            <tr v-for="item in viewDetails" :key="item.label">
              <th>{{ item.label }}</th>
              <td>{{ item.value || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <h4 class="detail-sub">退回记录</h4>
        <ul v-if="viewRow?.return_history?.length" class="history-list">
          <li v-for="(record, index) in viewRow.return_history" :key="index">
            <span class="history-time">{{ record.time }}</span>
            <span class="tag tag-locked">{{ record.from_status }} → 理货中</span>
            <span>退回人：{{ record.supervisor }}</span>
            <p class="history-reason">理由：{{ record.reason }}</p>
          </li>
        </ul>
        <p v-else class="modal-tip">暂无退回记录。</p>
        <div class="modal-foot">
          <button class="btn primary" type="button" @click="closeView">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, any>

interface ReturnRecord {
  time: string
  reason: string
  supervisor: string
  from_status: string
}

const ENDPOINT = '/api/tally'
const columns = ['理货单号', '关联航次', '理货方式', '理货箱量', '残损箱数', '理货人员', '完成时间', '理货状态']
const statuses = ['待理货', '理货中', '待复核', '已完成']
const tallyMethods = ['船边理货', '堆场理货', '舱内理货', '闸口理货']

const store = useSessionStore()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const okMessage = ref('')
const filters = reactive({ keyword: '', status: '', mine: false })

const stats = computed(() => [
  { label: '归属我的未提交', value: rows.value.filter((r) => r.is_owner && !r.locked).length },
  { label: '待复核（已锁定）', value: rows.value.filter((r) => r.status === '待复核').length },
  { label: '累计退回次数', value: rows.value.reduce((sum, r) => sum + ((r.return_history as ReturnRecord[])?.length ?? 0), 0) },
])

// ---- 登记 / 编辑 ----
const formVisible = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)
const emptyForm = () => ({ 理货单号: '', 关联航次: '', 理货方式: '', 理货箱量: '', 残损箱数: '' })
const form = reactive(emptyForm())

function openCreate() {
  formMode.value = 'create'
  editingId.value = null
  Object.assign(form, emptyForm())
  formVisible.value = true
}

function openEdit(row: Row) {
  formMode.value = 'edit'
  editingId.value = Number(row.id)
  Object.assign(form, emptyForm(), {
    理货单号: row.理货单号 ?? '',
    关联航次: row.关联航次 ?? '',
    理货方式: row.理货方式 ?? '',
    理货箱量: row.理货箱量 ?? '',
    残损箱数: row.残损箱数 ?? '',
  })
  formVisible.value = true
}

function closeForm() {
  formVisible.value = false
}

async function submitForm() {
  errorMessage.value = ''
  okMessage.value = ''
  const values = { ...form }
  const url = formMode.value === 'create'
    ? ENDPOINT
    : `${ENDPOINT}/${editingId.value}`
  const init: RequestInit = formMode.value === 'create'
    ? { method: 'POST', body: JSON.stringify({ values }) }
    : { method: 'PUT', body: JSON.stringify({ values }) }
  try {
    const response = await request(url, init)
    const payload = await response.json()
    if (!response.ok || payload.ok === false) {
      throw new Error(payload?.message ?? '理货单保存未生效，请稍后重试')
    }
    okMessage.value = payload.message
    closeForm()
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '理货单保存失败'
  }
}

// ---- 退回整改 ----
const returnVisible = ref(false)
const returnTarget = ref<Row | null>(null)
const returnReason = ref('')

function openReturn(row: Row) {
  returnTarget.value = row
  returnReason.value = ''
  returnVisible.value = true
}

function closeReturn() {
  returnVisible.value = false
  returnTarget.value = null
}

async function confirmReturn() {
  if (!returnTarget.value) {
    return
  }
  errorMessage.value = ''
  okMessage.value = ''
  try {
    const payload = await postAction('退回整改', returnTarget.value, returnReason.value)
    if (payload.ok === false) {
      throw new Error(payload.message)
    }
    okMessage.value = payload.message
    closeReturn()
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '退回操作失败'
  }
}

// ---- 查看 ----
const viewVisible = ref(false)
const viewRow = ref<Row | null>(null)

const viewDetails = computed(() => {
  const r = viewRow.value
  if (!r) {
    return []
  }
  return [
    { label: '理货单号', value: r.理货单号 },
    { label: '关联航次', value: r.关联航次 },
    { label: '理货方式', value: r.理货方式 },
    { label: '理货箱量', value: r.理货箱量 },
    { label: '残损箱数', value: r.残损箱数 },
    { label: '归属理货人员', value: r.owner_name },
    { label: '理货状态', value: r.status },
    { label: '提交时间', value: r.submitted_at },
    { label: '完成时间', value: r.完成时间 },
  ]
})

async function openView(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('理货单明细读取失败')
    }
    viewRow.value = await response.json()
    viewVisible.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '理货单明细读取失败'
  }
}

function closeView() {
  viewVisible.value = false
  viewRow.value = null
}

// ---- 动作与列表 ----
async function postAction(action: string, row: Row, reason?: string) {
  const response = await request(`${ENDPOINT}/${row.id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ values: { action, ...(reason ? { reason } : {}) } }),
  })
  return response.json()
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  okMessage.value = ''
  try {
    const payload = await postAction(action, row)
    if (payload.ok === false) {
      // 越权、状态不符等拒绝原因由后端给出，原样展示
      throw new Error(payload.message)
    }
    okMessage.value = payload.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '理货作业操作失败'
  }
}

function resetFilters() {
  filters.keyword = ''
  filters.status = ''
  filters.mine = false
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (filters.keyword.trim()) {
    params.set('keyword', filters.keyword.trim())
  }
  if (filters.status) {
    params.set('status', filters.status)
  }
  if (filters.mine) {
    params.set('owner', store.operator)
  }
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('理货单列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '理货作业列表读取失败'
  }
}

// 交接班或切换身份后重新拉取：新班次看冻结的已提交版本，未提交单仍只归属本人可改
watch(() => `${store.operator}|${store.role}|${store.shiftLabel}`, () => void reload())

onMounted(reload)
</script>
