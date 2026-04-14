import { Component, signal, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-setup',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="setup-root">
      <div class="setup-card">
        <div class="setup-header">
          <div class="setup-dot"></div>
          <span class="setup-title">CRYPTOBOT</span>
        </div>
        <p class="setup-subtitle">First-time setup</p>

        @if (qrPng()) {
          <div class="setup-steps">
            <p class="step-text">1. Open Google Authenticator on your phone</p>
            <p class="step-text">2. Scan this QR code or enter the key manually</p>
          </div>

          <img [src]="'data:image/png;base64,' + qrPng()" class="qr-img" alt="QR Code" />

          <div class="secret-row">
            <code class="secret-text">{{ secret() }}</code>
            <button class="copy-btn" (click)="copySecret()">{{ copied() ? 'Copied' : 'Copy' }}</button>
          </div>

          <p class="step-text" style="margin-top: 20px">3. Enter the 6-digit code to verify</p>

          <form (ngSubmit)="confirm()" class="setup-form">
            <input
              type="text"
              [(ngModel)]="code"
              name="code"
              class="code-input"
              placeholder="000000"
              maxlength="6"
              pattern="[0-9]*"
              inputmode="numeric"
              autocomplete="one-time-code"
            />
            <button type="submit" class="setup-btn" [disabled]="loading() || code.length !== 6">
              {{ loading() ? 'Verifying...' : 'Verify & Activate' }}
            </button>
          </form>

          @if (error()) {
            <div class="setup-error">{{ error() }}</div>
          }
        } @else {
          <p class="step-text">Loading setup...</p>
        }
      </div>
    </div>
  `,
  styles: [`
    .setup-root {
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; background: #0f1117;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }
    .setup-card {
      background: rgba(30,33,48,0.7); border: 1px solid #2d3148;
      border-radius: 12px; padding: 36px 32px; width: 380px;
      text-align: center;
    }
    .setup-header {
      display: flex; align-items: center; justify-content: center; gap: 8px;
      margin-bottom: 8px;
    }
    .setup-dot {
      width: 10px; height: 10px; border-radius: 50%;
      background: #4ade80; box-shadow: 0 0 8px rgba(74,222,128,0.4);
    }
    .setup-title {
      font-size: 14px; font-weight: 700; letter-spacing: 0.12em;
      color: #38bdf8;
    }
    .setup-subtitle {
      font-size: 13px; color: #94a3b8; margin-bottom: 20px; font-weight: 600;
    }
    .setup-steps { margin-bottom: 16px; }
    .step-text {
      font-size: 11px; color: #6b7280; margin: 4px 0; line-height: 1.5;
    }
    .qr-img {
      width: 200px; height: 200px; border-radius: 8px;
      background: white; padding: 8px; margin: 12px auto; display: block;
    }
    .secret-row {
      display: flex; align-items: center; justify-content: center; gap: 8px;
      margin: 12px 0;
    }
    .secret-text {
      font-size: 10px; color: #94a3b8; letter-spacing: 0.05em;
      font-family: 'JetBrains Mono', monospace;
      background: rgba(15,17,23,0.8); padding: 6px 10px; border-radius: 4px;
      border: 1px solid #2d3148; word-break: break-all;
    }
    .copy-btn {
      font-size: 9px; font-weight: 700; padding: 4px 10px;
      background: rgba(56,189,248,0.1); color: #38bdf8;
      border: 1px solid rgba(56,189,248,0.3); border-radius: 4px;
      cursor: pointer; text-transform: uppercase;
    }
    .copy-btn:hover { background: rgba(56,189,248,0.2); }
    .setup-form {
      display: flex; flex-direction: column; gap: 10px; margin-top: 12px;
    }
    .code-input {
      width: 100%; padding: 14px; font-size: 24px; font-weight: 700;
      text-align: center; letter-spacing: 0.3em;
      background: rgba(15,17,23,0.8); color: #f1f5f9;
      border: 1px solid #2d3148; border-radius: 8px;
      font-family: 'JetBrains Mono', monospace;
      outline: none; transition: border-color 0.15s;
      box-sizing: border-box;
    }
    .code-input:focus { border-color: #38bdf8; }
    .code-input::placeholder { color: #2d3148; }
    .setup-btn {
      padding: 12px; font-size: 12px; font-weight: 700;
      background: rgba(74,222,128,0.15); color: #4ade80;
      border: 1px solid rgba(74,222,128,0.3); border-radius: 8px;
      cursor: pointer; transition: all 0.15s;
      text-transform: uppercase; letter-spacing: 0.08em;
    }
    .setup-btn:hover:not(:disabled) { background: rgba(74,222,128,0.25); }
    .setup-btn:disabled { opacity: 0.4; cursor: not-allowed; }
    .setup-error {
      margin-top: 12px; font-size: 11px; color: #f87171; font-weight: 600;
    }
  `],
})
export class SetupComponent implements OnInit {
  private http = inject(HttpClient);
  private router = inject(Router);

  qrPng = signal('');
  secret = signal('');
  code = '';
  loading = signal(false);
  error = signal('');
  copied = signal(false);

  ngOnInit() {
    this.http.get<any>('/api/auth/setup').subscribe({
      next: (data) => {
        this.qrPng.set(data.qr_png);
        this.secret.set(data.secret);
      },
      error: (err) => {
        if (err.status === 400) {
          this.router.navigate(['/login']);
        }
      },
    });
  }

  copySecret() {
    navigator.clipboard.writeText(this.secret());
    this.copied.set(true);
    setTimeout(() => this.copied.set(false), 2000);
  }

  confirm() {
    this.loading.set(true);
    this.error.set('');
    this.http.post<any>('/api/auth/setup/confirm', { code: this.code }).subscribe({
      next: () => {
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.loading.set(false);
        this.code = '';
        if (err.status === 401) {
          this.error.set('Invalid code. Check your authenticator and try again.');
        } else {
          this.error.set('Setup error. Try refreshing the page.');
        }
      },
    });
  }
}
