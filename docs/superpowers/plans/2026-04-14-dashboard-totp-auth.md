# Dashboard TOTP Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add toggleable TOTP (Google Authenticator) authentication to the dashboard so only the bot owner can access it.

**Architecture:** Flask `before_request` middleware gates all API/page routes when `AUTH_ENABLED=true`. Angular login/setup components handle the UI. Session persists via signed cookie (30 days). TOTP secret stored in `data/.totp_secret` on the persistent volume.

**Tech Stack:** Python (`pyotp`, `qrcode`), Flask sessions, Angular 20 standalone components

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `requirements.txt` | Modify | Add `pyotp`, `qrcode[pil]` |
| `.gitignore` | Modify | Add `data/.totp_secret`, `data/.flask_secret` |
| `dashboard/api/app.py` | Modify | Auth middleware + 4 auth endpoints |
| `dashboard/ui/src/app/components/login/login.component.ts` | Create | Login page (6-digit code input) |
| `dashboard/ui/src/app/components/setup/setup.component.ts` | Create | First-time setup page (QR + verify) |
| `dashboard/ui/src/app/app.routes.ts` | Modify | Add `/login` and `/setup` routes |
| `dashboard/ui/src/app/app.config.ts` | Modify | Add `withInterceptors` for 401 handling |
| `dashboard/ui/src/app/services/api.service.ts` | Modify | Add auth API calls + 401 interceptor |
| `dashboard/ui/src/app/app.ts` | Modify | Add conditional logout button |

---

### Task 1: Backend Dependencies & Gitignore

**Files:**
- Modify: `requirements.txt`
- Modify: `.gitignore`

- [ ] **Step 1: Add Python dependencies**

Add to `requirements.txt`:
```
pyotp==2.9.0
qrcode==8.0
Pillow==11.2.1
```

- [ ] **Step 2: Add secret files to gitignore**

Add to `.gitignore` after the `data/*.json` line:
```
data/.totp_secret
data/.flask_secret
```

- [ ] **Step 3: Install dependencies locally**

Run: `pip install pyotp==2.9.0 qrcode==8.0 Pillow==11.2.1`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt .gitignore
git commit -m "chore: add pyotp and qrcode deps for TOTP auth"
```

---

### Task 2: Backend Auth Middleware & Endpoints

**Files:**
- Modify: `dashboard/api/app.py` (add imports, middleware, 4 endpoints)

- [ ] **Step 1: Add imports and auth config at top of app.py**

Add after the existing imports (around line 26):
```python
import hashlib
import hmac
import secrets
import pyotp
import qrcode
import io
import base64
```

Add after `DB_PATH` definition (around line 32):
```python
# --- Auth config ---
AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "false").lower() in ("true", "1", "yes")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
TOTP_SECRET_PATH = os.path.join(DATA_DIR, ".totp_secret")
FLASK_SECRET_PATH = os.path.join(DATA_DIR, ".flask_secret")

def _get_flask_secret():
    """Load or generate Flask secret key for cookie signing."""
    if os.path.exists(FLASK_SECRET_PATH):
        with open(FLASK_SECRET_PATH, "r") as f:
            return f.read().strip()
    secret = secrets.token_hex(32)
    with open(FLASK_SECRET_PATH, "w") as f:
        f.write(secret)
    return secret

if AUTH_ENABLED:
    app.secret_key = _get_flask_secret()
```

- [ ] **Step 2: Add the before_request auth middleware**

Add after the CORS setup (after line 30):
```python
@app.before_request
def check_auth():
    """Gate all requests behind TOTP auth when enabled."""
    if not AUTH_ENABLED:
        return None

    path = request.path

    # Always allow auth endpoints and static assets
    if path.startswith("/api/auth/"):
        return None
    if path in ("/login", "/setup"):
        return send_from_directory(STATIC_DIR, "index.html")
    # Static file extensions
    ext = path.rsplit(".", 1)[-1] if "." in path else ""
    if ext in ("js", "css", "ico", "png", "jpg", "svg", "woff", "woff2", "ttf", "map"):
        return None

    # Check if setup is needed
    if not os.path.exists(TOTP_SECRET_PATH):
        if path.startswith("/api/"):
            return jsonify({"error": "setup_required"}), 401
        return redirect("/setup")

    # Check session cookie
    session_token = request.cookies.get("bot_session")
    if not session_token or not _verify_session(session_token):
        if path.startswith("/api/"):
            return jsonify({"error": "unauthorized"}), 401
        return redirect("/login")

    return None
```

- [ ] **Step 3: Add session helper functions**

Add after the middleware:
```python
def _create_session_token():
    """Create a signed session token."""
    payload = f"{int(time.time())}"
    sig = hmac.new(app.secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"

def _verify_session(token):
    """Verify a session token is valid and not expired."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return False
        timestamp, sig = parts
        expected = hmac.new(app.secret_key.encode(), timestamp.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return False
        # Check expiry (30 days)
        age = int(time.time()) - int(timestamp)
        return age < 30 * 86400
    except (ValueError, TypeError):
        return False
```

- [ ] **Step 4: Add the 4 auth endpoints**

Add before the `serve_index` route (before the `@app.route("/")` line):
```python
@app.route("/api/auth/setup", methods=["GET"])
def auth_setup():
    """Generate TOTP secret and QR code for first-time setup."""
    if os.path.exists(TOTP_SECRET_PATH):
        return jsonify({"error": "already_setup"}), 400
    secret = pyotp.random_base32()
    # Store in memory temporarily — only saved after verification
    app.config["_pending_totp_secret"] = secret
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name="CryptoBot", issuer_name="CryptoBot Dashboard")
    # Generate QR code as base64 PNG
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return jsonify({"secret": secret, "qr_png": qr_b64})


@app.route("/api/auth/setup/confirm", methods=["POST"])
def auth_setup_confirm():
    """Verify TOTP code and save secret permanently."""
    secret = app.config.get("_pending_totp_secret")
    if not secret:
        return jsonify({"error": "no_pending_setup"}), 400
    code = (request.json or {}).get("code", "")
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "invalid_code"}), 401
    # Save secret permanently
    with open(TOTP_SECRET_PATH, "w") as f:
        f.write(secret)
    app.config.pop("_pending_totp_secret", None)
    # Log the user in
    resp = jsonify({"status": "ok"})
    resp.set_cookie("bot_session", _create_session_token(),
                     max_age=30 * 86400, httponly=True, samesite="Lax")
    return resp


@app.route("/api/auth/verify", methods=["POST"])
def auth_verify():
    """Verify TOTP code and create session."""
    if not os.path.exists(TOTP_SECRET_PATH):
        return jsonify({"error": "setup_required"}), 401
    with open(TOTP_SECRET_PATH, "r") as f:
        secret = f.read().strip()
    code = (request.json or {}).get("code", "")
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "invalid_code"}), 401
    resp = jsonify({"status": "ok"})
    resp.set_cookie("bot_session", _create_session_token(),
                     max_age=30 * 86400, httponly=True, samesite="Lax")
    return resp


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    """Clear session cookie."""
    resp = jsonify({"status": "ok"})
    resp.delete_cookie("bot_session")
    return resp
```

- [ ] **Step 5: Add redirect import**

Add `redirect` to the Flask import at line 20:
```python
from flask import Flask, jsonify, request, send_from_directory, send_file, redirect
```

- [ ] **Step 6: Commit**

```bash
git add dashboard/api/app.py
git commit -m "feat: add TOTP auth middleware and endpoints to Flask API"
```

---

### Task 3: Angular Login Component

**Files:**
- Create: `dashboard/ui/src/app/components/login/login.component.ts`

- [ ] **Step 1: Create the login component**

Theme: `#0f1117` background, `#38bdf8` accent, `Inter` font, `JetBrains Mono` for inputs — matching the existing dashboard.

```typescript
import { Component, signal } from '@angular/core';
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
```

Note: Add `inject` to the import from `@angular/core`:
```typescript
import { Component, signal, inject } from '@angular/core';
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/ui/src/app/components/login/login.component.ts
git commit -m "feat: add TOTP login component matching dashboard theme"
```

---

### Task 4: Angular Setup Component

**Files:**
- Create: `dashboard/ui/src/app/components/setup/setup.component.ts`

- [ ] **Step 1: Create the setup component**

```typescript
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
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/ui/src/app/components/setup/setup.component.ts
git commit -m "feat: add TOTP setup component with QR code and manual key entry"
```

---

### Task 5: Angular Routing, Interceptor & Logout

**Files:**
- Modify: `dashboard/ui/src/app/app.routes.ts`
- Modify: `dashboard/ui/src/app/app.config.ts`
- Modify: `dashboard/ui/src/app/services/api.service.ts`
- Modify: `dashboard/ui/src/app/app.ts`

- [ ] **Step 1: Add login and setup routes**

Replace the contents of `app.routes.ts`:
```typescript
import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () =>
      import('./components/command-center/command-center.component').then(
        (m) => m.CommandCenterComponent
      ),
  },
  {
    path: 'login',
    loadComponent: () =>
      import('./components/login/login.component').then(
        (m) => m.LoginComponent
      ),
  },
  {
    path: 'setup',
    loadComponent: () =>
      import('./components/setup/setup.component').then(
        (m) => m.SetupComponent
      ),
  },
  { path: 'pair/:symbol', redirectTo: '', pathMatch: 'full' },
  { path: 'ml-brain', redirectTo: '', pathMatch: 'full' },
  { path: 'pair-scanner', redirectTo: '', pathMatch: 'full' },
  { path: 'simulator', redirectTo: '', pathMatch: 'full' },
  { path: 'regime', redirectTo: '', pathMatch: 'full' },
  { path: 'self-check', redirectTo: '', pathMatch: 'full' },
];
```

- [ ] **Step 2: Add HTTP interceptor for 401 handling**

Replace the contents of `app.config.ts`:
```typescript
import { ApplicationConfig, provideBrowserGlobalErrorListeners, provideZoneChangeDetection } from '@angular/core';
import { provideRouter, Router } from '@angular/router';
import { provideHttpClient, withInterceptors, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { tap } from 'rxjs';

import { routes } from './app.routes';

const authInterceptor: HttpInterceptorFn = (req, next) => {
  const r = req.clone({ withCredentials: true });
  return next(r).pipe(
    tap({
      error: (err) => {
        if (err.status === 401) {
          const router = inject(Router);
          const body = err.error;
          if (body?.error === 'setup_required') {
            router.navigate(['/setup']);
          } else {
            router.navigate(['/login']);
          }
        }
      },
    })
  );
};

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor])),
  ]
};
```

- [ ] **Step 3: Add logout method to ApiService**

Add to `api.service.ts` near the other early-scanner methods:
```typescript
logout() {
  return this.http.post<any>('/api/auth/logout', {});
}
```

- [ ] **Step 4: Add conditional logout button to app root**

Replace the contents of `app.ts`:
```typescript
import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { RouterOutlet, Router } from '@angular/router';
import { ApiService } from './services/api.service';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, CommonModule],
  template: `
    <div class="min-h-screen" style="background: #0f1117; color: #e1e4ed;">
      <router-outlet />
    </div>
  `,
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
```

Note: The logout button will be added to the command-center header bar (where the tab nav lives) rather than the app root, since login/setup pages shouldn't show it. This is handled in Task 6.

- [ ] **Step 5: Commit**

```bash
git add dashboard/ui/src/app/app.routes.ts dashboard/ui/src/app/app.config.ts dashboard/ui/src/app/services/api.service.ts dashboard/ui/src/app/app.ts
git commit -m "feat: add auth routing, 401 interceptor, and logout API call"
```

---

### Task 6: Logout Button in Command Center Header

**Files:**
- Modify: `dashboard/ui/src/app/components/command-center/command-center.component.ts`

- [ ] **Step 1: Add logout button to the header nav bar**

In the command center template, find the header/nav area with the tab buttons (MOMENTUM, GRID TRADING, SCANNER). Add a logout button at the far right:

```html
<button class="logout-btn" (click)="logout()">Logout</button>
```

- [ ] **Step 2: Add logout method and styling**

Add to the component class:
```typescript
logout() {
  this.api.logout().subscribe({
    next: () => window.location.href = '/login',
  });
}
```

Add to styles:
```css
.logout-btn {
  position: absolute; right: 16px; top: 50%; transform: translateY(-50%);
  font-size: 9px; font-weight: 600; padding: 4px 10px;
  background: rgba(248,113,113,0.08); color: #6b7280;
  border: 1px solid rgba(248,113,113,0.15); border-radius: 4px;
  cursor: pointer; text-transform: uppercase; letter-spacing: 0.05em;
  transition: all 0.15s;
}
.logout-btn:hover {
  color: #f87171; background: rgba(248,113,113,0.15);
  border-color: rgba(248,113,113,0.3);
}
```

Make sure the parent nav container has `position: relative` for the absolute positioning to work.

- [ ] **Step 3: Commit**

```bash
git add dashboard/ui/src/app/components/command-center/command-center.component.ts
git commit -m "feat: add logout button to command center header"
```

---

### Task 7: Build, Test & Push

**Files:**
- Build output: `dashboard/ui/dist/`

- [ ] **Step 1: Build Angular**

Run: `cd dashboard/ui && npx ng build`
Expected: Build succeeds with no errors.

- [ ] **Step 2: Test locally with auth disabled (default)**

Run: `python start.py` (or `py -3 start.py` on Windows)
- Open dashboard — should work exactly as before, no login screen
- Verify no console errors

- [ ] **Step 3: Test locally with auth enabled**

Set environment variable `AUTH_ENABLED=true` and restart.
- Opening dashboard should redirect to `/setup`
- Setup page shows QR code and secret text
- Scan QR in Google Authenticator, enter code → verifies and redirects to dashboard
- Refresh dashboard → stays logged in (cookie)
- Click Logout → redirected to `/login`
- Enter code from authenticator → back in dashboard

- [ ] **Step 4: Commit build output and push**

```bash
git add dashboard/ui/dist/
git commit -m "build: compile Angular with auth components"
git push
```

- [ ] **Step 5: Update Docker image on ZimaOS**

After pushing, pull and rebuild on ZimaOS. The `data/.totp_secret` and `data/.flask_secret` files will persist on the volume mount at `/DATA/AppData/cryptobot/data/`.

Set `AUTH_ENABLED=true` in the Docker Compose environment variables:
```yaml
environment:
  - AUTH_ENABLED=true
```

---
