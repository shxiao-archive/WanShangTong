export type PortalRole = 'merchant' | 'operator'

const portalSubdomains: Record<PortalRole, string> = {
  merchant: 'merchant',
  operator: 'admin',
}

function configuredPortalRole(): PortalRole | null {
  const configured = import.meta.env.VITE_PORTAL_ROLE
  return configured === 'merchant' || configured === 'operator' ? configured : null
}

export function detectPortalRole(hostname = window.location.hostname): PortalRole | null {
  const configured = configuredPortalRole()
  if (configured) return configured

  const subdomain = hostname.toLowerCase().split('.')[0]
  if (subdomain === portalSubdomains.merchant) return 'merchant'
  if (subdomain === portalSubdomains.operator) return 'operator'
  return null
}

export const portalRole = detectPortalRole()

export function portalLabel(role: PortalRole) {
  return role === 'merchant' ? '商户端' : '管理端'
}

export function portalLoginUrl(role: PortalRole): string | null {
  const url = new URL(window.location.href)
  const labels = url.hostname.split('.')

  if (labels[0] === 'merchant' || labels[0] === 'admin' || labels[0] === 'www') {
    labels[0] = portalSubdomains[role]
  } else if (labels.length >= 2 && url.hostname !== 'localhost' && url.hostname !== '127.0.0.1') {
    labels.unshift(portalSubdomains[role])
  } else {
    return null
  }

  url.hostname = labels.join('.')
  url.pathname = '/login'
  url.search = ''
  url.hash = ''
  return url.toString()
}
