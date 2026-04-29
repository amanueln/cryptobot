// dashboard/ui/src/app/components/scanner-bot/scanner-bot.component.ts
import { Component, OnInit, OnDestroy, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-scanner-bot',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './scanner-bot.component.html',
  styleUrl: './scanner-bot.component.css',
})
export class ScannerBotComponent implements OnInit, OnDestroy {
  private api = inject(ApiService);
  private pollHandle: any = null;

  stats = signal<any>(null);
  positions = signal<any[]>([]);
  trades = signal<any[]>([]);
  decisions = signal<any[]>([]);

  ngOnInit() {
    this.refresh();
    this.pollHandle = setInterval(() => this.refresh(), 5000);
  }

  ngOnDestroy() {
    if (this.pollHandle) clearInterval(this.pollHandle);
  }

  refresh() {
    this.api.getScannerBotStats().subscribe(s => this.stats.set(s));
    this.api.getScannerBotPositions().subscribe(p => this.positions.set(p));
    this.api.getScannerBotTrades(50).subscribe(t => this.trades.set(t));
    this.api.getScannerBotAlertDecisions(50).subscribe(d => this.decisions.set(d));
  }

  sellNow(positionId: number) {
    if (!confirm('Sell this position at the current market price?')) return;
    this.api.scannerBotSellNow(positionId).subscribe({
      next: () => this.refresh(),
      error: (e) => alert('Sell failed: ' + (e?.error?.message || e?.message)),
    });
  }

  formatHeld(mins: number | null): string {
    if (mins == null) return '—';
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${h}h ${m}m`;
  }

  pctClass(v: number | null | undefined): string {
    if (v == null) return '';
    return v >= 0 ? 'pos' : 'neg';
  }
}
