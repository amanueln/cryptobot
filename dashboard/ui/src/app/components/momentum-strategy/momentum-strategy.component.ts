import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../services/api.service';

// ── Hardcoded simple-slider mapping tables ──────────────────────────────────
const RISK_LEVELS = [
  {
    label: 'Very Conservative',
    adx_min: 30, rsi_min: 55, rsi_max: 60, ath_dist_max: -15,
    chg3h_atr_max: 2.0, chg3h_atr_min: -2.0,
  },
  {
    label: 'Conservative',
    adx_min: 27, rsi_min: 52, rsi_max: 62, ath_dist_max: -12,
    chg3h_atr_max: 2.5, chg3h_atr_min: -2.5,
  },
  {
    label: 'Balanced',
    adx_min: 25, rsi_min: 50, rsi_max: 65, ath_dist_max: -10,
    chg3h_atr_max: 3.0, chg3h_atr_min: -3.0,
  },
  {
    label: 'Aggressive',
    adx_min: 22, rsi_min: 48, rsi_max: 70, ath_dist_max: -8,
    chg3h_atr_max: 3.5, chg3h_atr_min: -3.5,
  },
  {
    label: 'Very Aggressive',
    adx_min: 20, rsi_min: 45, rsi_max: 72, ath_dist_max: -7,
    chg3h_atr_max: 4.0, chg3h_atr_min: -4.0,
  },
];

const PROFIT_LEVELS = [
  {
    label: 'Very Quick',
    progressive: [[2.0, 0.5], [5.0, 1.0], [7.0, 0.5], [10.0, 0.3]],
  },
  {
    label: 'Quick',
    progressive: [[2.0, 0.7], [5.0, 1.5], [7.0, 0.7], [10.0, 0.4]],
  },
  {
    label: 'Balanced',
    progressive: [[2.0, 1.0], [6.0, 2.0], [8.0, 1.0], [12.0, 0.5]],
  },
  {
    label: 'Let it run',
    progressive: [[2.0, 1.5], [7.0, 2.5], [10.0, 1.5], [15.0, 1.0]],
  },
  {
    label: 'Patient',
    progressive: [[2.0, 2.0], [8.0, 3.0], [12.0, 2.0], [18.0, 1.5]],
  },
];

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

@Component({
  selector: 'app-momentum-strategy',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './momentum-strategy.component.html',
  styleUrls: ['./momentum-strategy.component.css'],
})
export class MomentumStrategyComponent implements OnInit {
  private api = inject(ApiService);

  // ── Core state ──────────────────────────────────────────────────────────
  profilesData = signal<any>(null);
  activeKey = signal<string>('builtin::recommended');
  currentValues = signal<any>({});
  savedValues = signal<any>({});
  changelog = signal<any>({});
  activeStrategyMeta = signal<any>(null);

  modified = computed(() =>
    JSON.stringify(this.currentValues()) !== JSON.stringify(this.savedValues())
  );

  // Apply button enabled when the form values differ from what's actually
  // running on the bot — true if the user tweaked things OR picked a
  // different profile from the dropdown.
  pendingApply = computed(() => {
    const meta = this.activeStrategyMeta();
    const cur = this.currentValues();
    if (!meta || !cur || !Object.keys(cur).length) return false;
    if (!meta.values) return false;
    return JSON.stringify(cur) !== JSON.stringify(meta.values);
  });

  mode = signal<'simple' | 'advanced'>('simple');

  // ── UI flags ────────────────────────────────────────────────────────────
  loading = signal(true);
  applying = signal(false);
  saving = signal(false);
  toast = signal<string | null>(null);
  showUpgradeBanner = signal(false);

  showSaveModal = signal(false);
  showSaveAsModal = signal(false);
  showDeleteModal = signal(false);
  showRevertModal = signal(false);
  showDiscardModal = signal(false);
  showRiskTable = signal(false);
  showProfitTable = signal(false);

  // Save-as modal fields
  newProfileName = signal('');
  newProfileDescription = signal('');

  // Pending navigation callback (for discard flow)
  private _pendingDiscard: (() => void) | null = null;

  // ── Lookups ──────────────────────────────────────────────────────────────
  readonly riskLevels = RISK_LEVELS;
  readonly profitLevels = PROFIT_LEVELS;
  readonly days = DAYS;

  // ── Computed helpers ────────────────────────────────────────────────────
  isBuiltin = computed(() => this.activeKey().startsWith('builtin::'));

  profileName = computed(() => {
    const key = this.activeKey();
    if (key === 'builtin::recommended') return 'Recommended';
    if (key === 'builtin::conservative') return 'Conservative';
    if (key === 'builtin::aggressive') return 'Aggressive';
    return key.replace('user::', '');
  });

  builtinProfiles = computed(() => {
    const d = this.profilesData();
    if (!d) return [];
    return Object.entries(d.built_in || {}).map(([k, v]: [string, any]) => ({
      key: `builtin::${k}`,
      label: v.name || k,
    }));
  });

  userProfiles = computed(() => {
    const d = this.profilesData();
    if (!d) return [];
    return Object.entries(d.user || {}).map(([k, v]: [string, any]) => ({
      key: `user::${k}`,
      label: k,
    }));
  });

  diffList = computed(() => {
    const cur = this.currentValues();
    const saved = this.savedValues();
    const diffs: { path: string; old: any; new: any }[] = [];
    this._flatDiff('', cur, saved, diffs);
    return diffs;
  });

  changeCount = computed(() => this.diffList().length);

  showBanner = computed(() => {
    const d = this.profilesData();
    const meta = this.activeStrategyMeta();
    if (!d || !meta) return false;
    if (this.activeKey() !== 'builtin::recommended') return false;
    const applied = d.applied_recommended_version;
    const latest = d.latest_recommended_version;
    return applied && latest && applied !== latest;
  });

  // ── Simple slider computed values ────────────────────────────────────────
  riskSliderValue = computed(() => {
    const cv = this.currentValues();
    if (!cv?.entry_gates) return 3;
    return this._detectRiskLevel(cv.entry_gates);
  });

  profitSliderValue = computed(() => {
    const cv = this.currentValues();
    if (!cv?.trail?.progressive) return 3;
    return this._detectProfitLevel(cv.trail.progressive);
  });

  riskLevelLabel = computed(() => RISK_LEVELS[this.riskSliderValue() - 1]?.label ?? 'Custom');
  profitLevelLabel = computed(() => PROFIT_LEVELS[this.profitSliderValue() - 1]?.label ?? 'Custom');

  // ── Lifecycle ────────────────────────────────────────────────────────────
  ngOnInit() {
    this.loadAll();
  }

  loadAll() {
    this.loading.set(true);
    this.api.getStrategyProfiles().subscribe({
      next: (data: any) => {
        this.profilesData.set(data);
        const activeKey = data.active || 'builtin::recommended';
        this.activeKey.set(activeKey);
        this.loadProfile(activeKey);
      },
      error: () => { this.loading.set(false); },
    });
    this.api.getStrategyChangelog().subscribe({
      next: (cl: any) => this.changelog.set(cl),
    });
    this.api.getActiveStrategy().subscribe({
      next: (meta: any) => this.activeStrategyMeta.set(meta),
    });
  }

  loadProfile(key: string) {
    this.api.getStrategyProfile(key).subscribe({
      next: (values: any) => {
        // Deep clone so mutations don't alias
        const clone = JSON.parse(JSON.stringify(values));
        this.currentValues.set(clone);
        this.savedValues.set(JSON.parse(JSON.stringify(values)));
        this.loading.set(false);
      },
      error: () => { this.loading.set(false); },
    });
  }

  // ── Profile switching ────────────────────────────────────────────────────
  onProfileChange(newKey: string) {
    if (this.modified()) {
      this._pendingDiscard = () => this._switchProfile(newKey);
      this.showDiscardModal.set(true);
    } else {
      this._switchProfile(newKey);
    }
  }

  private _switchProfile(key: string) {
    this.activeKey.set(key);
    this.loadProfile(key);
  }

  // ── Simple view mutations ────────────────────────────────────────────────
  setRiskLevel(idx: number) {
    // idx is 1-based from slider
    const level = RISK_LEVELS[idx - 1];
    if (!level) return;
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.entry_gates) cv.entry_gates = {};
    cv.entry_gates.adx_min = level.adx_min;
    cv.entry_gates.rsi_min = level.rsi_min;
    cv.entry_gates.rsi_max = level.rsi_max;
    cv.entry_gates.ath_dist_max = level.ath_dist_max;
    cv.entry_gates.chg3h_atr_max = level.chg3h_atr_max;
    cv.entry_gates.chg3h_atr_min = level.chg3h_atr_min;
    this.currentValues.set(cv);
  }

  setProfitLevel(idx: number) {
    const level = PROFIT_LEVELS[idx - 1];
    if (!level) return;
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.trail) cv.trail = {};
    cv.trail.progressive = level.progressive;
    this.currentValues.set(cv);
  }

  setMaxHold(val: number) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.exits) cv.exits = {};
    cv.exits.max_hold_hours = Number(val);
    this.currentValues.set(cv);
  }

  setAllocation(val: number) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.position) cv.position = {};
    cv.position.allocation_usd = Number(val);
    this.currentValues.set(cv);
  }

  toggleDay(dayIndex: number) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.entry_pause) cv.entry_pause = { enabled: true, weekday_block: [] };
    const block: number[] = cv.entry_pause.weekday_block || [];
    const pos = block.indexOf(dayIndex);
    if (pos >= 0) block.splice(pos, 1);
    else block.push(dayIndex);
    cv.entry_pause.weekday_block = block;
    this.currentValues.set(cv);
  }

  isDayBlocked(dayIndex: number): boolean {
    const cv = this.currentValues();
    return (cv?.entry_pause?.weekday_block || []).includes(dayIndex);
  }

  setWallAware(enabled: boolean) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.wall_aware) cv.wall_aware = {};
    cv.wall_aware.enabled = enabled;
    this.currentValues.set(cv);
  }

  // ── Blacklist / chips ────────────────────────────────────────────────────
  blacklistInput = '';

  getBlacklist(): string[] {
    return this.currentValues()?.universe?.blacklist || [];
  }

  addChip(pair: string) {
    const trimmed = pair.trim().toUpperCase();
    if (!trimmed) return;
    if (!trimmed.endsWith('-USD')) {
      // try to normalize
    }
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.universe) cv.universe = { min_price: 0.01, blacklist: [] };
    if (!cv.universe.blacklist.includes(trimmed)) {
      cv.universe.blacklist.push(trimmed);
    }
    this.currentValues.set(cv);
    this.blacklistInput = '';
  }

  removeChip(pair: string) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (cv.universe?.blacklist) {
      cv.universe.blacklist = cv.universe.blacklist.filter((p: string) => p !== pair);
    }
    this.currentValues.set(cv);
  }

  onChipKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter') {
      this.addChip(this.blacklistInput);
    }
  }

  // ── Advanced field mutations (generic deep-set) ──────────────────────────
  setField(section: string, key: string, value: any) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv[section]) cv[section] = {};
    cv[section][key] = Number(value);
    this.currentValues.set(cv);
  }

  getField(section: string, key: string): any {
    return this.currentValues()?.[section]?.[key] ?? '';
  }

  // ── Trail tier editing ───────────────────────────────────────────────────
  getTiers(): [number, number][] {
    return this.currentValues()?.trail?.progressive || [];
  }

  setTierValue(tierIdx: number, colIdx: number, value: number) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.trail?.progressive) return;
    cv.trail.progressive[tierIdx][colIdx] = Number(value);
    this.currentValues.set(cv);
  }

  addTier() {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.trail) cv.trail = {};
    if (!cv.trail.progressive) cv.trail.progressive = [];
    cv.trail.progressive.push([0, 0]);
    this.currentValues.set(cv);
  }

  removeTier(idx: number) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    cv.trail.progressive.splice(idx, 1);
    this.currentValues.set(cv);
  }

  // ── Reset section (restore section from savedValues) ─────────────────────
  resetSection(section: string) {
    const saved = this.savedValues();
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    cv[section] = JSON.parse(JSON.stringify(saved[section] || {}));
    this.currentValues.set(cv);
  }

  // ── Revert ───────────────────────────────────────────────────────────────
  openRevert() {
    this.showRevertModal.set(true);
  }

  confirmRevert() {
    this.currentValues.set(JSON.parse(JSON.stringify(this.savedValues())));
    this.showRevertModal.set(false);
  }

  // ── Apply ────────────────────────────────────────────────────────────────
  applyChanges() {
    if (!this.pendingApply() || this.applying()) return;
    this.applying.set(true);
    this.api.applyStrategy({ profile_key: this.activeKey(), values: this.currentValues() }).subscribe({
      next: () => {
        this.savedValues.set(JSON.parse(JSON.stringify(this.currentValues())));
        this.applying.set(false);
        this._showToast('Applied — bot reloaded');
        this.api.getStrategyProfiles().subscribe((d: any) => this.profilesData.set(d));
        this.api.getActiveStrategy().subscribe((m: any) => this.activeStrategyMeta.set(m));
      },
      error: (e: any) => {
        this.applying.set(false);
        this._showToast('Apply failed: ' + (e?.error?.message || 'unknown error'));
      },
    });
  }

  // ── Save (overwrite user profile) ────────────────────────────────────────
  openSave() {
    this.showSaveModal.set(true);
  }

  confirmSave() {
    const name = this.activeKey().replace('user::', '');
    this.saving.set(true);
    this.api.updateStrategyProfile(name, { values: this.currentValues(), description: '' }).subscribe({
      next: () => {
        this.savedValues.set(JSON.parse(JSON.stringify(this.currentValues())));
        this.showSaveModal.set(false);
        this.saving.set(false);
        this._showToast('Saved');
        this.api.getStrategyProfiles().subscribe((d: any) => this.profilesData.set(d));
      },
      error: (e: any) => {
        this.saving.set(false);
        this._showToast('Save failed: ' + (e?.error?.message || 'unknown error'));
      },
    });
  }

  // ── Save as new ───────────────────────────────────────────────────────────
  openSaveAs(prefill?: string) {
    this.newProfileName.set(prefill || `My ${this.profileName()} (custom)`);
    this.newProfileDescription.set('');
    this.showSaveAsModal.set(true);
  }

  confirmSaveAs() {
    const name = this.newProfileName().trim();
    if (!name) return;
    this.saving.set(true);
    this.api.saveStrategyProfile({
      name,
      description: this.newProfileDescription(),
      values: this.currentValues(),
    }).subscribe({
      next: () => {
        this.showSaveAsModal.set(false);
        this.saving.set(false);
        this._showToast('Saved as "' + name + '"');
        const newKey = `user::${name}`;
        this.api.getStrategyProfiles().subscribe((d: any) => {
          this.profilesData.set(d);
          this.activeKey.set(newKey);
          this.savedValues.set(JSON.parse(JSON.stringify(this.currentValues())));
        });
      },
      error: (e: any) => {
        this.saving.set(false);
        this._showToast('Save failed: ' + (e?.error?.message || 'unknown error'));
      },
    });
  }

  // ── Delete ────────────────────────────────────────────────────────────────
  openDelete() {
    this.showDeleteModal.set(true);
  }

  confirmDelete() {
    const name = this.activeKey().replace('user::', '');
    this.api.deleteStrategyProfile(name).subscribe({
      next: () => {
        this.showDeleteModal.set(false);
        this._showToast('Deleted "' + name + '"');
        this.api.getStrategyProfiles().subscribe((d: any) => {
          this.profilesData.set(d);
          const fallback = d.active || 'builtin::recommended';
          this.activeKey.set(fallback);
          this.loadProfile(fallback);
        });
      },
      error: (e: any) => {
        this._showToast('Delete failed: ' + (e?.error?.message || 'unknown error'));
      },
    });
  }

  // ── Discard ───────────────────────────────────────────────────────────────
  cancelDiscard() {
    this.showDiscardModal.set(false);
    this._pendingDiscard = null;
  }

  confirmDiscard() {
    this.showDiscardModal.set(false);
    if (this._pendingDiscard) {
      this._pendingDiscard();
      this._pendingDiscard = null;
    }
  }

  // ── Upgrade banner / rollback ─────────────────────────────────────────────
  changelogEntries = computed(() => {
    const cl = this.changelog();
    const d = this.profilesData();
    if (!cl || !d) return [];
    const latest = d.latest_recommended_version;
    return cl[latest] || [];
  });

  rollback() {
    const d = this.profilesData();
    if (!d) return;
    const oldVersion = d.applied_recommended_version;
    this._showToast(`Rollback to v${oldVersion} initiated`);
    // Load recommended and apply
    this.api.getStrategyProfile('builtin::recommended').subscribe((v: any) => {
      this.currentValues.set(JSON.parse(JSON.stringify(v)));
      this.applyChanges();
    });
  }

  dismissBanner() {
    this.showUpgradeBanner.set(false);
  }

  // ── Close tab ────────────────────────────────────────────────────────────
  backToDashboard() {
    window.close();
  }

  // ── Utility ──────────────────────────────────────────────────────────────
  private _showToast(msg: string) {
    this.toast.set(msg);
    setTimeout(() => this.toast.set(null), 3500);
  }

  private _flatDiff(prefix: string, cur: any, saved: any, out: { path: string; old: any; new: any }[]) {
    if (cur === null || typeof cur !== 'object' || Array.isArray(cur)) {
      const curStr = JSON.stringify(cur);
      const savedStr = JSON.stringify(saved);
      if (curStr !== savedStr) {
        out.push({ path: prefix, old: saved, new: cur });
      }
      return;
    }
    const keys = new Set([...Object.keys(cur || {}), ...Object.keys(saved || {})]);
    keys.forEach(k => {
      this._flatDiff(prefix ? `${prefix}.${k}` : k, cur?.[k], saved?.[k], out);
    });
  }

  private _detectRiskLevel(eg: any): number {
    const adx = eg?.adx_min;
    for (let i = 0; i < RISK_LEVELS.length; i++) {
      if (RISK_LEVELS[i].adx_min === adx) return i + 1;
    }
    return 3; // default balanced
  }

  private _detectProfitLevel(progressive: any[]): number {
    if (!progressive || progressive.length === 0) return 3;
    const str = JSON.stringify(progressive);
    for (let i = 0; i < PROFIT_LEVELS.length; i++) {
      if (JSON.stringify(PROFIT_LEVELS[i].progressive) === str) return i + 1;
    }
    return 3;
  }

  // Expose tables to template
  readonly riskTable = [
    { label: 'ADX min', values: [30, 27, 25, 22, 20] },
    { label: 'RSI min (uptrend)', values: [55, 52, 50, 48, 45] },
    { label: 'RSI max (overbought)', values: [60, 62, 65, 70, 72] },
    { label: 'ATH proximity gate', values: ['-15%', '-12%', '-10%', '-8%', '-7%'] },
    { label: '3h overpump (× ATR)', values: [2.0, 2.5, 3.0, 3.5, 4.0] },
    { label: '3h crash (× ATR)', values: [-2.0, -2.5, -3.0, -3.5, -4.0] },
  ];

  readonly profitTable = [
    { label: 'Tier 1 (small move)', values: ['2% → 0.5%', '2% → 0.7%', '2% → 1.0%', '2% → 1.5%', '2% → 2.0%'] },
    { label: 'Tier 2 (mid move)', values: ['5% → 1.0%', '5% → 1.5%', '6% → 2.0%', '7% → 2.5%', '8% → 3.0%'] },
    { label: 'Tier 3 (strong move)', values: ['7% → 0.5%', '7% → 0.7%', '8% → 1.0%', '10% → 1.5%', '12% → 2.0%'] },
    { label: 'Tier 4 (runner)', values: ['10% → 0.3%', '10% → 0.4%', '12% → 0.5%', '15% → 1.0%', '18% → 1.5%'] },
  ];

  readonly riskColHeaders = ['Very Cons.', 'Conservative', 'Balanced', 'Aggressive', 'Very Aggro.'];
  readonly profitColHeaders = ['Very Quick', 'Quick', 'Balanced', 'Let it run', 'Patient'];
}
