import { Component, signal, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="login-root">
      <div class="login-card">
        <div class="login-header">
          <div class="login-dot"></div>
          <span class="login-title">CRYPTOBOT</span>
        </div>
        <p class="login-subtitle">Enter your authenticator code</p>

        <form (ngSubmit)="verify()" class="login-form">
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
            autofocus
          />
          <button type="submit" class="login-btn" [disabled]="loading() || code.length !== 6">
            {{ loading() ? 'Verifying...' : 'Login' }}
          </button>
        </form>

        @if (error()) {
          <div class="login-error">{{ error() }}</div>
        }
      </div>
    </div>
  `,
  styles: [`
    .login-root {
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; background: #0f1117;
      font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    }
    .login-card {
      background: rgba(30,33,48,0.7); border: 1px solid #2d3148;
      border-radius: 12px; padding: 40px 36px; width: 340px;
      text-align: center;
    }
    .login-header {
      display: flex; align-items: center; justify-content: center; gap: 8px;
      margin-bottom: 24px;
    }
    .login-dot {
      width: 10px; height: 10px; border-radius: 50%;
      background: #38bdf8; box-shadow: 0 0 8px rgba(56,189,248,0.4);
      animation: pulse 2s ease-in-out infinite;
    }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
    .login-title {
      font-size: 14px; font-weight: 700; letter-spacing: 0.12em;
      color: #38bdf8;
    }
    .login-subtitle {
      font-size: 12px; color: #6b7280; margin-bottom: 24px;
    }
    .login-form { display: flex; flex-direction: column; gap: 12px; }
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
    .login-btn {
      padding: 12px; font-size: 12px; font-weight: 700;
      background: rgba(56,189,248,0.15); color: #38bdf8;
      border: 1px solid rgba(56,189,248,0.3); border-radius: 8px;
      cursor: pointer; transition: all 0.15s;
      text-transform: uppercase; letter-spacing: 0.08em;
    }
    .login-btn:hover:not(:disabled) { background: rgba(56,189,248,0.25); }
    .login-btn:disabled { opacity: 0.4; cursor: not-allowed; }
    .login-error {
      margin-top: 12px; font-size: 11px; color: #f87171;
      font-weight: 600;
    }
  `],
})
export class LoginComponent {
  private http = inject(HttpClient);
  private router = inject(Router);

  code = '';
  loading = signal(false);
  error = signal('');

  verify() {
    this.loading.set(true);
    this.error.set('');
    this.http.post<any>('/api/auth/verify', { code: this.code }).subscribe({
      next: () => {
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.loading.set(false);
        this.code = '';
        if (err.status === 401) {
          this.error.set('Invalid code. Try again.');
        } else {
          this.error.set('Connection error. Is the bot running?');
        }
      },
    });
  }
}
