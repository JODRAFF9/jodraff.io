import { Routes } from '@angular/router';

import { DepartmentNav } from './core/models';

/** Navigation des départements, même ordre dans les quatre interfaces. */
export const DEPARTMENTS: DepartmentNav[] = [
  { code: 'OVERVIEW', route: 'vue-ensemble', icon: '📊', name: "Vue d'ensemble" },
  { code: 'SALES', route: 'ventes', icon: '🧾', name: 'Ventes' },
  { code: 'STOCK', route: 'stock', icon: '📦', name: 'Stock' },
  { code: 'PURCH', route: 'achats', icon: '🚚', name: 'Achats' },
  { code: 'CRM', route: 'clients', icon: '👥', name: 'Clients' },
  { code: 'HR', route: 'rh', icon: '🧑‍💼', name: 'Ressources humaines' },
  { code: 'FIN', route: 'finance', icon: '💰', name: 'Finance' },
];

/** Chargement paresseux : chaque département arrive dans son propre bundle. */
export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'vue-ensemble' },
  {
    path: 'demarrage',
    loadComponent: () => import('./pages/onboarding.component').then((m) => m.OnboardingComponent),
    title: 'Créer ma boutique, ERP Boutique',
  },
  {
    path: 'vue-ensemble',
    loadComponent: () => import('./pages/overview.component').then((m) => m.OverviewComponent),
    title: "Vue d'ensemble, ERP Boutique",
  },
  {
    path: 'ventes',
    loadComponent: () => import('./pages/sales.component').then((m) => m.SalesComponent),
    title: 'Ventes, ERP Boutique',
  },
  {
    path: 'stock',
    loadComponent: () => import('./pages/stock.component').then((m) => m.StockComponent),
    title: 'Stock, ERP Boutique',
  },
  {
    path: 'achats',
    loadComponent: () => import('./pages/purchasing.component').then((m) => m.PurchasingComponent),
    title: 'Achats, ERP Boutique',
  },
  {
    path: 'clients',
    loadComponent: () => import('./pages/customers.component').then((m) => m.CustomersComponent),
    title: 'Clients, ERP Boutique',
  },
  {
    path: 'rh',
    loadComponent: () => import('./pages/hr.component').then((m) => m.HrComponent),
    title: 'Ressources humaines, ERP Boutique',
  },
  {
    path: 'finance',
    loadComponent: () => import('./pages/finance.component').then((m) => m.FinanceComponent),
    title: 'Finance, ERP Boutique',
  },
  { path: '**', redirectTo: 'vue-ensemble' },
];
