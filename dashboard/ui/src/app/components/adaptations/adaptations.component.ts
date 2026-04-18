import {
  Component, inject, signal, OnInit, OnDestroy,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, AdaptationData, asUtcDate } from '../../services/api.service';

interface LoopConfig {
  label: string;
  icon: string;
  color: string;
  bg: string;
}

const LOOP_MAP: Record<string, LoopConfig> = {
  spacing_learned:  { label: 'Spacing',   icon: '↕', color: '#60a5fa', bg: 'rgba(96,165,250,0.12)' },
  pair_adjustment:  { label: 'Selection', icon: '★', color: '#4ade80', bg: 'rgba(74,222,128,0.12)' },
  vol_window_tuned: { label: 'Vol Model', icon: '◎', color: '#c084fc', bg: 'rgba(192,132,252,0.12)' },
};

const DEFAULT_LOOP: LoopConfig = {
  label: 'Learned', icon: '•', color: '#6b7280', bg: 'rgba(107,114,128,0.10)',
};

@Component({
  selector: 'app-adaptations',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="adapt-root">
      <div class="adapt-header">
        <span class="adapt-title">What it's learning</span>
        <span class="adapt-count" *ngIf="adaptations().length">{{ adaptations().length }} insights</span>
      </div>

      <div class="adapt-scroll">
        <div *ngIf="loading() && adaptations().length === 0" class="adapt-empty">
          No learning data yet. The bot needs a few days of trading to start finding patterns.
        </div>

        <div *ngIf="!loading() && adaptations().length === 0" class="adapt-empty">
          No adaptations yet. After 24-48 hours of trading, the bot will start showing what it learned here.
        </div>

        <div
          *ngFor="let item of adaptations()"
          class="adapt-entry"
        >
          <span class="adapt-time">{{ formatRelTime(item.timestamp) }}</span>
          <span
            class="adapt-badge"
            [style.color]="loopConfig(item.loop_type).color"
            [style.background]="loopConfig(item.loop_type).bg"
          >{{ loopConfig(item.loop_type).icon }} {{ loopConfig(item.loop_type).label }}</span>
          <div class="adapt-body">
            <div class="adapt-desc">{{ item.description }}</div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; width: 100%; }

    .adapt-root {
      background: #1a1d2e;
      border: 1px solid #2d3148;
      border-radius: 10px;
      overflow: hidden;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }

    .adapt-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 16px 10px;
      border-bottom: 1px solid #2d3148;
    }

    .adapt-title {
      font-size: 13px;
      font-weight: 700;
      color: #e2e8f0;
      letter-spacing: 0.03em;
    }

    .adapt-count {
      font-size: 10px;
      font-weight: 600;
      color: #6b7280;
      background: #242840;
      padding: 2px 7px;
      border-radius: 10px;
    }

    .adapt-scroll {
      max-height: 240px;
      overflow-y: auto;
      padding: 4px 0;
      scrollbar-width: thin;
      scrollbar-color: #2d3148 transparent;
    }

    .adapt-scroll::-webkit-scrollbar { width: 4px; }
    .adapt-scroll::-webkit-scrollbar-thumb { background: #2d3148; border-radius: 2px; }
    .adapt-scroll::-webkit-scrollbar-track { background: transparent; }

    .adapt-empty {
      padding: 20px 16px;
      text-align: center;
      font-size: 12px;
      color: #6b7280;
      line-height: 1.5;
    }

    .adapt-entry {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 8px 16px;
      border-bottom: 1px solid rgba(45,49,72,0.5);
      transition: background 0.1s ease;
    }

    .adapt-entry:last-child { border-bottom: none; }
    .adapt-entry:hover { background: rgba(255,255,255,0.02); }

    .adapt-time {
      font-size: 10px;
      font-weight: 600;
      color: #6b7280;
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      min-width: 30px;
      margin-top: 3px;
      flex-shrink: 0;
    }

    .adapt-badge {
      font-size: 10px;
      font-weight: 700;
      padding: 2px 8px;
      border-radius: 4px;
      white-space: nowrap;
      flex-shrink: 0;
      margin-top: 1px;
      letter-spacing: 0.03em;
    }

    .adapt-body {
      min-width: 0;
    }

    .adapt-desc {
      font-size: 12px;
      font-weight: 500;
      color: #94a3b8;
      line-height: 1.45;
    }
  `],
})
export class AdaptationsComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);

  readonly adaptations = signal<AdaptationData[]>([]);
  readonly loading = signal(true);

  private _pollInterval: any;

  ngOnInit(): void {
    this.loadAdaptations();
    this._pollInterval = setInterval(() => this.loadAdaptations(), 120_000); // every 2 min
  }

  ngOnDestroy(): void {
    if (this._pollInterval) clearInterval(this._pollInterval);
  }

  private loadAdaptations(): void {
    this.api.fetchAdaptations(30).subscribe({
      next: (data) => {
        this.adaptations.set(data);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
      },
    });
  }

  loopConfig(loopType: string): LoopConfig {
    return LOOP_MAP[loopType] ?? DEFAULT_LOOP;
  }

  formatRelTime(timestamp: string): string {
    try {
      const diff = Date.now() - (asUtcDate(timestamp)?.getTime() ?? Date.now());
      const mins = Math.floor(diff / 60_000);
      if (mins < 1) return 'now';
      if (mins < 60) return `${mins}m`;
      const hrs = diff / 3_600_000;
      if (hrs < 24) return `${hrs.toFixed(0)}h`;
      return `${Math.floor(hrs / 24)}d`;
    } catch {
      return '?';
    }
  }
}
