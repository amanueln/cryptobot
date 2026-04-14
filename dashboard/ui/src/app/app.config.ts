import { ApplicationConfig, provideBrowserGlobalErrorListeners, provideZoneChangeDetection, inject } from '@angular/core';
import { provideRouter, Router } from '@angular/router';
import { provideHttpClient, withInterceptors, HttpInterceptorFn } from '@angular/common/http';
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
