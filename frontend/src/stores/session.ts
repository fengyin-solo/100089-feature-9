import { defineStore } from 'pinia'

/** 理货人员身份；值班负责人可退回已提交的理货单。 */
export type OperatorRole = 'tally' | 'supervisor'

export interface OperatorOption {
  name: string
  role: OperatorRole
}

/** 演示用的可切换身份，生产环境替换为登录账号即可。 */
export const OPERATORS: OperatorOption[] = [
  { name: '王理货', role: 'tally' },
  { name: '李理货', role: 'tally' },
  { name: '赵班长', role: 'supervisor' },
]

interface SessionState {
  operator: string
  role: OperatorRole
  shiftLabel: string
  scope: string
}

export const useSessionStore = defineStore('session', {
  state: (): SessionState => ({
    operator: '王理货',
    role: 'tally',
    shiftLabel: '白班 08:00-20:00',
    scope: '港口集装箱作业调度平台',
  }),
  getters: {
    canOperate: (state) => state.operator.length > 0,
    isSupervisor: (state) => state.role === 'supervisor',
    roleLabel: (state) => (state.role === 'supervisor' ? '值班负责人' : '理货人员'),
  },
  actions: {
    setOperator(name: string, role: OperatorRole) {
      this.operator = name
      this.role = role
    },
    setShift(label: string) {
      // 交接班只换班次标签：理货单归属跟人走，已提交版本冻结，未提交的仍归本人
      this.shiftLabel = label
    },
  },
})
