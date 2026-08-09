import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 12000,
  withCredentials: true,
  headers: { 'X-WST2-Browser-Session': '1' },
})

api.interceptors.response.use(
  (response) => response.data instanceof Blob ? response.data : response.data.data,
  (error) => {
    const status = error.response?.status
    const silentAuth = !!(error.config as any)?.silentAuth
    const message = error.response?.data?.message || (error.code === 'ECONNABORTED' ? '请求超时，请稍后重试' : '服务暂时不可用')
    if (status === 401 && !location.pathname.includes('/login')) {
      localStorage.removeItem('wst_token')
      localStorage.removeItem('wst_user')
      location.href = '/login'
    }
    if (
      status === 403
      && error.response?.data?.message === '请先修改初始密码'
      && !location.pathname.includes('/change-password')
    ) location.href = '/change-password'
    if (!silentAuth) ElMessage.error(message)
    return Promise.reject(error)
  },
)

// 响应拦截器已将统一响应解包为 data，页面层直接使用业务数据。
export default api as any
