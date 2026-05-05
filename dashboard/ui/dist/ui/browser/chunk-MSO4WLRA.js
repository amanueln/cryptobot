import {
  Router
} from "./chunk-U2LJZ7TA.js";
import {
  DefaultValueAccessor,
  FormsModule,
  MaxLengthValidator,
  NgControlStatus,
  NgControlStatusGroup,
  NgForm,
  NgModel,
  PatternValidator,
  ɵNgNoValidate
} from "./chunk-3OW2ALSA.js";
import {
  CommonModule,
  Component,
  HttpClient,
  inject,
  setClassMetadata,
  signal,
  ɵsetClassDebugInfo,
  ɵɵadvance,
  ɵɵconditional,
  ɵɵconditionalCreate,
  ɵɵdefineComponent,
  ɵɵelement,
  ɵɵelementEnd,
  ɵɵelementStart,
  ɵɵgetCurrentView,
  ɵɵlistener,
  ɵɵnextContext,
  ɵɵproperty,
  ɵɵresetView,
  ɵɵrestoreView,
  ɵɵsanitizeUrl,
  ɵɵtext,
  ɵɵtextInterpolate,
  ɵɵtextInterpolate1,
  ɵɵtwoWayBindingSet,
  ɵɵtwoWayListener,
  ɵɵtwoWayProperty
} from "./chunk-VJUHBL36.js";

// src/app/components/setup/setup.component.ts
function SetupComponent_Conditional_8_Conditional_17_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "div", 16);
    \u0275\u0275text(1);
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const ctx_r1 = \u0275\u0275nextContext(2);
    \u0275\u0275advance();
    \u0275\u0275textInterpolate(ctx_r1.error());
  }
}
function SetupComponent_Conditional_8_Template(rf, ctx) {
  if (rf & 1) {
    const _r1 = \u0275\u0275getCurrentView();
    \u0275\u0275elementStart(0, "div", 7)(1, "p", 6);
    \u0275\u0275text(2, "1. Open Google Authenticator on your phone");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(3, "p", 6);
    \u0275\u0275text(4, "2. Scan this QR code or enter the key manually");
    \u0275\u0275elementEnd()();
    \u0275\u0275element(5, "img", 8);
    \u0275\u0275elementStart(6, "div", 9)(7, "code", 10);
    \u0275\u0275text(8);
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(9, "button", 11);
    \u0275\u0275listener("click", function SetupComponent_Conditional_8_Template_button_click_9_listener() {
      \u0275\u0275restoreView(_r1);
      const ctx_r1 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r1.copySecret());
    });
    \u0275\u0275text(10);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(11, "p", 12);
    \u0275\u0275text(12, "3. Enter the 6-digit code to verify");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(13, "form", 13);
    \u0275\u0275listener("ngSubmit", function SetupComponent_Conditional_8_Template_form_ngSubmit_13_listener() {
      \u0275\u0275restoreView(_r1);
      const ctx_r1 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r1.confirm());
    });
    \u0275\u0275elementStart(14, "input", 14);
    \u0275\u0275twoWayListener("ngModelChange", function SetupComponent_Conditional_8_Template_input_ngModelChange_14_listener($event) {
      \u0275\u0275restoreView(_r1);
      const ctx_r1 = \u0275\u0275nextContext();
      \u0275\u0275twoWayBindingSet(ctx_r1.code, $event) || (ctx_r1.code = $event);
      return \u0275\u0275resetView($event);
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(15, "button", 15);
    \u0275\u0275text(16);
    \u0275\u0275elementEnd()();
    \u0275\u0275conditionalCreate(17, SetupComponent_Conditional_8_Conditional_17_Template, 2, 1, "div", 16);
  }
  if (rf & 2) {
    const ctx_r1 = \u0275\u0275nextContext();
    \u0275\u0275advance(5);
    \u0275\u0275property("src", "data:image/png;base64," + ctx_r1.qrPng(), \u0275\u0275sanitizeUrl);
    \u0275\u0275advance(3);
    \u0275\u0275textInterpolate(ctx_r1.secret());
    \u0275\u0275advance(2);
    \u0275\u0275textInterpolate(ctx_r1.copied() ? "Copied" : "Copy");
    \u0275\u0275advance(4);
    \u0275\u0275twoWayProperty("ngModel", ctx_r1.code);
    \u0275\u0275advance();
    \u0275\u0275property("disabled", ctx_r1.loading() || ctx_r1.code.length !== 6);
    \u0275\u0275advance();
    \u0275\u0275textInterpolate1(" ", ctx_r1.loading() ? "Verifying..." : "Verify & Activate", " ");
    \u0275\u0275advance();
    \u0275\u0275conditional(ctx_r1.error() ? 17 : -1);
  }
}
function SetupComponent_Conditional_9_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "p", 6);
    \u0275\u0275text(1, "Loading setup...");
    \u0275\u0275elementEnd();
  }
}
var SetupComponent = class _SetupComponent {
  http = inject(HttpClient);
  router = inject(Router);
  qrPng = signal("", ...ngDevMode ? [{ debugName: "qrPng" }] : []);
  secret = signal("", ...ngDevMode ? [{ debugName: "secret" }] : []);
  code = "";
  loading = signal(false, ...ngDevMode ? [{ debugName: "loading" }] : []);
  error = signal("", ...ngDevMode ? [{ debugName: "error" }] : []);
  copied = signal(false, ...ngDevMode ? [{ debugName: "copied" }] : []);
  ngOnInit() {
    this.http.get("/api/auth/setup").subscribe({
      next: (data) => {
        this.qrPng.set(data.qr_png);
        this.secret.set(data.secret);
      },
      error: (err) => {
        if (err.status === 400) {
          this.router.navigate(["/login"]);
        }
      }
    });
  }
  copySecret() {
    navigator.clipboard.writeText(this.secret());
    this.copied.set(true);
    setTimeout(() => this.copied.set(false), 2e3);
  }
  confirm() {
    this.loading.set(true);
    this.error.set("");
    this.http.post("/api/auth/setup/confirm", { code: this.code }).subscribe({
      next: () => {
        this.router.navigate(["/"]);
      },
      error: (err) => {
        this.loading.set(false);
        this.code = "";
        if (err.status === 401) {
          this.error.set("Invalid code. Check your authenticator and try again.");
        } else {
          this.error.set("Setup error. Try refreshing the page.");
        }
      }
    });
  }
  static \u0275fac = function SetupComponent_Factory(__ngFactoryType__) {
    return new (__ngFactoryType__ || _SetupComponent)();
  };
  static \u0275cmp = /* @__PURE__ */ \u0275\u0275defineComponent({ type: _SetupComponent, selectors: [["app-setup"]], decls: 10, vars: 1, consts: [[1, "setup-root"], [1, "setup-card"], [1, "setup-header"], [1, "setup-dot"], [1, "setup-title"], [1, "setup-subtitle"], [1, "step-text"], [1, "setup-steps"], ["alt", "QR Code", 1, "qr-img", 3, "src"], [1, "secret-row"], [1, "secret-text"], [1, "copy-btn", 3, "click"], [1, "step-text", 2, "margin-top", "20px"], [1, "setup-form", 3, "ngSubmit"], ["type", "text", "name", "code", "placeholder", "000000", "maxlength", "6", "pattern", "[0-9]*", "inputmode", "numeric", "autocomplete", "one-time-code", 1, "code-input", 3, "ngModelChange", "ngModel"], ["type", "submit", 1, "setup-btn", 3, "disabled"], [1, "setup-error"]], template: function SetupComponent_Template(rf, ctx) {
    if (rf & 1) {
      \u0275\u0275elementStart(0, "div", 0)(1, "div", 1)(2, "div", 2);
      \u0275\u0275element(3, "div", 3);
      \u0275\u0275elementStart(4, "span", 4);
      \u0275\u0275text(5, "CRYPTOBOT");
      \u0275\u0275elementEnd()();
      \u0275\u0275elementStart(6, "p", 5);
      \u0275\u0275text(7, "First-time setup");
      \u0275\u0275elementEnd();
      \u0275\u0275conditionalCreate(8, SetupComponent_Conditional_8_Template, 18, 7)(9, SetupComponent_Conditional_9_Template, 2, 0, "p", 6);
      \u0275\u0275elementEnd()();
    }
    if (rf & 2) {
      \u0275\u0275advance(8);
      \u0275\u0275conditional(ctx.qrPng() ? 8 : 9);
    }
  }, dependencies: [CommonModule, FormsModule, \u0275NgNoValidate, DefaultValueAccessor, NgControlStatus, NgControlStatusGroup, MaxLengthValidator, PatternValidator, NgModel, NgForm], styles: ['\n\n.setup-root[_ngcontent-%COMP%] {\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  min-height: 100vh;\n  background: #0f1117;\n  font-family:\n    "Inter",\n    "Segoe UI",\n    system-ui,\n    sans-serif;\n}\n.setup-card[_ngcontent-%COMP%] {\n  background: rgba(30, 33, 48, 0.7);\n  border: 1px solid #2d3148;\n  border-radius: 12px;\n  padding: 36px 32px;\n  width: 380px;\n  text-align: center;\n}\n.setup-header[_ngcontent-%COMP%] {\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  gap: 8px;\n  margin-bottom: 8px;\n}\n.setup-dot[_ngcontent-%COMP%] {\n  width: 10px;\n  height: 10px;\n  border-radius: 50%;\n  background: #4ade80;\n  box-shadow: 0 0 8px rgba(74, 222, 128, 0.4);\n}\n.setup-title[_ngcontent-%COMP%] {\n  font-size: 14px;\n  font-weight: 700;\n  letter-spacing: 0.12em;\n  color: #38bdf8;\n}\n.setup-subtitle[_ngcontent-%COMP%] {\n  font-size: 13px;\n  color: #94a3b8;\n  margin-bottom: 20px;\n  font-weight: 600;\n}\n.setup-steps[_ngcontent-%COMP%] {\n  margin-bottom: 16px;\n}\n.step-text[_ngcontent-%COMP%] {\n  font-size: 11px;\n  color: #6b7280;\n  margin: 4px 0;\n  line-height: 1.5;\n}\n.qr-img[_ngcontent-%COMP%] {\n  width: 200px;\n  height: 200px;\n  border-radius: 8px;\n  background: white;\n  padding: 8px;\n  margin: 12px auto;\n  display: block;\n}\n.secret-row[_ngcontent-%COMP%] {\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  gap: 8px;\n  margin: 12px 0;\n}\n.secret-text[_ngcontent-%COMP%] {\n  font-size: 10px;\n  color: #94a3b8;\n  letter-spacing: 0.05em;\n  font-family: "JetBrains Mono", monospace;\n  background: rgba(15, 17, 23, 0.8);\n  padding: 6px 10px;\n  border-radius: 4px;\n  border: 1px solid #2d3148;\n  word-break: break-all;\n}\n.copy-btn[_ngcontent-%COMP%] {\n  font-size: 9px;\n  font-weight: 700;\n  padding: 4px 10px;\n  background: rgba(56, 189, 248, 0.1);\n  color: #38bdf8;\n  border: 1px solid rgba(56, 189, 248, 0.3);\n  border-radius: 4px;\n  cursor: pointer;\n  text-transform: uppercase;\n}\n.copy-btn[_ngcontent-%COMP%]:hover {\n  background: rgba(56, 189, 248, 0.2);\n}\n.setup-form[_ngcontent-%COMP%] {\n  display: flex;\n  flex-direction: column;\n  gap: 10px;\n  margin-top: 12px;\n}\n.code-input[_ngcontent-%COMP%] {\n  width: 100%;\n  padding: 14px;\n  font-size: 24px;\n  font-weight: 700;\n  text-align: center;\n  letter-spacing: 0.3em;\n  background: rgba(15, 17, 23, 0.8);\n  color: #f1f5f9;\n  border: 1px solid #2d3148;\n  border-radius: 8px;\n  font-family: "JetBrains Mono", monospace;\n  outline: none;\n  transition: border-color 0.15s;\n  box-sizing: border-box;\n}\n.code-input[_ngcontent-%COMP%]:focus {\n  border-color: #38bdf8;\n}\n.code-input[_ngcontent-%COMP%]::placeholder {\n  color: #2d3148;\n}\n.setup-btn[_ngcontent-%COMP%] {\n  padding: 12px;\n  font-size: 12px;\n  font-weight: 700;\n  background: rgba(74, 222, 128, 0.15);\n  color: #4ade80;\n  border: 1px solid rgba(74, 222, 128, 0.3);\n  border-radius: 8px;\n  cursor: pointer;\n  transition: all 0.15s;\n  text-transform: uppercase;\n  letter-spacing: 0.08em;\n}\n.setup-btn[_ngcontent-%COMP%]:hover:not(:disabled) {\n  background: rgba(74, 222, 128, 0.25);\n}\n.setup-btn[_ngcontent-%COMP%]:disabled {\n  opacity: 0.4;\n  cursor: not-allowed;\n}\n.setup-error[_ngcontent-%COMP%] {\n  margin-top: 12px;\n  font-size: 11px;\n  color: #f87171;\n  font-weight: 600;\n}\n/*# sourceMappingURL=setup.component.css.map */'] });
};
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && setClassMetadata(SetupComponent, [{
    type: Component,
    args: [{ selector: "app-setup", standalone: true, imports: [CommonModule, FormsModule], template: `
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
  `, styles: ['/* angular:styles/component:css;0a8d1b40e65e4e0ef28eec27c3df250578ad93d9374acbb07032343fd3aa2923;C:/Users/Nathan/cryptobot/dashboard/ui/src/app/components/setup/setup.component.ts */\n.setup-root {\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  min-height: 100vh;\n  background: #0f1117;\n  font-family:\n    "Inter",\n    "Segoe UI",\n    system-ui,\n    sans-serif;\n}\n.setup-card {\n  background: rgba(30, 33, 48, 0.7);\n  border: 1px solid #2d3148;\n  border-radius: 12px;\n  padding: 36px 32px;\n  width: 380px;\n  text-align: center;\n}\n.setup-header {\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  gap: 8px;\n  margin-bottom: 8px;\n}\n.setup-dot {\n  width: 10px;\n  height: 10px;\n  border-radius: 50%;\n  background: #4ade80;\n  box-shadow: 0 0 8px rgba(74, 222, 128, 0.4);\n}\n.setup-title {\n  font-size: 14px;\n  font-weight: 700;\n  letter-spacing: 0.12em;\n  color: #38bdf8;\n}\n.setup-subtitle {\n  font-size: 13px;\n  color: #94a3b8;\n  margin-bottom: 20px;\n  font-weight: 600;\n}\n.setup-steps {\n  margin-bottom: 16px;\n}\n.step-text {\n  font-size: 11px;\n  color: #6b7280;\n  margin: 4px 0;\n  line-height: 1.5;\n}\n.qr-img {\n  width: 200px;\n  height: 200px;\n  border-radius: 8px;\n  background: white;\n  padding: 8px;\n  margin: 12px auto;\n  display: block;\n}\n.secret-row {\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  gap: 8px;\n  margin: 12px 0;\n}\n.secret-text {\n  font-size: 10px;\n  color: #94a3b8;\n  letter-spacing: 0.05em;\n  font-family: "JetBrains Mono", monospace;\n  background: rgba(15, 17, 23, 0.8);\n  padding: 6px 10px;\n  border-radius: 4px;\n  border: 1px solid #2d3148;\n  word-break: break-all;\n}\n.copy-btn {\n  font-size: 9px;\n  font-weight: 700;\n  padding: 4px 10px;\n  background: rgba(56, 189, 248, 0.1);\n  color: #38bdf8;\n  border: 1px solid rgba(56, 189, 248, 0.3);\n  border-radius: 4px;\n  cursor: pointer;\n  text-transform: uppercase;\n}\n.copy-btn:hover {\n  background: rgba(56, 189, 248, 0.2);\n}\n.setup-form {\n  display: flex;\n  flex-direction: column;\n  gap: 10px;\n  margin-top: 12px;\n}\n.code-input {\n  width: 100%;\n  padding: 14px;\n  font-size: 24px;\n  font-weight: 700;\n  text-align: center;\n  letter-spacing: 0.3em;\n  background: rgba(15, 17, 23, 0.8);\n  color: #f1f5f9;\n  border: 1px solid #2d3148;\n  border-radius: 8px;\n  font-family: "JetBrains Mono", monospace;\n  outline: none;\n  transition: border-color 0.15s;\n  box-sizing: border-box;\n}\n.code-input:focus {\n  border-color: #38bdf8;\n}\n.code-input::placeholder {\n  color: #2d3148;\n}\n.setup-btn {\n  padding: 12px;\n  font-size: 12px;\n  font-weight: 700;\n  background: rgba(74, 222, 128, 0.15);\n  color: #4ade80;\n  border: 1px solid rgba(74, 222, 128, 0.3);\n  border-radius: 8px;\n  cursor: pointer;\n  transition: all 0.15s;\n  text-transform: uppercase;\n  letter-spacing: 0.08em;\n}\n.setup-btn:hover:not(:disabled) {\n  background: rgba(74, 222, 128, 0.25);\n}\n.setup-btn:disabled {\n  opacity: 0.4;\n  cursor: not-allowed;\n}\n.setup-error {\n  margin-top: 12px;\n  font-size: 11px;\n  color: #f87171;\n  font-weight: 600;\n}\n/*# sourceMappingURL=setup.component.css.map */\n'] }]
  }], null, null);
})();
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && \u0275setClassDebugInfo(SetupComponent, { className: "SetupComponent", filePath: "src/app/components/setup/setup.component.ts", lineNumber: 140 });
})();
export {
  SetupComponent
};
//# sourceMappingURL=chunk-MSO4WLRA.js.map
