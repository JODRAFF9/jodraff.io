/**
 * Types partagés avec l'API REST (python/api/main.py).
 * Ils décrivent exactement ce que renvoient les vues SQL centrales.
 */

export interface Company {
  id: number;
  name: string;
  store_type: string;
  store_label: string;
  currency: string;
  currency_sym: string;
  tax_rate: number;
  city: string;
  country: string;
  opened_on: string;
  logo_emoji: string;
}

export interface StoreType {
  key: string;
  label: string;
  icon: string;
  tagline: string;
  tax_rate: number;
  margin_target: number;
  n_categories: number;
  n_products: number;
  n_roles: number;
}

export interface Currency {
  code: string;
  symbol: string;
  label: string;
  decimals: number;
  scale: number;
}

export interface StoreTypesResponse {
  types: StoreType[];
  currencies: Currency[];
  departments: { code: string; name: string; icon: string; description: string }[];
}

export interface CompanyCreate {
  name: string;
  store_type: string;
  currency: string;
  city: string;
  country: string;
  history_months: number;
  traffic_scale: number;
}

export interface Kpis {
  period_days: number;
  revenue: number;
  revenue_delta: number | null;
  tickets: number;
  tickets_delta: number | null;
  avg_basket: number;
  avg_basket_delta: number | null;
  margin: number;
  margin_delta: number | null;
  margin_rate: number;
  customers: number;
  stock_value: number;
  stock_alerts: number;
  out_of_stock: number;
  headcount: number;
  payroll: number;
  expenses: number;
  net_result: number;
}

export interface DepartmentCard {
  dept: string;
  name: string;
  metric: string;
  value: number;
  count: number;
  count_label: string;
}

export interface ActivityRow {
  at: string;
  dept: string;
  label: string;
  amount: number;
}

export interface DailySales {
  sale_date: string;
  tickets: number;
  revenue: number;
  revenue_ht: number;
  cogs: number;
  gross_margin: number;
  avg_basket: number;
}

export interface MonthlySales extends Omit<DailySales, 'sale_date'> {
  period: string;
}

export interface CategorySales {
  category: string;
  revenue: number;
  margin: number;
  quantity: number;
}

export interface DimensionRow {
  label: string;
  tickets: number;
  revenue: number;
}

export interface TopProduct {
  product: string;
  category: string;
  qty_sold: number;
  revenue_ht: number;
  margin: number;
}

export interface SaleRow {
  id: number;
  ref: string;
  sold_at: string;
  status: string;
  payment_method: string;
  channel: string;
  customer: string;
  seller: string;
  total: number;
  margin: number;
  lines: number;
}

export interface Product {
  id: number;
  sku: string;
  name: string;
  category: string;
  supplier: string | null;
  unit: string;
  cost_price: number;
  sale_price: number;
  unit_margin: number;
  margin_rate: number | null;
  stock: number;
  reorder_point: number;
  stock_value: number;
  stock_status: 'ok' | 'faible' | 'alerte' | 'rupture';
  active: number;
}

export interface StockAlert {
  product_id: number;
  sku: string;
  product: string;
  category: string;
  supplier: string | null;
  lead_time_days: number | null;
  stock: number;
  reorder_point: number;
  unit: string;
  suggested_qty: number;
  suggested_cost: number;
  severity: 'alerte' | 'rupture';
}

export interface StockValuation {
  category: string;
  refs: number;
  units: number;
  value: number;
  retail_value: number;
}

export interface StockMove {
  moved_at: string;
  move_date: string;
  product: string;
  quantity: number;
  move_type: string;
  source_dept: string;
  ref: string | null;
  note: string | null;
}

export interface Supplier {
  id: number;
  name: string;
  contact_name: string;
  phone: string;
  email: string;
  lead_time_days: number;
  rating: number;
  active: number;
  refs: number;
  orders: number;
  spend: number;
}

export interface PurchaseOrder {
  id: number;
  ref: string;
  ordered_on: string;
  received_on: string | null;
  status: string;
  total: number;
  supplier: string;
  lines: number;
}

export interface ReorderPlanRow {
  supplier: string;
  refs: number;
  units: number;
  amount: number;
  lead_time_days: number | null;
}

export interface Customer {
  customer_id: number;
  customer: string;
  segment: string;
  city: string;
  loyalty_points: number;
  orders: number;
  lifetime_value: number;
  avg_basket: number;
  last_purchase: string | null;
  days_since_last: number | null;
}

export interface Segment {
  segment: string;
  customers: number;
  revenue: number;
  avg_basket: number;
  avg_orders: number;
}

export interface Employee {
  employee_id: number;
  employee: string;
  role: string;
  department: string;
  salary: number;
  tickets: number;
  revenue: number;
  avg_basket: number;
}

export interface DepartmentHeadcount {
  department: string;
  headcount: number;
  payroll: number;
  avg_salary: number;
}

export interface PayrollRow {
  period: string;
  employees: number;
  gross: number;
  bonus: number;
  net: number;
}

export interface FinancialMonth {
  period: string;
  revenue: number;
  cogs: number;
  expenses: number;
  payroll: number;
  net_result: number;
}

export interface ExpenseRow {
  id: number;
  spent_on: string;
  label: string;
  category: string;
  department: string;
  amount: number;
  note: string | null;
}

/* --------------------------- réponses composées ------------------------ */

export interface OverviewResponse {
  company: Company;
  kpis: Kpis;
  departments: DepartmentCard[];
  sales_daily: DailySales[];
  sales_monthly: MonthlySales[];
  sales_by_category: CategorySales[];
  activity: ActivityRow[];
}

export interface SalesResponse {
  kpis: Kpis;
  daily: DailySales[];
  monthly: MonthlySales[];
  by_category: CategorySales[];
  by_payment: DimensionRow[];
  by_channel: DimensionRow[];
  by_hour: DimensionRow[];
  top_products: TopProduct[];
  recent: SaleRow[];
}

export interface StockResponse {
  products: Product[];
  alerts: StockAlert[];
  valuation: StockValuation[];
  rotation: unknown[];
  moves: StockMove[];
}

export interface PurchasingResponse {
  suppliers: Supplier[];
  orders: PurchaseOrder[];
  monthly: { period: string; orders: number; amount: number }[];
  reorder_plan: ReorderPlanRow[];
}

export interface CustomersResponse {
  customers: Customer[];
  segments: Segment[];
  dormant: Customer[];
  acquisition: { period: string; customers: number }[];
}

export interface HrResponse {
  employees: Employee[];
  by_department: DepartmentHeadcount[];
  payroll: PayrollRow[];
}

export interface FinanceResponse {
  monthly: FinancialMonth[];
  bridge: Record<string, number>;
  by_category: { category: string; entries: number; amount: number }[];
  by_department: { department: string; amount: number }[];
  entries: ExpenseRow[];
}

/** Un département de l'ERP, tel que présenté dans la navigation. */
export interface DepartmentNav {
  code: string;
  route: string;
  icon: string;
  name: string;
}
