<template>
  <section class="page" data-module="tally">
    <header class="page-head">
      <div>
        <h2>理货作业管理</h2>
        <p class="page-desc">
          理货单按归属人划分：只能修改自己还没提交的单，别人的单只可查看；提交后锁定，
          需修改时由当班值班负责人退回并写明理由；交接班后已提交版本全班次可见，未提交的单跟人走。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" :disabled="!session.isTally" @click="openCreate">登记理货单</button>
        <button class="btn" type="button" @click="exportRows">导出理货作业清单</button>
      </div>
    </header>

    <p v-if="!session.isTally" class="hint-bar">
      当前身份为{{ session.operator?.role_label }}：所有理货单仅可查看，不能修改或提交。
    </p>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <div class="scope-tabs" role="tablist">
      <button
        v-for="tab in scopes"
        :key="tab.value"
        type="button"
        class="scope-tab"
        :class="{ active: scope === tab.value }"
        @click="switchScope(tab.value)"
      >
        {{ tab.label }}
      </button>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>理货单号</span>
        <input v-model="keyword" placeholder="按理货单号检索" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table tally-table">
      <thead>
        <tr>
          <th>理货单号</th>
          <th>关联航次</th>
          <th>理货方式</th>
          <th>理货箱量</th>
          <th>残损箱数</th>
          <th>归属理货人员</th>
          <th>单据状态</th>
          <th>提交/退回</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :class="{ locked: row.locked, mine: row.mine }">
          <td>{{ row.理货单号 }}</td>
          <td>{{ row.关联航次 ?? '—' }}</td>
          <td>{{ row.理货方式 ?? '—' }}</td>
          <td>{{ row.理货箱量 ?? '—' }}</td>
          <td>{{ row.残损箱数 ?? '—' }}</td>
          <td>
            <div class="owner-cell">
              <strong>{{ row.owner_name || row.理货人员 || '—' }}</strong>
              <span class="owner-shift">{{ row.owner_shift_label }}</span>
              <span v-if="row.mine" class="tag tag-mine">我的</span>
            </div>
          </td>
          <td>
            <span class="status-dot" :data-status="row.status">{{ row.status }}</span>
          </td>
          <td class="trace-cell">
            <template v-if="row.submitted">
              <span class="tag tag-locked">已锁定</span>
              <span class="trace-line">{{ row.submitted_by }} · {{ row.submitted_at }}</span>
              <span class="trace-line muted">{{ row.submitted_shift }} 提交版本</span>
            </template>
            <template v-else-if="row.return_records?.length">
              <span class="tag tag-returned">已退回 {{ row.return_records.length }} 次</span>
              <span class="trace-line">最近：{{ row.return_records[row.return_records.length - 1].returned_by }}
                {{ row.return_records[row.return_records.length - 1].returned_at }}</span>
            </template>
            <template v-else>
              <span class="tag tag-draft">未提交·跟人</span>
            </template>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openView(row)">查看</button>
            <button v-if="canStart(row)" class="link" type="button" @click="runAction('开始理货', row)">开始理货</button>
            <button v-if="row.can_edit" class="link" type="button" @click="openEdit(row)">修改</button>
            <button v-if="row.can_submit" class="link submit-link" type="button" @click="submitRow(row)">提交</button>
            <button v-if="canComplete(row)" class="link" type="button" @click="runAction('确认完成', row)">确认完成</button>
            <button v-if="row.can_return" class="link return-link" type="button" @click="openReturn(row)">负责人退回</button>
            <span v-if="!hasAnyAction(row)" class="muted">无操作权限</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td colspan="9" class="empty-state">当前范围暂无理货单</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条理货单记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 登记 / 修改 -->
    <div v-if="formOpen" class="modal-mask" @click.self="closeForm">
      <div class="modal">
        <h3>{{ formMode === 'create' ? '登记理货单' : `修改理货单 ${formValues.理货单号}` }}</h3>
        <p v-if="formMode === 'edit'" class="modal-tip">
          归属：{{ editingRow?.owner_name }}（{{ editingRow?.owner_shift_label }}），理货方式与录入沿用原习惯。
        </p>
        <div class="form-grid">
          <label v-if="formMode === 'create'" class="form-field">
            <span>理货单号 *</span>
            <input v-model="formValues.理货单号" placeholder="如 TALL-0007" />
          </label>
          <label class="form-field">
            <span>关联航次 *</span>
            <input v-model="formValues.关联航次" placeholder="如 VOYA-0001" />
          </label>
          <label class="form-field">
            <span>理货方式 *</span>
            <select v-model="formValues.理货方式">
              <option value="" disabled>请选择理货方式</option>
              <option v-for="method in methods" :key="method" :value="method">{{ method }}</option>
            </select>
          </label>
          <label class="form-field">
            <span>理货箱量</span>
            <input v-model="formValues.理货箱量" type="number" min="0" />
          </label>
          <label class="form-field">
            <span>残损箱数</span>
            <input v-model="formValues.残损箱数" type="number" min="0" />
          </label>
          <label class="form-field">
            <span>完成时间</span>
            <input v-model="formValues.完成时间" placeholder="YYYY-MM-DD HH:mm:ss" />
          </label>
          <label class="form-field wide">
            <span>理货状态备注</span>
            <input v-model="formValues.理货状态" placeholder="如 正常 / 有残损待确认" />
          </label>
        </div>
        <p v-if="formError" class="error-text">{{ formError }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="closeForm">取消</button>
          <button class="btn primary" type="button" :disabled="saving" @click="saveForm">
            {{ saving ? '保存中…' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 负责人退回 -->
    <div v-if="returnOpen" class="modal-mask" @click.self="closeReturn">
      <div class="modal">
        <h3>退回理货单 {{ returningRow?.理货单号 }}</h3>
        <p class="modal-tip">
          该单由 {{ returningRow?.submitted_by }} 于 {{ returningRow?.submitted_at }}（{{ returningRow?.submitted_shift }}）提交并锁定，
          退回后归属人 {{ returningRow?.owner_name }} 可继续修改。退回时间与理由会随单留痕。
        </p>
        <label class="form-field wide">
          <span>退回理由 *</span>
          <textarea v-model="returnReason" rows="3" placeholder="请说明为什么退回，例如：箱量与舱口单不符，请复核"></textarea>
        </label>
        <p v-if="returnError" class="error-text">{{ returnError }}</p>
        <div class="modal-foot">
          <button class="btn ghost" type="button" @click="closeReturn">取消</button>
          <button class="btn primary danger" type="button" :disabled="returning" @click="confirmReturn">
            {{ returning ? '退回中…' : '确认退回' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 查看明细 -->
    <div v-if="viewOpen" class="modal-mask" @click.self="closeView">
      <div class="modal wide-modal">
        <h3>理货单明细 {{ viewingRow?.理货单号 }}</h3>
        <div class="detail-grid">
          <span class="detail-label">归属理货人员</span>
          <span>{{ viewingRow?.owner_name }}（{{ viewingRow?.owner_shift_label }}）{{ viewingRow?.mine ? '· 我的' : '' }}</span>
          <span class="detail-label">单据状态</span>
          <span>{{ viewingRow?.status }}（{{ viewingRow?.locked ? '已提交锁定' : '未提交，跟人走' }}）</span>
          <span class="detail-label">关联航次</span>
          <span>{{ viewingRow?.关联航次 ?? '—' }}</span>
          <span class="detail-label">理货方式</span>
          <span>{{ viewingRow?.理货方式 ?? '—' }}</span>
          <span class="detail-label">理货箱量 / 残损</span>
          <span>{{ viewingRow?.理货箱量 ?? '—' }} / {{ viewingRow?.残损箱数 ?? '—' }}</span>
          <span class="detail-label">完成时间</span>
          <span>{{ viewingRow?.完成时间 ?? '—' }}</span>
          <span class="detail-label">理货状态备注</span>
          <span>{{ viewingRow?.理货状态 ?? '—' }}</span>
        </div>

        <template v-if="viewingRow?.submitted">
          <h4 class="detail-sub">提交版本（交接班后新班次看到的就是这一版）</h4>
          <div class="detail-grid">
            <span class="detail-label">提交人 / 时间</span>
            <span>{{ viewingRow.submitted_by }} · {{ viewingRow.submitted_at }}</span>
            <span class="detail-label">提交班次</span>
            <span>{{ viewingRow.submitted_shift }}</span>
            <template v-if="viewingRow.submitted_snapshot">
              <span class="detail-label">快照箱量 / 残损</span>
              <span>{{ viewingRow.submitted_snapshot.理货箱量 }} / {{ viewingRow.submitted_snapshot.残损箱数 }}</span>
              <span class="detail-label">快照理货方式</span>
              <span>{{ viewingRow.submitted_snapshot.理货方式 }}</span>
            </template>
          </div>
        </template>

        <template v-else>
          <p class="modal-tip">该单尚未提交，内容可由归属人继续录入；交接班后仍归属 {{ viewingRow?.owner_name }}。</p>
        </template>

        <h4 class="detail-sub">退回记录</h4>
        <ul v-if="viewingRow?.return_records?.length" class="return-list">
          <li v-for="(record, index) in viewingRow.return_records" :key="index">
            <strong>{{ record.returned_at }}</strong>
            <span>{{ record.returned_by }}（{{ record.shift }}）退回：{{ record.reason }}</span>
          </li>
        </ul>
        <p v-else class="muted">暂无退回记录。</p>

        <div class="modal-foot">
          <button class="btn" type="button" @click="closeView">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

import { getOperatorId, readError, request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type CellValue = string | number | null

interface ReturnRecord {
  returned_at: string
  returned_by: string
  shift: string
  reason: string
}

interface TallyRow {
  id: number
  status: string
  理货单号: string
  关联航次: CellValue
  理货方式: CellValue
  理货箱量: CellValue
  残损箱数: CellValue
  理货人员: CellValue
  完成时间: CellValue
  理货状态: CellValue
  owner_id: string
  owner_name: string
  submitted: boolean
  submitted_at: string | null
  submitted_by: string | null
  submitted_shift: string | null
  submitted_snapshot: Record<string, CellValue> | null
  return_records: ReturnRecord[]
  mine: boolean
  locked: boolean
  owner_shift_label: string
  can_edit: boolean
  can_submit: boolean
  can_return: boolean
}

const ENDPOINT = '/api/tally'

const session = useSessionStore()
const scopes = [
  { value: '', label: '全部理货单' },
  { value: 'mine', label: '我的理货单' },
  { value: 'draft', label: '未提交（跟人走）' },
  { value: 'submitted', label: '已提交（锁定版本）' },
]

const rows = ref<TallyRow[]>([])
const total = ref(0)
const errorMessage = ref('')
const keyword = ref('')
const scope = ref('')
const methods = ref<string[]>([])
const stats = ref([
  { label: '理货单总数', value: 0 },
  { label: '我的未提交', value: 0 },
  { label: '已提交锁定', value: 0 },
  { label: '被退回次数', value: 0 },
])

const formOpen = ref(false)
const formMode = ref<'create' | 'edit'>('create')
const editingRow = ref<TallyRow | null>(null)
const formValues = ref<Record<string, string>>({})
const formError = ref('')
const saving = ref(false)

const returnOpen = ref(false)
const returningRow = ref<TallyRow | null>(null)
const returnReason = ref('')
const returnError = ref('')
const returning = ref(false)

const viewOpen = ref(false)
const viewingRow = ref<TallyRow | null>(null)

function switchScope(next: string) {
  scope.value = next
  void reload()
}

function resetFilters() {
  keyword.value = ''
  void reload()
}

function exportRows() {
  const operatorId = getOperatorId()
  const query = operatorId ? `?operator_id=${encodeURIComponent(operatorId)}` : ''
  window.open(`${ENDPOINT}/export${query}`, '_blank')
}

function canStart(row: TallyRow): boolean {
  return row.can_edit && row.status === '待理货'
}

function canComplete(row: TallyRow): boolean {
  return row.can_return && row.status !== '已完成'
}

function hasAnyAction(row: TallyRow): boolean {
  return canStart(row) || row.can_edit || row.can_submit || canComplete(row) || row.can_return
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (keyword.value.trim()) {
    params.set('keyword', keyword.value.trim())
  }
  if (scope.value) {
    params.set('scope', scope.value)
  }
  const operatorId = getOperatorId()
  if (operatorId) {
    params.set('operator_id', operatorId)
  }
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error(await readError(response, '理货单列表读取失败'))
    }
    const payload = (await response.json()) as { items: TallyRow[]; total: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '理货单列表读取失败'
  }
  void reloadStats()
}

async function reloadStats() {
  const operatorId = getOperatorId()
  const query = operatorId ? `?operator_id=${encodeURIComponent(operatorId)}` : ''
  try {
    const response = await request(`${ENDPOINT}/stats${query}`)
    if (!response.ok) {
      return
    }
    const data = (await response.json()) as Record<string, number>
    stats.value = [
      { label: '理货单总数', value: data.total ?? 0 },
      { label: '我的未提交', value: data.mine_unsubmitted ?? 0 },
      { label: '已提交锁定', value: data.submitted ?? 0 },
      { label: '被退回（单数）', value: data.returned ?? 0 },
    ]
  } catch {
    // 统计失败不影响主列表使用
  }
}

async function loadMeta() {
  try {
    const response = await request(`${ENDPOINT}/meta`)
    if (response.ok) {
      const data = (await response.json()) as { tally_methods: string[] }
      methods.value = data.tally_methods ?? []
    }
  } catch {
    // 元数据读不到时下拉为空，不影响主流程
  }
}

// ---------- 动作 ----------

async function runAction(action: string, row: TallyRow) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    if (!response.ok) {
      errorMessage.value = await readError(response, '理货作业动作未生效')
      return
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '理货作业操作失败'
  }
}

async function submitRow(row: TallyRow) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/submit`, { method: 'POST' })
    if (!response.ok) {
      errorMessage.value = await readError(response, '提交未生效')
      return
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '提交失败'
  }
}

// ---------- 登记 / 修改 ----------

function emptyForm(): Record<string, string> {
  return {
    理货单号: '',
    关联航次: '',
    理货方式: '',
    理货箱量: '',
    残损箱数: '',
    完成时间: '',
    理货状态: '',
  }
}

function openCreate() {
  formMode.value = 'create'
  editingRow.value = null
  formValues.value = emptyForm()
  formError.value = ''
  formOpen.value = true
}

function openEdit(row: TallyRow) {
  formMode.value = 'edit'
  editingRow.value = row
  formValues.value = {
    理货单号: String(row.理货单号 ?? ''),
    关联航次: String(row.关联航次 ?? ''),
    理货方式: String(row.理货方式 ?? ''),
    理货箱量: row.理货箱量 == null ? '' : String(row.理货箱量),
    残损箱数: row.残损箱数 == null ? '' : String(row.残损箱数),
    完成时间: row.完成时间 == null ? '' : String(row.完成时间),
    理货状态: row.理货状态 == null ? '' : String(row.理货状态),
  }
  formError.value = ''
  formOpen.value = true
}

function closeForm() {
  formOpen.value = false
  editingRow.value = null
}

function buildPayload(): Record<string, CellValue> {
  const values: Record<string, CellValue> = {}
  for (const [key, raw] of Object.entries(formValues.value)) {
    if (key === '理货箱量' || key === '残损箱数') {
      values[key] = raw === '' ? null : Number(raw)
    } else {
      values[key] = raw
    }
  }
  return values
}

async function saveForm() {
  formError.value = ''
  const url = formMode.value === 'create' ? ENDPOINT : `${ENDPOINT}/${editingRow.value?.id}`
  const method = formMode.value === 'create' ? 'POST' : 'PATCH'
  const body = formMode.value === 'create'
    ? JSON.stringify({ values: buildPayload() })
    : JSON.stringify({ values: buildPayload() })
  saving.value = true
  try {
    const response = await request(url, { method, body })
    const data = (await response.json().catch(() => ({}))) as { detail?: string; message?: string }
    if (!response.ok) {
      formError.value = data.detail ?? '理货单保存失败'
      return
    }
    if (data.message && response.status === 200 && formMode.value === 'create' && data.message.includes('缺少')) {
      formError.value = data.message
      return
    }
    closeForm()
    await reload()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '理货单保存失败'
  } finally {
    saving.value = false
  }
}

// ---------- 退回 ----------

function openReturn(row: TallyRow) {
  returningRow.value = row
  returnReason.value = ''
  returnError.value = ''
  returnOpen.value = true
}

function closeReturn() {
  returnOpen.value = false
  returningRow.value = null
  returnReason.value = ''
}

async function confirmReturn() {
  if (!returningRow.value) {
    return
  }
  returnError.value = ''
  returning.value = true
  try {
    const response = await request(`${ENDPOINT}/${returningRow.value.id}/return`, {
      method: 'POST',
      body: JSON.stringify({ reason: returnReason.value }),
    })
    const data = (await response.json()) as { detail?: string; message?: string }
    if (!response.ok) {
      returnError.value = data.detail ?? '退回未生效'
      return
    }
    if (data.message && !data.message.startsWith('理货单已退回')) {
      returnError.value = data.message
      return
    }
    closeReturn()
    await reload()
  } catch (error) {
    returnError.value = error instanceof Error ? error.message : '退回失败'
  } finally {
    returning.value = false
  }
}

// ---------- 查看 ----------

async function openView(row: TallyRow) {
  const query = getOperatorId() ? `?operator_id=${encodeURIComponent(getOperatorId())}` : ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}${query}`)
    if (!response.ok) {
      viewingRow.value = row
    } else {
      viewingRow.value = (await response.json()) as TallyRow
    }
  } catch {
    viewingRow.value = row
  }
  viewOpen.value = true
}

function closeView() {
  viewOpen.value = false
  viewingRow.value = null
}

function onSessionChanged() {
  void reload()
}

onMounted(() => {
  void loadMeta()
  void reload()
  window.addEventListener('tally:operator-changed', onSessionChanged)
  window.addEventListener('tally:shift-changed', onSessionChanged)
})

onUnmounted(() => {
  window.removeEventListener('tally:operator-changed', onSessionChanged)
  window.removeEventListener('tally:shift-changed', onSessionChanged)
})
</script>

<style scoped>
.hint-bar {
  margin: 0 0 10px;
  padding: 6px 10px;
  font-size: 12px;
  color: #664d03;
  background: #fff7e0;
  border: 1px solid #f2dfa0;
  border-radius: 6px;
}
.scope-tabs {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
}
.scope-tab {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 999px;
  padding: 4px 14px;
  font-size: 12px;
  cursor: pointer;
}
.scope-tab.active {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
.tally-table tr.mine {
  background: #f2f7ff;
}
.tally-table tr.locked {
  background: #fafbfc;
}
.owner-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.owner-shift {
  font-size: 11px;
  color: var(--muted);
}
.tag {
  display: inline-block;
  font-size: 11px;
  padding: 1px 8px;
  border-radius: 999px;
  margin-right: 4px;
}
.tag-mine {
  background: #dbeafe;
  color: #1d4ed8;
}
.tag-locked {
  background: #fee4e2;
  color: #b42318;
}
.tag-draft {
  background: #e6f6ee;
  color: #067647;
}
.tag-returned {
  background: #fff1d6;
  color: #9a5b00;
}
.status-dot {
  font-size: 12px;
}
.trace-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.trace-line {
  font-size: 11px;
}
.muted {
  color: var(--muted);
}
.submit-link {
  color: #067647;
}
.return-link {
  color: #b42318;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.modal {
  width: 560px;
  max-height: 86vh;
  overflow-y: auto;
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px;
}
.wide-modal {
  width: 680px;
}
.modal h3 {
  margin: 0 0 8px;
  font-size: 16px;
}
.modal-tip {
  font-size: 12px;
  color: var(--muted);
  margin: 0 0 12px;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 14px;
}
.form-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}
.form-field.wide {
  grid-column: 1 / -1;
}
.form-field input,
.form-field select,
.form-field textarea {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  color: #1f2937;
}
.modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}
.btn.primary.danger {
  background: #b42318;
  border-color: #b42318;
}
.detail-grid {
  display: grid;
  grid-template-columns: 130px 1fr;
  gap: 6px 12px;
  font-size: 13px;
  margin-bottom: 10px;
}
.detail-label {
  color: var(--muted);
}
.detail-sub {
  font-size: 13px;
  margin: 12px 0 6px;
  padding-top: 8px;
  border-top: 1px dashed var(--border);
}
.return-list {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
}
.return-list li {
  margin-bottom: 4px;
}
</style>
