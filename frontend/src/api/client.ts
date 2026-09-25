/** 统一请求封装：拼后端地址、带当班身份、抛网络错误、给页脚留一句可读的说明。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''
const OPERATOR_STORAGE_KEY = 'tally.operatorId'

export function getOperatorId(): string {
  return localStorage.getItem(OPERATOR_STORAGE_KEY) ?? ''
}

export function setOperatorId(operatorId: string) {
  localStorage.setItem(OPERATOR_STORAGE_KEY, operatorId)
  window.dispatchEvent(new CustomEvent('tally:operator-changed', { detail: operatorId }))
}

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const operatorId = getOperatorId()
  if (operatorId) {
    headers.set('X-Operator-Id', operatorId)
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

/** 从错误响应里读出服务端给出的拒绝原因；读不出来时回退到调用方的兜底文案。 */
export async function readError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown; message?: unknown }
    if (typeof payload.detail === 'string') {
      return payload.detail
    }
    if (typeof payload.message === 'string') {
      return payload.message
    }
  } catch {
    // 非 JSON 响应时用兜底文案
  }
  return fallback
}
