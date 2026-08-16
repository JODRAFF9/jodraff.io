import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { ApiService } from './core/api.service';
import { DEPARTMENTS } from './app.routes';

/**
 * Coquille de l'application : barre latérale des départements, sélecteur de
 * période et zone de contenu. Tant que la boutique n'est pas créée, l'utilisateur
 * est redirigé vers l'écran de démarrage.
 */
@Component({
  selector: 'erp-root',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    @if (ready()) {
      @if (company(); as c) {
        <div class="shell">
          <aside class="sidebar">
            <div class="brand">
              <span class="brand-logo">{{ c.logo_emoji }}</span>
              <div>
                <div class="brand-name">{{ c.name }}</div>
                <div class="brand-type">{{ c.store_label }}</div>
              </div>
            </div>
            <div class="nav-label">Départements</div>
            <nav>
              @for (dept of departments; track dept.code) {
                <a class="nav-link" [routerLink]="'/' + dept.route"
                   routerLinkActive="active">
                  <span class="nav-icon">{{ dept.icon }}</span>{{ dept.name }}
                </a>
              }
            </nav>
            <div class="sidebar-foot">
              <div>Base SQL centrale</div>
              <div>{{ c.currency }} · TVA {{ (c.tax_rate * 100).toFixed(0) }} %</div>
              <button type="button" class="btn btn-danger" (click)="reset()">
                Réinitialiser la plateforme
              </button>
            </div>
          </aside>

          <main class="main">
            <div class="topbar">
              <span class="muted">Période analysée</span>
              <div class="seg" role="group" aria-label="Période analysée">
                @for (option of periods; track option.days) {
                  <button type="button" [class.on]="days() === option.days"
                          (click)="setDays(option.days)">{{ option.label }}</button>
                }
              </div>
            </div>
            <router-outlet />
          </main>
        </div>
      } @else {
        <router-outlet />
      }
    } @else {
      <div class="overlay">
        <div class="overlay-box">
          <div class="spinner" aria-hidden="true"></div>
          <div>Connexion à l'API…</div>
        </div>
      </div>
    }
  `,
})
export class AppComponent {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  protected readonly departments = DEPARTMENTS;
  protected readonly periods = [
    { label: '7 jours', days: 7 },
    { label: '30 jours', days: 30 },
    { label: '90 jours', days: 90 },
    { label: '12 mois', days: 365 },
  ];

  protected readonly company = this.api.company;
  protected readonly days = this.api.days;
  protected readonly ready = signal(false);

  constructor() {
    this.api.health().subscribe({
      next: (health) => {
        if (!health.configured) {
          this.ready.set(true);
          void this.router.navigate(['/demarrage']);
          return;
        }
        this.api.loadCompany().subscribe({
          next: () => this.ready.set(true),
          error: () => { this.ready.set(true); void this.router.navigate(['/demarrage']); },
        });
      },
      error: () => { this.ready.set(true); void this.router.navigate(['/demarrage']); },
    });
  }

  protected setDays(days: number): void {
    this.api.days.set(days);
  }

  protected reset(): void {
    if (!confirm('Réinitialiser la plateforme ? Toutes les données seront effacées.')) return;
    this.api.resetCompany().subscribe(() => void this.router.navigate(['/demarrage']));
  }
}
