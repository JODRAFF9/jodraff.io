import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { ApiService } from '../core/api.service';
import { Currency, StoreType } from '../core/models';

/**
 * Écran de démarrage : type de boutique + nom, et l'ERP est créé.
 * C'est exactement le même parcours que dans le dashboard Python et le
 * front HTML/CSS/JS, l'API fait le travail dans les trois cas.
 */
@Component({
  selector: 'erp-onboarding',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [FormsModule],
  template: `
    <main class="onboard-page">
      <section class="onboard">
        <div class="onboard-logo">🏪</div>
        <h1>Créez le tableau de bord de votre boutique</h1>
        <p class="lead">
          Indiquez le type de commerce que vous exploitez et son nom. La plateforme génère
          un ERP complet, ventes, stock, achats, clients, ressources humaines et finance, dans une base SQL unique, avec un historique d'activité déjà consolidé.
        </p>

        <h2 class="step-label"><span class="step-num">1</span> Quel type de boutique ?</h2>
        <div class="type-grid" role="radiogroup" aria-label="Type de boutique">
          @for (type of types(); track type.key) {
            <button type="button" class="type-card" role="radio"
                    [attr.aria-checked]="storeType() === type.key"
                    (click)="storeType.set(type.key)">
              <div class="type-icon">{{ type.icon }}</div>
              <div class="type-name">{{ type.label }}</div>
              <div class="type-tag">{{ type.tagline }}</div>
              <div class="type-meta">
                <span>{{ type.n_categories }} rayons</span>
                <span>{{ type.n_products }} produits</span>
                <span>{{ type.n_roles }} métiers</span>
              </div>
            </button>
          } @empty {
            <p class="type-tag">Chargement du catalogue des métiers…</p>
          }
        </div>

        <h2 class="step-label" style="margin-top:26px">
          <span class="step-num">2</span> Comment s'appelle-t-elle ?
        </h2>
        <div class="grid grid-3">
          <div class="field">
            <label for="name">Nom de la boutique</label>
            <input id="name" type="text" placeholder="Ex. : Chez Aminata"
                   [(ngModel)]="name" autocomplete="off">
          </div>
          <div class="field">
            <label for="city">Ville</label>
            <input id="city" type="text" [(ngModel)]="city">
          </div>
          <div class="field">
            <label for="country">Pays</label>
            <input id="country" type="text" [(ngModel)]="country">
          </div>
        </div>

        <details class="advanced">
          <summary>Options avancées</summary>
          <div class="grid grid-3">
            <div class="field">
              <label for="currency">Devise</label>
              <select id="currency" [(ngModel)]="currency">
                @for (c of currencies(); track c.code) {
                  <option [value]="c.code">{{ c.label }} ({{ c.symbol }})</option>
                }
              </select>
            </div>
            <div class="field">
              <label for="months">Profondeur d'historique</label>
              <select id="months" [(ngModel)]="months">
                <option [ngValue]="6">6 mois</option>
                <option [ngValue]="12">12 mois</option>
                <option [ngValue]="24">24 mois</option>
              </select>
            </div>
            <div class="field">
              <label for="traffic">Intensité d'activité</label>
              <select id="traffic" [(ngModel)]="traffic">
                <option [ngValue]="0.4">Petit commerce (×0,4)</option>
                <option [ngValue]="1">Activité normale (×1)</option>
                <option [ngValue]="2">Forte affluence (×2)</option>
              </select>
            </div>
          </div>
        </details>

        @if (error()) {
          <div class="notice notice-warn"><span>⚠️</span><div>{{ error() }}</div></div>
        } @else {
          <div class="notice notice-info">
            <span>ℹ️</span>
            <div>
              <b>Les six départements sont livrés d'office.</b>
              Ils partagent une seule base de données : une vente décharge le stock,
              met à jour la fiche client et le compte de résultat au même instant.
            </div>
          </div>
        }

        <div class="onboard-actions">
          <button type="button" class="btn" [disabled]="busy()" (click)="create()">
            {{ busy() ? 'Génération en cours…' : 'Créer mon tableau de bord' }}
          </button>
          <span class="muted">{{ echo() }}</span>
        </div>
      </section>
    </main>

    @if (busy()) {
      <div class="overlay">
        <div class="overlay-box">
          <div class="spinner" aria-hidden="true"></div>
          <div>Génération de l'ERP « {{ name() }} »…</div>
          <div class="progress"><div class="progress-bar" style="width:70%"></div></div>
        </div>
      </div>
    }
  `,
})
export class OnboardingComponent {
  private readonly api = inject(ApiService);
  private readonly router = inject(Router);

  protected readonly types = signal<StoreType[]>([]);
  protected readonly currencies = signal<Currency[]>([]);
  protected readonly storeType = signal<string | null>(null);
  protected readonly name = signal('');
  protected readonly city = signal('Abidjan');
  protected readonly country = signal("Côte d'Ivoire");
  protected readonly currency = signal('XOF');
  protected readonly months = signal(12);
  protected readonly traffic = signal(1);
  protected readonly busy = signal(false);
  protected readonly error = signal('');

  constructor() {
    this.api.storeTypes().subscribe({
      next: (data) => {
        this.types.set(data.types);
        this.currencies.set(data.currencies);
      },
      error: (err: { message?: string }) =>
        this.error.set(`API injoignable. Lancez : cd python && uvicorn api.main:app --port 8000 (${err.message ?? ''})`),
    });
  }

  protected echo(): string {
    if (!this.storeType()) return "Choisissez d'abord un type de boutique.";
    if (!this.name().trim()) return 'Indiquez maintenant le nom de la boutique.';
    return `Prêt : « ${this.name().trim()} ».`;
  }

  protected create(): void {
    const type = this.storeType();
    const name = this.name().trim();
    if (!type) { this.error.set('Sélectionnez le type de boutique (étape 1).'); return; }
    if (!name) { this.error.set('Le nom de la boutique est obligatoire (étape 2).'); return; }

    this.error.set('');
    this.busy.set(true);
    this.api.createCompany({
      name, store_type: type, currency: this.currency(),
      city: this.city().trim() || 'Abidjan',
      country: this.country().trim() || "Côte d'Ivoire",
      history_months: Number(this.months()),
      traffic_scale: Number(this.traffic()),
    }).subscribe({
      next: () => { this.busy.set(false); void this.router.navigate(['/vue-ensemble']); },
      error: (err: { message?: string }) => {
        this.busy.set(false);
        this.error.set(err.message ?? 'La création a échoué.');
      },
    });
  }
}
