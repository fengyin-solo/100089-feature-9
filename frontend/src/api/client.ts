/** 统一请求封装：拼后端地址、注入当前操作人身份、抛网络错误、给页脚留一句可读的说明。 */
import { useSessionStore } from '@/stores/session'

const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  // 演示阶段用请求头告诉后端"谁在操作、是什么角色"；后端据此做归属与越权校验
  const session = useSessionStore()
  const headers = new Headers(init?.headers ?? { 'Content-Type': 'application/json' })
  // HTTP 头只能安全传 ASCII，中文姓名做百分号编码，后端解码；角色为固定英文枚举
  headers.set('X-Operator', encodeURIComponent(session.operator))
  headers.set('X-Operator-Role', session.role)
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  return fetch(url, { ...init, headers }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

export async function fetchJson<T>(path: string): Promise<T> {
  const response = await request(path)
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as T
}
