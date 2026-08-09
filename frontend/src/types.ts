export interface User {
  id: number
  username: string
  display_name: string
  role: 'operator' | 'merchant'
  merchant_id: number | null
  is_active: boolean
  must_change_password: boolean
  last_login_at: string | null
  created_at: string
}

export interface Merchant {
  id: number
  name: string
  industry: string
  phone: string
  address: string
  business_hours: string
  contact_name: string
  scale: string
  employee_count: number
  store_area: number
  network_environment: string
  bandwidth_mbps: number
  tags: string[]
  needs: string[]
  image_url: string
  products: Product[]
  status: 'enabled' | 'disabled'
  is_demo: boolean
  created_at: string
  updated_at: string
}

export interface Product {
  id: string
  name: string
  price: number
  category: string
  image_id: number | null
}

export interface Resource {
  id: number
  subscription_count: number
  name: string
  category: string
  description: string
  price: number
  unit: string
  bandwidth_mbps?: number
  target_industries: string[]
  matched_needs: string[]
  included_services: string[]
  is_universal: boolean
  status: 'enabled' | 'disabled'
}

export type ApplicationStatus = 'pending' | 'processing' | 'completed' | 'canceled'

export interface ApplicationEvent {
  id: number
  actor_user_id: number
  event_type: string
  from_status: string | null
  to_status: string | null
  note: string
  created_at: string
}

export interface ServiceApplication {
  id: number
  merchant_id: number
  merchant_name: string
  resource_id: number
  contact_name: string
  contact_phone: string
  merchant_note: string
  recommendation_score: number
  recommendation_reasons: string[]
  resource_snapshot: {
    name: string
    category: string
    price: number
    unit: string
    description: string
    included_services: string[]
  }
  status: ApplicationStatus
  is_demo: boolean
  created_at: string
  updated_at: string
  completed_at: string | null
  events: ApplicationEvent[]
}

export interface BusinessData {
  id: number
  merchant_id: number
  business_date: string
  visitors: number
  orders: number
  revenue: number
  rating: number
  dine_in_orders: number
  delivery_orders: number
  group_buy_orders: number
  other_orders: number
  peak_hour: number
}
