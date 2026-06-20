import zhCN from "@/i18n/locales/zh-CN.json";
import { ASHARE_NAV_ITEMS, ASHARE_NAV_LABELS_ZH } from "../ashareNavigation";

describe("A-share navigation", () => {
  it("contains the two-module A-share product shell entries in order", () => {
    const labels = ASHARE_NAV_ITEMS.map((item) => {
      const [, key] = item.labelKey.split(".");
      return zhCN.layout[key as keyof typeof zhCN.layout];
    });

    expect(labels).toEqual([...ASHARE_NAV_LABELS_ZH]);
    expect(ASHARE_NAV_ITEMS.map((item) => item.to)).toEqual([
      "/",
      "/event-records",
      "/sector-stock-analysis",
      "/strategy-lab",
      "/backtest-results",
      "/risk-portfolio",
      "/trade-plan",
      "/joinquant-export",
      "/strategy-lifecycle",
      "/daily-workflow",
      "/data-sources",
      "/settings",
    ]);
  });

  it("does not expose legacy multi-market navigation entries", () => {
    const text = ASHARE_NAV_ITEMS.map((item) => `${item.to} ${item.labelKey}`).join(" ");

    expect(text).not.toMatch(/agent|runtime|alpha|correlation|crypto|options|connector/i);
  });
});
