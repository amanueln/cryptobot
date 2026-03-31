import {
  Component, inject, signal, computed, output, OnInit, OnDestroy,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, HealthData } from '../../services/api.service';

@Component({
  selector: 'app-status-banner',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="banner-root">

      <!-- Left: status dot + text -->
      <div class="banner-left">
        <span
          class="status-dot"
          [class.running]="isRunning()"
          [class.stopped]="!isRunning()"
          [title]="isRunning() ? 'Bot is running' : 'Bot is stopped'"
        ></span>
        <div class="status-text-block">
          <span class="status-headline">{{ statusHeadline() }}</span>
          <span class="status-sub">{{ lastActionText() }}</span>
        </div>
      </div>

      <!-- Centre: quick stats -->
      <div class="quick-stats">
        <div class="qs-item">
          <span class="qs-label">EQUITY</span>
          <span class="qs-value">{{ equityText() }}</span>
        </div>
        <div class="qs-divider"></div>
        <div class="qs-item">
          <span class="qs-label">NET P&amp;L</span>
          <span class="qs-value" [class.positive]="pnlPositive()" [class.negative]="!pnlPositive()">
            {{ pnlText() }}
          </span>
        </div>
        <div class="qs-divider"></div>
        <div class="qs-item">
          <span class="qs-label">TRADES</span>
          <span class="qs-value">{{ tradesText() }}</span>
        </div>
        <div class="qs-divider"></div>
        <div class="qs-item">
          <span class="qs-label">UPTIME</span>
          <span class="qs-value">{{ uptimeText() }}</span>
        </div>
      </div>

      <!-- Right: action buttons -->
      <div class="banner-actions">
        <!-- Tools dropdown -->
        <div class="dropdown-wrapper">
          <button class="btn btn-tools" (click)="toggleDropdown()">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.07 4.93l-1.41 1.41M4.93 4.93l1.41 1.41M12 2v2M12 20v2M2 12h2M20 12h2M19.07 19.07l-1.41-1.41M4.93 19.07l1.41-1.41"></path>
            </svg>
            Tools
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>
          <div class="dropdown-menu" *ngIf="dropdownOpen()">
            <button class="dropdown-item" (click)="selectTool('simulator')">
              <span class="tool-icon">⟳</span> DCA Simulator
            </button>
            <button class="dropdown-item" (click)="selectTool('regime')">
              <span class="tool-icon">◈</span> Regime Visualizer
            </button>
            <button class="dropdown-item" (click)="selectTool('self-check')">
              <span class="tool-icon">✓</span> Self-Check
            </button>
          </div>
        </div>

        <button class="btn btn-reset" (click)="onResetClicked()">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
          Reset Data
        </button>
        <button class="btn btn-update" (click)="onUpdateClicked()">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="23 4 23 10 17 10"></polyline>
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
          </svg>
          Update Bot
        </button>
      </div>

    </div>
  `,
  styles: [`
    :host { display: block; width: 100%; }

    .banner-root {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
      padding: 14px 20px;
      background: linear-gradient(135deg, #1a1d2e 0%, #242840 100%);
      border-bottom: 1px solid #2d3148;
      box-shadow: 0 2px 12px rgba(0,0,0,0.4);
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }

    /* Status dot + text */
    .banner-left {
      display: flex;
      align-items: center;
      gap: 10px;
      flex-shrink: 0;
    }

    .status-dot {
      width: 12px;
      height: 12px;
      border-radius: 50%;
      flex-shrink: 0;
      box-shadow: 0 0 0 3px rgba(0,0,0,0.3);
    }

    .status-dot.running {
      background: #4ade80;
      box-shadow: 0 0 0 3px rgba(74, 222, 128, 0.2), 0 0 8px rgba(74, 222, 128, 0.5);
      animation: pulse-green 2s ease-in-out infinite;
    }

    .status-dot.stopped {
      background: #f87171;
      box-shadow: 0 0 0 3px rgba(248, 113, 113, 0.2);
    }

    @keyframes pulse-green {
      0%, 100% { box-shadow: 0 0 0 3px rgba(74,222,128,0.2), 0 0 8px rgba(74,222,128,0.4); }
      50%       { box-shadow: 0 0 0 5px rgba(74,222,128,0.1), 0 0 16px rgba(74,222,128,0.6); }
    }

    .status-text-block {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .status-headline {
      font-size: 14px;
      font-weight: 600;
      color: #e2e8f0;
      white-space: nowrap;
    }

    .status-sub {
      font-size: 11px;
      color: #6b7280;
      white-space: nowrap;
    }

    /* Quick stats */
    .quick-stats {
      display: flex;
      align-items: center;
      gap: 0;
      flex: 1;
      justify-content: center;
      flex-wrap: wrap;
      gap: 0;
    }

    .qs-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 2px;
      padding: 0 18px;
    }

    .qs-divider {
      width: 1px;
      height: 30px;
      background: #2d3148;
      flex-shrink: 0;
    }

    .qs-label {
      font-size: 9px;
      font-weight: 700;
      letter-spacing: 0.1em;
      color: #6b7280;
      text-transform: uppercase;
      white-space: nowrap;
    }

    .qs-value {
      font-size: 15px;
      font-weight: 600;
      color: #e2e8f0;
      white-space: nowrap;
    }

    .qs-value.positive { color: #4ade80; }
    .qs-value.negative { color: #f87171; }

    /* Action buttons */
    .banner-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
      margin-left: auto;
    }

    .btn {
      display: flex;
      align-items: center;
      gap: 5px;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid transparent;
      transition: all 0.15s ease;
      white-space: nowrap;
    }

    .btn-tools {
      background: #1e2130;
      border-color: #2d3148;
      color: #94a3b8;
    }

    .btn-tools:hover {
      background: #2d3148;
      border-color: #60a5fa;
      color: #e2e8f0;
    }

    .btn-reset {
      background: #3b1a1a;
      border-color: #dc2626;
      color: #f87171;
    }

    .btn-reset:hover {
      background: #dc2626;
      color: #fff;
    }

    .btn-update {
      background: #1e3a5f;
      border-color: #2563eb;
      color: #60a5fa;
    }

    .btn-update:hover {
      background: #2563eb;
      color: #fff;
    }

    /* Dropdown */
    .dropdown-wrapper {
      position: relative;
    }

    .dropdown-menu {
      position: absolute;
      top: calc(100% + 6px);
      right: 0;
      background: #1a1d2e;
      border: 1px solid #2d3148;
      border-radius: 8px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.5);
      z-index: 50;
      min-width: 160px;
      overflow: hidden;
      animation: fadeIn 0.1s ease;
    }

    .dropdown-item {
      display: flex;
      align-items: center;
      gap: 8px;
      width: 100%;
      padding: 9px 14px;
      background: transparent;
      border: none;
      color: #e2e8f0;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      text-align: left;
      transition: background 0.1s ease;
    }

    .dropdown-item:hover { background: #242840; }

    .tool-icon {
      font-size: 13px;
      color: #6b7280;
    }

    @keyframes fadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
  `],
})
export class StatusBannerComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);

  readonly toolSelected = output<'simulator' | 'regime' | 'self-check'>();
  readonly updateClicked = output<void>();
  readonly resetClicked = output<void>();

  readonly health = signal<HealthData | null>(null);
  readonly dropdownOpen = signal(false);

  private readonly status = this.api.status;

  readonly isRunning = computed(() => this.health()?.bot_running ?? false);

  readonly statusHeadline = computed(() => {
    const s = this.status();
    const h = this.health();
    if (!s && !h) return 'Loading…';
    const running = h?.bot_running ?? false;
    const pairCount = s?.pairs?.length ?? h?.active_pairs?.length ?? 0;
    const verb = running ? 'running' : 'stopped';
    return `Bot is ${verb} · watching ${pairCount} pair${pairCount !== 1 ? 's' : ''}`;
  });

  readonly lastActionText = computed(() => {
    const s = this.status();
    const ts = s?.last_trade_time ?? this.health()?.last_trade ?? null;
    if (!ts) return 'No recent trades';
    try {
      const diff = Date.now() - new Date(ts).getTime();
      const mins = Math.floor(diff / 60_000);
      if (mins < 1)   return 'Last trade: just now';
      if (mins < 60)  return `Last trade: ${mins}m ago`;
      const hrs = Math.floor(mins / 60);
      if (hrs < 24)   return `Last trade: ${hrs}h ago`;
      return `Last trade: ${Math.floor(hrs / 24)}d ago`;
    } catch { return 'Last trade: unknown'; }
  });

  readonly equityText = computed(() => {
    const s = this.status();
    if (!s) return '—';
    const v = s.equity;
    if (v >= 1_000_000) return '$' + (v / 1_000_000).toFixed(2) + 'M';
    if (v >= 1_000)     return '$' + (v / 1_000).toFixed(2) + 'K';
    return '$' + v.toFixed(2);
  });

  readonly pnlPositive = computed(() => (this.status()?.pnl ?? 0) >= 0);

  readonly pnlText = computed(() => {
    const s = this.status();
    if (!s) return '—';
    const sign = s.pnl >= 0 ? '+' : '';
    return sign + '$' + Math.abs(s.pnl).toFixed(2);
  });

  readonly tradesText = computed(() => {
    const s = this.status();
    return s ? String(s.total_trades) : '—';
  });

  readonly uptimeText = computed(() => {
    const h = this.health();
    if (!h) return '—';
    const secs = h.uptime_seconds;
    if (secs < 60)     return `${secs}s`;
    if (secs < 3600)   return `${Math.floor(secs / 60)}m`;
    if (secs < 86400)  return `${Math.floor(secs / 3600)}h`;
    return `${Math.floor(secs / 86400)}d`;
  });

  ngOnInit(): void {
    this.api.fetchHealth().subscribe({
      next: (h) => this.health.set(h),
      error: () => {},
    });
  }

  ngOnDestroy(): void {}

  toggleDropdown(): void {
    this.dropdownOpen.update(v => !v);
  }

  selectTool(tool: 'simulator' | 'regime' | 'self-check'): void {
    this.dropdownOpen.set(false);
    this.toolSelected.emit(tool);
  }

  onResetClicked(): void {
    this.resetClicked.emit();
  }

  onUpdateClicked(): void {
    this.updateClicked.emit();
  }
}
