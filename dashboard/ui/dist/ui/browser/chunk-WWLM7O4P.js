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
  ɵɵlistener,
  ɵɵnextContext,
  ɵɵproperty,
  ɵɵtext,
  ɵɵtextInterpolate,
  ɵɵtextInterpolate1,
  ɵɵtwoWayBindingSet,
  ɵɵtwoWayListener,
  ɵɵtwoWayProperty
} from "./chunk-VJUHBL36.js";

// src/app/components/login/login.component.ts
function LoginComponent_Conditional_12_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "div", 9);
    \u0275\u0275text(1);
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const ctx_r0 = \u0275\u0275nextContext();
    \u0275\u0275advance();
    \u0275\u0275textInterpolate(ctx_r0.error());
  }
}
var LoginComponent = class _LoginComponent {
  http = inject(HttpClient);
  router = inject(Router);
  code = "";
  loading = signal(false, ...ngDevMode ? [{ debugName: "loading" }] : []);
  error = signal("", ...ngDevMode ? [{ debugName: "error" }] : []);
  verify() {
    this.loading.set(true);
    this.error.set("");
    this.http.post("/api/auth/verify", { code: this.code }).subscribe({
      next: () => {
        this.router.navigate(["/"]);
      },
      error: (err) => {
        this.loading.set(false);
        this.code = "";
        if (err.status === 401) {
          this.error.set("Invalid code. Try again.");
        } else {
          this.error.set("Connection error. Is the bot running?");
        }
      }
    });
  }
  static \u0275fac = function LoginComponent_Factory(__ngFactoryType__) {
    return new (__ngFactoryType__ || _LoginComponent)();
  };
  static \u0275cmp = /* @__PURE__ */ \u0275\u0275defineComponent({ type: _LoginComponent, selectors: [["app-login"]], decls: 13, vars: 4, consts: [[1, "login-root"], [1, "login-card"], [1, "login-header"], [1, "login-dot"], [1, "login-title"], [1, "login-subtitle"], [1, "login-form", 3, "ngSubmit"], ["type", "text", "name", "code", "placeholder", "000000", "maxlength", "6", "pattern", "[0-9]*", "inputmode", "numeric", "autocomplete", "one-time-code", "autofocus", "", 1, "code-input", 3, "ngModelChange", "ngModel"], ["type", "submit", 1, "login-btn", 3, "disabled"], [1, "login-error"]], template: function LoginComponent_Template(rf, ctx) {
    if (rf & 1) {
      \u0275\u0275elementStart(0, "div", 0)(1, "div", 1)(2, "div", 2);
      \u0275\u0275element(3, "div", 3);
      \u0275\u0275elementStart(4, "span", 4);
      \u0275\u0275text(5, "CRYPTOBOT");
      \u0275\u0275elementEnd()();
      \u0275\u0275elementStart(6, "p", 5);
      \u0275\u0275text(7, "Enter your authenticator code");
      \u0275\u0275elementEnd();
      \u0275\u0275elementStart(8, "form", 6);
      \u0275\u0275listener("ngSubmit", function LoginComponent_Template_form_ngSubmit_8_listener() {
        return ctx.verify();
      });
      \u0275\u0275elementStart(9, "input", 7);
      \u0275\u0275twoWayListener("ngModelChange", function LoginComponent_Template_input_ngModelChange_9_listener($event) {
        \u0275\u0275twoWayBindingSet(ctx.code, $event) || (ctx.code = $event);
        return $event;
      });
      \u0275\u0275elementEnd();
      \u0275\u0275elementStart(10, "button", 8);
      \u0275\u0275text(11);
      \u0275\u0275elementEnd()();
      \u0275\u0275conditionalCreate(12, LoginComponent_Conditional_12_Template, 2, 1, "div", 9);
      \u0275\u0275elementEnd()();
    }
    if (rf & 2) {
      \u0275\u0275advance(9);
      \u0275\u0275twoWayProperty("ngModel", ctx.code);
      \u0275\u0275advance();
      \u0275\u0275property("disabled", ctx.loading() || ctx.code.length !== 6);
      \u0275\u0275advance();
      \u0275\u0275textInterpolate1(" ", ctx.loading() ? "Verifying..." : "Login", " ");
      \u0275\u0275advance();
      \u0275\u0275conditional(ctx.error() ? 12 : -1);
    }
  }, dependencies: [CommonModule, FormsModule, \u0275NgNoValidate, DefaultValueAccessor, NgControlStatus, NgControlStatusGroup, MaxLengthValidator, PatternValidator, NgModel, NgForm], styles: ['\n\n.login-root[_ngcontent-%COMP%] {\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  min-height: 100vh;\n  background: #0f1117;\n  font-family:\n    "Inter",\n    "Segoe UI",\n    system-ui,\n    sans-serif;\n}\n.login-card[_ngcontent-%COMP%] {\n  background: rgba(30, 33, 48, 0.7);\n  border: 1px solid #2d3148;\n  border-radius: 12px;\n  padding: 40px 36px;\n  width: 340px;\n  text-align: center;\n}\n.login-header[_ngcontent-%COMP%] {\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  gap: 8px;\n  margin-bottom: 24px;\n}\n.login-dot[_ngcontent-%COMP%] {\n  width: 10px;\n  height: 10px;\n  border-radius: 50%;\n  background: #38bdf8;\n  box-shadow: 0 0 8px rgba(56, 189, 248, 0.4);\n  animation: _ngcontent-%COMP%_pulse 2s ease-in-out infinite;\n}\n@keyframes _ngcontent-%COMP%_pulse {\n  0%, 100% {\n    opacity: 1;\n  }\n  50% {\n    opacity: 0.5;\n  }\n}\n.login-title[_ngcontent-%COMP%] {\n  font-size: 14px;\n  font-weight: 700;\n  letter-spacing: 0.12em;\n  color: #38bdf8;\n}\n.login-subtitle[_ngcontent-%COMP%] {\n  font-size: 12px;\n  color: #6b7280;\n  margin-bottom: 24px;\n}\n.login-form[_ngcontent-%COMP%] {\n  display: flex;\n  flex-direction: column;\n  gap: 12px;\n}\n.code-input[_ngcontent-%COMP%] {\n  width: 100%;\n  padding: 14px;\n  font-size: 24px;\n  font-weight: 700;\n  text-align: center;\n  letter-spacing: 0.3em;\n  background: rgba(15, 17, 23, 0.8);\n  color: #f1f5f9;\n  border: 1px solid #2d3148;\n  border-radius: 8px;\n  font-family: "JetBrains Mono", monospace;\n  outline: none;\n  transition: border-color 0.15s;\n  box-sizing: border-box;\n}\n.code-input[_ngcontent-%COMP%]:focus {\n  border-color: #38bdf8;\n}\n.code-input[_ngcontent-%COMP%]::placeholder {\n  color: #2d3148;\n}\n.login-btn[_ngcontent-%COMP%] {\n  padding: 12px;\n  font-size: 12px;\n  font-weight: 700;\n  background: rgba(56, 189, 248, 0.15);\n  color: #38bdf8;\n  border: 1px solid rgba(56, 189, 248, 0.3);\n  border-radius: 8px;\n  cursor: pointer;\n  transition: all 0.15s;\n  text-transform: uppercase;\n  letter-spacing: 0.08em;\n}\n.login-btn[_ngcontent-%COMP%]:hover:not(:disabled) {\n  background: rgba(56, 189, 248, 0.25);\n}\n.login-btn[_ngcontent-%COMP%]:disabled {\n  opacity: 0.4;\n  cursor: not-allowed;\n}\n.login-error[_ngcontent-%COMP%] {\n  margin-top: 12px;\n  font-size: 11px;\n  color: #f87171;\n  font-weight: 600;\n}\n/*# sourceMappingURL=login.component.css.map */'] });
};
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && setClassMetadata(LoginComponent, [{
    type: Component,
    args: [{ selector: "app-login", standalone: true, imports: [CommonModule, FormsModule], template: `
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
  `, styles: ['/* angular:styles/component:css;32a537e54dbee499cd5fc1161f6a7a6efb46a4f4ad32cd6f63b9a42a207f8f8f;C:/Users/Nathan/cryptobot/dashboard/ui/src/app/components/login/login.component.ts */\n.login-root {\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  min-height: 100vh;\n  background: #0f1117;\n  font-family:\n    "Inter",\n    "Segoe UI",\n    system-ui,\n    sans-serif;\n}\n.login-card {\n  background: rgba(30, 33, 48, 0.7);\n  border: 1px solid #2d3148;\n  border-radius: 12px;\n  padding: 40px 36px;\n  width: 340px;\n  text-align: center;\n}\n.login-header {\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  gap: 8px;\n  margin-bottom: 24px;\n}\n.login-dot {\n  width: 10px;\n  height: 10px;\n  border-radius: 50%;\n  background: #38bdf8;\n  box-shadow: 0 0 8px rgba(56, 189, 248, 0.4);\n  animation: pulse 2s ease-in-out infinite;\n}\n@keyframes pulse {\n  0%, 100% {\n    opacity: 1;\n  }\n  50% {\n    opacity: 0.5;\n  }\n}\n.login-title {\n  font-size: 14px;\n  font-weight: 700;\n  letter-spacing: 0.12em;\n  color: #38bdf8;\n}\n.login-subtitle {\n  font-size: 12px;\n  color: #6b7280;\n  margin-bottom: 24px;\n}\n.login-form {\n  display: flex;\n  flex-direction: column;\n  gap: 12px;\n}\n.code-input {\n  width: 100%;\n  padding: 14px;\n  font-size: 24px;\n  font-weight: 700;\n  text-align: center;\n  letter-spacing: 0.3em;\n  background: rgba(15, 17, 23, 0.8);\n  color: #f1f5f9;\n  border: 1px solid #2d3148;\n  border-radius: 8px;\n  font-family: "JetBrains Mono", monospace;\n  outline: none;\n  transition: border-color 0.15s;\n  box-sizing: border-box;\n}\n.code-input:focus {\n  border-color: #38bdf8;\n}\n.code-input::placeholder {\n  color: #2d3148;\n}\n.login-btn {\n  padding: 12px;\n  font-size: 12px;\n  font-weight: 700;\n  background: rgba(56, 189, 248, 0.15);\n  color: #38bdf8;\n  border: 1px solid rgba(56, 189, 248, 0.3);\n  border-radius: 8px;\n  cursor: pointer;\n  transition: all 0.15s;\n  text-transform: uppercase;\n  letter-spacing: 0.08em;\n}\n.login-btn:hover:not(:disabled) {\n  background: rgba(56, 189, 248, 0.25);\n}\n.login-btn:disabled {\n  opacity: 0.4;\n  cursor: not-allowed;\n}\n.login-error {\n  margin-top: 12px;\n  font-size: 11px;\n  color: #f87171;\n  font-weight: 600;\n}\n/*# sourceMappingURL=login.component.css.map */\n'] }]
  }], null, null);
})();
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && \u0275setClassDebugInfo(LoginComponent, { className: "LoginComponent", filePath: "src/app/components/login/login.component.ts", lineNumber: 99 });
})();
export {
  LoginComponent
};
//# sourceMappingURL=chunk-WWLM7O4P.js.map
