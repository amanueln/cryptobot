import { Component, input, output } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { LiveCandleChartComponent } from '../live-candle-chart/live-candle-chart.component';

@Component({
  selector: 'app-holding-card-chart-modal',
  standalone: true,
  imports: [DecimalPipe, LiveCandleChartComponent],
  template: `
    <div class="modal-backdrop" (click)="close.emit()">
      <div class="modal" (click)="$event.stopPropagation()">
        <div class="modal-head">
          <div class="modal-title">{{ pair() }}</div>
          <button class="modal-close" (click)="close.emit()">close</button>
        </div>
        <div class="modal-body">
          <app-live-candle-chart
            [pair]="pair()"
            [entry]="entry()"
            [trailStop]="trailStop()"
            [height]="460"
          />
          <div class="info-panel">
            <div class="cell">
              <div class="label">Entry</div>
              <div class="value">{{ entry() | number:'1.4-6' }}</div>
            </div>
            <div class="cell">
              <div class="label">Now</div>
              <div class="value">{{ nowPrice() | number:'1.4-6' }}</div>
            </div>
            <div class="cell">
              <div class="label">Trail stop</div>
              <div class="value" style="color:#ef4444">{{ trailStop() | number:'1.4-6' }}</div>
            </div>
            <div class="cell">
              <div class="label">Peak (session)</div>
              <div class="value" style="color:#22c55e">{{ peakPrice() | number:'1.4-6' }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .modal-backdrop {
      position: fixed; inset: 0; background: rgba(0,0,0,.6);
      display: flex; align-items: center; justify-content: center; z-index: 100;
    }
    .modal {
      background: #161926; border: 1px solid #2d3148; border-radius: 8px;
      width: min(1080px, 94vw); max-height: 90vh; overflow: auto;
    }
    .modal-head {
      display: flex; justify-content: space-between; align-items: center;
      padding: 12px 16px; border-bottom: 1px solid #2d3148;
    }
    .modal-title { font-weight: 700; font-size: 16px; color: #e6ecf5; }
    .modal-close {
      background: transparent; color: #8895ad; border: 1px solid #2d3148;
      border-radius: 4px; padding: 4px 10px; cursor: pointer; font-family: inherit;
    }
    .modal-close:hover { color: #e6ecf5; border-color: #3b82f6; }
    .modal-body { padding: 12px 16px; }
    .info-panel {
      display: grid; grid-template-columns: repeat(4, 1fr);
      gap: 10px; margin-top: 12px;
    }
    .cell {
      background: #0f1117; border: 1px solid #2d3148; border-radius: 6px;
      padding: 8px 12px;
    }
    .label { color: #8895ad; font-size: 11px; text-transform: uppercase; letter-spacing: .5px; }
    .value { color: #e6ecf5; font-size: 16px; font-weight: 600; margin-top: 4px; }
  `],
})
export class HoldingCardChartModalComponent {
  pair = input.required<string>();
  entry = input<number>(0);
  trailStop = input<number>(0);
  nowPrice = input<number>(0);
  peakPrice = input<number>(0);
  close = output<void>();
}
