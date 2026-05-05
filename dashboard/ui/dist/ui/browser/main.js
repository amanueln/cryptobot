import {
  Router,
  RouterOutlet,
  bootstrapApplication,
  provideRouter
} from "./chunk-U2LJZ7TA.js";
import {
  ApiService
} from "./chunk-W2ARAOE3.js";
import {
  Component,
  inject,
  provideBrowserGlobalErrorListeners,
  provideHttpClient,
  provideZoneChangeDetection,
  setClassMetadata,
  tap,
  withInterceptors,
  ɵsetClassDebugInfo,
  ɵɵdefineComponent,
  ɵɵelement,
  ɵɵelementEnd,
  ɵɵelementStart
} from "./chunk-VJUHBL36.js";

// src/app/app.routes.ts
var routes = [
  {
    path: "",
    loadComponent: () => import("./chunk-2USDJSPT.js").then((m) => m.CommandCenterComponent)
  },
  {
    path: "login",
    loadComponent: () => import("./chunk-WWLM7O4P.js").then((m) => m.LoginComponent)
  },
  {
    path: "setup",
    loadComponent: () => import("./chunk-MSO4WLRA.js").then((m) => m.SetupComponent)
  },
  {
    path: "momentum-strategy",
    loadComponent: () => import("./chunk-ZBNIRSTJ.js").then((m) => m.MomentumStrategyComponent)
  },
  { path: "pair/:symbol", redirectTo: "", pathMatch: "full" },
  { path: "ml-brain", redirectTo: "", pathMatch: "full" },
  { path: "pair-scanner", redirectTo: "", pathMatch: "full" },
  { path: "simulator", redirectTo: "", pathMatch: "full" },
  { path: "regime", redirectTo: "", pathMatch: "full" },
  { path: "self-check", redirectTo: "", pathMatch: "full" }
];

// src/app/app.config.ts
var authInterceptor = (req, next) => {
  const r = req.clone({ withCredentials: true });
  return next(r).pipe(tap({
    error: (err) => {
      if (err.status === 401) {
        const url = req.url;
        const path = window.location.pathname;
        if (path === "/login" || path === "/setup" || url.includes("/api/auth/")) {
          return;
        }
        const router = inject(Router);
        const body = err.error;
        if (body?.error === "setup_required") {
          router.navigate(["/setup"]);
        } else {
          router.navigate(["/login"]);
        }
      }
    }
  }));
};
var appConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor]))
  ]
};

// src/app/app.ts
var App = class _App {
  api = inject(ApiService);
  ngOnInit() {
    const path = window.location.pathname;
    if (path !== "/login" && path !== "/setup") {
      this.api.startPolling(60);
    }
  }
  ngOnDestroy() {
    this.api.stopPolling();
  }
  static \u0275fac = function App_Factory(__ngFactoryType__) {
    return new (__ngFactoryType__ || _App)();
  };
  static \u0275cmp = /* @__PURE__ */ \u0275\u0275defineComponent({ type: _App, selectors: [["app-root"]], decls: 2, vars: 0, consts: [[1, "min-h-screen", 2, "background", "#0f1117", "color", "#e1e4ed"]], template: function App_Template(rf, ctx) {
    if (rf & 1) {
      \u0275\u0275elementStart(0, "div", 0);
      \u0275\u0275element(1, "router-outlet");
      \u0275\u0275elementEnd();
    }
  }, dependencies: [RouterOutlet], encapsulation: 2 });
};
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && setClassMetadata(App, [{
    type: Component,
    args: [{
      selector: "app-root",
      standalone: true,
      imports: [RouterOutlet],
      template: `
    <div class="min-h-screen" style="background: #0f1117; color: #e1e4ed;">
      <router-outlet />
    </div>
  `
    }]
  }], null, null);
})();
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && \u0275setClassDebugInfo(App, { className: "App", filePath: "src/app/app.ts", lineNumber: 15 });
})();

// src/main.ts
bootstrapApplication(App, appConfig).catch((err) => console.error(err));
//# sourceMappingURL=main.js.map
