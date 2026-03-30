import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { StatsBarComponent } from './components/stats-bar/stats-bar.component';
import { ApiService } from './services/api.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, StatsBarComponent],
  template: `
    <div class="min-h-screen" style="background: #0f1117; color: #e1e4ed;">
      <app-stats-bar />

      <nav class="flex gap-1 px-4 py-2" style="background: #1a1d29; border-bottom: 1px solid #2d3148;">
        <a routerLink="/" routerLinkActive="tab-active" [routerLinkActiveOptions]="{exact: true}"
           class="tab-link">Combined</a>
        <a routerLink="/pair/DOGE-USD" routerLinkActive="tab-active"
           class="tab-link">DOGE</a>
        <a routerLink="/pair/ETH-USD" routerLinkActive="tab-active"
           class="tab-link">ETH</a>
        <a routerLink="/pair/PEPE-USD" routerLinkActive="tab-active"
           class="tab-link">PEPE</a>
        <a routerLink="/simulator" routerLinkActive="tab-active"
           class="tab-link">Simulator</a>
        <a routerLink="/regime" routerLinkActive="tab-active"
           class="tab-link">Regime</a>
      </nav>

      <main class="p-4">
        <router-outlet />
      </main>
    </div>
  `,
  styles: [`
    .tab-link {
      padding: 6px 16px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 500;
      color: #8b8fa3;
      text-decoration: none;
      transition: all 0.15s;
    }
    .tab-link:hover {
      background: #242736;
      color: #e1e4ed;
    }
    .tab-active {
      background: #242736 !important;
      color: #e1e4ed !important;
      border: 1px solid #2d3148;
    }
  `]
})
export class App implements OnInit, OnDestroy {
  private api = inject(ApiService);

  ngOnInit() {
    this.api.startPolling(60);
  }

  ngOnDestroy() {
    this.api.stopPolling();
  }
}
