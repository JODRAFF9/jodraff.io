import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

import {
  Company, CompanyCreate, CustomersResponse, FinanceResponse, HrResponse,
  Kpis, OverviewResponse, PurchasingResponse, SalesResponse, StockResponse,
  StoreTypesResponse,
} from './models';

/** URL de l'API REST, surchargeable par ?api=... pour un déploiement distinct. */
export const API_BASE = (() => {
  const override = new URLSearchParams(location.search).get('api');
  return (override ?? 'http://127.0.0.1:8000').replace(/\/$/, '');
})();

interface CreateResult {
  summary: Record<string, string | number>;
  company: Company;
}

/**
 * Point d'accès unique aux données.
 *
 * L'application Angular ne connaît pas la base : elle interroge l'API REST,
 * exactement comme le front HTML/CSS/JS. Les deux voient donc toujours les
 * mêmes chiffres, puisqu'il n'existe qu'une seule base SQL derrière.
 */
@Injectable({ providedIn: 'root' })
export class ApiService {
  /** Entreprise courante, signal partagé par toute l'application. */
  readonly company = signal<Company | null>(null);
  /** Période analysée, en jours (barre supérieure). */
  readonly days = signal<number>(30);

  constructor(private readonly http: HttpClient) {}

  private url(path: string): string {
    return `${API_BASE}/api${path}`;
  }

  /** Symbole monétaire courant, avec repli tant que l'entreprise n'est pas chargée. */
  symbol(): string {
    return this.company()?.currency_sym ?? '';
  }

  health(): Observable<{ status: string; configured: boolean; database: string }> {
    return this.http.get<{ status: string; configured: boolean; database: string }>(
      this.url('/health'));
  }

  storeTypes(): Observable<StoreTypesResponse> {
    return this.http.get<StoreTypesResponse>(this.url('/store-types'));
  }

  loadCompany(): Observable<Company> {
    return this.http.get<Company>(this.url('/company'))
      .pipe(tap((company) => this.company.set(company)));
  }

  createCompany(payload: CompanyCreate): Observable<CreateResult> {
    return this.http.post<CreateResult>(this.url('/company'), payload)
      .pipe(tap((result) => this.company.set(result.company)));
  }

  resetCompany(): Observable<{ status: string }> {
    return this.http.delete<{ status: string }>(this.url('/company'))
      .pipe(tap(() => this.company.set(null)));
  }

  kpis(days: number): Observable<Kpis> {
    return this.http.get<Kpis>(this.url(`/kpis?days=${days}`));
  }

  overview(days: number): Observable<OverviewResponse> {
    return this.http.get<OverviewResponse>(this.url(`/overview?days=${days}`));
  }

  sales(days: number): Observable<SalesResponse> {
    return this.http.get<SalesResponse>(this.url(`/sales?days=${days}`));
  }

  stock(days: number): Observable<StockResponse> {
    return this.http.get<StockResponse>(this.url(`/stock?days=${days}`));
  }

  purchasing(): Observable<PurchasingResponse> {
    return this.http.get<PurchasingResponse>(this.url('/purchasing'));
  }

  customers(): Observable<CustomersResponse> {
    return this.http.get<CustomersResponse>(this.url('/customers'));
  }

  hr(): Observable<HrResponse> {
    return this.http.get<HrResponse>(this.url('/hr'));
  }

  finance(): Observable<FinanceResponse> {
    return this.http.get<FinanceResponse>(this.url('/finance'));
  }
}
