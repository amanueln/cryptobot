import {
  ApiService
} from "./chunk-W2ARAOE3.js";
import {
  DefaultValueAccessor,
  FormsModule,
  MaxValidator,
  MinValidator,
  NgControlStatus,
  NgModel,
  NgSelectOption,
  NumberValueAccessor,
  SelectControlValueAccessor,
  ɵNgSelectMultipleOption
} from "./chunk-3OW2ALSA.js";
import {
  CommonModule,
  Component,
  DecimalPipe,
  JsonPipe,
  computed,
  inject,
  setClassMetadata,
  signal,
  ɵsetClassDebugInfo,
  ɵɵadvance,
  ɵɵclassProp,
  ɵɵconditional,
  ɵɵconditionalCreate,
  ɵɵdefineComponent,
  ɵɵelement,
  ɵɵelementEnd,
  ɵɵelementStart,
  ɵɵgetCurrentView,
  ɵɵlistener,
  ɵɵnextContext,
  ɵɵpipe,
  ɵɵpipeBind1,
  ɵɵproperty,
  ɵɵrepeater,
  ɵɵrepeaterCreate,
  ɵɵrepeaterTrackByIdentity,
  ɵɵrepeaterTrackByIndex,
  ɵɵresetView,
  ɵɵrestoreView,
  ɵɵtext,
  ɵɵtextInterpolate,
  ɵɵtextInterpolate1,
  ɵɵtextInterpolate2,
  ɵɵtwoWayBindingSet,
  ɵɵtwoWayListener,
  ɵɵtwoWayProperty
} from "./chunk-VJUHBL36.js";

// src/app/components/momentum-strategy/momentum-strategy.component.ts
var _forTrack0 = ($index, $item) => $item.key;
var _forTrack1 = ($index, $item) => $item.path;
var _forTrack2 = ($index, $item) => $item.label;
function MomentumStrategyComponent_Conditional_11_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "div", 5);
    \u0275\u0275text(1, "Loading profiles\u2026");
    \u0275\u0275elementEnd();
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_0_For_15_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "div", 37)(1, "div", 39)(2, "div", 40);
    \u0275\u0275text(3);
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(4, "div", 41);
    \u0275\u0275text(5);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(6, "div", 42);
    \u0275\u0275text(7);
    \u0275\u0275elementEnd()();
  }
  if (rf & 2) {
    const ch_r4 = ctx.$implicit;
    \u0275\u0275advance(3);
    \u0275\u0275textInterpolate(ch_r4.label);
    \u0275\u0275advance(2);
    \u0275\u0275textInterpolate(ch_r4.rationale);
    \u0275\u0275advance(2);
    \u0275\u0275textInterpolate2("", ch_r4.old ?? "none", " \u2192 ", ch_r4.new);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_0_Template(rf, ctx) {
  if (rf & 1) {
    const _r2 = \u0275\u0275getCurrentView();
    \u0275\u0275elementStart(0, "div", 15)(1, "div", 30)(2, "div", 31)(3, "span", 32);
    \u0275\u0275text(4, "\u2713");
    \u0275\u0275elementEnd();
    \u0275\u0275text(5, " Applied ");
    \u0275\u0275elementStart(6, "strong");
    \u0275\u0275text(7);
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(8, "span", 33);
    \u0275\u0275text(9, " \u2014 auto-applied on startup");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(10, "button", 34);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_0_Template_button_click_10_listener() {
      \u0275\u0275restoreView(_r2);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.dismissBanner());
    });
    \u0275\u0275text(11, "dismiss");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(12, "div", 35)(13, "div", 36);
    \u0275\u0275repeaterCreate(14, MomentumStrategyComponent_Conditional_12_Conditional_0_For_15_Template, 8, 4, "div", 37, _forTrack1);
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(16, "div", 38)(17, "button", 25);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_0_Template_button_click_17_listener() {
      \u0275\u0275restoreView(_r2);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.rollback());
    });
    \u0275\u0275text(18);
    \u0275\u0275elementEnd()()()();
  }
  if (rf & 2) {
    let tmp_2_0;
    let tmp_4_0;
    const ctx_r2 = \u0275\u0275nextContext(2);
    \u0275\u0275advance(7);
    \u0275\u0275textInterpolate1("Recommended (v", (tmp_2_0 = ctx_r2.profilesData()) == null ? null : tmp_2_0.latest_recommended_version, ")");
    \u0275\u0275advance(7);
    \u0275\u0275repeater(ctx_r2.changelogEntries());
    \u0275\u0275advance(4);
    \u0275\u0275textInterpolate1("\u21BA Rollback to v", (tmp_4_0 = ctx_r2.profilesData()) == null ? null : tmp_4_0.applied_recommended_version);
  }
}
function MomentumStrategyComponent_Conditional_12_For_9_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "option", 21);
    \u0275\u0275text(1);
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const p_r5 = ctx.$implicit;
    \u0275\u0275property("value", p_r5.key);
    \u0275\u0275advance();
    \u0275\u0275textInterpolate1("\u{1F512} ", p_r5.label);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_10_For_2_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "option", 21);
    \u0275\u0275text(1);
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const p_r6 = ctx.$implicit;
    \u0275\u0275property("value", p_r6.key);
    \u0275\u0275advance();
    \u0275\u0275textInterpolate(p_r6.label);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_10_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "optgroup", 22);
    \u0275\u0275repeaterCreate(1, MomentumStrategyComponent_Conditional_12_Conditional_10_For_2_Template, 2, 2, "option", 21, _forTrack0);
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const ctx_r2 = \u0275\u0275nextContext(2);
    \u0275\u0275advance();
    \u0275\u0275repeater(ctx_r2.userProfiles());
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_11_Template(rf, ctx) {
  if (rf & 1) {
    const _r7 = \u0275\u0275getCurrentView();
    \u0275\u0275elementStart(0, "span", 43);
    \u0275\u0275text(1, "(modified)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(2, "button", 44);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_11_Template_button_click_2_listener() {
      \u0275\u0275restoreView(_r7);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.openRevert());
    });
    \u0275\u0275text(3, " \u21BA Revert");
    \u0275\u0275elementStart(4, "span", 45);
    \u0275\u0275text(5);
    \u0275\u0275elementEnd()();
  }
  if (rf & 2) {
    const ctx_r2 = \u0275\u0275nextContext(2);
    \u0275\u0275advance(5);
    \u0275\u0275textInterpolate(ctx_r2.changeCount());
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_19_Template(rf, ctx) {
  if (rf & 1) {
    const _r8 = \u0275\u0275getCurrentView();
    \u0275\u0275elementStart(0, "div", 27)(1, "div", 46);
    \u0275\u0275text(2, "\u{1F512}");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(3, "div", 39)(4, "div", 31);
    \u0275\u0275text(5, "This profile is bot-curated and read-only");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(6, "div", 41);
    \u0275\u0275text(7);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(8, "button", 25);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_19_Template_button_click_8_listener() {
      \u0275\u0275restoreView(_r8);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.openSaveAs("My " + ctx_r2.profileName() + " (custom)"));
    });
    \u0275\u0275text(9, "\u2B50 Customize as new profile");
    \u0275\u0275elementEnd()();
  }
  if (rf & 2) {
    const ctx_r2 = \u0275\u0275nextContext(2);
    \u0275\u0275advance(7);
    \u0275\u0275textInterpolate1(' "', ctx_r2.profileName(), `" evolves with each release of the bot's research. To customize without losing the original, save it as a new profile first. `);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_25_For_12_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "span");
    \u0275\u0275text(1);
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const l_r10 = ctx.$implicit;
    const \u0275$index_157_r11 = ctx.$index;
    const ctx_r2 = \u0275\u0275nextContext(3);
    \u0275\u0275classProp("active", ctx_r2.riskSliderValue() === \u0275$index_157_r11 + 1);
    \u0275\u0275advance();
    \u0275\u0275textInterpolate(l_r10.label);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_53_For_7_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "th");
    \u0275\u0275text(1);
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const h_r12 = ctx.$implicit;
    const \u0275$index_237_r13 = ctx.$index;
    const ctx_r2 = \u0275\u0275nextContext(4);
    \u0275\u0275classProp("col-active", ctx_r2.riskSliderValue() === \u0275$index_237_r13 + 1);
    \u0275\u0275advance();
    \u0275\u0275textInterpolate(h_r12);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_53_For_10_For_4_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "td");
    \u0275\u0275text(1);
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const v_r14 = ctx.$implicit;
    const \u0275$index_249_r15 = ctx.$index;
    const ctx_r2 = \u0275\u0275nextContext(5);
    \u0275\u0275classProp("col-active", ctx_r2.riskSliderValue() === \u0275$index_249_r15 + 1);
    \u0275\u0275advance();
    \u0275\u0275textInterpolate(v_r14);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_53_For_10_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "tr")(1, "td");
    \u0275\u0275text(2);
    \u0275\u0275elementEnd();
    \u0275\u0275repeaterCreate(3, MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_53_For_10_For_4_Template, 2, 3, "td", 77, \u0275\u0275repeaterTrackByIndex);
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const row_r16 = ctx.$implicit;
    \u0275\u0275advance(2);
    \u0275\u0275textInterpolate(row_r16.label);
    \u0275\u0275advance();
    \u0275\u0275repeater(row_r16.values);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_53_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "div", 61)(1, "table")(2, "thead")(3, "tr")(4, "th");
    \u0275\u0275text(5, "Setting");
    \u0275\u0275elementEnd();
    \u0275\u0275repeaterCreate(6, MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_53_For_7_Template, 2, 3, "th", 77, \u0275\u0275repeaterTrackByIdentity);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(8, "tbody");
    \u0275\u0275repeaterCreate(9, MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_53_For_10_Template, 5, 1, "tr", null, _forTrack2);
    \u0275\u0275elementEnd()()();
  }
  if (rf & 2) {
    const ctx_r2 = \u0275\u0275nextContext(3);
    \u0275\u0275advance(6);
    \u0275\u0275repeater(ctx_r2.riskColHeaders);
    \u0275\u0275advance(3);
    \u0275\u0275repeater(ctx_r2.riskTable);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_25_For_65_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "span");
    \u0275\u0275text(1);
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const l_r17 = ctx.$implicit;
    const \u0275$index_270_r18 = ctx.$index;
    const ctx_r2 = \u0275\u0275nextContext(3);
    \u0275\u0275classProp("active", ctx_r2.profitSliderValue() === \u0275$index_270_r18 + 1);
    \u0275\u0275advance();
    \u0275\u0275textInterpolate(l_r17.label);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_25_For_77_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "span", 58)(1, "span", 59);
    \u0275\u0275text(2);
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(3, "span", 60);
    \u0275\u0275text(4);
    \u0275\u0275elementEnd()();
  }
  if (rf & 2) {
    const tier_r19 = ctx.$implicit;
    const \u0275$index_290_r20 = ctx.$index;
    \u0275\u0275advance(2);
    \u0275\u0275textInterpolate1("Tier ", \u0275$index_290_r20 + 1);
    \u0275\u0275advance(2);
    \u0275\u0275textInterpolate2("peak \u2265", tier_r19[0], "% \u2192 trail ", tier_r19[1], "%");
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_78_For_7_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "th");
    \u0275\u0275text(1);
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const h_r21 = ctx.$implicit;
    const \u0275$index_311_r22 = ctx.$index;
    const ctx_r2 = \u0275\u0275nextContext(4);
    \u0275\u0275classProp("col-active", ctx_r2.profitSliderValue() === \u0275$index_311_r22 + 1);
    \u0275\u0275advance();
    \u0275\u0275textInterpolate(h_r21);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_78_For_10_For_4_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "td");
    \u0275\u0275text(1);
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const v_r23 = ctx.$implicit;
    const \u0275$index_323_r24 = ctx.$index;
    const ctx_r2 = \u0275\u0275nextContext(5);
    \u0275\u0275classProp("col-active", ctx_r2.profitSliderValue() === \u0275$index_323_r24 + 1);
    \u0275\u0275advance();
    \u0275\u0275textInterpolate(v_r23);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_78_For_10_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "tr")(1, "td");
    \u0275\u0275text(2);
    \u0275\u0275elementEnd();
    \u0275\u0275repeaterCreate(3, MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_78_For_10_For_4_Template, 2, 3, "td", 77, \u0275\u0275repeaterTrackByIndex);
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const row_r25 = ctx.$implicit;
    \u0275\u0275advance(2);
    \u0275\u0275textInterpolate(row_r25.label);
    \u0275\u0275advance();
    \u0275\u0275repeater(row_r25.values);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_78_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "div", 61)(1, "table")(2, "thead")(3, "tr")(4, "th");
    \u0275\u0275text(5, "Tier (peak \u2192 trail give-back)");
    \u0275\u0275elementEnd();
    \u0275\u0275repeaterCreate(6, MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_78_For_7_Template, 2, 3, "th", 77, \u0275\u0275repeaterTrackByIdentity);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(8, "tbody");
    \u0275\u0275repeaterCreate(9, MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_78_For_10_Template, 5, 1, "tr", null, _forTrack2);
    \u0275\u0275elementEnd()()();
  }
  if (rf & 2) {
    const ctx_r2 = \u0275\u0275nextContext(3);
    \u0275\u0275advance(6);
    \u0275\u0275repeater(ctx_r2.profitColHeaders);
    \u0275\u0275advance(3);
    \u0275\u0275repeater(ctx_r2.profitTable);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_25_For_117_Template(rf, ctx) {
  if (rf & 1) {
    const _r26 = \u0275\u0275getCurrentView();
    \u0275\u0275elementStart(0, "span", 69);
    \u0275\u0275text(1);
    \u0275\u0275elementStart(2, "button", 24);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_25_For_117_Template_button_click_2_listener() {
      const pair_r27 = \u0275\u0275restoreView(_r26).$implicit;
      const ctx_r2 = \u0275\u0275nextContext(3);
      return \u0275\u0275resetView(ctx_r2.removeChip(pair_r27));
    });
    \u0275\u0275text(3, "\xD7");
    \u0275\u0275elementEnd()();
  }
  if (rf & 2) {
    const pair_r27 = ctx.$implicit;
    const ctx_r2 = \u0275\u0275nextContext(3);
    \u0275\u0275advance();
    \u0275\u0275textInterpolate1("", pair_r27, " ");
    \u0275\u0275advance();
    \u0275\u0275property("disabled", ctx_r2.isBuiltin());
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_25_For_126_Template(rf, ctx) {
  if (rf & 1) {
    const _r28 = \u0275\u0275getCurrentView();
    \u0275\u0275elementStart(0, "button", 24);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_25_For_126_Template_button_click_0_listener() {
      const \u0275$index_406_r29 = \u0275\u0275restoreView(_r28).$index;
      const ctx_r2 = \u0275\u0275nextContext(3);
      return \u0275\u0275resetView(ctx_r2.toggleDay(\u0275$index_406_r29));
    });
    \u0275\u0275text(1);
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const day_r30 = ctx.$implicit;
    const \u0275$index_406_r29 = ctx.$index;
    const ctx_r2 = \u0275\u0275nextContext(3);
    \u0275\u0275classProp("active", ctx_r2.isDayBlocked(\u0275$index_406_r29));
    \u0275\u0275property("disabled", ctx_r2.isBuiltin());
    \u0275\u0275advance();
    \u0275\u0275textInterpolate(day_r30);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_25_Template(rf, ctx) {
  if (rf & 1) {
    const _r9 = \u0275\u0275getCurrentView();
    \u0275\u0275elementStart(0, "div")(1, "section", 47)(2, "h2");
    \u0275\u0275text(3, "Risk level ");
    \u0275\u0275elementStart(4, "span", 48);
    \u0275\u0275text(5, "controls 6 entry gates");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(6, "div", 49);
    \u0275\u0275text(7, "Controls how strict entries are: ADX, RSI, distance from ATH, and 3-hour overextension thresholds. Conservative = fewer but cleaner trades. Aggressive = more trades, more noise.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(8, "div", 50)(9, "input", 51);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_25_Template_input_input_9_listener($event) {
      \u0275\u0275restoreView(_r9);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setRiskLevel(+$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(10, "div", 52);
    \u0275\u0275repeaterCreate(11, MomentumStrategyComponent_Conditional_12_Conditional_25_For_12_Template, 2, 3, "span", 53, _forTrack2);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(13, "div", 54)(14, "div", 55)(15, "span");
    \u0275\u0275text(16, "Currently set to ");
    \u0275\u0275elementStart(17, "strong");
    \u0275\u0275text(18);
    \u0275\u0275elementEnd();
    \u0275\u0275text(19, " \u2014 these are the actual values:");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(20, "button", 56);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_25_Template_button_click_20_listener() {
      \u0275\u0275restoreView(_r9);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.showRiskTable.set(!ctx_r2.showRiskTable()));
    });
    \u0275\u0275text(21);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(22, "div", 57)(23, "span", 58)(24, "span", 59);
    \u0275\u0275text(25, "ADX min");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(26, "span", 60);
    \u0275\u0275text(27);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(28, "span", 58)(29, "span", 59);
    \u0275\u0275text(30, "RSI min");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(31, "span", 60);
    \u0275\u0275text(32);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(33, "span", 58)(34, "span", 59);
    \u0275\u0275text(35, "RSI max");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(36, "span", 60);
    \u0275\u0275text(37);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(38, "span", 58)(39, "span", 59);
    \u0275\u0275text(40, "ATH gate");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(41, "span", 60);
    \u0275\u0275text(42);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(43, "span", 58)(44, "span", 59);
    \u0275\u0275text(45, "3h overpump");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(46, "span", 60);
    \u0275\u0275text(47);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(48, "span", 58)(49, "span", 59);
    \u0275\u0275text(50, "3h crash");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(51, "span", 60);
    \u0275\u0275text(52);
    \u0275\u0275elementEnd()()();
    \u0275\u0275conditionalCreate(53, MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_53_Template, 11, 0, "div", 61);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(54, "section", 47)(55, "h2");
    \u0275\u0275text(56, "Profit-taking style ");
    \u0275\u0275elementStart(57, "span", 48);
    \u0275\u0275text(58, "controls 4 trail tiers");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(59, "div", 49);
    \u0275\u0275text(60, "How tightly we trail behind a winning peak. Quick locks small wins early. Let-it-run gives more room but risks giving back more.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(61, "div", 50)(62, "input", 51);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_25_Template_input_input_62_listener($event) {
      \u0275\u0275restoreView(_r9);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setProfitLevel(+$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(63, "div", 52);
    \u0275\u0275repeaterCreate(64, MomentumStrategyComponent_Conditional_12_Conditional_25_For_65_Template, 2, 3, "span", 53, _forTrack2);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(66, "div", 54)(67, "div", 55)(68, "span");
    \u0275\u0275text(69, "Currently set to ");
    \u0275\u0275elementStart(70, "strong");
    \u0275\u0275text(71);
    \u0275\u0275elementEnd();
    \u0275\u0275text(72, " \u2014 these are the trail tiers:");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(73, "button", 56);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_25_Template_button_click_73_listener() {
      \u0275\u0275restoreView(_r9);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.showProfitTable.set(!ctx_r2.showProfitTable()));
    });
    \u0275\u0275text(74);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(75, "div", 57);
    \u0275\u0275repeaterCreate(76, MomentumStrategyComponent_Conditional_12_Conditional_25_For_77_Template, 5, 3, "span", 58, \u0275\u0275repeaterTrackByIndex);
    \u0275\u0275elementEnd();
    \u0275\u0275conditionalCreate(78, MomentumStrategyComponent_Conditional_12_Conditional_25_Conditional_78_Template, 11, 0, "div", 61);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(79, "section", 47)(80, "h2");
    \u0275\u0275text(81, "Max hold per trade");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(82, "div", 49);
    \u0275\u0275text(83, "Force-exit after this many hours, regardless of P&L. Prevents trades from sitting in slow bleed.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(84, "div", 62)(85, "select", 19);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_25_Template_select_ngModelChange_85_listener($event) {
      \u0275\u0275restoreView(_r9);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setMaxHold($event));
    });
    \u0275\u0275elementStart(86, "option", 21);
    \u0275\u0275text(87, "12 hours");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(88, "option", 21);
    \u0275\u0275text(89, "24 hours");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(90, "option", 21);
    \u0275\u0275text(91, "48 hours");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(92, "option", 21);
    \u0275\u0275text(93, "72 hours (recommended)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(94, "option", 21);
    \u0275\u0275text(95, "168 hours (1 week)");
    \u0275\u0275elementEnd()()()();
    \u0275\u0275elementStart(96, "section", 47)(97, "h2");
    \u0275\u0275text(98, "Position size per trade");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(99, "div", 49);
    \u0275\u0275text(100, "USD amount allocated to each trade. Higher = bigger wins/losses, fees as % stay the same.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(101, "div", 63)(102, "div", 64);
    \u0275\u0275text(103, "Allocation");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(104, "div", 65);
    \u0275\u0275text(105);
    \u0275\u0275pipe(106, "number");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(107, "div", 62)(108, "input", 66);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_25_Template_input_input_108_listener($event) {
      \u0275\u0275restoreView(_r9);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setAllocation(+$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(109, "input", 67);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_25_Template_input_ngModelChange_109_listener($event) {
      \u0275\u0275restoreView(_r9);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setAllocation($event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(110, "section", 47)(111, "h2");
    \u0275\u0275text(112, "Pairs to skip (blacklist)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(113, "div", 49);
    \u0275\u0275text(114, "Pairs the bot will never enter. Use this for known dead-money coins.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(115, "div", 68);
    \u0275\u0275repeaterCreate(116, MomentumStrategyComponent_Conditional_12_Conditional_25_For_117_Template, 4, 2, "span", 69, \u0275\u0275repeaterTrackByIdentity);
    \u0275\u0275elementStart(118, "input", 70);
    \u0275\u0275twoWayListener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_25_Template_input_ngModelChange_118_listener($event) {
      \u0275\u0275restoreView(_r9);
      const ctx_r2 = \u0275\u0275nextContext(2);
      \u0275\u0275twoWayBindingSet(ctx_r2.blacklistInput, $event) || (ctx_r2.blacklistInput = $event);
      return \u0275\u0275resetView($event);
    });
    \u0275\u0275listener("keydown", function MomentumStrategyComponent_Conditional_12_Conditional_25_Template_input_keydown_118_listener($event) {
      \u0275\u0275restoreView(_r9);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.onChipKeydown($event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(119, "section", 47)(120, "h2");
    \u0275\u0275text(121, "Pause entries on these days");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(122, "div", 49);
    \u0275\u0275text(123, "No new positions opened on selected days. Existing positions still exit normally. Default: Sunday only.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(124, "div", 71);
    \u0275\u0275repeaterCreate(125, MomentumStrategyComponent_Conditional_12_Conditional_25_For_126_Template, 2, 4, "button", 72, \u0275\u0275repeaterTrackByIdentity);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(127, "section", 47)(128, "h2");
    \u0275\u0275text(129, "Wall-aware trail");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(130, "div", 49);
    \u0275\u0275text(131, "Anchor trail stops to qualifying L2 bid walls instead of arbitrary percentages. Improves stop placement when there's real liquidity below current price.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(132, "div", 62)(133, "label", 73)(134, "input", 74);
    \u0275\u0275listener("change", function MomentumStrategyComponent_Conditional_12_Conditional_25_Template_input_change_134_listener($event) {
      \u0275\u0275restoreView(_r9);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setWallAware($event.target.checked));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275element(135, "span", 75);
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(136, "span", 76);
    \u0275\u0275text(137, " Currently ");
    \u0275\u0275elementStart(138, "strong");
    \u0275\u0275text(139);
    \u0275\u0275elementEnd()()()()();
  }
  if (rf & 2) {
    const ctx_r2 = \u0275\u0275nextContext(2);
    \u0275\u0275classProp("read-only", ctx_r2.isBuiltin());
    \u0275\u0275advance(9);
    \u0275\u0275property("value", ctx_r2.riskSliderValue());
    \u0275\u0275advance(2);
    \u0275\u0275repeater(ctx_r2.riskLevels);
    \u0275\u0275advance(7);
    \u0275\u0275textInterpolate(ctx_r2.riskLevelLabel());
    \u0275\u0275advance(3);
    \u0275\u0275textInterpolate1(" ", ctx_r2.showRiskTable() ? "hide table \u2191" : "show all 5 levels \u2193", " ");
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate(ctx_r2.getField("entry_gates", "adx_min"));
    \u0275\u0275advance(5);
    \u0275\u0275textInterpolate(ctx_r2.getField("entry_gates", "rsi_min"));
    \u0275\u0275advance(5);
    \u0275\u0275textInterpolate(ctx_r2.getField("entry_gates", "rsi_max"));
    \u0275\u0275advance(5);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("entry_gates", "ath_dist_max"), "%");
    \u0275\u0275advance(5);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("entry_gates", "chg3h_atr_max"), "\xD7 ATR");
    \u0275\u0275advance(5);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("entry_gates", "chg3h_atr_min"), "\xD7 ATR");
    \u0275\u0275advance();
    \u0275\u0275conditional(ctx_r2.showRiskTable() ? 53 : -1);
    \u0275\u0275advance(9);
    \u0275\u0275property("value", ctx_r2.profitSliderValue());
    \u0275\u0275advance(2);
    \u0275\u0275repeater(ctx_r2.profitLevels);
    \u0275\u0275advance(7);
    \u0275\u0275textInterpolate(ctx_r2.profitLevelLabel());
    \u0275\u0275advance(3);
    \u0275\u0275textInterpolate1(" ", ctx_r2.showProfitTable() ? "hide table \u2191" : "show all 5 levels \u2193", " ");
    \u0275\u0275advance(2);
    \u0275\u0275repeater(ctx_r2.getTiers());
    \u0275\u0275advance(2);
    \u0275\u0275conditional(ctx_r2.showProfitTable() ? 78 : -1);
    \u0275\u0275advance(7);
    \u0275\u0275property("ngModel", ctx_r2.getField("exits", "max_hold_hours"));
    \u0275\u0275advance();
    \u0275\u0275property("value", 12);
    \u0275\u0275advance(2);
    \u0275\u0275property("value", 24);
    \u0275\u0275advance(2);
    \u0275\u0275property("value", 48);
    \u0275\u0275advance(2);
    \u0275\u0275property("value", 72);
    \u0275\u0275advance(2);
    \u0275\u0275property("value", 168);
    \u0275\u0275advance(11);
    \u0275\u0275textInterpolate1("$", \u0275\u0275pipeBind1(106, 34, ctx_r2.getField("position", "allocation_usd")));
    \u0275\u0275advance(3);
    \u0275\u0275property("value", ctx_r2.getField("position", "allocation_usd"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("position", "allocation_usd"));
    \u0275\u0275advance(7);
    \u0275\u0275repeater(ctx_r2.getBlacklist());
    \u0275\u0275advance(2);
    \u0275\u0275twoWayProperty("ngModel", ctx_r2.blacklistInput);
    \u0275\u0275property("disabled", ctx_r2.isBuiltin());
    \u0275\u0275advance(7);
    \u0275\u0275repeater(ctx_r2.days);
    \u0275\u0275advance(9);
    \u0275\u0275property("checked", ctx_r2.getField("wall_aware", "enabled"))("disabled", ctx_r2.isBuiltin());
    \u0275\u0275advance(4);
    \u0275\u0275classProp("on-label", ctx_r2.getField("wall_aware", "enabled"))("off-label", !ctx_r2.getField("wall_aware", "enabled"));
    \u0275\u0275advance();
    \u0275\u0275textInterpolate1(" ", ctx_r2.getField("wall_aware", "enabled") ? "on" : "off", " ");
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_26_For_137_Template(rf, ctx) {
  if (rf & 1) {
    const _r32 = \u0275\u0275getCurrentView();
    \u0275\u0275elementStart(0, "div", 107)(1, "div", 105);
    \u0275\u0275text(2);
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(3, "input", 140);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_For_137_Template_input_input_3_listener($event) {
      const \u0275$index_665_r33 = \u0275\u0275restoreView(_r32).$index;
      const ctx_r2 = \u0275\u0275nextContext(3);
      return \u0275\u0275resetView(ctx_r2.setTierValue(\u0275$index_665_r33, 0, +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(4, "input", 141);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_For_137_Template_input_input_4_listener($event) {
      const \u0275$index_665_r33 = \u0275\u0275restoreView(_r32).$index;
      const ctx_r2 = \u0275\u0275nextContext(3);
      return \u0275\u0275resetView(ctx_r2.setTierValue(\u0275$index_665_r33, 1, +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(5, "button", 142);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_26_For_137_Template_button_click_5_listener() {
      const \u0275$index_665_r33 = \u0275\u0275restoreView(_r32).$index;
      const ctx_r2 = \u0275\u0275nextContext(3);
      return \u0275\u0275resetView(ctx_r2.removeTier(\u0275$index_665_r33));
    });
    \u0275\u0275text(6, "\xD7");
    \u0275\u0275elementEnd()();
  }
  if (rf & 2) {
    const tier_r34 = ctx.$implicit;
    const \u0275$index_665_r33 = ctx.$index;
    \u0275\u0275advance(2);
    \u0275\u0275textInterpolate(\u0275$index_665_r33 + 1);
    \u0275\u0275advance();
    \u0275\u0275property("value", tier_r34[0]);
    \u0275\u0275advance();
    \u0275\u0275property("value", tier_r34[1]);
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_26_For_387_Template(rf, ctx) {
  if (rf & 1) {
    const _r35 = \u0275\u0275getCurrentView();
    \u0275\u0275elementStart(0, "span", 69);
    \u0275\u0275text(1);
    \u0275\u0275elementStart(2, "button", 24);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_26_For_387_Template_button_click_2_listener() {
      const pair_r36 = \u0275\u0275restoreView(_r35).$implicit;
      const ctx_r2 = \u0275\u0275nextContext(3);
      return \u0275\u0275resetView(ctx_r2.removeChip(pair_r36));
    });
    \u0275\u0275text(3, "\xD7");
    \u0275\u0275elementEnd()();
  }
  if (rf & 2) {
    const pair_r36 = ctx.$implicit;
    const ctx_r2 = \u0275\u0275nextContext(3);
    \u0275\u0275advance();
    \u0275\u0275textInterpolate1("", pair_r36, " ");
    \u0275\u0275advance();
    \u0275\u0275property("disabled", ctx_r2.isBuiltin());
  }
}
function MomentumStrategyComponent_Conditional_12_Conditional_26_Template(rf, ctx) {
  if (rf & 1) {
    const _r31 = \u0275\u0275getCurrentView();
    \u0275\u0275elementStart(0, "div")(1, "details", 78)(2, "summary")(3, "span", 79)(4, "span", 80);
    \u0275\u0275text(5, "\u25B6");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(6, "strong");
    \u0275\u0275text(7, "Entry gates");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(8, "span", 81);
    \u0275\u0275text(9, "9 controls");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(10, "button", 82);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_button_click_10_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      $event.preventDefault();
      return \u0275\u0275resetView(ctx_r2.resetSection("entry_gates"));
    });
    \u0275\u0275text(11, "\u21BB Reset section");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(12, "div", 83)(13, "div", 84)(14, "div", 63)(15, "div", 64);
    \u0275\u0275text(16, "ADX min ");
    \u0275\u0275elementStart(17, "span", 85);
    \u0275\u0275text(18, "?");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(19, "div", 65);
    \u0275\u0275text(20);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(21, "div", 86);
    \u0275\u0275text(22, "Higher = only enter very strong trends. Sane range: 15\u201340.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(23, "div", 62)(24, "input", 87);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_24_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "adx_min", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(25, "input", 88);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_25_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "adx_min", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(26, "div", 84)(27, "div", 63)(28, "div", 64);
    \u0275\u0275text(29, "RSI min (uptrend)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(30, "div", 65);
    \u0275\u0275text(31);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(32, "div", 86);
    \u0275\u0275text(33, "Reject entries when RSI is below this \u2014 coin must be above the midline. Sane range: 40\u201360.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(34, "div", 62)(35, "input", 89);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_35_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "rsi_min", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(36, "input", 90);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_36_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "rsi_min", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(37, "div", 84)(38, "div", 63)(39, "div", 64);
    \u0275\u0275text(40, "RSI max (overbought)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(41, "div", 65);
    \u0275\u0275text(42);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(43, "div", 86);
    \u0275\u0275text(44, "Reject entries when RSI is above this \u2014 coin is overbought. Sane range: 60\u201380.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(45, "div", 62)(46, "input", 91);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_46_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "rsi_max", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(47, "input", 92);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_47_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "rsi_max", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(48, "div", 84)(49, "div", 63)(50, "div", 64);
    \u0275\u0275text(51, "Re-entry accel threshold (%)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(52, "div", 65);
    \u0275\u0275text(53);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(54, "div", 86);
    \u0275\u0275text(55, "Minimum acceleration % required to enter. Below this is too weak. Sane range: 5\u201325.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(56, "div", 62)(57, "input", 87);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_57_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "accel_min", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(58, "input", 88);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_58_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "accel_min", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(59, "div", 84)(60, "div", 63)(61, "div", 64);
    \u0275\u0275text(62, "ATH proximity gate (%)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(63, "div", 65);
    \u0275\u0275text(64);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(65, "div", 86);
    \u0275\u0275text(66, "Reject if price is within X% of all-time high. Negative = below ATH. Sane range: -5 to -25.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(67, "div", 62)(68, "input", 93);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_68_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "ath_dist_max", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(69, "input", 94);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_69_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "ath_dist_max", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(70, "div", 84)(71, "div", 63)(72, "div", 64);
    \u0275\u0275text(73, "3-hour overpump (\xD7 ATR)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(74, "div", 65);
    \u0275\u0275text(75);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(76, "div", 86);
    \u0275\u0275text(77, "Reject if 3-hour move exceeds X ATR upward (already pumped). Sane range: 1.5\u20136.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(78, "div", 62)(79, "input", 95);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_79_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "chg3h_atr_max", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(80, "input", 96);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_80_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "chg3h_atr_max", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(81, "div", 84)(82, "div", 63)(83, "div", 64);
    \u0275\u0275text(84, "3-hour crash (\xD7 ATR, lower bound)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(85, "div", 65);
    \u0275\u0275text(86);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(87, "div", 86);
    \u0275\u0275text(88, "Reject if 3-hour move dropped more than X ATR (falling-knife). Sane range: -1.5 to -6.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(89, "div", 62)(90, "input", 97);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_90_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "chg3h_atr_min", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(91, "input", 98);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_91_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "chg3h_atr_min", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(92, "div", 84)(93, "div", 63)(94, "div", 64);
    \u0275\u0275text(95, "Green candles min (of last 6)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(96, "div", 65);
    \u0275\u0275text(97);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(98, "div", 86);
    \u0275\u0275text(99, "Require at least N of last 6 candles to close green. Sane range: 1\u20135.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(100, "div", 62)(101, "input", 99);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_101_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "green_count_min", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(102, "input", 100);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_102_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "green_count_min", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(103, "div", 84)(104, "div", 63)(105, "div", 64);
    \u0275\u0275text(106, "Body ratio min");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(107, "div", 65);
    \u0275\u0275text(108);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(109, "div", 86);
    \u0275\u0275text(110, "Average candle body / range. Higher = more decisive candles required. Sane range: 0.1\u20130.7.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(111, "div", 62)(112, "input", 101);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_112_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "body_ratio_min", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(113, "input", 102);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_113_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("entry_gates", "body_ratio_min", $event));
    });
    \u0275\u0275elementEnd()()()()();
    \u0275\u0275elementStart(114, "details", 103)(115, "summary")(116, "span", 79)(117, "span", 80);
    \u0275\u0275text(118, "\u25B6");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(119, "strong");
    \u0275\u0275text(120, "Trail tiers");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(121, "span", 81);
    \u0275\u0275text(122, "progressive trail");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(123, "button", 82);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_button_click_123_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      $event.preventDefault();
      return \u0275\u0275resetView(ctx_r2.resetSection("trail"));
    });
    \u0275\u0275text(124, "\u21BB Reset section");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(125, "div", 83)(126, "div", 86);
    \u0275\u0275text(127, "Each tier: when peak reaches the % shown, lock the stop at peak \u2212 give-back %. The bot uses the tightest tier whose threshold is met.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(128, "div", 104)(129, "div", 105);
    \u0275\u0275text(130, "Tier");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(131, "div", 106);
    \u0275\u0275text(132, "Peak \u2265");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(133, "div", 106);
    \u0275\u0275text(134, "Trail give-back");
    \u0275\u0275elementEnd();
    \u0275\u0275element(135, "div");
    \u0275\u0275elementEnd();
    \u0275\u0275repeaterCreate(136, MomentumStrategyComponent_Conditional_12_Conditional_26_For_137_Template, 7, 3, "div", 107, \u0275\u0275repeaterTrackByIndex);
    \u0275\u0275elementStart(138, "div", 108)(139, "button", 109);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_button_click_139_listener() {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.addTier());
    });
    \u0275\u0275text(140, "+ Add tier");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(141, "div", 110)(142, "div", 63)(143, "div", 64);
    \u0275\u0275text(144, "ATR stop multiplier (entry-time stop)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(145, "div", 65);
    \u0275\u0275text(146);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(147, "div", 86);
    \u0275\u0275text(148, "Wide trail % used before first tier activates. Sane range: 2\u201310.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(149, "div", 62)(150, "input", 111);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_150_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("trail", "wide_pct", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(151, "input", 112);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_151_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("trail", "wide_pct", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(152, "div", 84)(153, "div", 63)(154, "div", 64);
    \u0275\u0275text(155, "Stale ticks (no new high)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(156, "div", 65);
    \u0275\u0275text(157);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(158, "div", 86);
    \u0275\u0275text(159, "After this many ticks without a new high, switch to the stale (tightest) trail. Sane range: 10\u2013120.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(160, "div", 62)(161, "input", 113);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_161_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("trail", "stale_ticks", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(162, "input", 114);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_162_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("trail", "stale_ticks", $event));
    });
    \u0275\u0275elementEnd()()()()();
    \u0275\u0275elementStart(163, "details", 103)(164, "summary")(165, "span", 79)(166, "span", 80);
    \u0275\u0275text(167, "\u25B6");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(168, "strong");
    \u0275\u0275text(169, "Exits & safety stops");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(170, "span", 81);
    \u0275\u0275text(171, "5 controls");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(172, "button", 82);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_button_click_172_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      $event.preventDefault();
      return \u0275\u0275resetView(ctx_r2.resetSection("exits"));
    });
    \u0275\u0275text(173, "\u21BB Reset section");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(174, "div", 83)(175, "div", 84)(176, "div", 63)(177, "div", 64);
    \u0275\u0275text(178, "Max hold (hours)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(179, "div", 65);
    \u0275\u0275text(180);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(181, "div", 86);
    \u0275\u0275text(182, "Force-exit after this many hours. Sane range: 12\u2013168.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(183, "div", 62)(184, "input", 115);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_184_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("exits", "max_hold_hours", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(185, "input", 116);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_185_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("exits", "max_hold_hours", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(186, "div", 84)(187, "div", 63)(188, "div", 64);
    \u0275\u0275text(189, "Accel-fade exit threshold (%)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(190, "div", 65);
    \u0275\u0275text(191);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(192, "div", 86);
    \u0275\u0275text(193, "Exit if acceleration drops below this after min-hold. Sane range: 0\u201315.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(194, "div", 62)(195, "input", 117);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_195_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("exits", "accel_exit_thresh", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(196, "input", 118);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_196_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("exits", "accel_exit_thresh", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(197, "div", 84)(198, "div", 63)(199, "div", 64);
    \u0275\u0275text(200, "Accel-fade min hold (hours)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(201, "div", 65);
    \u0275\u0275text(202);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(203, "div", 86);
    \u0275\u0275text(204, "Don't trigger accel-fade until trade is held this long. Sane range: 1\u201324.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(205, "div", 62)(206, "input", 119);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_206_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("exits", "accel_exit_min_hold", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(207, "input", 120);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_207_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("exits", "accel_exit_min_hold", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(208, "div", 84)(209, "div", 63)(210, "div", 64);
    \u0275\u0275text(211, "Equity trailing stop (%)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(212, "div", 65);
    \u0275\u0275text(213);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(214, "div", 86);
    \u0275\u0275text(215, "Portfolio-level emergency stop. Exit all positions if equity falls X% from peak. Sane range: 5\u201330.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(216, "div", 62)(217, "input", 121);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_217_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("exits", "equity_trail_pct", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(218, "input", 122);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_218_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("exits", "equity_trail_pct", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(219, "div", 84)(220, "div", 63)(221, "div", 64);
    \u0275\u0275text(222, "Min hold (hours)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(223, "div", 65);
    \u0275\u0275text(224);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(225, "div", 86);
    \u0275\u0275text(226, "Don't allow regime/rebalance exit until trade has been held this long. Sane range: 0\u201312.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(227, "div", 62)(228, "input", 119);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_228_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("exits", "min_hold_hours", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(229, "input", 120);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_229_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("exits", "min_hold_hours", $event));
    });
    \u0275\u0275elementEnd()()()()();
    \u0275\u0275elementStart(230, "details", 103)(231, "summary")(232, "span", 79)(233, "span", 80);
    \u0275\u0275text(234, "\u25B6");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(235, "strong");
    \u0275\u0275text(236, "Lockouts");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(237, "span", 81);
    \u0275\u0275text(238, "3 controls");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(239, "button", 82);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_button_click_239_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      $event.preventDefault();
      return \u0275\u0275resetView(ctx_r2.resetSection("lockouts"));
    });
    \u0275\u0275text(240, "\u21BB Reset section");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(241, "div", 83)(242, "div", 84)(243, "div", 63)(244, "div", 64);
    \u0275\u0275text(245, "Same-coin lockout (hours)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(246, "div", 65);
    \u0275\u0275text(247);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(248, "div", 86);
    \u0275\u0275text(249, "After exiting a coin, can't re-buy for X hours. Sane range: 4\u2013168.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(250, "div", 62)(251, "input", 123);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_251_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("lockouts", "same_coin_hours", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(252, "input", 124);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_252_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("lockouts", "same_coin_hours", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(253, "div", 84)(254, "div", 63)(255, "div", 64);
    \u0275\u0275text(256, "Loss-lockout (hours)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(257, "div", 65);
    \u0275\u0275text(258);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(259, "div", 86);
    \u0275\u0275text(260, "After a losing trade, that coin is locked out for X hours. Sane range: 24\u2013336.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(261, "div", 62)(262, "input", 125);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_262_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("lockouts", "loss_lockout_hours", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(263, "input", 126);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_263_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("lockouts", "loss_lockout_hours", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(264, "div", 84)(265, "div", 63)(266, "div", 64);
    \u0275\u0275text(267, "Exit cooldown (hours)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(268, "div", 65);
    \u0275\u0275text(269);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(270, "div", 86);
    \u0275\u0275text(271, "Pause for this many hours after any exit before considering new entries. Sane range: 0\u201348.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(272, "div", 62)(273, "input", 127);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_273_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("lockouts", "exit_cooldown_hours", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(274, "input", 128);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_274_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("lockouts", "exit_cooldown_hours", $event));
    });
    \u0275\u0275elementEnd()()()()();
    \u0275\u0275elementStart(275, "details", 103)(276, "summary")(277, "span", 79)(278, "span", 80);
    \u0275\u0275text(279, "\u25B6");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(280, "strong");
    \u0275\u0275text(281, "Regime detector");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(282, "span", 81);
    \u0275\u0275text(283, "2 controls");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(284, "button", 82);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_button_click_284_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      $event.preventDefault();
      return \u0275\u0275resetView(ctx_r2.resetSection("regime"));
    });
    \u0275\u0275text(285, "\u21BB Reset section");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(286, "div", 83)(287, "div", 84)(288, "div", 63)(289, "div", 64);
    \u0275\u0275text(290, "BTC SMA period (candles)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(291, "div", 65);
    \u0275\u0275text(292);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(293, "div", 86);
    \u0275\u0275text(294, "Number of hourly candles to average for the BTC regime MA. Sane range: 100\u20131000.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(295, "div", 62)(296, "input", 129);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_296_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("regime", "ma_period", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(297, "input", 130);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_297_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("regime", "ma_period", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(298, "div", 84)(299, "div", 63)(300, "div", 64);
    \u0275\u0275text(301, "Regime hysteresis (%)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(302, "div", 65);
    \u0275\u0275text(303);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(304, "div", 86);
    \u0275\u0275text(305, "BTC must cross MA by this % to flip regime \u2014 prevents whipsaw. Sane range: 1\u201315.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(306, "div", 62)(307, "input", 131);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_307_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("regime", "hysteresis_pct", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(308, "input", 132);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_308_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("regime", "hysteresis_pct", $event));
    });
    \u0275\u0275elementEnd()()()()();
    \u0275\u0275elementStart(309, "details", 103)(310, "summary")(311, "span", 79)(312, "span", 80);
    \u0275\u0275text(313, "\u25B6");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(314, "strong");
    \u0275\u0275text(315, "Position & sizing");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(316, "span", 81);
    \u0275\u0275text(317, "3 controls");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(318, "button", 82);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_button_click_318_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      $event.preventDefault();
      return \u0275\u0275resetView(ctx_r2.resetSection("position"));
    });
    \u0275\u0275text(319, "\u21BB Reset section");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(320, "div", 83)(321, "div", 84)(322, "div", 63)(323, "div", 64);
    \u0275\u0275text(324, "Allocation USD");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(325, "div", 65);
    \u0275\u0275text(326);
    \u0275\u0275pipe(327, "number");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(328, "div", 86);
    \u0275\u0275text(329, "Total capital pool the bot trades with. Sane range: $500\u2013$20000.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(330, "div", 62)(331, "input", 133);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_331_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("position", "allocation_usd", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(332, "input", 134);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_332_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("position", "allocation_usd", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(333, "div", 84)(334, "div", 63)(335, "div", 64);
    \u0275\u0275text(336, "Top N to buy");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(337, "div", 65);
    \u0275\u0275text(338);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(339, "div", 86);
    \u0275\u0275text(340, "How many top-ranked candidates to buy each entry tick. Sane range: 1\u20135.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(341, "div", 62)(342, "input", 51);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_342_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("position", "top_n", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(343, "input", 135);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_343_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("position", "top_n", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(344, "div", 84)(345, "div", 63)(346, "div", 64);
    \u0275\u0275text(347, "Rebalance interval (hours)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(348, "div", 65);
    \u0275\u0275text(349);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(350, "div", 86);
    \u0275\u0275text(351, "Hours between full rebalance/rotation checks. Sane range: 24\u2013336.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(352, "div", 62)(353, "input", 136);
    \u0275\u0275listener("input", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_input_353_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("position", "rebal_hours", +$event.target.value));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(354, "input", 137);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_354_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("position", "rebal_hours", $event));
    });
    \u0275\u0275elementEnd()()()()();
    \u0275\u0275elementStart(355, "details", 103)(356, "summary")(357, "span", 79)(358, "span", 80);
    \u0275\u0275text(359, "\u25B6");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(360, "strong");
    \u0275\u0275text(361, "Universe");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(362, "span", 81);
    \u0275\u0275text(363, "2 controls");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(364, "button", 82);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_button_click_364_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      $event.preventDefault();
      return \u0275\u0275resetView(ctx_r2.resetSection("universe"));
    });
    \u0275\u0275text(365, "\u21BB Reset section");
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(366, "div", 83)(367, "div", 84)(368, "div", 63)(369, "div", 64);
    \u0275\u0275text(370, "Min price ($)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(371, "div", 65);
    \u0275\u0275text(372);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(373, "div", 86);
    \u0275\u0275text(374, "Don't trade pairs priced below this \u2014 too noisy for reliable signals. Sane range: $0.001\u2013$1.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(375, "div", 62)(376, "input", 138);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_376_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.setField("universe", "min_price", $event));
    });
    \u0275\u0275elementEnd()()();
    \u0275\u0275elementStart(377, "div", 84)(378, "div", 63)(379, "div", 64);
    \u0275\u0275text(380, "Blacklist");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(381, "div", 139);
    \u0275\u0275text(382);
    \u0275\u0275elementEnd()();
    \u0275\u0275elementStart(383, "div", 86);
    \u0275\u0275text(384, "Pairs that will never be entered. (Also editable in Simple view.)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(385, "div", 68);
    \u0275\u0275repeaterCreate(386, MomentumStrategyComponent_Conditional_12_Conditional_26_For_387_Template, 4, 2, "span", 69, \u0275\u0275repeaterTrackByIdentity);
    \u0275\u0275elementStart(388, "input", 70);
    \u0275\u0275twoWayListener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_ngModelChange_388_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      \u0275\u0275twoWayBindingSet(ctx_r2.blacklistInput, $event) || (ctx_r2.blacklistInput = $event);
      return \u0275\u0275resetView($event);
    });
    \u0275\u0275listener("keydown", function MomentumStrategyComponent_Conditional_12_Conditional_26_Template_input_keydown_388_listener($event) {
      \u0275\u0275restoreView(_r31);
      const ctx_r2 = \u0275\u0275nextContext(2);
      return \u0275\u0275resetView(ctx_r2.onChipKeydown($event));
    });
    \u0275\u0275elementEnd()()()()()();
  }
  if (rf & 2) {
    const ctx_r2 = \u0275\u0275nextContext(2);
    \u0275\u0275classProp("read-only", ctx_r2.isBuiltin());
    \u0275\u0275advance(20);
    \u0275\u0275textInterpolate(ctx_r2.getField("entry_gates", "adx_min"));
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("entry_gates", "adx_min"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("entry_gates", "adx_min"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate(ctx_r2.getField("entry_gates", "rsi_min"));
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("entry_gates", "rsi_min"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("entry_gates", "rsi_min"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate(ctx_r2.getField("entry_gates", "rsi_max"));
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("entry_gates", "rsi_max"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("entry_gates", "rsi_max"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("entry_gates", "accel_min"), "%");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("entry_gates", "accel_min"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("entry_gates", "accel_min"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("entry_gates", "ath_dist_max"), "%");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("entry_gates", "ath_dist_max"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("entry_gates", "ath_dist_max"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("entry_gates", "chg3h_atr_max"), "\xD7");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("entry_gates", "chg3h_atr_max"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("entry_gates", "chg3h_atr_max"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("entry_gates", "chg3h_atr_min"), "\xD7");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("entry_gates", "chg3h_atr_min"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("entry_gates", "chg3h_atr_min"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("entry_gates", "green_count_min"), "/6");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("entry_gates", "green_count_min"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("entry_gates", "green_count_min"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate(ctx_r2.getField("entry_gates", "body_ratio_min"));
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("entry_gates", "body_ratio_min"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("entry_gates", "body_ratio_min"));
    \u0275\u0275advance(23);
    \u0275\u0275repeater(ctx_r2.getTiers());
    \u0275\u0275advance(10);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("trail", "wide_pct"), "%");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("trail", "wide_pct"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("trail", "wide_pct"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate(ctx_r2.getField("trail", "stale_ticks"));
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("trail", "stale_ticks"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("trail", "stale_ticks"));
    \u0275\u0275advance(18);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("exits", "max_hold_hours"), "h");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("exits", "max_hold_hours"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("exits", "max_hold_hours"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("exits", "accel_exit_thresh"), "%");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("exits", "accel_exit_thresh"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("exits", "accel_exit_thresh"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("exits", "accel_exit_min_hold"), "h");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("exits", "accel_exit_min_hold"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("exits", "accel_exit_min_hold"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("exits", "equity_trail_pct"), "%");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("exits", "equity_trail_pct"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("exits", "equity_trail_pct"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("exits", "min_hold_hours"), "h");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("exits", "min_hold_hours"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("exits", "min_hold_hours"));
    \u0275\u0275advance(18);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("lockouts", "same_coin_hours"), "h");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("lockouts", "same_coin_hours"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("lockouts", "same_coin_hours"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("lockouts", "loss_lockout_hours"), "h");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("lockouts", "loss_lockout_hours"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("lockouts", "loss_lockout_hours"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("lockouts", "exit_cooldown_hours"), "h");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("lockouts", "exit_cooldown_hours"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("lockouts", "exit_cooldown_hours"));
    \u0275\u0275advance(18);
    \u0275\u0275textInterpolate(ctx_r2.getField("regime", "ma_period"));
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("regime", "ma_period"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("regime", "ma_period"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("regime", "hysteresis_pct"), "%");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("regime", "hysteresis_pct"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("regime", "hysteresis_pct"));
    \u0275\u0275advance(18);
    \u0275\u0275textInterpolate1("$", \u0275\u0275pipeBind1(327, 80, ctx_r2.getField("position", "allocation_usd")));
    \u0275\u0275advance(5);
    \u0275\u0275property("value", ctx_r2.getField("position", "allocation_usd"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("position", "allocation_usd"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate(ctx_r2.getField("position", "top_n"));
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("position", "top_n"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("position", "top_n"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate1("", ctx_r2.getField("position", "rebal_hours"), "h");
    \u0275\u0275advance(4);
    \u0275\u0275property("value", ctx_r2.getField("position", "rebal_hours"));
    \u0275\u0275advance();
    \u0275\u0275property("ngModel", ctx_r2.getField("position", "rebal_hours"));
    \u0275\u0275advance(18);
    \u0275\u0275textInterpolate1("$", ctx_r2.getField("universe", "min_price"));
    \u0275\u0275advance(4);
    \u0275\u0275property("ngModel", ctx_r2.getField("universe", "min_price"));
    \u0275\u0275advance(6);
    \u0275\u0275textInterpolate2("", ctx_r2.getBlacklist().length, " pair", ctx_r2.getBlacklist().length !== 1 ? "s" : "");
    \u0275\u0275advance(4);
    \u0275\u0275repeater(ctx_r2.getBlacklist());
    \u0275\u0275advance(2);
    \u0275\u0275twoWayProperty("ngModel", ctx_r2.blacklistInput);
    \u0275\u0275property("disabled", ctx_r2.isBuiltin());
  }
}
function MomentumStrategyComponent_Conditional_12_Template(rf, ctx) {
  if (rf & 1) {
    const _r1 = \u0275\u0275getCurrentView();
    \u0275\u0275conditionalCreate(0, MomentumStrategyComponent_Conditional_12_Conditional_0_Template, 19, 2, "div", 15);
    \u0275\u0275elementStart(1, "div", 16)(2, "div")(3, "div", 17);
    \u0275\u0275text(4, "Profile");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(5, "div", 18)(6, "select", 19);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_12_Template_select_ngModelChange_6_listener($event) {
      \u0275\u0275restoreView(_r1);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.onProfileChange($event));
    });
    \u0275\u0275elementStart(7, "optgroup", 20);
    \u0275\u0275repeaterCreate(8, MomentumStrategyComponent_Conditional_12_For_9_Template, 2, 2, "option", 21, _forTrack0);
    \u0275\u0275elementEnd();
    \u0275\u0275conditionalCreate(10, MomentumStrategyComponent_Conditional_12_Conditional_10_Template, 3, 0, "optgroup", 22);
    \u0275\u0275elementEnd();
    \u0275\u0275conditionalCreate(11, MomentumStrategyComponent_Conditional_12_Conditional_11_Template, 6, 1);
    \u0275\u0275elementEnd()();
    \u0275\u0275element(12, "div", 23);
    \u0275\u0275elementStart(13, "button", 24);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Template_button_click_13_listener() {
      \u0275\u0275restoreView(_r1);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.openSave());
    });
    \u0275\u0275text(14, "\u2913 Save");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(15, "button", 25);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Template_button_click_15_listener() {
      \u0275\u0275restoreView(_r1);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.openSaveAs());
    });
    \u0275\u0275text(16, "\u2B50 Save as new\u2026");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(17, "button", 26);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Template_button_click_17_listener() {
      \u0275\u0275restoreView(_r1);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.openDelete());
    });
    \u0275\u0275text(18, "\u2715 Delete");
    \u0275\u0275elementEnd()();
    \u0275\u0275conditionalCreate(19, MomentumStrategyComponent_Conditional_12_Conditional_19_Template, 10, 1, "div", 27);
    \u0275\u0275elementStart(20, "div", 28)(21, "button", 25);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Template_button_click_21_listener() {
      \u0275\u0275restoreView(_r1);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.mode.set("simple"));
    });
    \u0275\u0275text(22, "Simple");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(23, "button", 25);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_12_Template_button_click_23_listener() {
      \u0275\u0275restoreView(_r1);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.mode.set("advanced"));
    });
    \u0275\u0275text(24, "Advanced");
    \u0275\u0275elementEnd()();
    \u0275\u0275conditionalCreate(25, MomentumStrategyComponent_Conditional_12_Conditional_25_Template, 140, 36, "div", 29);
    \u0275\u0275conditionalCreate(26, MomentumStrategyComponent_Conditional_12_Conditional_26_Template, 389, 82, "div", 29);
  }
  if (rf & 2) {
    const ctx_r2 = \u0275\u0275nextContext();
    \u0275\u0275conditional(ctx_r2.showBanner() ? 0 : -1);
    \u0275\u0275advance(6);
    \u0275\u0275property("ngModel", ctx_r2.activeKey());
    \u0275\u0275advance(2);
    \u0275\u0275repeater(ctx_r2.builtinProfiles());
    \u0275\u0275advance(2);
    \u0275\u0275conditional(ctx_r2.userProfiles().length > 0 ? 10 : -1);
    \u0275\u0275advance();
    \u0275\u0275conditional(ctx_r2.modified() ? 11 : -1);
    \u0275\u0275advance(2);
    \u0275\u0275property("disabled", ctx_r2.isBuiltin() || !ctx_r2.modified());
    \u0275\u0275advance(4);
    \u0275\u0275property("disabled", ctx_r2.isBuiltin());
    \u0275\u0275advance(2);
    \u0275\u0275conditional(ctx_r2.isBuiltin() ? 19 : -1);
    \u0275\u0275advance(2);
    \u0275\u0275classProp("active", ctx_r2.mode() === "simple");
    \u0275\u0275advance(2);
    \u0275\u0275classProp("active", ctx_r2.mode() === "advanced");
    \u0275\u0275advance(2);
    \u0275\u0275conditional(ctx_r2.mode() === "simple" ? 25 : -1);
    \u0275\u0275advance();
    \u0275\u0275conditional(ctx_r2.mode() === "advanced" ? 26 : -1);
  }
}
function MomentumStrategyComponent_Conditional_24_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "div", 13)(1, "span", 143);
    \u0275\u0275text(2, "\u2713");
    \u0275\u0275elementEnd();
    \u0275\u0275text(3);
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const ctx_r2 = \u0275\u0275nextContext();
    \u0275\u0275advance(3);
    \u0275\u0275textInterpolate1("", ctx_r2.toast(), " ");
  }
}
function MomentumStrategyComponent_Conditional_25_For_8_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "div");
    \u0275\u0275text(1);
    \u0275\u0275pipe(2, "json");
    \u0275\u0275elementStart(3, "span", 80);
    \u0275\u0275text(4, "\u2192");
    \u0275\u0275elementEnd();
    \u0275\u0275text(5);
    \u0275\u0275pipe(6, "json");
    \u0275\u0275elementEnd();
  }
  if (rf & 2) {
    const d_r38 = ctx.$implicit;
    \u0275\u0275advance();
    \u0275\u0275textInterpolate2("", d_r38.path, " \xA0 ", \u0275\u0275pipeBind1(2, 3, d_r38.old), " ");
    \u0275\u0275advance(4);
    \u0275\u0275textInterpolate1(" ", \u0275\u0275pipeBind1(6, 5, d_r38.new));
  }
}
function MomentumStrategyComponent_Conditional_25_Conditional_9_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "div");
    \u0275\u0275text(1, "No changes");
    \u0275\u0275elementEnd();
  }
}
function MomentumStrategyComponent_Conditional_25_Template(rf, ctx) {
  if (rf & 1) {
    const _r37 = \u0275\u0275getCurrentView();
    \u0275\u0275elementStart(0, "div", 144);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_25_Template_div_click_0_listener() {
      \u0275\u0275restoreView(_r37);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.showSaveModal.set(false));
    });
    \u0275\u0275elementStart(1, "div", 145);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_25_Template_div_click_1_listener($event) {
      \u0275\u0275restoreView(_r37);
      return \u0275\u0275resetView($event.stopPropagation());
    });
    \u0275\u0275elementStart(2, "h3");
    \u0275\u0275text(3);
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(4, "p");
    \u0275\u0275text(5, "This will replace the saved values for this favorite with your current tweaks. The previous values cannot be recovered.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(6, "div", 146);
    \u0275\u0275repeaterCreate(7, MomentumStrategyComponent_Conditional_25_For_8_Template, 7, 7, "div", null, _forTrack1);
    \u0275\u0275conditionalCreate(9, MomentumStrategyComponent_Conditional_25_Conditional_9_Template, 2, 0, "div");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(10, "div", 147)(11, "button", 25);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_25_Template_button_click_11_listener() {
      \u0275\u0275restoreView(_r37);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.showSaveModal.set(false));
    });
    \u0275\u0275text(12, "Cancel");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(13, "button", 148);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_25_Template_button_click_13_listener() {
      \u0275\u0275restoreView(_r37);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.confirmSave());
    });
    \u0275\u0275text(14);
    \u0275\u0275elementEnd()()()();
  }
  if (rf & 2) {
    const ctx_r2 = \u0275\u0275nextContext();
    \u0275\u0275advance(3);
    \u0275\u0275textInterpolate1('Update "', ctx_r2.profileName(), '"?');
    \u0275\u0275advance(4);
    \u0275\u0275repeater(ctx_r2.diffList());
    \u0275\u0275advance(2);
    \u0275\u0275conditional(ctx_r2.diffList().length === 0 ? 9 : -1);
    \u0275\u0275advance(4);
    \u0275\u0275property("disabled", ctx_r2.saving());
    \u0275\u0275advance();
    \u0275\u0275textInterpolate(ctx_r2.saving() ? "Saving\u2026" : "Update");
  }
}
function MomentumStrategyComponent_Conditional_26_Template(rf, ctx) {
  if (rf & 1) {
    const _r39 = \u0275\u0275getCurrentView();
    \u0275\u0275elementStart(0, "div", 144);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_26_Template_div_click_0_listener() {
      \u0275\u0275restoreView(_r39);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.showSaveAsModal.set(false));
    });
    \u0275\u0275elementStart(1, "div", 145);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_26_Template_div_click_1_listener($event) {
      \u0275\u0275restoreView(_r39);
      return \u0275\u0275resetView($event.stopPropagation());
    });
    \u0275\u0275elementStart(2, "h3");
    \u0275\u0275text(3, "Save current settings as a new favorite");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(4, "p");
    \u0275\u0275text(5, "Capture all settings as a named profile you can return to later.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(6, "label");
    \u0275\u0275text(7, "Name");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(8, "input", 149);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_26_Template_input_ngModelChange_8_listener($event) {
      \u0275\u0275restoreView(_r39);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.newProfileName.set($event));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(9, "label");
    \u0275\u0275text(10, "Description (optional)");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(11, "textarea", 150);
    \u0275\u0275listener("ngModelChange", function MomentumStrategyComponent_Conditional_26_Template_textarea_ngModelChange_11_listener($event) {
      \u0275\u0275restoreView(_r39);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.newProfileDescription.set($event));
    });
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(12, "div", 147)(13, "button", 25);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_26_Template_button_click_13_listener() {
      \u0275\u0275restoreView(_r39);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.showSaveAsModal.set(false));
    });
    \u0275\u0275text(14, "Cancel");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(15, "button", 148);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_26_Template_button_click_15_listener() {
      \u0275\u0275restoreView(_r39);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.confirmSaveAs());
    });
    \u0275\u0275text(16);
    \u0275\u0275elementEnd()()()();
  }
  if (rf & 2) {
    const ctx_r2 = \u0275\u0275nextContext();
    \u0275\u0275advance(8);
    \u0275\u0275property("ngModel", ctx_r2.newProfileName());
    \u0275\u0275advance(3);
    \u0275\u0275property("ngModel", ctx_r2.newProfileDescription());
    \u0275\u0275advance(4);
    \u0275\u0275property("disabled", ctx_r2.saving() || !ctx_r2.newProfileName().trim());
    \u0275\u0275advance();
    \u0275\u0275textInterpolate(ctx_r2.saving() ? "Saving\u2026" : "Save");
  }
}
function MomentumStrategyComponent_Conditional_27_Template(rf, ctx) {
  if (rf & 1) {
    const _r40 = \u0275\u0275getCurrentView();
    \u0275\u0275elementStart(0, "div", 144);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_27_Template_div_click_0_listener() {
      \u0275\u0275restoreView(_r40);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.showDeleteModal.set(false));
    });
    \u0275\u0275elementStart(1, "div", 145);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_27_Template_div_click_1_listener($event) {
      \u0275\u0275restoreView(_r40);
      return \u0275\u0275resetView($event.stopPropagation());
    });
    \u0275\u0275elementStart(2, "h3");
    \u0275\u0275text(3);
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(4, "p");
    \u0275\u0275text(5, `This action can't be undone. If you want to save the values somewhere else first, click Cancel and use "Save as new".`);
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(6, "div", 147)(7, "button", 25);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_27_Template_button_click_7_listener() {
      \u0275\u0275restoreView(_r40);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.showDeleteModal.set(false));
    });
    \u0275\u0275text(8, "Cancel");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(9, "button", 151);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_27_Template_button_click_9_listener() {
      \u0275\u0275restoreView(_r40);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.confirmDelete());
    });
    \u0275\u0275text(10, "Delete");
    \u0275\u0275elementEnd()()()();
  }
  if (rf & 2) {
    const ctx_r2 = \u0275\u0275nextContext();
    \u0275\u0275advance(3);
    \u0275\u0275textInterpolate1('Permanently delete "', ctx_r2.profileName(), '"?');
  }
}
function MomentumStrategyComponent_Conditional_28_For_14_Template(rf, ctx) {
  if (rf & 1) {
    \u0275\u0275elementStart(0, "div");
    \u0275\u0275text(1);
    \u0275\u0275elementStart(2, "span", 154);
    \u0275\u0275text(3);
    \u0275\u0275pipe(4, "json");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(5, "span", 80);
    \u0275\u0275text(6, "\u2192");
    \u0275\u0275elementEnd();
    \u0275\u0275text(7);
    \u0275\u0275pipe(8, "json");
    \u0275\u0275elementStart(9, "span", 155);
    \u0275\u0275text(10, "(saved)");
    \u0275\u0275elementEnd()();
  }
  if (rf & 2) {
    const d_r42 = ctx.$implicit;
    \u0275\u0275advance();
    \u0275\u0275textInterpolate1("", d_r42.path, " \xA0 ");
    \u0275\u0275advance(2);
    \u0275\u0275textInterpolate(\u0275\u0275pipeBind1(4, 3, d_r42.new));
    \u0275\u0275advance(4);
    \u0275\u0275textInterpolate1(" ", \u0275\u0275pipeBind1(8, 5, d_r42.old), " ");
  }
}
function MomentumStrategyComponent_Conditional_28_Template(rf, ctx) {
  if (rf & 1) {
    const _r41 = \u0275\u0275getCurrentView();
    \u0275\u0275elementStart(0, "div", 144);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_28_Template_div_click_0_listener() {
      \u0275\u0275restoreView(_r41);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.showRevertModal.set(false));
    });
    \u0275\u0275elementStart(1, "div", 145);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_28_Template_div_click_1_listener($event) {
      \u0275\u0275restoreView(_r41);
      return \u0275\u0275resetView($event.stopPropagation());
    });
    \u0275\u0275elementStart(2, "h3");
    \u0275\u0275text(3, "Revert all unsaved tweaks?");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(4, "p");
    \u0275\u0275text(5, "You'll go back to the last saved version of ");
    \u0275\u0275elementStart(6, "strong");
    \u0275\u0275text(7);
    \u0275\u0275elementEnd();
    \u0275\u0275text(8, ". This affects ");
    \u0275\u0275elementStart(9, "strong");
    \u0275\u0275text(10);
    \u0275\u0275elementEnd();
    \u0275\u0275text(11, " change(s) you haven't applied or saved yet.");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(12, "div", 146);
    \u0275\u0275repeaterCreate(13, MomentumStrategyComponent_Conditional_28_For_14_Template, 11, 7, "div", null, _forTrack1);
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(15, "p", 152);
    \u0275\u0275text(16, `Tweaks can't be recovered after revert. If you want to keep them, click Cancel and use "Save as new" first.`);
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(17, "div", 147)(18, "button", 25);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_28_Template_button_click_18_listener() {
      \u0275\u0275restoreView(_r41);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.showRevertModal.set(false));
    });
    \u0275\u0275text(19, "Cancel");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(20, "button", 153);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_28_Template_button_click_20_listener() {
      \u0275\u0275restoreView(_r41);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.confirmRevert());
    });
    \u0275\u0275text(21, "Revert");
    \u0275\u0275elementEnd()()()();
  }
  if (rf & 2) {
    const ctx_r2 = \u0275\u0275nextContext();
    \u0275\u0275advance(7);
    \u0275\u0275textInterpolate(ctx_r2.profileName());
    \u0275\u0275advance(3);
    \u0275\u0275textInterpolate(ctx_r2.changeCount());
    \u0275\u0275advance(3);
    \u0275\u0275repeater(ctx_r2.diffList());
  }
}
function MomentumStrategyComponent_Conditional_29_Template(rf, ctx) {
  if (rf & 1) {
    const _r43 = \u0275\u0275getCurrentView();
    \u0275\u0275elementStart(0, "div", 144);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_29_Template_div_click_0_listener() {
      \u0275\u0275restoreView(_r43);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.cancelDiscard());
    });
    \u0275\u0275elementStart(1, "div", 145);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_29_Template_div_click_1_listener($event) {
      \u0275\u0275restoreView(_r43);
      return \u0275\u0275resetView($event.stopPropagation());
    });
    \u0275\u0275elementStart(2, "h3");
    \u0275\u0275text(3, "Discard unsaved changes?");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(4, "p");
    \u0275\u0275text(5, "You have modified ");
    \u0275\u0275elementStart(6, "strong");
    \u0275\u0275text(7);
    \u0275\u0275elementEnd();
    \u0275\u0275text(8);
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(9, "div", 147)(10, "button", 25);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_29_Template_button_click_10_listener() {
      \u0275\u0275restoreView(_r43);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.cancelDiscard());
    });
    \u0275\u0275text(11, "Keep editing");
    \u0275\u0275elementEnd();
    \u0275\u0275elementStart(12, "button", 151);
    \u0275\u0275listener("click", function MomentumStrategyComponent_Conditional_29_Template_button_click_12_listener() {
      \u0275\u0275restoreView(_r43);
      const ctx_r2 = \u0275\u0275nextContext();
      return \u0275\u0275resetView(ctx_r2.confirmDiscard());
    });
    \u0275\u0275text(13, "Discard");
    \u0275\u0275elementEnd()()()();
  }
  if (rf & 2) {
    const ctx_r2 = \u0275\u0275nextContext();
    \u0275\u0275advance(7);
    \u0275\u0275textInterpolate(ctx_r2.profileName());
    \u0275\u0275advance();
    \u0275\u0275textInterpolate2(" (", ctx_r2.changeCount(), " change", ctx_r2.changeCount() !== 1 ? "s" : "", "). These tweaks haven't been saved or applied yet.");
  }
}
var RISK_LEVELS = [
  {
    label: "Very Conservative",
    adx_min: 30,
    rsi_min: 55,
    rsi_max: 60,
    ath_dist_max: -15,
    chg3h_atr_max: 2,
    chg3h_atr_min: -2
  },
  {
    label: "Conservative",
    adx_min: 27,
    rsi_min: 52,
    rsi_max: 62,
    ath_dist_max: -12,
    chg3h_atr_max: 2.5,
    chg3h_atr_min: -2.5
  },
  {
    label: "Balanced",
    adx_min: 25,
    rsi_min: 50,
    rsi_max: 65,
    ath_dist_max: -10,
    chg3h_atr_max: 3,
    chg3h_atr_min: -3
  },
  {
    label: "Aggressive",
    adx_min: 22,
    rsi_min: 48,
    rsi_max: 70,
    ath_dist_max: -8,
    chg3h_atr_max: 3.5,
    chg3h_atr_min: -3.5
  },
  {
    label: "Very Aggressive",
    adx_min: 20,
    rsi_min: 45,
    rsi_max: 72,
    ath_dist_max: -7,
    chg3h_atr_max: 4,
    chg3h_atr_min: -4
  }
];
var PROFIT_LEVELS = [
  {
    label: "Very Quick",
    progressive: [[2, 0.5], [5, 1], [7, 0.5], [10, 0.3]]
  },
  {
    label: "Quick",
    progressive: [[2, 0.7], [5, 1.5], [7, 0.7], [10, 0.4]]
  },
  {
    label: "Balanced",
    progressive: [[2, 1], [6, 2], [8, 1], [12, 0.5]]
  },
  {
    label: "Let it run",
    progressive: [[2, 1.5], [7, 2.5], [10, 1.5], [15, 1]]
  },
  {
    label: "Patient",
    progressive: [[2, 2], [8, 3], [12, 2], [18, 1.5]]
  }
];
var DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
var MomentumStrategyComponent = class _MomentumStrategyComponent {
  api = inject(ApiService);
  // ── Core state ──────────────────────────────────────────────────────────
  profilesData = signal(null, ...ngDevMode ? [{ debugName: "profilesData" }] : []);
  activeKey = signal("builtin::recommended", ...ngDevMode ? [{ debugName: "activeKey" }] : []);
  currentValues = signal({}, ...ngDevMode ? [{ debugName: "currentValues" }] : []);
  savedValues = signal({}, ...ngDevMode ? [{ debugName: "savedValues" }] : []);
  changelog = signal({}, ...ngDevMode ? [{ debugName: "changelog" }] : []);
  activeStrategyMeta = signal(null, ...ngDevMode ? [{ debugName: "activeStrategyMeta" }] : []);
  modified = computed(() => JSON.stringify(this.currentValues()) !== JSON.stringify(this.savedValues()), ...ngDevMode ? [{ debugName: "modified" }] : []);
  mode = signal("simple", ...ngDevMode ? [{ debugName: "mode" }] : []);
  // ── UI flags ────────────────────────────────────────────────────────────
  loading = signal(true, ...ngDevMode ? [{ debugName: "loading" }] : []);
  applying = signal(false, ...ngDevMode ? [{ debugName: "applying" }] : []);
  saving = signal(false, ...ngDevMode ? [{ debugName: "saving" }] : []);
  toast = signal(null, ...ngDevMode ? [{ debugName: "toast" }] : []);
  showUpgradeBanner = signal(false, ...ngDevMode ? [{ debugName: "showUpgradeBanner" }] : []);
  showSaveModal = signal(false, ...ngDevMode ? [{ debugName: "showSaveModal" }] : []);
  showSaveAsModal = signal(false, ...ngDevMode ? [{ debugName: "showSaveAsModal" }] : []);
  showDeleteModal = signal(false, ...ngDevMode ? [{ debugName: "showDeleteModal" }] : []);
  showRevertModal = signal(false, ...ngDevMode ? [{ debugName: "showRevertModal" }] : []);
  showDiscardModal = signal(false, ...ngDevMode ? [{ debugName: "showDiscardModal" }] : []);
  showRiskTable = signal(false, ...ngDevMode ? [{ debugName: "showRiskTable" }] : []);
  showProfitTable = signal(false, ...ngDevMode ? [{ debugName: "showProfitTable" }] : []);
  // Save-as modal fields
  newProfileName = signal("", ...ngDevMode ? [{ debugName: "newProfileName" }] : []);
  newProfileDescription = signal("", ...ngDevMode ? [{ debugName: "newProfileDescription" }] : []);
  // Pending navigation callback (for discard flow)
  _pendingDiscard = null;
  // ── Lookups ──────────────────────────────────────────────────────────────
  riskLevels = RISK_LEVELS;
  profitLevels = PROFIT_LEVELS;
  days = DAYS;
  // ── Computed helpers ────────────────────────────────────────────────────
  isBuiltin = computed(() => this.activeKey().startsWith("builtin::"), ...ngDevMode ? [{ debugName: "isBuiltin" }] : []);
  profileName = computed(() => {
    const key = this.activeKey();
    if (key === "builtin::recommended")
      return "Recommended";
    if (key === "builtin::conservative")
      return "Conservative";
    if (key === "builtin::aggressive")
      return "Aggressive";
    return key.replace("user::", "");
  }, ...ngDevMode ? [{ debugName: "profileName" }] : []);
  builtinProfiles = computed(() => {
    const d = this.profilesData();
    if (!d)
      return [];
    return Object.entries(d.built_in || {}).map(([k, v]) => ({
      key: `builtin::${k}`,
      label: v.name || k
    }));
  }, ...ngDevMode ? [{ debugName: "builtinProfiles" }] : []);
  userProfiles = computed(() => {
    const d = this.profilesData();
    if (!d)
      return [];
    return Object.entries(d.user || {}).map(([k, v]) => ({
      key: `user::${k}`,
      label: k
    }));
  }, ...ngDevMode ? [{ debugName: "userProfiles" }] : []);
  diffList = computed(() => {
    const cur = this.currentValues();
    const saved = this.savedValues();
    const diffs = [];
    this._flatDiff("", cur, saved, diffs);
    return diffs;
  }, ...ngDevMode ? [{ debugName: "diffList" }] : []);
  changeCount = computed(() => this.diffList().length, ...ngDevMode ? [{ debugName: "changeCount" }] : []);
  showBanner = computed(() => {
    const d = this.profilesData();
    const meta = this.activeStrategyMeta();
    if (!d || !meta)
      return false;
    if (this.activeKey() !== "builtin::recommended")
      return false;
    const applied = d.applied_recommended_version;
    const latest = d.latest_recommended_version;
    return applied && latest && applied !== latest;
  }, ...ngDevMode ? [{ debugName: "showBanner" }] : []);
  // ── Simple slider computed values ────────────────────────────────────────
  riskSliderValue = computed(() => {
    const cv = this.currentValues();
    if (!cv?.entry_gates)
      return 3;
    return this._detectRiskLevel(cv.entry_gates);
  }, ...ngDevMode ? [{ debugName: "riskSliderValue" }] : []);
  profitSliderValue = computed(() => {
    const cv = this.currentValues();
    if (!cv?.trail?.progressive)
      return 3;
    return this._detectProfitLevel(cv.trail.progressive);
  }, ...ngDevMode ? [{ debugName: "profitSliderValue" }] : []);
  riskLevelLabel = computed(() => RISK_LEVELS[this.riskSliderValue() - 1]?.label ?? "Custom", ...ngDevMode ? [{ debugName: "riskLevelLabel" }] : []);
  profitLevelLabel = computed(() => PROFIT_LEVELS[this.profitSliderValue() - 1]?.label ?? "Custom", ...ngDevMode ? [{ debugName: "profitLevelLabel" }] : []);
  // ── Lifecycle ────────────────────────────────────────────────────────────
  ngOnInit() {
    this.loadAll();
  }
  loadAll() {
    this.loading.set(true);
    this.api.getStrategyProfiles().subscribe({
      next: (data) => {
        this.profilesData.set(data);
        const activeKey = data.active || "builtin::recommended";
        this.activeKey.set(activeKey);
        this.loadProfile(activeKey);
      },
      error: () => {
        this.loading.set(false);
      }
    });
    this.api.getStrategyChangelog().subscribe({
      next: (cl) => this.changelog.set(cl)
    });
    this.api.getActiveStrategy().subscribe({
      next: (meta) => this.activeStrategyMeta.set(meta)
    });
  }
  loadProfile(key) {
    this.api.getStrategyProfile(key).subscribe({
      next: (values) => {
        const clone = JSON.parse(JSON.stringify(values));
        this.currentValues.set(clone);
        this.savedValues.set(JSON.parse(JSON.stringify(values)));
        this.loading.set(false);
      },
      error: () => {
        this.loading.set(false);
      }
    });
  }
  // ── Profile switching ────────────────────────────────────────────────────
  onProfileChange(newKey) {
    if (this.modified()) {
      this._pendingDiscard = () => this._switchProfile(newKey);
      this.showDiscardModal.set(true);
    } else {
      this._switchProfile(newKey);
    }
  }
  _switchProfile(key) {
    this.activeKey.set(key);
    this.loadProfile(key);
  }
  // ── Simple view mutations ────────────────────────────────────────────────
  setRiskLevel(idx) {
    const level = RISK_LEVELS[idx - 1];
    if (!level)
      return;
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.entry_gates)
      cv.entry_gates = {};
    cv.entry_gates.adx_min = level.adx_min;
    cv.entry_gates.rsi_min = level.rsi_min;
    cv.entry_gates.rsi_max = level.rsi_max;
    cv.entry_gates.ath_dist_max = level.ath_dist_max;
    cv.entry_gates.chg3h_atr_max = level.chg3h_atr_max;
    cv.entry_gates.chg3h_atr_min = level.chg3h_atr_min;
    this.currentValues.set(cv);
  }
  setProfitLevel(idx) {
    const level = PROFIT_LEVELS[idx - 1];
    if (!level)
      return;
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.trail)
      cv.trail = {};
    cv.trail.progressive = level.progressive;
    this.currentValues.set(cv);
  }
  setMaxHold(val) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.exits)
      cv.exits = {};
    cv.exits.max_hold_hours = Number(val);
    this.currentValues.set(cv);
  }
  setAllocation(val) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.position)
      cv.position = {};
    cv.position.allocation_usd = Number(val);
    this.currentValues.set(cv);
  }
  toggleDay(dayIndex) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.entry_pause)
      cv.entry_pause = { enabled: true, weekday_block: [] };
    const block = cv.entry_pause.weekday_block || [];
    const pos = block.indexOf(dayIndex);
    if (pos >= 0)
      block.splice(pos, 1);
    else
      block.push(dayIndex);
    cv.entry_pause.weekday_block = block;
    this.currentValues.set(cv);
  }
  isDayBlocked(dayIndex) {
    const cv = this.currentValues();
    return (cv?.entry_pause?.weekday_block || []).includes(dayIndex);
  }
  setWallAware(enabled) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.wall_aware)
      cv.wall_aware = {};
    cv.wall_aware.enabled = enabled;
    this.currentValues.set(cv);
  }
  // ── Blacklist / chips ────────────────────────────────────────────────────
  blacklistInput = "";
  getBlacklist() {
    return this.currentValues()?.universe?.blacklist || [];
  }
  addChip(pair) {
    const trimmed = pair.trim().toUpperCase();
    if (!trimmed)
      return;
    if (!trimmed.endsWith("-USD")) {
    }
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.universe)
      cv.universe = { min_price: 0.01, blacklist: [] };
    if (!cv.universe.blacklist.includes(trimmed)) {
      cv.universe.blacklist.push(trimmed);
    }
    this.currentValues.set(cv);
    this.blacklistInput = "";
  }
  removeChip(pair) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (cv.universe?.blacklist) {
      cv.universe.blacklist = cv.universe.blacklist.filter((p) => p !== pair);
    }
    this.currentValues.set(cv);
  }
  onChipKeydown(event) {
    if (event.key === "Enter") {
      this.addChip(this.blacklistInput);
    }
  }
  // ── Advanced field mutations (generic deep-set) ──────────────────────────
  setField(section, key, value) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv[section])
      cv[section] = {};
    cv[section][key] = Number(value);
    this.currentValues.set(cv);
  }
  getField(section, key) {
    return this.currentValues()?.[section]?.[key] ?? "";
  }
  // ── Trail tier editing ───────────────────────────────────────────────────
  getTiers() {
    return this.currentValues()?.trail?.progressive || [];
  }
  setTierValue(tierIdx, colIdx, value) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.trail?.progressive)
      return;
    cv.trail.progressive[tierIdx][colIdx] = Number(value);
    this.currentValues.set(cv);
  }
  addTier() {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    if (!cv.trail)
      cv.trail = {};
    if (!cv.trail.progressive)
      cv.trail.progressive = [];
    cv.trail.progressive.push([0, 0]);
    this.currentValues.set(cv);
  }
  removeTier(idx) {
    const cv = JSON.parse(JSON.stringify(this.currentValues()));
    cv.trail.progressive.splice(idx, 1);
    this.currentValues.set(cv);
  }
  // ── Reset section (restore section from savedValues) ─────────────────────
  resetSection(section) {
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
    if (!this.modified() || this.applying())
      return;
    this.applying.set(true);
    this.api.applyStrategy({ profile_key: this.activeKey(), values: this.currentValues() }).subscribe({
      next: () => {
        this.savedValues.set(JSON.parse(JSON.stringify(this.currentValues())));
        this.applying.set(false);
        this._showToast("Applied \u2014 bot reloaded");
        this.api.getStrategyProfiles().subscribe((d) => this.profilesData.set(d));
        this.api.getActiveStrategy().subscribe((m) => this.activeStrategyMeta.set(m));
      },
      error: (e) => {
        this.applying.set(false);
        this._showToast("Apply failed: " + (e?.error?.message || "unknown error"));
      }
    });
  }
  // ── Save (overwrite user profile) ────────────────────────────────────────
  openSave() {
    this.showSaveModal.set(true);
  }
  confirmSave() {
    const name = this.activeKey().replace("user::", "");
    this.saving.set(true);
    this.api.updateStrategyProfile(name, { values: this.currentValues(), description: "" }).subscribe({
      next: () => {
        this.savedValues.set(JSON.parse(JSON.stringify(this.currentValues())));
        this.showSaveModal.set(false);
        this.saving.set(false);
        this._showToast("Saved");
        this.api.getStrategyProfiles().subscribe((d) => this.profilesData.set(d));
      },
      error: (e) => {
        this.saving.set(false);
        this._showToast("Save failed: " + (e?.error?.message || "unknown error"));
      }
    });
  }
  // ── Save as new ───────────────────────────────────────────────────────────
  openSaveAs(prefill) {
    this.newProfileName.set(prefill || `My ${this.profileName()} (custom)`);
    this.newProfileDescription.set("");
    this.showSaveAsModal.set(true);
  }
  confirmSaveAs() {
    const name = this.newProfileName().trim();
    if (!name)
      return;
    this.saving.set(true);
    this.api.saveStrategyProfile({
      name,
      description: this.newProfileDescription(),
      values: this.currentValues()
    }).subscribe({
      next: () => {
        this.showSaveAsModal.set(false);
        this.saving.set(false);
        this._showToast('Saved as "' + name + '"');
        const newKey = `user::${name}`;
        this.api.getStrategyProfiles().subscribe((d) => {
          this.profilesData.set(d);
          this.activeKey.set(newKey);
          this.savedValues.set(JSON.parse(JSON.stringify(this.currentValues())));
        });
      },
      error: (e) => {
        this.saving.set(false);
        this._showToast("Save failed: " + (e?.error?.message || "unknown error"));
      }
    });
  }
  // ── Delete ────────────────────────────────────────────────────────────────
  openDelete() {
    this.showDeleteModal.set(true);
  }
  confirmDelete() {
    const name = this.activeKey().replace("user::", "");
    this.api.deleteStrategyProfile(name).subscribe({
      next: () => {
        this.showDeleteModal.set(false);
        this._showToast('Deleted "' + name + '"');
        this.api.getStrategyProfiles().subscribe((d) => {
          this.profilesData.set(d);
          const fallback = d.active || "builtin::recommended";
          this.activeKey.set(fallback);
          this.loadProfile(fallback);
        });
      },
      error: (e) => {
        this._showToast("Delete failed: " + (e?.error?.message || "unknown error"));
      }
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
    if (!cl || !d)
      return [];
    const latest = d.latest_recommended_version;
    return cl[latest] || [];
  }, ...ngDevMode ? [{ debugName: "changelogEntries" }] : []);
  rollback() {
    const d = this.profilesData();
    if (!d)
      return;
    const oldVersion = d.applied_recommended_version;
    this._showToast(`Rollback to v${oldVersion} initiated`);
    this.api.getStrategyProfile("builtin::recommended").subscribe((v) => {
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
  _showToast(msg) {
    this.toast.set(msg);
    setTimeout(() => this.toast.set(null), 3500);
  }
  _flatDiff(prefix, cur, saved, out) {
    if (cur === null || typeof cur !== "object" || Array.isArray(cur)) {
      const curStr = JSON.stringify(cur);
      const savedStr = JSON.stringify(saved);
      if (curStr !== savedStr) {
        out.push({ path: prefix, old: saved, new: cur });
      }
      return;
    }
    const keys = /* @__PURE__ */ new Set([...Object.keys(cur || {}), ...Object.keys(saved || {})]);
    keys.forEach((k) => {
      this._flatDiff(prefix ? `${prefix}.${k}` : k, cur?.[k], saved?.[k], out);
    });
  }
  _detectRiskLevel(eg) {
    const adx = eg?.adx_min;
    for (let i = 0; i < RISK_LEVELS.length; i++) {
      if (RISK_LEVELS[i].adx_min === adx)
        return i + 1;
    }
    return 3;
  }
  _detectProfitLevel(progressive) {
    if (!progressive || progressive.length === 0)
      return 3;
    const str = JSON.stringify(progressive);
    for (let i = 0; i < PROFIT_LEVELS.length; i++) {
      if (JSON.stringify(PROFIT_LEVELS[i].progressive) === str)
        return i + 1;
    }
    return 3;
  }
  // Expose tables to template
  riskTable = [
    { label: "ADX min", values: [30, 27, 25, 22, 20] },
    { label: "RSI min (uptrend)", values: [55, 52, 50, 48, 45] },
    { label: "RSI max (overbought)", values: [60, 62, 65, 70, 72] },
    { label: "ATH proximity gate", values: ["-15%", "-12%", "-10%", "-8%", "-7%"] },
    { label: "3h overpump (\xD7 ATR)", values: [2, 2.5, 3, 3.5, 4] },
    { label: "3h crash (\xD7 ATR)", values: [-2, -2.5, -3, -3.5, -4] }
  ];
  profitTable = [
    { label: "Tier 1 (small move)", values: ["2% \u2192 0.5%", "2% \u2192 0.7%", "2% \u2192 1.0%", "2% \u2192 1.5%", "2% \u2192 2.0%"] },
    { label: "Tier 2 (mid move)", values: ["5% \u2192 1.0%", "5% \u2192 1.5%", "6% \u2192 2.0%", "7% \u2192 2.5%", "8% \u2192 3.0%"] },
    { label: "Tier 3 (strong move)", values: ["7% \u2192 0.5%", "7% \u2192 0.7%", "8% \u2192 1.0%", "10% \u2192 1.5%", "12% \u2192 2.0%"] },
    { label: "Tier 4 (runner)", values: ["10% \u2192 0.3%", "10% \u2192 0.4%", "12% \u2192 0.5%", "15% \u2192 1.0%", "18% \u2192 1.5%"] }
  ];
  riskColHeaders = ["Very Cons.", "Conservative", "Balanced", "Aggressive", "Very Aggro."];
  profitColHeaders = ["Very Quick", "Quick", "Balanced", "Let it run", "Patient"];
  static \u0275fac = function MomentumStrategyComponent_Factory(__ngFactoryType__) {
    return new (__ngFactoryType__ || _MomentumStrategyComponent)();
  };
  static \u0275cmp = /* @__PURE__ */ \u0275\u0275defineComponent({ type: _MomentumStrategyComponent, selectors: [["app-momentum-strategy"]], decls: 30, vars: 10, consts: [[1, "page-shell"], [1, "topbar"], [1, "accent"], [1, "meta"], [1, "close-btn", 3, "click"], [1, "loading-state"], [1, "footer"], [1, "footer-inner"], [1, "status-pill"], [1, "dot"], [1, "actions"], [1, "cancel", 3, "click"], [1, "apply", 3, "click", "disabled"], [1, "toast"], [1, "modal-backdrop"], [1, "upgrade"], [1, "profile-bar"], [1, "bar-label"], [1, "profile-row"], [3, "ngModelChange", "ngModel"], ["label", "Built-in (bot-curated, read-only)"], [3, "value"], ["label", "Your favorites (editable)"], [1, "spacer"], [3, "click", "disabled"], [3, "click"], [1, "danger", 3, "click", "disabled"], [1, "lock-banner"], [1, "tabs"], [3, "read-only"], [1, "upgrade-head"], [1, "title"], [1, "lamp"], [1, "meta-inline"], [1, "toggle", 3, "click"], [1, "upgrade-body"], [1, "upgrade-changes"], [1, "upgrade-change"], [1, "upgrade-cta"], [1, "body"], [1, "label"], [1, "why"], [1, "delta"], [1, "modified-tag"], ["title", "Discard all unsaved tweaks", 1, "revert-btn", 3, "click"], [1, "count"], [1, "icon"], [1, "panel"], [1, "num"], [1, "help"], [1, "stepped-slider"], ["type", "range", "min", "1", "max", "5", 3, "input", "value"], [1, "ticks"], [3, "active"], [1, "preset-readout"], [1, "readout-head"], [1, "toggle-table", 3, "click"], [1, "values"], [1, "kv"], [1, "k"], [1, "v"], [1, "compare-table"], [1, "field-control"], [1, "field-head"], [1, "name"], [1, "value-display"], ["type", "range", "min", "500", "max", "5000", "step", "250", 3, "input", "value"], ["type", "number", "min", "500", "max", "5000", "step", "250", 3, "ngModelChange", "ngModel"], [1, "chip-input"], [1, "chip"], ["type", "text", "placeholder", "add pair (press Enter)\u2026", 3, "ngModelChange", "keydown", "ngModel", "disabled"], [1, "day-buttons"], [3, "active", "disabled"], [1, "toggle-switch"], ["type", "checkbox", 3, "change", "checked", "disabled"], [1, "track"], [1, "toggle-label"], [3, "col-active"], ["open", "", 1, "adv"], [1, "left"], [1, "arrow"], [1, "sub-count"], [1, "reset", 3, "click"], [1, "adv-body"], [1, "field"], ["title", "Average Directional Index \u2014 minimum trend strength", 1, "help-icon"], [1, "field-help"], ["type", "range", "min", "0", "max", "50", 3, "input", "value"], ["type", "number", "min", "0", "max", "50", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "30", "max", "70", 3, "input", "value"], ["type", "number", "min", "30", "max", "70", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "50", "max", "90", 3, "input", "value"], ["type", "number", "min", "50", "max", "90", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "-30", "max", "-3", 3, "input", "value"], ["type", "number", "min", "-30", "max", "-3", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "1", "max", "6", "step", "0.1", 3, "input", "value"], ["type", "number", "min", "1", "max", "6", "step", "0.1", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "-6", "max", "-1", "step", "0.1", 3, "input", "value"], ["type", "number", "min", "-6", "max", "-1", "step", "0.1", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "0", "max", "6", 3, "input", "value"], ["type", "number", "min", "0", "max", "6", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "0", "max", "1", "step", "0.05", 3, "input", "value"], ["type", "number", "min", "0", "max", "1", "step", "0.05", 3, "ngModelChange", "ngModel"], [1, "adv"], [1, "tier-row", "tier-header"], [1, "tier-label"], [1, "tier-col-head"], [1, "tier-row"], [1, "add-tier-row"], [1, "add-tier-btn", 3, "click"], [1, "field", 2, "border-top", "1px solid var(--border)", "padding-top", "14px", "margin-top", "8px"], ["type", "range", "min", "1", "max", "15", "step", "0.5", 3, "input", "value"], ["type", "number", "min", "1", "max", "15", "step", "0.5", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "5", "max", "120", 3, "input", "value"], ["type", "number", "min", "5", "max", "120", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "6", "max", "168", 3, "input", "value"], ["type", "number", "min", "6", "max", "168", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "0", "max", "20", "step", "0.5", 3, "input", "value"], ["type", "number", "min", "0", "max", "20", "step", "0.5", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "0", "max", "24", 3, "input", "value"], ["type", "number", "min", "0", "max", "24", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "5", "max", "30", "step", "0.5", 3, "input", "value"], ["type", "number", "min", "5", "max", "30", "step", "0.5", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "0", "max", "168", 3, "input", "value"], ["type", "number", "min", "0", "max", "168", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "0", "max", "336", 3, "input", "value"], ["type", "number", "min", "0", "max", "336", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "0", "max", "48", "step", "0.5", 3, "input", "value"], ["type", "number", "min", "0", "max", "48", "step", "0.5", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "100", "max", "1000", "step", "50", 3, "input", "value"], ["type", "number", "min", "100", "max", "1000", "step", "50", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "0", "max", "15", "step", "0.5", 3, "input", "value"], ["type", "number", "min", "0", "max", "15", "step", "0.5", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "500", "max", "20000", "step", "250", 3, "input", "value"], ["type", "number", "min", "500", "max", "20000", "step", "250", 3, "ngModelChange", "ngModel"], ["type", "number", "min", "1", "max", "5", 3, "ngModelChange", "ngModel"], ["type", "range", "min", "24", "max", "336", 3, "input", "value"], ["type", "number", "min", "24", "max", "336", 3, "ngModelChange", "ngModel"], ["type", "number", "min", "0", "max", "1", "step", "0.001", 3, "ngModelChange", "ngModel"], [1, "value-display", "neg"], ["type", "number", "step", "0.5", 3, "input", "value"], ["type", "number", "step", "0.1", 3, "input", "value"], [1, "x", 3, "click"], [1, "icon", "ok"], [1, "modal-backdrop", 3, "click"], [1, "modal", 3, "click"], [1, "diff-list"], [1, "modal-actions"], [1, "primary", 3, "click", "disabled"], ["type", "text", "placeholder", "e.g. My aggressive tweak", "autofocus", "", 3, "ngModelChange", "ngModel"], ["placeholder", "Notes about what this profile is for\u2026", 3, "ngModelChange", "ngModel"], [1, "danger", 3, "click"], [1, "small-note"], [1, "primary", 3, "click"], [2, "color", "var(--accent)"], [1, "saved-label"]], template: function MomentumStrategyComponent_Template(rf, ctx) {
    if (rf & 1) {
      \u0275\u0275elementStart(0, "div", 0)(1, "div", 1)(2, "div")(3, "h1")(4, "span", 2);
      \u0275\u0275text(5, "\u2699");
      \u0275\u0275elementEnd();
      \u0275\u0275text(6, "Momentum Strategy Settings");
      \u0275\u0275elementEnd();
      \u0275\u0275elementStart(7, "div", 3);
      \u0275\u0275text(8, "Hot reload \u2014 changes apply within 1\u20132s, no bot restart");
      \u0275\u0275elementEnd()();
      \u0275\u0275elementStart(9, "button", 4);
      \u0275\u0275listener("click", function MomentumStrategyComponent_Template_button_click_9_listener() {
        return ctx.backToDashboard();
      });
      \u0275\u0275text(10, "\u2190 Back to Dashboard");
      \u0275\u0275elementEnd()();
      \u0275\u0275conditionalCreate(11, MomentumStrategyComponent_Conditional_11_Template, 2, 0, "div", 5)(12, MomentumStrategyComponent_Conditional_12_Template, 27, 13);
      \u0275\u0275elementEnd();
      \u0275\u0275elementStart(13, "div", 6)(14, "div", 7)(15, "div", 8);
      \u0275\u0275element(16, "span", 9);
      \u0275\u0275elementStart(17, "span");
      \u0275\u0275text(18);
      \u0275\u0275elementEnd()();
      \u0275\u0275elementStart(19, "div", 10)(20, "button", 11);
      \u0275\u0275listener("click", function MomentumStrategyComponent_Template_button_click_20_listener() {
        return ctx.backToDashboard();
      });
      \u0275\u0275text(21, "Cancel");
      \u0275\u0275elementEnd();
      \u0275\u0275elementStart(22, "button", 12);
      \u0275\u0275listener("click", function MomentumStrategyComponent_Template_button_click_22_listener() {
        return ctx.applyChanges();
      });
      \u0275\u0275text(23);
      \u0275\u0275elementEnd()()()();
      \u0275\u0275conditionalCreate(24, MomentumStrategyComponent_Conditional_24_Template, 4, 1, "div", 13);
      \u0275\u0275conditionalCreate(25, MomentumStrategyComponent_Conditional_25_Template, 15, 4, "div", 14);
      \u0275\u0275conditionalCreate(26, MomentumStrategyComponent_Conditional_26_Template, 17, 4, "div", 14);
      \u0275\u0275conditionalCreate(27, MomentumStrategyComponent_Conditional_27_Template, 11, 1, "div", 14);
      \u0275\u0275conditionalCreate(28, MomentumStrategyComponent_Conditional_28_Template, 22, 2, "div", 14);
      \u0275\u0275conditionalCreate(29, MomentumStrategyComponent_Conditional_29_Template, 14, 3, "div", 14);
    }
    if (rf & 2) {
      let tmp_1_0;
      \u0275\u0275advance(11);
      \u0275\u0275conditional(ctx.loading() ? 11 : 12);
      \u0275\u0275advance(7);
      \u0275\u0275textInterpolate(((tmp_1_0 = ctx.activeStrategyMeta()) == null ? null : tmp_1_0.active) ? "Active: " + (((tmp_1_0 = ctx.activeStrategyMeta()) == null ? null : tmp_1_0.active) || "") : "Strategy loaded");
      \u0275\u0275advance(4);
      \u0275\u0275property("disabled", !ctx.modified() || ctx.applying());
      \u0275\u0275advance();
      \u0275\u0275textInterpolate1(" ", ctx.applying() ? "Applying\u2026" : "Apply changes", " ");
      \u0275\u0275advance();
      \u0275\u0275conditional(ctx.toast() ? 24 : -1);
      \u0275\u0275advance();
      \u0275\u0275conditional(ctx.showSaveModal() ? 25 : -1);
      \u0275\u0275advance();
      \u0275\u0275conditional(ctx.showSaveAsModal() ? 26 : -1);
      \u0275\u0275advance();
      \u0275\u0275conditional(ctx.showDeleteModal() ? 27 : -1);
      \u0275\u0275advance();
      \u0275\u0275conditional(ctx.showRevertModal() ? 28 : -1);
      \u0275\u0275advance();
      \u0275\u0275conditional(ctx.showDiscardModal() ? 29 : -1);
    }
  }, dependencies: [CommonModule, FormsModule, NgSelectOption, \u0275NgSelectMultipleOption, DefaultValueAccessor, NumberValueAccessor, SelectControlValueAccessor, NgControlStatus, MinValidator, MaxValidator, NgModel, JsonPipe, DecimalPipe], styles: ['\n\n[_nghost-%COMP%] {\n  --bg: #0f1117;\n  --panel: rgba(255,255,255,0.03);\n  --panel-2: rgba(255,255,255,0.05);\n  --border: rgba(255,255,255,0.08);\n  --border-strong: rgba(255,255,255,0.16);\n  --text: #e2e8f0;\n  --subtext: #94a3b8;\n  --muted: #64748b;\n  --accent: #38bdf8;\n  --pos: #4ade80;\n  --neg: #f87171;\n  --warn: #f59e0b;\n  --upgrade: rgba(56,189,248,0.13);\n  --upgrade-border: rgba(56,189,248,0.45);\n  display: block;\n  background: #0f1117;\n  color: #e2e8f0;\n  font-family:\n    -apple-system,\n    BlinkMacSystemFont,\n    "Segoe UI",\n    Roboto,\n    Oxygen,\n    Ubuntu,\n    sans-serif;\n  font-size: 14px;\n  line-height: 1.5;\n  min-height: 100vh;\n}\n*[_ngcontent-%COMP%] {\n  box-sizing: border-box;\n}\na[_ngcontent-%COMP%] {\n  color: var(--accent);\n  text-decoration: none;\n}\n.page-shell[_ngcontent-%COMP%] {\n  max-width: 1100px;\n  margin: 0 auto;\n  padding: 24px;\n  padding-bottom: 120px;\n}\n.loading-state[_ngcontent-%COMP%] {\n  color: var(--subtext);\n  text-align: center;\n  padding: 60px 0;\n}\n.topbar[_ngcontent-%COMP%] {\n  display: flex;\n  justify-content: space-between;\n  align-items: center;\n  padding-bottom: 18px;\n  border-bottom: 1px solid var(--border);\n  margin-bottom: 24px;\n}\n.topbar[_ngcontent-%COMP%]   h1[_ngcontent-%COMP%] {\n  font-size: 20px;\n  font-weight: 700;\n  margin: 0;\n}\n.topbar[_ngcontent-%COMP%]   h1[_ngcontent-%COMP%]   .accent[_ngcontent-%COMP%] {\n  color: var(--accent);\n  margin-right: 8px;\n}\n.topbar[_ngcontent-%COMP%]   .meta[_ngcontent-%COMP%] {\n  font-size: 12px;\n  color: var(--subtext);\n  margin-top: 2px;\n}\n.close-btn[_ngcontent-%COMP%] {\n  background: none;\n  border: 1px solid var(--border-strong);\n  color: var(--text);\n  padding: 6px 14px;\n  border-radius: 6px;\n  font-size: 12px;\n  cursor: pointer;\n}\n.close-btn[_ngcontent-%COMP%]:hover {\n  background: rgba(255, 255, 255, 0.05);\n}\n.upgrade[_ngcontent-%COMP%] {\n  background: var(--upgrade);\n  border: 1px solid var(--upgrade-border);\n  border-radius: 10px;\n  padding: 16px 18px;\n  margin-bottom: 22px;\n}\n.upgrade-head[_ngcontent-%COMP%] {\n  display: flex;\n  justify-content: space-between;\n  align-items: center;\n  gap: 12px;\n}\n.upgrade-head[_ngcontent-%COMP%]   .title[_ngcontent-%COMP%] {\n  font-size: 14px;\n  font-weight: 600;\n}\n.meta-inline[_ngcontent-%COMP%] {\n  font-size: 12px;\n  color: var(--subtext);\n  font-weight: 400;\n  margin-left: 6px;\n}\n.upgrade-body[_ngcontent-%COMP%] {\n  margin-top: 10px;\n}\n.upgrade-changes[_ngcontent-%COMP%] {\n  margin-top: 8px;\n}\n.upgrade-change[_ngcontent-%COMP%] {\n  display: grid;\n  grid-template-columns: 1fr auto;\n  gap: 8px;\n  padding: 8px 10px;\n  background: rgba(0, 0, 0, 0.18);\n  border-radius: 6px;\n  margin-bottom: 4px;\n  font-size: 13px;\n}\n.upgrade-change[_ngcontent-%COMP%]   .body[_ngcontent-%COMP%]   .label[_ngcontent-%COMP%] {\n  font-weight: 600;\n}\n.upgrade-change[_ngcontent-%COMP%]   .body[_ngcontent-%COMP%]   .why[_ngcontent-%COMP%] {\n  font-size: 12px;\n  color: var(--subtext);\n}\n.upgrade-change[_ngcontent-%COMP%]   .delta[_ngcontent-%COMP%] {\n  font-family:\n    ui-monospace,\n    SFMono-Regular,\n    Menlo,\n    Monaco,\n    monospace;\n  font-size: 12px;\n  color: var(--accent);\n  white-space: nowrap;\n  align-self: center;\n}\n.upgrade-cta[_ngcontent-%COMP%] {\n  display: flex;\n  gap: 8px;\n  flex-wrap: wrap;\n  align-items: center;\n  margin-top: 12px;\n}\n.upgrade-cta[_ngcontent-%COMP%]   button[_ngcontent-%COMP%] {\n  font-size: 12px;\n  padding: 6px 12px;\n  border-radius: 6px;\n  cursor: pointer;\n  border: 1px solid var(--border-strong);\n  background: rgba(255, 255, 255, 0.03);\n  color: var(--text);\n}\n.upgrade-cta[_ngcontent-%COMP%]   button[_ngcontent-%COMP%]:hover {\n  filter: brightness(1.08);\n}\n.toggle[_ngcontent-%COMP%] {\n  background: none;\n  border: none;\n  color: var(--subtext);\n  cursor: pointer;\n  font-size: 12px;\n}\n.profile-bar[_ngcontent-%COMP%] {\n  display: flex;\n  align-items: flex-end;\n  gap: 12px;\n  padding: 14px 16px;\n  background: var(--panel);\n  border: 1px solid var(--border);\n  border-radius: 10px;\n  margin-bottom: 18px;\n  flex-wrap: wrap;\n}\n.bar-label[_ngcontent-%COMP%] {\n  font-size: 12px;\n  color: var(--subtext);\n  text-transform: uppercase;\n  letter-spacing: 0.05em;\n  margin-bottom: 6px;\n}\n.profile-row[_ngcontent-%COMP%] {\n  display: flex;\n  gap: 8px;\n  align-items: center;\n}\n.profile-bar[_ngcontent-%COMP%]   select[_ngcontent-%COMP%] {\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  color: var(--text);\n  padding: 8px 12px;\n  border-radius: 6px;\n  font-size: 14px;\n  min-width: 260px;\n}\n.modified-tag[_ngcontent-%COMP%] {\n  color: var(--warn);\n  font-size: 12px;\n  font-weight: 600;\n}\n.revert-btn[_ngcontent-%COMP%] {\n  background: rgba(245, 158, 11, 0.15);\n  border: 1px solid rgba(245, 158, 11, 0.45);\n  color: var(--warn);\n  padding: 4px 10px;\n  border-radius: 4px;\n  font-size: 12px;\n  font-weight: 600;\n  cursor: pointer;\n}\n.revert-btn[_ngcontent-%COMP%]:hover {\n  filter: brightness(1.15);\n}\n.revert-btn[_ngcontent-%COMP%]   .count[_ngcontent-%COMP%] {\n  background: rgba(245, 158, 11, 0.25);\n  padding: 0 5px;\n  border-radius: 999px;\n  margin-left: 4px;\n  font-size: 10px;\n}\n.spacer[_ngcontent-%COMP%] {\n  flex: 1 1 auto;\n}\n.profile-bar[_ngcontent-%COMP%]   button[_ngcontent-%COMP%] {\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  color: var(--text);\n  padding: 7px 14px;\n  border-radius: 6px;\n  font-size: 13px;\n  cursor: pointer;\n}\n.profile-bar[_ngcontent-%COMP%]   button.danger[_ngcontent-%COMP%] {\n  color: var(--neg);\n  border-color: rgba(248, 113, 113, 0.4);\n}\n.profile-bar[_ngcontent-%COMP%]   button[_ngcontent-%COMP%]:disabled {\n  opacity: 0.4;\n  cursor: not-allowed;\n}\n.profile-bar[_ngcontent-%COMP%]   button[_ngcontent-%COMP%]:hover:not(:disabled) {\n  filter: brightness(1.15);\n}\n.lock-banner[_ngcontent-%COMP%] {\n  background: rgba(56, 189, 248, 0.10);\n  border: 1px solid rgba(56, 189, 248, 0.4);\n  border-radius: 10px;\n  padding: 14px 18px;\n  margin-bottom: 18px;\n  display: flex;\n  align-items: center;\n  gap: 14px;\n}\n.lock-banner[_ngcontent-%COMP%]   .icon[_ngcontent-%COMP%] {\n  font-size: 22px;\n}\n.lock-banner[_ngcontent-%COMP%]   .body[_ngcontent-%COMP%] {\n  flex: 1;\n}\n.lock-banner[_ngcontent-%COMP%]   .body[_ngcontent-%COMP%]   .title[_ngcontent-%COMP%] {\n  font-size: 13px;\n  font-weight: 600;\n  margin-bottom: 2px;\n}\n.lock-banner[_ngcontent-%COMP%]   .body[_ngcontent-%COMP%]   .why[_ngcontent-%COMP%] {\n  font-size: 12px;\n  color: var(--subtext);\n}\n.lock-banner[_ngcontent-%COMP%]    > button[_ngcontent-%COMP%] {\n  background: var(--accent);\n  color: #062032;\n  border: 1px solid var(--accent);\n  padding: 8px 16px;\n  border-radius: 6px;\n  font-size: 13px;\n  font-weight: 600;\n  cursor: pointer;\n  white-space: nowrap;\n}\n.lock-banner[_ngcontent-%COMP%]    > button[_ngcontent-%COMP%]:hover {\n  filter: brightness(1.08);\n}\n.tabs[_ngcontent-%COMP%] {\n  display: inline-flex;\n  background: var(--panel);\n  border: 1px solid var(--border);\n  border-radius: 8px;\n  padding: 3px;\n  margin-bottom: 18px;\n  gap: 0;\n}\n.tabs[_ngcontent-%COMP%]   button[_ngcontent-%COMP%] {\n  background: transparent;\n  border: none;\n  color: var(--subtext);\n  padding: 8px 22px;\n  font-size: 13px;\n  font-weight: 600;\n  border-radius: 6px;\n  cursor: pointer;\n}\n.tabs[_ngcontent-%COMP%]   button.active[_ngcontent-%COMP%] {\n  background: rgba(56, 189, 248, 0.18);\n  color: var(--accent);\n}\nsection.panel[_ngcontent-%COMP%] {\n  background: var(--panel);\n  border: 1px solid var(--border);\n  border-radius: 10px;\n  padding: 18px 20px;\n  margin-bottom: 16px;\n}\nsection.panel[_ngcontent-%COMP%]   h2[_ngcontent-%COMP%] {\n  font-size: 14px;\n  margin: 0 0 6px;\n  display: flex;\n  align-items: center;\n  gap: 8px;\n}\n.num[_ngcontent-%COMP%] {\n  background: rgba(56, 189, 248, 0.15);\n  color: var(--accent);\n  font-size: 11px;\n  padding: 2px 6px;\n  border-radius: 999px;\n  font-weight: 600;\n}\n.help[_ngcontent-%COMP%] {\n  font-size: 12px;\n  color: var(--subtext);\n  margin-bottom: 12px;\n}\n.field[_ngcontent-%COMP%] {\n  padding: 14px 0;\n  border-bottom: 1px solid rgba(255, 255, 255, 0.04);\n}\n.field[_ngcontent-%COMP%]:last-child {\n  border-bottom: none;\n}\n.field-head[_ngcontent-%COMP%] {\n  display: flex;\n  justify-content: space-between;\n  align-items: center;\n  gap: 12px;\n  margin-bottom: 6px;\n}\n.field-head[_ngcontent-%COMP%]   .name[_ngcontent-%COMP%] {\n  font-size: 13px;\n  font-weight: 600;\n}\n.help-icon[_ngcontent-%COMP%] {\n  color: var(--subtext);\n  margin-left: 6px;\n  cursor: help;\n  font-size: 11px;\n}\n.value-display[_ngcontent-%COMP%] {\n  font-family:\n    ui-monospace,\n    SFMono-Regular,\n    Menlo,\n    Monaco,\n    monospace;\n  font-size: 13px;\n  color: var(--accent);\n  font-weight: 600;\n}\n.value-display.neg[_ngcontent-%COMP%] {\n  color: var(--neg);\n}\n.field-help[_ngcontent-%COMP%] {\n  font-size: 12px;\n  color: var(--subtext);\n  margin-bottom: 10px;\n}\n.field-control[_ngcontent-%COMP%] {\n  display: flex;\n  align-items: center;\n  gap: 12px;\n}\n.field-control[_ngcontent-%COMP%]   input[type=range][_ngcontent-%COMP%] {\n  flex: 1;\n  accent-color: var(--accent);\n}\n.field-control[_ngcontent-%COMP%]   input[type=number][_ngcontent-%COMP%] {\n  width: 90px;\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  color: var(--text);\n  padding: 6px 10px;\n  border-radius: 6px;\n  font-family: ui-monospace, monospace;\n  font-size: 13px;\n}\n.field-control[_ngcontent-%COMP%]   select[_ngcontent-%COMP%] {\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  color: var(--text);\n  padding: 6px 10px;\n  border-radius: 6px;\n  font-size: 13px;\n}\n.stepped-slider[_ngcontent-%COMP%] {\n  display: flex;\n  flex-direction: column;\n  gap: 8px;\n}\n.stepped-slider[_ngcontent-%COMP%]   input[type=range][_ngcontent-%COMP%] {\n  accent-color: var(--accent);\n  width: 100%;\n}\n.ticks[_ngcontent-%COMP%] {\n  display: flex;\n  justify-content: space-between;\n  font-size: 11px;\n  color: var(--muted);\n}\n.ticks[_ngcontent-%COMP%]   span.active[_ngcontent-%COMP%] {\n  color: var(--accent);\n  font-weight: 600;\n}\n.preset-readout[_ngcontent-%COMP%] {\n  margin-top: 14px;\n  padding: 12px 14px;\n  background: rgba(0, 0, 0, 0.18);\n  border: 1px solid var(--border);\n  border-radius: 8px;\n  font-size: 12px;\n}\n.readout-head[_ngcontent-%COMP%] {\n  color: var(--subtext);\n  margin-bottom: 8px;\n  display: flex;\n  justify-content: space-between;\n  align-items: center;\n}\n.readout-head[_ngcontent-%COMP%]   strong[_ngcontent-%COMP%] {\n  color: var(--accent);\n}\n.toggle-table[_ngcontent-%COMP%] {\n  background: none;\n  border: none;\n  color: var(--accent);\n  cursor: pointer;\n  font-size: 12px;\n  padding: 0;\n}\n.toggle-table[_ngcontent-%COMP%]:hover {\n  text-decoration: underline;\n}\n.values[_ngcontent-%COMP%] {\n  display: flex;\n  flex-wrap: wrap;\n  gap: 8px 16px;\n  font-family:\n    ui-monospace,\n    SFMono-Regular,\n    Menlo,\n    Monaco,\n    monospace;\n}\n.kv[_ngcontent-%COMP%]   .k[_ngcontent-%COMP%] {\n  color: var(--subtext);\n  margin-right: 4px;\n}\n.kv[_ngcontent-%COMP%]   .v[_ngcontent-%COMP%] {\n  color: var(--accent);\n  font-weight: 600;\n}\n.compare-table[_ngcontent-%COMP%] {\n  margin-top: 12px;\n  overflow-x: auto;\n  border: 1px solid var(--border);\n  border-radius: 8px;\n}\n.compare-table[_ngcontent-%COMP%]   table[_ngcontent-%COMP%] {\n  border-collapse: collapse;\n  width: 100%;\n  font-size: 12px;\n  font-family:\n    ui-monospace,\n    SFMono-Regular,\n    Menlo,\n    Monaco,\n    monospace;\n}\n.compare-table[_ngcontent-%COMP%]   th[_ngcontent-%COMP%], \n.compare-table[_ngcontent-%COMP%]   td[_ngcontent-%COMP%] {\n  padding: 8px 10px;\n  border-bottom: 1px solid var(--border);\n  text-align: center;\n  white-space: nowrap;\n}\n.compare-table[_ngcontent-%COMP%]   th[_ngcontent-%COMP%] {\n  background: rgba(0, 0, 0, 0.25);\n  color: var(--subtext);\n  font-weight: 600;\n  font-size: 11px;\n  text-transform: uppercase;\n  letter-spacing: 0.04em;\n}\n.compare-table[_ngcontent-%COMP%]   td[_ngcontent-%COMP%]:first-child, \n.compare-table[_ngcontent-%COMP%]   th[_ngcontent-%COMP%]:first-child {\n  text-align: left;\n  color: var(--subtext);\n}\n.compare-table[_ngcontent-%COMP%]   tr[_ngcontent-%COMP%]:last-child   td[_ngcontent-%COMP%] {\n  border-bottom: none;\n}\n.compare-table[_ngcontent-%COMP%]   .col-active[_ngcontent-%COMP%] {\n  background: rgba(56, 189, 248, 0.12);\n  color: var(--accent);\n  font-weight: 700;\n}\n.compare-table[_ngcontent-%COMP%]   th.col-active[_ngcontent-%COMP%] {\n  background: rgba(56, 189, 248, 0.22);\n}\n.chip-input[_ngcontent-%COMP%] {\n  display: flex;\n  flex-wrap: wrap;\n  gap: 6px;\n  padding: 8px;\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  border-radius: 6px;\n  min-height: 40px;\n  align-items: center;\n}\n.chip[_ngcontent-%COMP%] {\n  display: inline-flex;\n  align-items: center;\n  gap: 6px;\n  background: rgba(248, 113, 113, 0.15);\n  color: var(--neg);\n  border: 1px solid rgba(248, 113, 113, 0.4);\n  padding: 4px 10px;\n  border-radius: 999px;\n  font-size: 12px;\n}\n.chip[_ngcontent-%COMP%]   button[_ngcontent-%COMP%] {\n  background: none;\n  border: none;\n  color: var(--neg);\n  cursor: pointer;\n  padding: 0 0 0 4px;\n  font-size: 14px;\n  line-height: 1;\n}\n.chip-input[_ngcontent-%COMP%]   input[_ngcontent-%COMP%] {\n  background: transparent;\n  border: none;\n  color: var(--text);\n  flex: 1;\n  font-size: 13px;\n  min-width: 120px;\n  outline: none;\n}\n.day-buttons[_ngcontent-%COMP%] {\n  display: flex;\n  gap: 6px;\n  flex-wrap: wrap;\n}\n.day-buttons[_ngcontent-%COMP%]   button[_ngcontent-%COMP%] {\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  color: var(--subtext);\n  padding: 6px 14px;\n  border-radius: 6px;\n  font-size: 12px;\n  cursor: pointer;\n  font-weight: 600;\n}\n.day-buttons[_ngcontent-%COMP%]   button.active[_ngcontent-%COMP%] {\n  background: rgba(245, 158, 11, 0.18);\n  border-color: var(--warn);\n  color: var(--warn);\n}\n.day-buttons[_ngcontent-%COMP%]   button[_ngcontent-%COMP%]:hover {\n  filter: brightness(1.15);\n}\n.toggle-switch[_ngcontent-%COMP%] {\n  position: relative;\n  display: inline-block;\n  width: 42px;\n  height: 24px;\n}\n.toggle-switch[_ngcontent-%COMP%]   input[_ngcontent-%COMP%] {\n  opacity: 0;\n  width: 0;\n  height: 0;\n}\n.track[_ngcontent-%COMP%] {\n  position: absolute;\n  cursor: pointer;\n  inset: 0;\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  border-radius: 24px;\n  transition: 0.2s;\n}\n.track[_ngcontent-%COMP%]:before {\n  position: absolute;\n  content: "";\n  height: 18px;\n  width: 18px;\n  left: 2px;\n  top: 2px;\n  background: var(--subtext);\n  border-radius: 50%;\n  transition: 0.2s;\n}\n.toggle-switch[_ngcontent-%COMP%]   input[_ngcontent-%COMP%]:checked    + .track[_ngcontent-%COMP%] {\n  background: rgba(74, 222, 128, 0.2);\n  border-color: var(--pos);\n}\n.toggle-switch[_ngcontent-%COMP%]   input[_ngcontent-%COMP%]:checked    + .track[_ngcontent-%COMP%]:before {\n  transform: translateX(18px);\n  background: var(--pos);\n}\n.toggle-label[_ngcontent-%COMP%] {\n  margin-left: 8px;\n  font-size: 13px;\n  color: var(--subtext);\n}\n.on-label[_ngcontent-%COMP%] {\n  color: var(--pos);\n}\n.off-label[_ngcontent-%COMP%] {\n  color: var(--muted);\n}\ndetails.adv[_ngcontent-%COMP%] {\n  background: var(--panel);\n  border: 1px solid var(--border);\n  border-radius: 10px;\n  margin-bottom: 12px;\n  overflow: hidden;\n}\ndetails.adv[_ngcontent-%COMP%]   summary[_ngcontent-%COMP%] {\n  padding: 14px 18px;\n  cursor: pointer;\n  display: flex;\n  justify-content: space-between;\n  align-items: center;\n  -webkit-user-select: none;\n  user-select: none;\n  list-style: none;\n}\ndetails.adv[_ngcontent-%COMP%]   summary[_ngcontent-%COMP%]::-webkit-details-marker {\n  display: none;\n}\n.left[_ngcontent-%COMP%] {\n  display: flex;\n  align-items: center;\n  gap: 10px;\n}\n.arrow[_ngcontent-%COMP%] {\n  color: var(--subtext);\n  transition: 0.2s;\n}\ndetails.adv[open][_ngcontent-%COMP%]   summary[_ngcontent-%COMP%]   .arrow[_ngcontent-%COMP%] {\n  transform: rotate(90deg);\n}\n.sub-count[_ngcontent-%COMP%] {\n  color: var(--subtext);\n  font-size: 12px;\n}\n.reset[_ngcontent-%COMP%] {\n  font-size: 11px;\n  color: var(--subtext);\n  cursor: pointer;\n  padding: 3px 8px;\n  border-radius: 4px;\n  border: 1px solid var(--border-strong);\n  background: var(--panel-2);\n}\n.reset[_ngcontent-%COMP%]:hover {\n  color: var(--text);\n}\n.adv-body[_ngcontent-%COMP%] {\n  padding: 0 18px 16px;\n}\n.tier-header[_ngcontent-%COMP%] {\n  border-bottom: 1px solid var(--border);\n  padding-bottom: 8px;\n  margin-bottom: 6px;\n}\n.tier-row[_ngcontent-%COMP%] {\n  display: grid;\n  grid-template-columns: 40px 1fr 1fr 28px;\n  gap: 8px;\n  align-items: center;\n  padding: 6px 0;\n}\n.tier-label[_ngcontent-%COMP%] {\n  font-size: 12px;\n  color: var(--subtext);\n}\n.tier-col-head[_ngcontent-%COMP%] {\n  font-size: 12px;\n  color: var(--subtext);\n}\n.tier-row[_ngcontent-%COMP%]   input[_ngcontent-%COMP%] {\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  color: var(--text);\n  padding: 4px 8px;\n  border-radius: 4px;\n  font-family: monospace;\n  font-size: 12px;\n  width: 100%;\n}\n.x[_ngcontent-%COMP%] {\n  background: none;\n  border: none;\n  color: var(--neg);\n  cursor: pointer;\n  font-size: 16px;\n  line-height: 1;\n}\n.add-tier-row[_ngcontent-%COMP%] {\n  padding: 10px 0;\n}\n.add-tier-btn[_ngcontent-%COMP%] {\n  background: var(--panel-2);\n  border: 1px dashed var(--border-strong);\n  color: var(--subtext);\n  padding: 6px 14px;\n  border-radius: 6px;\n  cursor: pointer;\n  font-size: 13px;\n}\n.add-tier-btn[_ngcontent-%COMP%]:hover {\n  color: var(--text);\n}\n.footer[_ngcontent-%COMP%] {\n  position: fixed;\n  bottom: 0;\n  left: 0;\n  right: 0;\n  background: rgba(15, 17, 23, 0.95);\n  border-top: 1px solid var(--border);\n  padding: 14px 24px;\n  -webkit-backdrop-filter: blur(8px);\n  backdrop-filter: blur(8px);\n  z-index: 50;\n}\n.footer-inner[_ngcontent-%COMP%] {\n  max-width: 1100px;\n  margin: 0 auto;\n  display: flex;\n  justify-content: space-between;\n  align-items: center;\n  gap: 12px;\n  flex-wrap: wrap;\n}\n.status-pill[_ngcontent-%COMP%] {\n  font-size: 12px;\n  color: var(--subtext);\n  display: flex;\n  align-items: center;\n  gap: 6px;\n}\n.status-pill[_ngcontent-%COMP%]   .dot[_ngcontent-%COMP%] {\n  width: 7px;\n  height: 7px;\n  border-radius: 50%;\n  background: var(--pos);\n}\n.actions[_ngcontent-%COMP%] {\n  display: flex;\n  gap: 10px;\n}\n.actions[_ngcontent-%COMP%]   button[_ngcontent-%COMP%] {\n  padding: 9px 22px;\n  border-radius: 6px;\n  font-size: 14px;\n  font-weight: 600;\n  cursor: pointer;\n  border: 1px solid var(--border-strong);\n  background: var(--panel-2);\n  color: var(--text);\n}\n.cancel[_ngcontent-%COMP%] {\n  background: transparent !important;\n}\n.apply[_ngcontent-%COMP%] {\n  background: var(--accent) !important;\n  color: #062032 !important;\n  border-color: var(--accent) !important;\n}\n.actions[_ngcontent-%COMP%]   button[_ngcontent-%COMP%]:disabled {\n  opacity: 0.5;\n  cursor: not-allowed;\n}\n.actions[_ngcontent-%COMP%]   button[_ngcontent-%COMP%]:hover:not(:disabled) {\n  filter: brightness(1.1);\n}\n.modal-backdrop[_ngcontent-%COMP%] {\n  position: fixed;\n  inset: 0;\n  background: rgba(0, 0, 0, 0.6);\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  z-index: 100;\n  padding: 16px;\n}\n.modal[_ngcontent-%COMP%] {\n  background: #1a1d28;\n  border: 1px solid var(--border-strong);\n  border-radius: 12px;\n  padding: 24px;\n  max-width: 560px;\n  width: 100%;\n  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);\n}\n.modal[_ngcontent-%COMP%]   h3[_ngcontent-%COMP%] {\n  margin-top: 0;\n  font-size: 17px;\n  color: var(--text);\n}\n.modal[_ngcontent-%COMP%]   p[_ngcontent-%COMP%] {\n  color: var(--subtext);\n  font-size: 13px;\n}\n.modal[_ngcontent-%COMP%]   label[_ngcontent-%COMP%] {\n  display: block;\n  font-size: 12px;\n  color: var(--subtext);\n  margin: 14px 0 6px;\n}\n.modal[_ngcontent-%COMP%]   input[type=text][_ngcontent-%COMP%], \n.modal[_ngcontent-%COMP%]   textarea[_ngcontent-%COMP%] {\n  width: 100%;\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  color: var(--text);\n  padding: 8px 12px;\n  border-radius: 6px;\n  font-size: 13px;\n  font-family: inherit;\n}\n.modal[_ngcontent-%COMP%]   textarea[_ngcontent-%COMP%] {\n  resize: vertical;\n  min-height: 60px;\n}\n.diff-list[_ngcontent-%COMP%] {\n  background: rgba(0, 0, 0, 0.3);\n  border-radius: 6px;\n  padding: 10px 12px;\n  font-family: ui-monospace, monospace;\n  font-size: 12px;\n  margin: 10px 0;\n  max-height: 200px;\n  overflow-y: auto;\n  color: var(--text);\n}\n.diff-list[_ngcontent-%COMP%]   div[_ngcontent-%COMP%] {\n  padding: 2px 0;\n}\n.arrow[_ngcontent-%COMP%] {\n  color: var(--accent);\n}\n.saved-label[_ngcontent-%COMP%] {\n  color: var(--subtext);\n  font-size: 11px;\n  margin-left: 4px;\n}\n.small-note[_ngcontent-%COMP%] {\n  font-size: 12px;\n  color: var(--subtext);\n  margin: 6px 0 0;\n}\n.modal-actions[_ngcontent-%COMP%] {\n  display: flex;\n  gap: 10px;\n  justify-content: flex-end;\n  margin-top: 18px;\n}\n.modal-actions[_ngcontent-%COMP%]   button[_ngcontent-%COMP%] {\n  padding: 8px 18px;\n  border-radius: 6px;\n  font-size: 13px;\n  cursor: pointer;\n  border: 1px solid var(--border-strong);\n  background: var(--panel-2);\n  color: var(--text);\n}\n.modal-actions[_ngcontent-%COMP%]   .primary[_ngcontent-%COMP%] {\n  background: var(--accent);\n  color: #062032;\n  border-color: var(--accent);\n  font-weight: 600;\n}\n.modal-actions[_ngcontent-%COMP%]   .danger[_ngcontent-%COMP%] {\n  background: rgba(248, 113, 113, 0.2);\n  border-color: var(--neg);\n  color: var(--neg);\n  font-weight: 600;\n}\n.modal-actions[_ngcontent-%COMP%]   button[_ngcontent-%COMP%]:disabled {\n  opacity: 0.5;\n  cursor: not-allowed;\n}\n.toast[_ngcontent-%COMP%] {\n  position: fixed;\n  bottom: 88px;\n  left: 50%;\n  transform: translateX(-50%);\n  background: rgba(0, 0, 0, 0.8);\n  color: var(--text);\n  padding: 10px 18px;\n  border-radius: 8px;\n  font-size: 13px;\n  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.4);\n  border: 1px solid var(--border-strong);\n  z-index: 80;\n  white-space: nowrap;\n}\n.icon.ok[_ngcontent-%COMP%] {\n  color: var(--pos);\n  margin-right: 8px;\n}\n.read-only[_ngcontent-%COMP%]   input[type=range][_ngcontent-%COMP%], \n.read-only[_ngcontent-%COMP%]   input[type=number][_ngcontent-%COMP%], \n.read-only[_ngcontent-%COMP%]   input[type=text][_ngcontent-%COMP%], \n.read-only[_ngcontent-%COMP%]   select[_ngcontent-%COMP%], \n.read-only[_ngcontent-%COMP%]   .day-buttons[_ngcontent-%COMP%]   button[_ngcontent-%COMP%], \n.read-only[_ngcontent-%COMP%]   .toggle-switch[_ngcontent-%COMP%]   input[_ngcontent-%COMP%], \n.read-only[_ngcontent-%COMP%]   .chip[_ngcontent-%COMP%], \n.read-only[_ngcontent-%COMP%]   .chip-input[_ngcontent-%COMP%], \n.read-only[_ngcontent-%COMP%]   .chip-input[_ngcontent-%COMP%]   input[_ngcontent-%COMP%] {\n  pointer-events: none;\n  opacity: 0.65;\n}\n.read-only[_ngcontent-%COMP%]   .field-control[_ngcontent-%COMP%], \n.read-only[_ngcontent-%COMP%]   .stepped-slider[_ngcontent-%COMP%], \n.read-only[_ngcontent-%COMP%]   .day-buttons[_ngcontent-%COMP%], \n.read-only[_ngcontent-%COMP%]   .toggle-switch[_ngcontent-%COMP%], \n.read-only[_ngcontent-%COMP%]   .tier-row[_ngcontent-%COMP%], \n.read-only[_ngcontent-%COMP%]   .add-tier-btn[_ngcontent-%COMP%], \n.read-only[_ngcontent-%COMP%]   .reset[_ngcontent-%COMP%] {\n  pointer-events: none;\n  opacity: 0.7;\n}\n/*# sourceMappingURL=momentum-strategy.component.css.map */'] });
};
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && setClassMetadata(MomentumStrategyComponent, [{
    type: Component,
    args: [{ selector: "app-momentum-strategy", standalone: true, imports: [CommonModule, FormsModule], template: `<div class="page-shell">

  <!-- TOP BAR -->
  <div class="topbar">
    <div>
      <h1><span class="accent">\u2699</span>Momentum Strategy Settings</h1>
      <div class="meta">Hot reload \u2014 changes apply within 1\u20132s, no bot restart</div>
    </div>
    <button class="close-btn" (click)="backToDashboard()">\u2190 Back to Dashboard</button>
  </div>

  <!-- LOADING -->
  @if (loading()) {
    <div class="loading-state">Loading profiles\u2026</div>
  } @else {

  <!-- POST-UPDATE NOTIFICATION BANNER -->
  @if (showBanner()) {
    <div class="upgrade">
      <div class="upgrade-head">
        <div class="title">
          <span class="lamp">\u2713</span> Applied <strong>Recommended (v{{ profilesData()?.latest_recommended_version }})</strong>
          <span class="meta-inline"> \u2014 auto-applied on startup</span>
        </div>
        <button class="toggle" (click)="dismissBanner()">dismiss</button>
      </div>
      <div class="upgrade-body">
        <div class="upgrade-changes">
          @for (ch of changelogEntries(); track ch.path) {
            <div class="upgrade-change">
              <div class="body">
                <div class="label">{{ ch.label }}</div>
                <div class="why">{{ ch.rationale }}</div>
              </div>
              <div class="delta">{{ ch.old ?? 'none' }} \u2192 {{ ch.new }}</div>
            </div>
          }
        </div>
        <div class="upgrade-cta">
          <button (click)="rollback()">\u21BA Rollback to v{{ profilesData()?.applied_recommended_version }}</button>
        </div>
      </div>
    </div>
  }

  <!-- PROFILE BAR -->
  <div class="profile-bar">
    <div>
      <div class="bar-label">Profile</div>
      <div class="profile-row">
        <select [ngModel]="activeKey()" (ngModelChange)="onProfileChange($event)">
          <optgroup label="Built-in (bot-curated, read-only)">
            @for (p of builtinProfiles(); track p.key) {
              <option [value]="p.key">\u{1F512} {{ p.label }}</option>
            }
          </optgroup>
          @if (userProfiles().length > 0) {
            <optgroup label="Your favorites (editable)">
              @for (p of userProfiles(); track p.key) {
                <option [value]="p.key">{{ p.label }}</option>
              }
            </optgroup>
          }
        </select>
        @if (modified()) {
          <span class="modified-tag">(modified)</span>
          <button class="revert-btn" (click)="openRevert()" title="Discard all unsaved tweaks">
            \u21BA Revert<span class="count">{{ changeCount() }}</span>
          </button>
        }
      </div>
    </div>
    <div class="spacer"></div>
    <button [disabled]="isBuiltin() || !modified()" (click)="openSave()">\u2913 Save</button>
    <button (click)="openSaveAs()">\u2B50 Save as new\u2026</button>
    <button class="danger" [disabled]="isBuiltin()" (click)="openDelete()">\u2715 Delete</button>
  </div>

  <!-- LOCK BANNER -->
  @if (isBuiltin()) {
    <div class="lock-banner">
      <div class="icon">\u{1F512}</div>
      <div class="body">
        <div class="title">This profile is bot-curated and read-only</div>
        <div class="why">
          "{{ profileName() }}" evolves with each release of the bot's research.
          To customize without losing the original, save it as a new profile first.
        </div>
      </div>
      <button (click)="openSaveAs('My ' + profileName() + ' (custom)')">\u2B50 Customize as new profile</button>
    </div>
  }

  <!-- TABS -->
  <div class="tabs">
    <button [class.active]="mode() === 'simple'" (click)="mode.set('simple')">Simple</button>
    <button [class.active]="mode() === 'advanced'" (click)="mode.set('advanced')">Advanced</button>
  </div>

  <!-- ==================== SIMPLE VIEW ==================== -->
  @if (mode() === 'simple') {
    <div [class.read-only]="isBuiltin()">

      <!-- Risk level -->
      <section class="panel">
        <h2>Risk level <span class="num">controls 6 entry gates</span></h2>
        <div class="help">Controls how strict entries are: ADX, RSI, distance from ATH, and 3-hour overextension thresholds. Conservative = fewer but cleaner trades. Aggressive = more trades, more noise.</div>
        <div class="stepped-slider">
          <input type="range" min="1" max="5" [value]="riskSliderValue()"
                 (input)="setRiskLevel(+$any($event.target).value)">
          <div class="ticks">
            @for (l of riskLevels; track l.label; let i = $index) {
              <span [class.active]="riskSliderValue() === i + 1">{{ l.label }}</span>
            }
          </div>
        </div>
        <div class="preset-readout">
          <div class="readout-head">
            <span>Currently set to <strong>{{ riskLevelLabel() }}</strong> \u2014 these are the actual values:</span>
            <button class="toggle-table" (click)="showRiskTable.set(!showRiskTable())">
              {{ showRiskTable() ? 'hide table \u2191' : 'show all 5 levels \u2193' }}
            </button>
          </div>
          <div class="values">
            <span class="kv"><span class="k">ADX min</span><span class="v">{{ getField('entry_gates','adx_min') }}</span></span>
            <span class="kv"><span class="k">RSI min</span><span class="v">{{ getField('entry_gates','rsi_min') }}</span></span>
            <span class="kv"><span class="k">RSI max</span><span class="v">{{ getField('entry_gates','rsi_max') }}</span></span>
            <span class="kv"><span class="k">ATH gate</span><span class="v">{{ getField('entry_gates','ath_dist_max') }}%</span></span>
            <span class="kv"><span class="k">3h overpump</span><span class="v">{{ getField('entry_gates','chg3h_atr_max') }}\xD7 ATR</span></span>
            <span class="kv"><span class="k">3h crash</span><span class="v">{{ getField('entry_gates','chg3h_atr_min') }}\xD7 ATR</span></span>
          </div>
          @if (showRiskTable()) {
            <div class="compare-table">
              <table>
                <thead>
                  <tr>
                    <th>Setting</th>
                    @for (h of riskColHeaders; track h; let ci = $index) {
                      <th [class.col-active]="riskSliderValue() === ci + 1">{{ h }}</th>
                    }
                  </tr>
                </thead>
                <tbody>
                  @for (row of riskTable; track row.label) {
                    <tr>
                      <td>{{ row.label }}</td>
                      @for (v of row.values; track $index; let ci = $index) {
                        <td [class.col-active]="riskSliderValue() === ci + 1">{{ v }}</td>
                      }
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          }
        </div>
      </section>

      <!-- Profit-taking style -->
      <section class="panel">
        <h2>Profit-taking style <span class="num">controls 4 trail tiers</span></h2>
        <div class="help">How tightly we trail behind a winning peak. Quick locks small wins early. Let-it-run gives more room but risks giving back more.</div>
        <div class="stepped-slider">
          <input type="range" min="1" max="5" [value]="profitSliderValue()"
                 (input)="setProfitLevel(+$any($event.target).value)">
          <div class="ticks">
            @for (l of profitLevels; track l.label; let i = $index) {
              <span [class.active]="profitSliderValue() === i + 1">{{ l.label }}</span>
            }
          </div>
        </div>
        <div class="preset-readout">
          <div class="readout-head">
            <span>Currently set to <strong>{{ profitLevelLabel() }}</strong> \u2014 these are the trail tiers:</span>
            <button class="toggle-table" (click)="showProfitTable.set(!showProfitTable())">
              {{ showProfitTable() ? 'hide table \u2191' : 'show all 5 levels \u2193' }}
            </button>
          </div>
          <div class="values">
            @for (tier of getTiers(); track $index; let i = $index) {
              <span class="kv"><span class="k">Tier {{ i + 1 }}</span><span class="v">peak \u2265{{ tier[0] }}% \u2192 trail {{ tier[1] }}%</span></span>
            }
          </div>
          @if (showProfitTable()) {
            <div class="compare-table">
              <table>
                <thead>
                  <tr>
                    <th>Tier (peak \u2192 trail give-back)</th>
                    @for (h of profitColHeaders; track h; let ci = $index) {
                      <th [class.col-active]="profitSliderValue() === ci + 1">{{ h }}</th>
                    }
                  </tr>
                </thead>
                <tbody>
                  @for (row of profitTable; track row.label) {
                    <tr>
                      <td>{{ row.label }}</td>
                      @for (v of row.values; track $index; let ci = $index) {
                        <td [class.col-active]="profitSliderValue() === ci + 1">{{ v }}</td>
                      }
                    </tr>
                  }
                </tbody>
              </table>
            </div>
          }
        </div>
      </section>

      <!-- Max hold -->
      <section class="panel">
        <h2>Max hold per trade</h2>
        <div class="help">Force-exit after this many hours, regardless of P&L. Prevents trades from sitting in slow bleed.</div>
        <div class="field-control">
          <select [ngModel]="getField('exits','max_hold_hours')" (ngModelChange)="setMaxHold($event)">
            <option [value]="12">12 hours</option>
            <option [value]="24">24 hours</option>
            <option [value]="48">48 hours</option>
            <option [value]="72">72 hours (recommended)</option>
            <option [value]="168">168 hours (1 week)</option>
          </select>
        </div>
      </section>

      <!-- Position size -->
      <section class="panel">
        <h2>Position size per trade</h2>
        <div class="help">USD amount allocated to each trade. Higher = bigger wins/losses, fees as % stay the same.</div>
        <div class="field-head">
          <div class="name">Allocation</div>
          <div class="value-display">\${{ getField('position','allocation_usd') | number }}</div>
        </div>
        <div class="field-control">
          <input type="range" min="500" max="5000" step="250"
                 [value]="getField('position','allocation_usd')"
                 (input)="setAllocation(+$any($event.target).value)">
          <input type="number" min="500" max="5000" step="250"
                 [ngModel]="getField('position','allocation_usd')"
                 (ngModelChange)="setAllocation($event)">
        </div>
      </section>

      <!-- Pairs to skip -->
      <section class="panel">
        <h2>Pairs to skip (blacklist)</h2>
        <div class="help">Pairs the bot will never enter. Use this for known dead-money coins.</div>
        <div class="chip-input">
          @for (pair of getBlacklist(); track pair) {
            <span class="chip">{{ pair }} <button (click)="removeChip(pair)" [disabled]="isBuiltin()">\xD7</button></span>
          }
          <input type="text" placeholder="add pair (press Enter)\u2026"
                 [(ngModel)]="blacklistInput"
                 (keydown)="onChipKeydown($event)"
                 [disabled]="isBuiltin()">
        </div>
      </section>

      <!-- Entry pause days -->
      <section class="panel">
        <h2>Pause entries on these days</h2>
        <div class="help">No new positions opened on selected days. Existing positions still exit normally. Default: Sunday only.</div>
        <div class="day-buttons">
          @for (day of days; track day; let i = $index) {
            <button [class.active]="isDayBlocked(i)"
                    (click)="toggleDay(i)"
                    [disabled]="isBuiltin()">{{ day }}</button>
          }
        </div>
      </section>

      <!-- Wall-aware toggle -->
      <section class="panel">
        <h2>Wall-aware trail</h2>
        <div class="help">Anchor trail stops to qualifying L2 bid walls instead of arbitrary percentages. Improves stop placement when there's real liquidity below current price.</div>
        <div class="field-control">
          <label class="toggle-switch">
            <input type="checkbox"
                   [checked]="getField('wall_aware','enabled')"
                   (change)="setWallAware($any($event.target).checked)"
                   [disabled]="isBuiltin()">
            <span class="track"></span>
          </label>
          <span class="toggle-label">
            Currently <strong [class.on-label]="getField('wall_aware','enabled')" [class.off-label]="!getField('wall_aware','enabled')">
              {{ getField('wall_aware','enabled') ? 'on' : 'off' }}
            </strong>
          </span>
        </div>
      </section>

    </div>
  }

  <!-- ==================== ADVANCED VIEW ==================== -->
  @if (mode() === 'advanced') {
    <div [class.read-only]="isBuiltin()">

      <!-- Entry gates -->
      <details class="adv" open>
        <summary>
          <span class="left"><span class="arrow">\u25B6</span><strong>Entry gates</strong> <span class="sub-count">9 controls</span></span>
          <button class="reset" (click)="$event.preventDefault(); resetSection('entry_gates')">\u21BB Reset section</button>
        </summary>
        <div class="adv-body">
          <div class="field">
            <div class="field-head"><div class="name">ADX min <span class="help-icon" title="Average Directional Index \u2014 minimum trend strength">?</span></div>
              <div class="value-display">{{ getField('entry_gates','adx_min') }}</div></div>
            <div class="field-help">Higher = only enter very strong trends. Sane range: 15\u201340.</div>
            <div class="field-control">
              <input type="range" min="0" max="50" [value]="getField('entry_gates','adx_min')"
                     (input)="setField('entry_gates','adx_min',+$any($event.target).value)">
              <input type="number" min="0" max="50" [ngModel]="getField('entry_gates','adx_min')"
                     (ngModelChange)="setField('entry_gates','adx_min',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">RSI min (uptrend)</div>
              <div class="value-display">{{ getField('entry_gates','rsi_min') }}</div></div>
            <div class="field-help">Reject entries when RSI is below this \u2014 coin must be above the midline. Sane range: 40\u201360.</div>
            <div class="field-control">
              <input type="range" min="30" max="70" [value]="getField('entry_gates','rsi_min')"
                     (input)="setField('entry_gates','rsi_min',+$any($event.target).value)">
              <input type="number" min="30" max="70" [ngModel]="getField('entry_gates','rsi_min')"
                     (ngModelChange)="setField('entry_gates','rsi_min',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">RSI max (overbought)</div>
              <div class="value-display">{{ getField('entry_gates','rsi_max') }}</div></div>
            <div class="field-help">Reject entries when RSI is above this \u2014 coin is overbought. Sane range: 60\u201380.</div>
            <div class="field-control">
              <input type="range" min="50" max="90" [value]="getField('entry_gates','rsi_max')"
                     (input)="setField('entry_gates','rsi_max',+$any($event.target).value)">
              <input type="number" min="50" max="90" [ngModel]="getField('entry_gates','rsi_max')"
                     (ngModelChange)="setField('entry_gates','rsi_max',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">Re-entry accel threshold (%)</div>
              <div class="value-display">{{ getField('entry_gates','accel_min') }}%</div></div>
            <div class="field-help">Minimum acceleration % required to enter. Below this is too weak. Sane range: 5\u201325.</div>
            <div class="field-control">
              <input type="range" min="0" max="50" [value]="getField('entry_gates','accel_min')"
                     (input)="setField('entry_gates','accel_min',+$any($event.target).value)">
              <input type="number" min="0" max="50" [ngModel]="getField('entry_gates','accel_min')"
                     (ngModelChange)="setField('entry_gates','accel_min',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">ATH proximity gate (%)</div>
              <div class="value-display">{{ getField('entry_gates','ath_dist_max') }}%</div></div>
            <div class="field-help">Reject if price is within X% of all-time high. Negative = below ATH. Sane range: -5 to -25.</div>
            <div class="field-control">
              <input type="range" min="-30" max="-3" [value]="getField('entry_gates','ath_dist_max')"
                     (input)="setField('entry_gates','ath_dist_max',+$any($event.target).value)">
              <input type="number" min="-30" max="-3" [ngModel]="getField('entry_gates','ath_dist_max')"
                     (ngModelChange)="setField('entry_gates','ath_dist_max',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">3-hour overpump (\xD7 ATR)</div>
              <div class="value-display">{{ getField('entry_gates','chg3h_atr_max') }}\xD7</div></div>
            <div class="field-help">Reject if 3-hour move exceeds X ATR upward (already pumped). Sane range: 1.5\u20136.</div>
            <div class="field-control">
              <input type="range" min="1" max="6" step="0.1" [value]="getField('entry_gates','chg3h_atr_max')"
                     (input)="setField('entry_gates','chg3h_atr_max',+$any($event.target).value)">
              <input type="number" min="1" max="6" step="0.1" [ngModel]="getField('entry_gates','chg3h_atr_max')"
                     (ngModelChange)="setField('entry_gates','chg3h_atr_max',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">3-hour crash (\xD7 ATR, lower bound)</div>
              <div class="value-display">{{ getField('entry_gates','chg3h_atr_min') }}\xD7</div></div>
            <div class="field-help">Reject if 3-hour move dropped more than X ATR (falling-knife). Sane range: -1.5 to -6.</div>
            <div class="field-control">
              <input type="range" min="-6" max="-1" step="0.1" [value]="getField('entry_gates','chg3h_atr_min')"
                     (input)="setField('entry_gates','chg3h_atr_min',+$any($event.target).value)">
              <input type="number" min="-6" max="-1" step="0.1" [ngModel]="getField('entry_gates','chg3h_atr_min')"
                     (ngModelChange)="setField('entry_gates','chg3h_atr_min',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">Green candles min (of last 6)</div>
              <div class="value-display">{{ getField('entry_gates','green_count_min') }}/6</div></div>
            <div class="field-help">Require at least N of last 6 candles to close green. Sane range: 1\u20135.</div>
            <div class="field-control">
              <input type="range" min="0" max="6" [value]="getField('entry_gates','green_count_min')"
                     (input)="setField('entry_gates','green_count_min',+$any($event.target).value)">
              <input type="number" min="0" max="6" [ngModel]="getField('entry_gates','green_count_min')"
                     (ngModelChange)="setField('entry_gates','green_count_min',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">Body ratio min</div>
              <div class="value-display">{{ getField('entry_gates','body_ratio_min') }}</div></div>
            <div class="field-help">Average candle body / range. Higher = more decisive candles required. Sane range: 0.1\u20130.7.</div>
            <div class="field-control">
              <input type="range" min="0" max="1" step="0.05" [value]="getField('entry_gates','body_ratio_min')"
                     (input)="setField('entry_gates','body_ratio_min',+$any($event.target).value)">
              <input type="number" min="0" max="1" step="0.05" [ngModel]="getField('entry_gates','body_ratio_min')"
                     (ngModelChange)="setField('entry_gates','body_ratio_min',$event)">
            </div>
          </div>
        </div>
      </details>

      <!-- Trail tiers -->
      <details class="adv">
        <summary>
          <span class="left"><span class="arrow">\u25B6</span><strong>Trail tiers</strong> <span class="sub-count">progressive trail</span></span>
          <button class="reset" (click)="$event.preventDefault(); resetSection('trail')">\u21BB Reset section</button>
        </summary>
        <div class="adv-body">
          <div class="field-help">Each tier: when peak reaches the % shown, lock the stop at peak \u2212 give-back %. The bot uses the tightest tier whose threshold is met.</div>
          <div class="tier-row tier-header">
            <div class="tier-label">Tier</div>
            <div class="tier-col-head">Peak \u2265</div>
            <div class="tier-col-head">Trail give-back</div>
            <div></div>
          </div>
          @for (tier of getTiers(); track $index; let i = $index) {
            <div class="tier-row">
              <div class="tier-label">{{ i + 1 }}</div>
              <input type="number" [value]="tier[0]" step="0.5"
                     (input)="setTierValue(i, 0, +$any($event.target).value)">
              <input type="number" [value]="tier[1]" step="0.1"
                     (input)="setTierValue(i, 1, +$any($event.target).value)">
              <button class="x" (click)="removeTier(i)">\xD7</button>
            </div>
          }
          <div class="add-tier-row">
            <button class="add-tier-btn" (click)="addTier()">+ Add tier</button>
          </div>

          <div class="field" style="border-top:1px solid var(--border); padding-top:14px; margin-top:8px;">
            <div class="field-head"><div class="name">ATR stop multiplier (entry-time stop)</div>
              <div class="value-display">{{ getField('trail','wide_pct') }}%</div></div>
            <div class="field-help">Wide trail % used before first tier activates. Sane range: 2\u201310.</div>
            <div class="field-control">
              <input type="range" min="1" max="15" step="0.5" [value]="getField('trail','wide_pct')"
                     (input)="setField('trail','wide_pct',+$any($event.target).value)">
              <input type="number" min="1" max="15" step="0.5" [ngModel]="getField('trail','wide_pct')"
                     (ngModelChange)="setField('trail','wide_pct',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">Stale ticks (no new high)</div>
              <div class="value-display">{{ getField('trail','stale_ticks') }}</div></div>
            <div class="field-help">After this many ticks without a new high, switch to the stale (tightest) trail. Sane range: 10\u2013120.</div>
            <div class="field-control">
              <input type="range" min="5" max="120" [value]="getField('trail','stale_ticks')"
                     (input)="setField('trail','stale_ticks',+$any($event.target).value)">
              <input type="number" min="5" max="120" [ngModel]="getField('trail','stale_ticks')"
                     (ngModelChange)="setField('trail','stale_ticks',$event)">
            </div>
          </div>
        </div>
      </details>

      <!-- Exits -->
      <details class="adv">
        <summary>
          <span class="left"><span class="arrow">\u25B6</span><strong>Exits &amp; safety stops</strong> <span class="sub-count">5 controls</span></span>
          <button class="reset" (click)="$event.preventDefault(); resetSection('exits')">\u21BB Reset section</button>
        </summary>
        <div class="adv-body">
          <div class="field">
            <div class="field-head"><div class="name">Max hold (hours)</div><div class="value-display">{{ getField('exits','max_hold_hours') }}h</div></div>
            <div class="field-help">Force-exit after this many hours. Sane range: 12\u2013168.</div>
            <div class="field-control">
              <input type="range" min="6" max="168" [value]="getField('exits','max_hold_hours')"
                     (input)="setField('exits','max_hold_hours',+$any($event.target).value)">
              <input type="number" min="6" max="168" [ngModel]="getField('exits','max_hold_hours')"
                     (ngModelChange)="setField('exits','max_hold_hours',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">Accel-fade exit threshold (%)</div><div class="value-display">{{ getField('exits','accel_exit_thresh') }}%</div></div>
            <div class="field-help">Exit if acceleration drops below this after min-hold. Sane range: 0\u201315.</div>
            <div class="field-control">
              <input type="range" min="0" max="20" step="0.5" [value]="getField('exits','accel_exit_thresh')"
                     (input)="setField('exits','accel_exit_thresh',+$any($event.target).value)">
              <input type="number" min="0" max="20" step="0.5" [ngModel]="getField('exits','accel_exit_thresh')"
                     (ngModelChange)="setField('exits','accel_exit_thresh',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">Accel-fade min hold (hours)</div><div class="value-display">{{ getField('exits','accel_exit_min_hold') }}h</div></div>
            <div class="field-help">Don't trigger accel-fade until trade is held this long. Sane range: 1\u201324.</div>
            <div class="field-control">
              <input type="range" min="0" max="24" [value]="getField('exits','accel_exit_min_hold')"
                     (input)="setField('exits','accel_exit_min_hold',+$any($event.target).value)">
              <input type="number" min="0" max="24" [ngModel]="getField('exits','accel_exit_min_hold')"
                     (ngModelChange)="setField('exits','accel_exit_min_hold',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">Equity trailing stop (%)</div><div class="value-display">{{ getField('exits','equity_trail_pct') }}%</div></div>
            <div class="field-help">Portfolio-level emergency stop. Exit all positions if equity falls X% from peak. Sane range: 5\u201330.</div>
            <div class="field-control">
              <input type="range" min="5" max="30" step="0.5" [value]="getField('exits','equity_trail_pct')"
                     (input)="setField('exits','equity_trail_pct',+$any($event.target).value)">
              <input type="number" min="5" max="30" step="0.5" [ngModel]="getField('exits','equity_trail_pct')"
                     (ngModelChange)="setField('exits','equity_trail_pct',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">Min hold (hours)</div><div class="value-display">{{ getField('exits','min_hold_hours') }}h</div></div>
            <div class="field-help">Don't allow regime/rebalance exit until trade has been held this long. Sane range: 0\u201312.</div>
            <div class="field-control">
              <input type="range" min="0" max="24" [value]="getField('exits','min_hold_hours')"
                     (input)="setField('exits','min_hold_hours',+$any($event.target).value)">
              <input type="number" min="0" max="24" [ngModel]="getField('exits','min_hold_hours')"
                     (ngModelChange)="setField('exits','min_hold_hours',$event)">
            </div>
          </div>
        </div>
      </details>

      <!-- Lockouts -->
      <details class="adv">
        <summary>
          <span class="left"><span class="arrow">\u25B6</span><strong>Lockouts</strong> <span class="sub-count">3 controls</span></span>
          <button class="reset" (click)="$event.preventDefault(); resetSection('lockouts')">\u21BB Reset section</button>
        </summary>
        <div class="adv-body">
          <div class="field">
            <div class="field-head"><div class="name">Same-coin lockout (hours)</div><div class="value-display">{{ getField('lockouts','same_coin_hours') }}h</div></div>
            <div class="field-help">After exiting a coin, can't re-buy for X hours. Sane range: 4\u2013168.</div>
            <div class="field-control">
              <input type="range" min="0" max="168" [value]="getField('lockouts','same_coin_hours')"
                     (input)="setField('lockouts','same_coin_hours',+$any($event.target).value)">
              <input type="number" min="0" max="168" [ngModel]="getField('lockouts','same_coin_hours')"
                     (ngModelChange)="setField('lockouts','same_coin_hours',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">Loss-lockout (hours)</div><div class="value-display">{{ getField('lockouts','loss_lockout_hours') }}h</div></div>
            <div class="field-help">After a losing trade, that coin is locked out for X hours. Sane range: 24\u2013336.</div>
            <div class="field-control">
              <input type="range" min="0" max="336" [value]="getField('lockouts','loss_lockout_hours')"
                     (input)="setField('lockouts','loss_lockout_hours',+$any($event.target).value)">
              <input type="number" min="0" max="336" [ngModel]="getField('lockouts','loss_lockout_hours')"
                     (ngModelChange)="setField('lockouts','loss_lockout_hours',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">Exit cooldown (hours)</div><div class="value-display">{{ getField('lockouts','exit_cooldown_hours') }}h</div></div>
            <div class="field-help">Pause for this many hours after any exit before considering new entries. Sane range: 0\u201348.</div>
            <div class="field-control">
              <input type="range" min="0" max="48" step="0.5" [value]="getField('lockouts','exit_cooldown_hours')"
                     (input)="setField('lockouts','exit_cooldown_hours',+$any($event.target).value)">
              <input type="number" min="0" max="48" step="0.5" [ngModel]="getField('lockouts','exit_cooldown_hours')"
                     (ngModelChange)="setField('lockouts','exit_cooldown_hours',$event)">
            </div>
          </div>
        </div>
      </details>

      <!-- Regime -->
      <details class="adv">
        <summary>
          <span class="left"><span class="arrow">\u25B6</span><strong>Regime detector</strong> <span class="sub-count">2 controls</span></span>
          <button class="reset" (click)="$event.preventDefault(); resetSection('regime')">\u21BB Reset section</button>
        </summary>
        <div class="adv-body">
          <div class="field">
            <div class="field-head"><div class="name">BTC SMA period (candles)</div><div class="value-display">{{ getField('regime','ma_period') }}</div></div>
            <div class="field-help">Number of hourly candles to average for the BTC regime MA. Sane range: 100\u20131000.</div>
            <div class="field-control">
              <input type="range" min="100" max="1000" step="50" [value]="getField('regime','ma_period')"
                     (input)="setField('regime','ma_period',+$any($event.target).value)">
              <input type="number" min="100" max="1000" step="50" [ngModel]="getField('regime','ma_period')"
                     (ngModelChange)="setField('regime','ma_period',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">Regime hysteresis (%)</div><div class="value-display">{{ getField('regime','hysteresis_pct') }}%</div></div>
            <div class="field-help">BTC must cross MA by this % to flip regime \u2014 prevents whipsaw. Sane range: 1\u201315.</div>
            <div class="field-control">
              <input type="range" min="0" max="15" step="0.5" [value]="getField('regime','hysteresis_pct')"
                     (input)="setField('regime','hysteresis_pct',+$any($event.target).value)">
              <input type="number" min="0" max="15" step="0.5" [ngModel]="getField('regime','hysteresis_pct')"
                     (ngModelChange)="setField('regime','hysteresis_pct',$event)">
            </div>
          </div>
        </div>
      </details>

      <!-- Position & sizing -->
      <details class="adv">
        <summary>
          <span class="left"><span class="arrow">\u25B6</span><strong>Position &amp; sizing</strong> <span class="sub-count">3 controls</span></span>
          <button class="reset" (click)="$event.preventDefault(); resetSection('position')">\u21BB Reset section</button>
        </summary>
        <div class="adv-body">
          <div class="field">
            <div class="field-head"><div class="name">Allocation USD</div><div class="value-display">\${{ getField('position','allocation_usd') | number }}</div></div>
            <div class="field-help">Total capital pool the bot trades with. Sane range: $500\u2013$20000.</div>
            <div class="field-control">
              <input type="range" min="500" max="20000" step="250" [value]="getField('position','allocation_usd')"
                     (input)="setField('position','allocation_usd',+$any($event.target).value)">
              <input type="number" min="500" max="20000" step="250" [ngModel]="getField('position','allocation_usd')"
                     (ngModelChange)="setField('position','allocation_usd',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">Top N to buy</div><div class="value-display">{{ getField('position','top_n') }}</div></div>
            <div class="field-help">How many top-ranked candidates to buy each entry tick. Sane range: 1\u20135.</div>
            <div class="field-control">
              <input type="range" min="1" max="5" [value]="getField('position','top_n')"
                     (input)="setField('position','top_n',+$any($event.target).value)">
              <input type="number" min="1" max="5" [ngModel]="getField('position','top_n')"
                     (ngModelChange)="setField('position','top_n',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">Rebalance interval (hours)</div><div class="value-display">{{ getField('position','rebal_hours') }}h</div></div>
            <div class="field-help">Hours between full rebalance/rotation checks. Sane range: 24\u2013336.</div>
            <div class="field-control">
              <input type="range" min="24" max="336" [value]="getField('position','rebal_hours')"
                     (input)="setField('position','rebal_hours',+$any($event.target).value)">
              <input type="number" min="24" max="336" [ngModel]="getField('position','rebal_hours')"
                     (ngModelChange)="setField('position','rebal_hours',$event)">
            </div>
          </div>
        </div>
      </details>

      <!-- Universe -->
      <details class="adv">
        <summary>
          <span class="left"><span class="arrow">\u25B6</span><strong>Universe</strong> <span class="sub-count">2 controls</span></span>
          <button class="reset" (click)="$event.preventDefault(); resetSection('universe')">\u21BB Reset section</button>
        </summary>
        <div class="adv-body">
          <div class="field">
            <div class="field-head"><div class="name">Min price ($)</div><div class="value-display">\${{ getField('universe','min_price') }}</div></div>
            <div class="field-help">Don't trade pairs priced below this \u2014 too noisy for reliable signals. Sane range: $0.001\u2013$1.</div>
            <div class="field-control">
              <input type="number" min="0" max="1" step="0.001" [ngModel]="getField('universe','min_price')"
                     (ngModelChange)="setField('universe','min_price',$event)">
            </div>
          </div>
          <div class="field">
            <div class="field-head"><div class="name">Blacklist</div>
              <div class="value-display neg">{{ getBlacklist().length }} pair{{ getBlacklist().length !== 1 ? 's' : '' }}</div></div>
            <div class="field-help">Pairs that will never be entered. (Also editable in Simple view.)</div>
            <div class="chip-input">
              @for (pair of getBlacklist(); track pair) {
                <span class="chip">{{ pair }} <button (click)="removeChip(pair)" [disabled]="isBuiltin()">\xD7</button></span>
              }
              <input type="text" placeholder="add pair (press Enter)\u2026"
                     [(ngModel)]="blacklistInput"
                     (keydown)="onChipKeydown($event)"
                     [disabled]="isBuiltin()">
            </div>
          </div>
        </div>
      </details>

    </div>
  }

  } <!-- end @if !loading -->
</div>

<!-- STICKY FOOTER -->
<div class="footer">
  <div class="footer-inner">
    <div class="status-pill">
      <span class="dot"></span>
      <span>{{ activeStrategyMeta()?.active ? ('Active: ' + (activeStrategyMeta()?.active || '')) : 'Strategy loaded' }}</span>
    </div>
    <div class="actions">
      <button class="cancel" (click)="backToDashboard()">Cancel</button>
      <button class="apply" [disabled]="!modified() || applying()" (click)="applyChanges()">
        {{ applying() ? 'Applying\u2026' : 'Apply changes' }}
      </button>
    </div>
  </div>
</div>

<!-- TOAST -->
@if (toast()) {
  <div class="toast">
    <span class="icon ok">\u2713</span>{{ toast() }}
  </div>
}

<!-- ============ MODALS ============ -->

<!-- Save (overwrite) -->
@if (showSaveModal()) {
  <div class="modal-backdrop" (click)="showSaveModal.set(false)">
    <div class="modal" (click)="$event.stopPropagation()">
      <h3>Update "{{ profileName() }}"?</h3>
      <p>This will replace the saved values for this favorite with your current tweaks. The previous values cannot be recovered.</p>
      <div class="diff-list">
        @for (d of diffList(); track d.path) {
          <div>{{ d.path }} &nbsp; {{ d.old | json }} <span class="arrow">\u2192</span> {{ d.new | json }}</div>
        }
        @if (diffList().length === 0) {
          <div>No changes</div>
        }
      </div>
      <div class="modal-actions">
        <button (click)="showSaveModal.set(false)">Cancel</button>
        <button class="primary" [disabled]="saving()" (click)="confirmSave()">{{ saving() ? 'Saving\u2026' : 'Update' }}</button>
      </div>
    </div>
  </div>
}

<!-- Save as new -->
@if (showSaveAsModal()) {
  <div class="modal-backdrop" (click)="showSaveAsModal.set(false)">
    <div class="modal" (click)="$event.stopPropagation()">
      <h3>Save current settings as a new favorite</h3>
      <p>Capture all settings as a named profile you can return to later.</p>
      <label>Name</label>
      <input type="text" [ngModel]="newProfileName()" (ngModelChange)="newProfileName.set($event)" placeholder="e.g. My aggressive tweak" autofocus>
      <label>Description (optional)</label>
      <textarea [ngModel]="newProfileDescription()" (ngModelChange)="newProfileDescription.set($event)" placeholder="Notes about what this profile is for\u2026"></textarea>
      <div class="modal-actions">
        <button (click)="showSaveAsModal.set(false)">Cancel</button>
        <button class="primary" [disabled]="saving() || !newProfileName().trim()" (click)="confirmSaveAs()">{{ saving() ? 'Saving\u2026' : 'Save' }}</button>
      </div>
    </div>
  </div>
}

<!-- Delete -->
@if (showDeleteModal()) {
  <div class="modal-backdrop" (click)="showDeleteModal.set(false)">
    <div class="modal" (click)="$event.stopPropagation()">
      <h3>Permanently delete "{{ profileName() }}"?</h3>
      <p>This action can't be undone. If you want to save the values somewhere else first, click Cancel and use "Save as new".</p>
      <div class="modal-actions">
        <button (click)="showDeleteModal.set(false)">Cancel</button>
        <button class="danger" (click)="confirmDelete()">Delete</button>
      </div>
    </div>
  </div>
}

<!-- Revert -->
@if (showRevertModal()) {
  <div class="modal-backdrop" (click)="showRevertModal.set(false)">
    <div class="modal" (click)="$event.stopPropagation()">
      <h3>Revert all unsaved tweaks?</h3>
      <p>You'll go back to the last saved version of <strong>{{ profileName() }}</strong>. This affects <strong>{{ changeCount() }}</strong> change(s) you haven't applied or saved yet.</p>
      <div class="diff-list">
        @for (d of diffList(); track d.path) {
          <div>{{ d.path }} &nbsp; <span style="color:var(--accent)">{{ d.new | json }}</span> <span class="arrow">\u2192</span> {{ d.old | json }} <span class="saved-label">(saved)</span></div>
        }
      </div>
      <p class="small-note">Tweaks can't be recovered after revert. If you want to keep them, click Cancel and use "Save as new" first.</p>
      <div class="modal-actions">
        <button (click)="showRevertModal.set(false)">Cancel</button>
        <button class="primary" (click)="confirmRevert()">Revert</button>
      </div>
    </div>
  </div>
}

<!-- Discard changes -->
@if (showDiscardModal()) {
  <div class="modal-backdrop" (click)="cancelDiscard()">
    <div class="modal" (click)="$event.stopPropagation()">
      <h3>Discard unsaved changes?</h3>
      <p>You have modified <strong>{{ profileName() }}</strong> ({{ changeCount() }} change{{ changeCount() !== 1 ? 's' : '' }}). These tweaks haven't been saved or applied yet.</p>
      <div class="modal-actions">
        <button (click)="cancelDiscard()">Keep editing</button>
        <button class="danger" (click)="confirmDiscard()">Discard</button>
      </div>
    </div>
  </div>
}
`, styles: ['/* src/app/components/momentum-strategy/momentum-strategy.component.css */\n:host {\n  --bg: #0f1117;\n  --panel: rgba(255,255,255,0.03);\n  --panel-2: rgba(255,255,255,0.05);\n  --border: rgba(255,255,255,0.08);\n  --border-strong: rgba(255,255,255,0.16);\n  --text: #e2e8f0;\n  --subtext: #94a3b8;\n  --muted: #64748b;\n  --accent: #38bdf8;\n  --pos: #4ade80;\n  --neg: #f87171;\n  --warn: #f59e0b;\n  --upgrade: rgba(56,189,248,0.13);\n  --upgrade-border: rgba(56,189,248,0.45);\n  display: block;\n  background: #0f1117;\n  color: #e2e8f0;\n  font-family:\n    -apple-system,\n    BlinkMacSystemFont,\n    "Segoe UI",\n    Roboto,\n    Oxygen,\n    Ubuntu,\n    sans-serif;\n  font-size: 14px;\n  line-height: 1.5;\n  min-height: 100vh;\n}\n* {\n  box-sizing: border-box;\n}\na {\n  color: var(--accent);\n  text-decoration: none;\n}\n.page-shell {\n  max-width: 1100px;\n  margin: 0 auto;\n  padding: 24px;\n  padding-bottom: 120px;\n}\n.loading-state {\n  color: var(--subtext);\n  text-align: center;\n  padding: 60px 0;\n}\n.topbar {\n  display: flex;\n  justify-content: space-between;\n  align-items: center;\n  padding-bottom: 18px;\n  border-bottom: 1px solid var(--border);\n  margin-bottom: 24px;\n}\n.topbar h1 {\n  font-size: 20px;\n  font-weight: 700;\n  margin: 0;\n}\n.topbar h1 .accent {\n  color: var(--accent);\n  margin-right: 8px;\n}\n.topbar .meta {\n  font-size: 12px;\n  color: var(--subtext);\n  margin-top: 2px;\n}\n.close-btn {\n  background: none;\n  border: 1px solid var(--border-strong);\n  color: var(--text);\n  padding: 6px 14px;\n  border-radius: 6px;\n  font-size: 12px;\n  cursor: pointer;\n}\n.close-btn:hover {\n  background: rgba(255, 255, 255, 0.05);\n}\n.upgrade {\n  background: var(--upgrade);\n  border: 1px solid var(--upgrade-border);\n  border-radius: 10px;\n  padding: 16px 18px;\n  margin-bottom: 22px;\n}\n.upgrade-head {\n  display: flex;\n  justify-content: space-between;\n  align-items: center;\n  gap: 12px;\n}\n.upgrade-head .title {\n  font-size: 14px;\n  font-weight: 600;\n}\n.meta-inline {\n  font-size: 12px;\n  color: var(--subtext);\n  font-weight: 400;\n  margin-left: 6px;\n}\n.upgrade-body {\n  margin-top: 10px;\n}\n.upgrade-changes {\n  margin-top: 8px;\n}\n.upgrade-change {\n  display: grid;\n  grid-template-columns: 1fr auto;\n  gap: 8px;\n  padding: 8px 10px;\n  background: rgba(0, 0, 0, 0.18);\n  border-radius: 6px;\n  margin-bottom: 4px;\n  font-size: 13px;\n}\n.upgrade-change .body .label {\n  font-weight: 600;\n}\n.upgrade-change .body .why {\n  font-size: 12px;\n  color: var(--subtext);\n}\n.upgrade-change .delta {\n  font-family:\n    ui-monospace,\n    SFMono-Regular,\n    Menlo,\n    Monaco,\n    monospace;\n  font-size: 12px;\n  color: var(--accent);\n  white-space: nowrap;\n  align-self: center;\n}\n.upgrade-cta {\n  display: flex;\n  gap: 8px;\n  flex-wrap: wrap;\n  align-items: center;\n  margin-top: 12px;\n}\n.upgrade-cta button {\n  font-size: 12px;\n  padding: 6px 12px;\n  border-radius: 6px;\n  cursor: pointer;\n  border: 1px solid var(--border-strong);\n  background: rgba(255, 255, 255, 0.03);\n  color: var(--text);\n}\n.upgrade-cta button:hover {\n  filter: brightness(1.08);\n}\n.toggle {\n  background: none;\n  border: none;\n  color: var(--subtext);\n  cursor: pointer;\n  font-size: 12px;\n}\n.profile-bar {\n  display: flex;\n  align-items: flex-end;\n  gap: 12px;\n  padding: 14px 16px;\n  background: var(--panel);\n  border: 1px solid var(--border);\n  border-radius: 10px;\n  margin-bottom: 18px;\n  flex-wrap: wrap;\n}\n.bar-label {\n  font-size: 12px;\n  color: var(--subtext);\n  text-transform: uppercase;\n  letter-spacing: 0.05em;\n  margin-bottom: 6px;\n}\n.profile-row {\n  display: flex;\n  gap: 8px;\n  align-items: center;\n}\n.profile-bar select {\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  color: var(--text);\n  padding: 8px 12px;\n  border-radius: 6px;\n  font-size: 14px;\n  min-width: 260px;\n}\n.modified-tag {\n  color: var(--warn);\n  font-size: 12px;\n  font-weight: 600;\n}\n.revert-btn {\n  background: rgba(245, 158, 11, 0.15);\n  border: 1px solid rgba(245, 158, 11, 0.45);\n  color: var(--warn);\n  padding: 4px 10px;\n  border-radius: 4px;\n  font-size: 12px;\n  font-weight: 600;\n  cursor: pointer;\n}\n.revert-btn:hover {\n  filter: brightness(1.15);\n}\n.revert-btn .count {\n  background: rgba(245, 158, 11, 0.25);\n  padding: 0 5px;\n  border-radius: 999px;\n  margin-left: 4px;\n  font-size: 10px;\n}\n.spacer {\n  flex: 1 1 auto;\n}\n.profile-bar button {\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  color: var(--text);\n  padding: 7px 14px;\n  border-radius: 6px;\n  font-size: 13px;\n  cursor: pointer;\n}\n.profile-bar button.danger {\n  color: var(--neg);\n  border-color: rgba(248, 113, 113, 0.4);\n}\n.profile-bar button:disabled {\n  opacity: 0.4;\n  cursor: not-allowed;\n}\n.profile-bar button:hover:not(:disabled) {\n  filter: brightness(1.15);\n}\n.lock-banner {\n  background: rgba(56, 189, 248, 0.10);\n  border: 1px solid rgba(56, 189, 248, 0.4);\n  border-radius: 10px;\n  padding: 14px 18px;\n  margin-bottom: 18px;\n  display: flex;\n  align-items: center;\n  gap: 14px;\n}\n.lock-banner .icon {\n  font-size: 22px;\n}\n.lock-banner .body {\n  flex: 1;\n}\n.lock-banner .body .title {\n  font-size: 13px;\n  font-weight: 600;\n  margin-bottom: 2px;\n}\n.lock-banner .body .why {\n  font-size: 12px;\n  color: var(--subtext);\n}\n.lock-banner > button {\n  background: var(--accent);\n  color: #062032;\n  border: 1px solid var(--accent);\n  padding: 8px 16px;\n  border-radius: 6px;\n  font-size: 13px;\n  font-weight: 600;\n  cursor: pointer;\n  white-space: nowrap;\n}\n.lock-banner > button:hover {\n  filter: brightness(1.08);\n}\n.tabs {\n  display: inline-flex;\n  background: var(--panel);\n  border: 1px solid var(--border);\n  border-radius: 8px;\n  padding: 3px;\n  margin-bottom: 18px;\n  gap: 0;\n}\n.tabs button {\n  background: transparent;\n  border: none;\n  color: var(--subtext);\n  padding: 8px 22px;\n  font-size: 13px;\n  font-weight: 600;\n  border-radius: 6px;\n  cursor: pointer;\n}\n.tabs button.active {\n  background: rgba(56, 189, 248, 0.18);\n  color: var(--accent);\n}\nsection.panel {\n  background: var(--panel);\n  border: 1px solid var(--border);\n  border-radius: 10px;\n  padding: 18px 20px;\n  margin-bottom: 16px;\n}\nsection.panel h2 {\n  font-size: 14px;\n  margin: 0 0 6px;\n  display: flex;\n  align-items: center;\n  gap: 8px;\n}\n.num {\n  background: rgba(56, 189, 248, 0.15);\n  color: var(--accent);\n  font-size: 11px;\n  padding: 2px 6px;\n  border-radius: 999px;\n  font-weight: 600;\n}\n.help {\n  font-size: 12px;\n  color: var(--subtext);\n  margin-bottom: 12px;\n}\n.field {\n  padding: 14px 0;\n  border-bottom: 1px solid rgba(255, 255, 255, 0.04);\n}\n.field:last-child {\n  border-bottom: none;\n}\n.field-head {\n  display: flex;\n  justify-content: space-between;\n  align-items: center;\n  gap: 12px;\n  margin-bottom: 6px;\n}\n.field-head .name {\n  font-size: 13px;\n  font-weight: 600;\n}\n.help-icon {\n  color: var(--subtext);\n  margin-left: 6px;\n  cursor: help;\n  font-size: 11px;\n}\n.value-display {\n  font-family:\n    ui-monospace,\n    SFMono-Regular,\n    Menlo,\n    Monaco,\n    monospace;\n  font-size: 13px;\n  color: var(--accent);\n  font-weight: 600;\n}\n.value-display.neg {\n  color: var(--neg);\n}\n.field-help {\n  font-size: 12px;\n  color: var(--subtext);\n  margin-bottom: 10px;\n}\n.field-control {\n  display: flex;\n  align-items: center;\n  gap: 12px;\n}\n.field-control input[type=range] {\n  flex: 1;\n  accent-color: var(--accent);\n}\n.field-control input[type=number] {\n  width: 90px;\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  color: var(--text);\n  padding: 6px 10px;\n  border-radius: 6px;\n  font-family: ui-monospace, monospace;\n  font-size: 13px;\n}\n.field-control select {\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  color: var(--text);\n  padding: 6px 10px;\n  border-radius: 6px;\n  font-size: 13px;\n}\n.stepped-slider {\n  display: flex;\n  flex-direction: column;\n  gap: 8px;\n}\n.stepped-slider input[type=range] {\n  accent-color: var(--accent);\n  width: 100%;\n}\n.ticks {\n  display: flex;\n  justify-content: space-between;\n  font-size: 11px;\n  color: var(--muted);\n}\n.ticks span.active {\n  color: var(--accent);\n  font-weight: 600;\n}\n.preset-readout {\n  margin-top: 14px;\n  padding: 12px 14px;\n  background: rgba(0, 0, 0, 0.18);\n  border: 1px solid var(--border);\n  border-radius: 8px;\n  font-size: 12px;\n}\n.readout-head {\n  color: var(--subtext);\n  margin-bottom: 8px;\n  display: flex;\n  justify-content: space-between;\n  align-items: center;\n}\n.readout-head strong {\n  color: var(--accent);\n}\n.toggle-table {\n  background: none;\n  border: none;\n  color: var(--accent);\n  cursor: pointer;\n  font-size: 12px;\n  padding: 0;\n}\n.toggle-table:hover {\n  text-decoration: underline;\n}\n.values {\n  display: flex;\n  flex-wrap: wrap;\n  gap: 8px 16px;\n  font-family:\n    ui-monospace,\n    SFMono-Regular,\n    Menlo,\n    Monaco,\n    monospace;\n}\n.kv .k {\n  color: var(--subtext);\n  margin-right: 4px;\n}\n.kv .v {\n  color: var(--accent);\n  font-weight: 600;\n}\n.compare-table {\n  margin-top: 12px;\n  overflow-x: auto;\n  border: 1px solid var(--border);\n  border-radius: 8px;\n}\n.compare-table table {\n  border-collapse: collapse;\n  width: 100%;\n  font-size: 12px;\n  font-family:\n    ui-monospace,\n    SFMono-Regular,\n    Menlo,\n    Monaco,\n    monospace;\n}\n.compare-table th,\n.compare-table td {\n  padding: 8px 10px;\n  border-bottom: 1px solid var(--border);\n  text-align: center;\n  white-space: nowrap;\n}\n.compare-table th {\n  background: rgba(0, 0, 0, 0.25);\n  color: var(--subtext);\n  font-weight: 600;\n  font-size: 11px;\n  text-transform: uppercase;\n  letter-spacing: 0.04em;\n}\n.compare-table td:first-child,\n.compare-table th:first-child {\n  text-align: left;\n  color: var(--subtext);\n}\n.compare-table tr:last-child td {\n  border-bottom: none;\n}\n.compare-table .col-active {\n  background: rgba(56, 189, 248, 0.12);\n  color: var(--accent);\n  font-weight: 700;\n}\n.compare-table th.col-active {\n  background: rgba(56, 189, 248, 0.22);\n}\n.chip-input {\n  display: flex;\n  flex-wrap: wrap;\n  gap: 6px;\n  padding: 8px;\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  border-radius: 6px;\n  min-height: 40px;\n  align-items: center;\n}\n.chip {\n  display: inline-flex;\n  align-items: center;\n  gap: 6px;\n  background: rgba(248, 113, 113, 0.15);\n  color: var(--neg);\n  border: 1px solid rgba(248, 113, 113, 0.4);\n  padding: 4px 10px;\n  border-radius: 999px;\n  font-size: 12px;\n}\n.chip button {\n  background: none;\n  border: none;\n  color: var(--neg);\n  cursor: pointer;\n  padding: 0 0 0 4px;\n  font-size: 14px;\n  line-height: 1;\n}\n.chip-input input {\n  background: transparent;\n  border: none;\n  color: var(--text);\n  flex: 1;\n  font-size: 13px;\n  min-width: 120px;\n  outline: none;\n}\n.day-buttons {\n  display: flex;\n  gap: 6px;\n  flex-wrap: wrap;\n}\n.day-buttons button {\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  color: var(--subtext);\n  padding: 6px 14px;\n  border-radius: 6px;\n  font-size: 12px;\n  cursor: pointer;\n  font-weight: 600;\n}\n.day-buttons button.active {\n  background: rgba(245, 158, 11, 0.18);\n  border-color: var(--warn);\n  color: var(--warn);\n}\n.day-buttons button:hover {\n  filter: brightness(1.15);\n}\n.toggle-switch {\n  position: relative;\n  display: inline-block;\n  width: 42px;\n  height: 24px;\n}\n.toggle-switch input {\n  opacity: 0;\n  width: 0;\n  height: 0;\n}\n.track {\n  position: absolute;\n  cursor: pointer;\n  inset: 0;\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  border-radius: 24px;\n  transition: 0.2s;\n}\n.track:before {\n  position: absolute;\n  content: "";\n  height: 18px;\n  width: 18px;\n  left: 2px;\n  top: 2px;\n  background: var(--subtext);\n  border-radius: 50%;\n  transition: 0.2s;\n}\n.toggle-switch input:checked + .track {\n  background: rgba(74, 222, 128, 0.2);\n  border-color: var(--pos);\n}\n.toggle-switch input:checked + .track:before {\n  transform: translateX(18px);\n  background: var(--pos);\n}\n.toggle-label {\n  margin-left: 8px;\n  font-size: 13px;\n  color: var(--subtext);\n}\n.on-label {\n  color: var(--pos);\n}\n.off-label {\n  color: var(--muted);\n}\ndetails.adv {\n  background: var(--panel);\n  border: 1px solid var(--border);\n  border-radius: 10px;\n  margin-bottom: 12px;\n  overflow: hidden;\n}\ndetails.adv summary {\n  padding: 14px 18px;\n  cursor: pointer;\n  display: flex;\n  justify-content: space-between;\n  align-items: center;\n  -webkit-user-select: none;\n  user-select: none;\n  list-style: none;\n}\ndetails.adv summary::-webkit-details-marker {\n  display: none;\n}\n.left {\n  display: flex;\n  align-items: center;\n  gap: 10px;\n}\n.arrow {\n  color: var(--subtext);\n  transition: 0.2s;\n}\ndetails.adv[open] summary .arrow {\n  transform: rotate(90deg);\n}\n.sub-count {\n  color: var(--subtext);\n  font-size: 12px;\n}\n.reset {\n  font-size: 11px;\n  color: var(--subtext);\n  cursor: pointer;\n  padding: 3px 8px;\n  border-radius: 4px;\n  border: 1px solid var(--border-strong);\n  background: var(--panel-2);\n}\n.reset:hover {\n  color: var(--text);\n}\n.adv-body {\n  padding: 0 18px 16px;\n}\n.tier-header {\n  border-bottom: 1px solid var(--border);\n  padding-bottom: 8px;\n  margin-bottom: 6px;\n}\n.tier-row {\n  display: grid;\n  grid-template-columns: 40px 1fr 1fr 28px;\n  gap: 8px;\n  align-items: center;\n  padding: 6px 0;\n}\n.tier-label {\n  font-size: 12px;\n  color: var(--subtext);\n}\n.tier-col-head {\n  font-size: 12px;\n  color: var(--subtext);\n}\n.tier-row input {\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  color: var(--text);\n  padding: 4px 8px;\n  border-radius: 4px;\n  font-family: monospace;\n  font-size: 12px;\n  width: 100%;\n}\n.x {\n  background: none;\n  border: none;\n  color: var(--neg);\n  cursor: pointer;\n  font-size: 16px;\n  line-height: 1;\n}\n.add-tier-row {\n  padding: 10px 0;\n}\n.add-tier-btn {\n  background: var(--panel-2);\n  border: 1px dashed var(--border-strong);\n  color: var(--subtext);\n  padding: 6px 14px;\n  border-radius: 6px;\n  cursor: pointer;\n  font-size: 13px;\n}\n.add-tier-btn:hover {\n  color: var(--text);\n}\n.footer {\n  position: fixed;\n  bottom: 0;\n  left: 0;\n  right: 0;\n  background: rgba(15, 17, 23, 0.95);\n  border-top: 1px solid var(--border);\n  padding: 14px 24px;\n  -webkit-backdrop-filter: blur(8px);\n  backdrop-filter: blur(8px);\n  z-index: 50;\n}\n.footer-inner {\n  max-width: 1100px;\n  margin: 0 auto;\n  display: flex;\n  justify-content: space-between;\n  align-items: center;\n  gap: 12px;\n  flex-wrap: wrap;\n}\n.status-pill {\n  font-size: 12px;\n  color: var(--subtext);\n  display: flex;\n  align-items: center;\n  gap: 6px;\n}\n.status-pill .dot {\n  width: 7px;\n  height: 7px;\n  border-radius: 50%;\n  background: var(--pos);\n}\n.actions {\n  display: flex;\n  gap: 10px;\n}\n.actions button {\n  padding: 9px 22px;\n  border-radius: 6px;\n  font-size: 14px;\n  font-weight: 600;\n  cursor: pointer;\n  border: 1px solid var(--border-strong);\n  background: var(--panel-2);\n  color: var(--text);\n}\n.cancel {\n  background: transparent !important;\n}\n.apply {\n  background: var(--accent) !important;\n  color: #062032 !important;\n  border-color: var(--accent) !important;\n}\n.actions button:disabled {\n  opacity: 0.5;\n  cursor: not-allowed;\n}\n.actions button:hover:not(:disabled) {\n  filter: brightness(1.1);\n}\n.modal-backdrop {\n  position: fixed;\n  inset: 0;\n  background: rgba(0, 0, 0, 0.6);\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  z-index: 100;\n  padding: 16px;\n}\n.modal {\n  background: #1a1d28;\n  border: 1px solid var(--border-strong);\n  border-radius: 12px;\n  padding: 24px;\n  max-width: 560px;\n  width: 100%;\n  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);\n}\n.modal h3 {\n  margin-top: 0;\n  font-size: 17px;\n  color: var(--text);\n}\n.modal p {\n  color: var(--subtext);\n  font-size: 13px;\n}\n.modal label {\n  display: block;\n  font-size: 12px;\n  color: var(--subtext);\n  margin: 14px 0 6px;\n}\n.modal input[type=text],\n.modal textarea {\n  width: 100%;\n  background: var(--panel-2);\n  border: 1px solid var(--border-strong);\n  color: var(--text);\n  padding: 8px 12px;\n  border-radius: 6px;\n  font-size: 13px;\n  font-family: inherit;\n}\n.modal textarea {\n  resize: vertical;\n  min-height: 60px;\n}\n.diff-list {\n  background: rgba(0, 0, 0, 0.3);\n  border-radius: 6px;\n  padding: 10px 12px;\n  font-family: ui-monospace, monospace;\n  font-size: 12px;\n  margin: 10px 0;\n  max-height: 200px;\n  overflow-y: auto;\n  color: var(--text);\n}\n.diff-list div {\n  padding: 2px 0;\n}\n.arrow {\n  color: var(--accent);\n}\n.saved-label {\n  color: var(--subtext);\n  font-size: 11px;\n  margin-left: 4px;\n}\n.small-note {\n  font-size: 12px;\n  color: var(--subtext);\n  margin: 6px 0 0;\n}\n.modal-actions {\n  display: flex;\n  gap: 10px;\n  justify-content: flex-end;\n  margin-top: 18px;\n}\n.modal-actions button {\n  padding: 8px 18px;\n  border-radius: 6px;\n  font-size: 13px;\n  cursor: pointer;\n  border: 1px solid var(--border-strong);\n  background: var(--panel-2);\n  color: var(--text);\n}\n.modal-actions .primary {\n  background: var(--accent);\n  color: #062032;\n  border-color: var(--accent);\n  font-weight: 600;\n}\n.modal-actions .danger {\n  background: rgba(248, 113, 113, 0.2);\n  border-color: var(--neg);\n  color: var(--neg);\n  font-weight: 600;\n}\n.modal-actions button:disabled {\n  opacity: 0.5;\n  cursor: not-allowed;\n}\n.toast {\n  position: fixed;\n  bottom: 88px;\n  left: 50%;\n  transform: translateX(-50%);\n  background: rgba(0, 0, 0, 0.8);\n  color: var(--text);\n  padding: 10px 18px;\n  border-radius: 8px;\n  font-size: 13px;\n  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.4);\n  border: 1px solid var(--border-strong);\n  z-index: 80;\n  white-space: nowrap;\n}\n.icon.ok {\n  color: var(--pos);\n  margin-right: 8px;\n}\n.read-only input[type=range],\n.read-only input[type=number],\n.read-only input[type=text],\n.read-only select,\n.read-only .day-buttons button,\n.read-only .toggle-switch input,\n.read-only .chip,\n.read-only .chip-input,\n.read-only .chip-input input {\n  pointer-events: none;\n  opacity: 0.65;\n}\n.read-only .field-control,\n.read-only .stepped-slider,\n.read-only .day-buttons,\n.read-only .toggle-switch,\n.read-only .tier-row,\n.read-only .add-tier-btn,\n.read-only .reset {\n  pointer-events: none;\n  opacity: 0.7;\n}\n/*# sourceMappingURL=momentum-strategy.component.css.map */\n'] }]
  }], null, null);
})();
(() => {
  (typeof ngDevMode === "undefined" || ngDevMode) && \u0275setClassDebugInfo(MomentumStrategyComponent, { className: "MomentumStrategyComponent", filePath: "src/app/components/momentum-strategy/momentum-strategy.component.ts", lineNumber: 67 });
})();
export {
  MomentumStrategyComponent
};
//# sourceMappingURL=chunk-ZBNIRSTJ.js.map
