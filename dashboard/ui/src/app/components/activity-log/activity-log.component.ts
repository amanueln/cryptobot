import {
  Component, inject, signal, OnInit, OnDestroy,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, EventData } from '../../services/api.service';

interface ActionConfig {
  label: string;
  color: string;
  bg: string;
}

const ACTION_MAP: Record<string, ActionConfig> = {
  trade_buy:    { label: 'Bought',         color: '#4ade80', bg: 'rgba(74,222,128,0.12)' },
  trade_sell:   { label: 'Sold',           color: '#f87171', bg: 'rgba(248,113,113,0.12)' },
  atr_adjust:   { label: 'Spacing changed',color: '#60a5fa', bg: 'rgba(96,165,250,0.12)' },
  vol_check:    { label: 'Vol check',      color: '#c084fc', bg: 'rgba(192,132,252,0.12)' },
  range_recalc: { label: 'Range recalc',   color: '#fbbf24', bg: 'rgba(251,191,36,0.12)' },
  scan_complete:{ label: 'Scan complete',  color: '#9ca3af', bg: 'rgba(156,163,175,0.10)' },
};

const DEFAULT_ACTION: ActionConfig = {
  label: 'Event',
  color: '#6b7280',
  bg: 'rgba(107,114,128,0.10)',
};

@Component({
  selector: 'app-activity-log',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="log-root">
      <div class="log-header">
        <span class="log-title">Activity Log</span>
        <span class="log-count" *ngIf="events().length">{{ events().length }} events</span>
      </div>

      <div class="log-scroll">
        <div *ngIf="loading() && events().length === 0" class="log-loading">
          Loading events…
        </div>

        <div *ngIf="!loading() && events().length === 0" class="log-empty">
          No recent activity
        </div>

        <div
          *ngFor="let evt of events()"
          class="log-entry"
        >
          <span class="log-time">{{ formatRelTime(evt.timestamp) }}</span>
          <span
            class="log-action"
            [style.color]="actionConfig(evt.event_type).color"
            [style.background]="actionConfig(evt.event_type).bg"
          >{{ actionConfig(evt.event_type).label }}</span>
          <div class="log-body">
            <div class="log-title-text">{{ evt.title }}</div>
            <div class="log-detail" *ngIf="evt.detail">{{ evt.detail }}</div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host { display: block; width: 100%; }

    .log-root {
      background: #1a1d2e;
      border: 1px solid #2d3148;
      border-radius: 10px;
      overflow: hidden;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }

    .log-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 16px 10px;
      border-bottom: 1px solid #2d3148;
    }

    .log-title {
      font-size: 13px;
      font-weight: 700;
      color: #e2e8f0;
      letter-spacing: 0.03em;
    }

    .log-count {
      font-size: 10px;
      font-weight: 600;
      color: #6b7280;
      background: #242840;
      padding: 2px 7px;
      border-radius: 10px;
    }

    .log-scroll {
      max-height: 280px;
      overflow-y: auto;
      padding: 4px 0;
      scrollbar-width: thin;
      scrollbar-color: #2d3148 transparent;
    }

    .log-scroll::-webkit-scrollbar { width: 4px; }
    .log-scroll::-webkit-scrollbar-thumb { background: #2d3148; border-radius: 2px; }
    .log-scroll::-webkit-scrollbar-track { background: transparent; }

    .log-loading,
    .log-empty {
      padding: 24px 16px;
      text-align: center;
      font-size: 12px;
      color: #6b7280;
      font-style: italic;
    }

    .log-entry {
      display: flex;
      align-items: flex-start;
      gap: 8px;
      padding: 7px 16px;
      border-bottom: 1px solid rgba(45,49,72,0.5);
      transition: background 0.1s ease;
    }

    .log-entry:last-child { border-bottom: none; }
    .log-entry:hover { background: rgba(255,255,255,0.02); }

    .log-time {
      font-size: 10px;
      font-weight: 600;
      color: #6b7280;
      font-family: 'JetBrains Mono', 'Fira Code', monospace;
      min-width: 30px;
      margin-top: 2px;
      flex-shrink: 0;
    }

    .log-action {
      font-size: 10px;
      font-weight: 700;
      padding: 2px 7px;
      border-radius: 4px;
      white-space: nowrap;
      flex-shrink: 0;
      margin-top: 1px;
      letter-spacing: 0.03em;
    }

    .log-body {
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 0;
    }

    .log-title-text {
      font-size: 12px;
      font-weight: 500;
      color: #e2e8f0;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .log-detail {
      font-size: 11px;
      color: #6b7280;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  `],
})
export class ActivityLogComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);

  readonly events = signal<EventData[]>([]);
  readonly loading = signal(true);

  private _pollInterval: any;

  ngOnInit(): void {
    this.loadEvents();
    this._pollInterval = setInterval(() => this.loadEvents(), 60_000);
  }

  ngOnDestroy(): void {
    if (this._pollInterval) clearInterval(this._pollInterval);
  }

  private loadEvents(): void {
    this.api.fetchEvents(50).subscribe({
      next: (data) => {
        this.events.set(data);
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
      },
    });
  }

  actionConfig(eventType: string): ActionConfig {
    return ACTION_MAP[eventType] ?? DEFAULT_ACTION;
  }

  formatRelTime(timestamp: string): string {
    try {
      const diff = Date.now() - new Date(timestamp).getTime();
      const mins  = Math.floor(diff / 60_000);
      if (mins < 1)  return 'now';
      if (mins < 60) return `${mins}m`;
      const hrs = diff / 3_600_000;
      if (hrs < 24)  return `${hrs.toFixed(1)}h`;
      return `${Math.floor(hrs / 24)}d`;
    } catch {
      return '?';
    }
  }
}
