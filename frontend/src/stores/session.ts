import { defineStore } from 'pinia'

import { getOperatorId, request, setOperatorId } from '@/api/client'

export type Role = 'tally' | 'lead' | 'viewer'

export interface OperatorInfo {
  id: string
  name: string
  role: Role
  role_label: string
}

export interface ShiftClerk {
  id: string
  name: string
  role: Role
}

export interface ShiftInfo {
  index: number
  label: string
  lead_id: string
  lead_name: string
  clerks: ShiftClerk[]
}

interface HandoverRecord {
  from_shift: string
  to_shift: string
  by_id: string
  by_name: string
  handed_at: string
}

interface SessionState {
  operators: OperatorInfo[]
  operatorId: string
  currentShift: ShiftInfo | null
  nextShift: ShiftInfo | null
  history: HandoverRecord[]
  loaded: boolean
  lastMessage: string
  lastError: string
}

export const useSessionStore = defineStore('session', {
  state: (): SessionState => ({
    operators: [],
    operatorId: getOperatorId(),
    currentShift: null,
    nextShift: null,
    history: [],
    loaded: false,
    lastMessage: '',
    lastError: '',
  }),
  getters: {
    operator(state): OperatorInfo | undefined {
      return state.operators.find((item) => item.id === state.operatorId)
    },
    isTally(state): boolean {
      const current = state.operators.find((item) => item.id === state.operatorId)
      return current?.role === 'tally'
    },
    isLead(state): boolean {
      const current = state.operators.find((item) => item.id === state.operatorId)
      return current?.role === 'lead'
    },
    isCurrentLead(state): boolean {
      const current = state.operators.find((item) => item.id === state.operatorId)
      return current?.role === 'lead' && state.currentShift?.lead_id === state.operatorId
    },
    shiftLabel(state): string {
      return state.currentShift?.label ?? ''
    },
    scope(state): string {
      return state.operators.length ? '港口集装箱作业调度平台' : ''
    },
  },
  actions: {
    async bootstrap() {
      await this.refresh()
      // 首次进入默认选当前班次的值班负责人，方便直接看到完整界面。
      if (!this.operatorId && this.currentShift) {
        this.operatorId = this.currentShift.lead_id
        setOperatorId(this.operatorId)
      }
    },
    async refresh() {
      const payload = await request('/api/session')
      if (!payload.ok) {
        throw new Error('当班信息读取失败')
      }
      const data = (await payload.json()) as {
        operators: OperatorInfo[]
        current_shift: ShiftInfo
        next_shift: ShiftInfo
        handover_history: HandoverRecord[]
      }
      this.operators = data.operators
      this.currentShift = data.current_shift
      this.nextShift = data.next_shift
      this.history = data.handover_history
      this.loaded = true
    },
    selectOperator(operatorId: string) {
      this.operatorId = operatorId
      setOperatorId(operatorId)
    },
    async handover() {
      this.lastError = ''
      this.lastMessage = ''
      const response = await request('/api/session/handover', { method: 'POST' })
      const data = (await response.json()) as {
        message?: string
        detail?: string
        current_shift?: ShiftInfo
        next_shift?: ShiftInfo
        record?: HandoverRecord
      }
      if (!response.ok) {
        this.lastError = data.detail ?? '交接班未完成'
        return false
      }
      if (data.current_shift) {
        this.currentShift = data.current_shift
      }
      if (data.next_shift) {
        this.nextShift = data.next_shift
      }
      if (data.record) {
        this.history = [...this.history, data.record]
      }
      this.lastMessage = data.message ?? '已完成交接班'
      // 交班后自动切到下一班的值班负责人，新班次立即进入查看状态。
      if (data.current_shift) {
        this.selectOperator(data.current_shift.lead_id)
      }
      window.dispatchEvent(new CustomEvent('tally:shift-changed'))
      return true
    },
    setShift(label: string) {
      // 兼容旧调用点：班次由交接班维护，这里只保留接口。
      this.lastMessage = label
    },
  },
})
