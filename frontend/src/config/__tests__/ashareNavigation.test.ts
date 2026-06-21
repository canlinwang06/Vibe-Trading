import zhCN from "@/i18n/locales/zh-CN.json";
import { ASHARE_NAV_ITEMS, ASHARE_NAV_LABELS_ZH } from "../ashareNavigation";

describe("A-share navigation", () => {
  it("contains only the current advisor display entries in order", () => {
    const labels = ASHARE_NAV_ITEMS.map((item) => {
      const [, key] = item.labelKey.split(".");
      return zhCN.layout[key as keyof typeof zhCN.layout];
    });

    expect(labels).toEqual([...ASHARE_NAV_LABELS_ZH]);
    expect(ASHARE_NAV_ITEMS.map((item) => item.to)).toEqual([
      "/advisor/today",
      "/advisor/stocks",
      "/advisor/memory",
    ]);
  });

  it("keeps legacy research, backtest, or settings entries hidden", () => {
    const text = ASHARE_NAV_ITEMS.map((item) => `${item.to} ${item.labelKey}`).join(" ");

    expect(text).not.toMatch(/dashboard|sector|strategy|backtest|risk|trade|joinquant|workflow|data|settings|agent|runtime|alpha|correlation|crypto|options|connector/i);
  });
});
