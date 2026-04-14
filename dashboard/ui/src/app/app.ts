import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { ApiService } from './services/api.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  template: `
    <div class="min-h-screen" style="background: #0f1117; color: #e1e4ed;">
      <router-outlet />
    </div>
  `,
})
export class App implements OnInit, OnDestroy {
  private api = inject(ApiService);

  ngOnInit() {
    // Don't start polling on login/setup pages — no session yet
    const path = window.location.pathname;
    if (path !== '/login' && path !== '/setup') {
      this.api.startPolling(60);
    }
  }

  ngOnDestroy() {
    this.api.stopPolling();
  }
}
