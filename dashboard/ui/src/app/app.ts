import { Component, OnInit, OnDestroy, signal, inject } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { CommonModule } from '@angular/common';
import { StatsBarComponent } from './components/stats-bar/stats-bar.component';
import { ApiService } from './services/api.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, StatsBarComponent, CommonModule],
  template: `
    <div class="min-h-screen" style="background: #0f1117; color: #e1e4ed;">
      <app-stats-bar />

      <nav class="flex gap-1 px-4 py-2" style="background: #1a1d29; border-bottom: 1px solid #2d3148;">
        <a routerLink="/" routerLinkActive="tab-active" [routerLinkActiveOptions]="{exact: true}"
           class="tab-link">Combined</a>
        <a *ngFor="let pair of activePairs()"
           [routerLink]="'/pair/' + pair" routerLinkActive="tab-active"
           class="tab-link">{{ pairLabel(pair) }}</a>
        <span class="tab-separator"></span>
        <a routerLink="/ml-brain" routerLinkActive="tab-active"
           class="tab-link tab-ai">AI Brain</a>
        <a routerLink="/pair-scanner" routerLinkActive="tab-active"
           class="tab-link tab-ai">Scanner</a>
        <a routerLink="/simulator" routerLinkActive="tab-active"
           class="tab-link">Simulator</a>
        <a routerLink="/regime" routerLinkActive="tab-active"
           class="tab-link">Regime</a>
        <a routerLink="/self-check" routerLinkActive="tab-active"
           class="tab-link tab-ai">Self-Check</a>
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
    .tab-ai {
      color: #a78bfa;
    }
    .tab-ai:hover {
      color: #c4b5fd;
    }
    .tab-separator {
      width: 1px;
      background: #2d3148;
      margin: 4px 6px;
    }
  `]
})
export class App implements OnInit, OnDestroy {
  private api = inject(ApiService);
  activePairs = signal<string[]>([]);

  ngOnInit() {
    this.api.startPolling(60);
    this.api.fetchPairs().subscribe({
      next: (pairs) => this.activePairs.set(pairs),
      error: () => {},
    });
  }

  ngOnDestroy() {
    this.api.stopPolling();
  }

  pairLabel(pair: string): string {
    return pair.replace('-USD', '');
  }
}
