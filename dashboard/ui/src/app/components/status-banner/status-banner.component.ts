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

      <!-- Left: status dot + summary text -->
      <div class="banner-left">
        <span
          class="status-dot"
          [class.running]="isRunning()"
          [class.stopped]="!isRunning()"
        ></span>
        <div class="status-text-block">
          <span class="status-headline">{{ statusHeadline() }}</span>
          <span class="status-summary">{{ summaryText() }}</span>
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
            <button class="dropdown-item" (click)="selectTool('scanner')">
              <span class="tool-icon">&#8853;</span> Pair Scanner
            </button>
            <button class="dropdown-item" (click)="selectTool('simulator')">
              <span class="tool-icon">&#10227;</span> DCA Simulator
            </button>
            <button class="dropdown-item" (click)="selectTool('regime')">
              <span class="tool-icon">&#9672;</span> Regime Visualizer
            </button>
            <button class="dropdown-item" (click)="selectTool('self-check')">
              <span class="tool-icon">&#10003;</span> Self-Check
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

    .banner-left {
      display: flex;
      align-items: center;
      gap: 10px;
      flex: 1;
      min-width: 0;
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
      gap: 3px;
      min-width: 0;
    }

    .status-headline {
      font-size: 14px;
      font-weight: 600;
      color: #e2e8f0;
      white-space: nowrap;
    }

    .status-summary {
      font-size: 12px;
      color: #94a3b8;
      line-height: 1.4;
    }

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

  readonly toolSelected = output<'scanner' | 'simulator' | 'regime' | 'self-check'>();
  readonly updateClicked = output<void>();
  readonly resetClicked = output<void>();

  readonly health = signal<HealthData | null>(null);
  readonly dropdownOpen = signal(false);

  private readonly status = this.api.status;

  readonly isRunning = computed(() => this.health()?.bot_running ?? false);

  readonly statusHeadline = computed(() => {
    const s = this.status();
    const h = this.health();
    if (!s && !h) return 'Connecting...';
    const running = h?.bot_running ?? false;
    const pairCount = s?.pairs?.length ?? h?.active_pairs?.length ?? 0;
    if (!running) return 'Bot is stopped';
    const names = s?.pairs?.map(p => p.pair.replace('-USD', '')).join(', ') ?? '';
    return `Watching ${pairCount} pairs${names ? ': ' + names : ''}`;
  });

  readonly summaryText = computed(() => {
    const s = this.status();
    if (!s) return 'Loading...';

    // Use server-generated summary if available
    if (s.summary) return s.summary;

    // Fallback: generate client-side
    const pnl = s.pnl;
    const trades = s.total_trades;
    let text = '';
    if (pnl >= 0) {
      text = `Up $${pnl.toFixed(2)}.`;
    } else {
      text = `Down $${Math.abs(pnl).toFixed(2)}.`;
    }
    if (trades === 0) {
      text += ' No trades yet — waiting for the right entry.';
    } else {
      text += ` ${trades} trade${trades !== 1 ? 's' : ''} completed.`;
    }
    return text;
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

  selectTool(tool: 'scanner' | 'simulator' | 'regime' | 'self-check'): void {
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
