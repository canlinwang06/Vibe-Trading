import { useTranslation } from "react-i18next";
import { useEffect, useState } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import {
  BriefcaseBusiness,
  ChevronsLeft,
  ChevronsRight,
  ClipboardList,
  Gauge,
  Languages,
  Moon,
  Sun,
} from "lucide-react";
import { ASHARE_NAV_ITEMS } from "@/config/ashareNavigation";
import { cn } from "@/lib/utils";
import { useDarkMode } from "@/hooks/useDarkMode";
import { useAgentStore } from "@/stores/agent";
import { ConnectionBanner } from "@/components/layout/ConnectionBanner";

// Bump on each release; one place keeps the footer in sync with package.json.
const APP_VERSION = "v0.1.9";

export function Layout() {
  const { t, i18n: i18nHook } = useTranslation();

  const iconByRoute = {
    "/advisor/today": Gauge,
    "/advisor/stocks": BriefcaseBusiness,
    "/advisor/memory": ClipboardList,
  };
  const { pathname } = useLocation();
  const { dark, toggle } = useDarkMode();
  const sseStatus = useAgentStore(s => s.sseStatus);
  const sseRetryAttempt = useAgentStore(s => s.sseRetryAttempt);
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem("qa-sidebar") === "collapsed");

  useEffect(() => {
    localStorage.setItem("qa-sidebar", collapsed ? "collapsed" : "expanded");
  }, [collapsed]);

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <aside className={cn(
        "border-r bg-card flex flex-col shrink-0 transition-all duration-200",
        collapsed ? "w-12" : "w-64"
      )}>
        {/* Brand */}
        <div className={cn("border-b", collapsed ? "p-2 flex justify-center" : "p-4")}>
          <Link to="/advisor/today" className={cn("flex items-center font-bold text-base tracking-tight", collapsed ? "justify-center" : "gap-2")}>
            <BriefcaseBusiness className="h-5 w-5 text-primary shrink-0" />
            {!collapsed && <span className="truncate">{t("layout.productName")}</span>}
          </Link>
        </div>

        {/* Nav */}
        <nav className={cn("space-y-0.5 overflow-y-auto", collapsed ? "p-1" : "p-2")}>
          {ASHARE_NAV_ITEMS.map(({ to, labelKey }) => {
            const Icon = iconByRoute[to];
            const text = t(labelKey);
            return (
              <Link
                key={to}
                to={to}
                className={cn(
                  "flex items-center rounded-md text-sm transition-colors",
                  collapsed ? "justify-center p-2" : "gap-3 px-3 py-2",
                  pathname.startsWith(to)
                    ? "bg-primary/10 text-primary font-medium"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
                title={collapsed ? text : undefined}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                {!collapsed && text}
              </Link>
            );
          })}
        </nav>

        {/* Spacer when collapsed */}
        <div className="flex-1" />

        {/* Footer */}
        <div className={cn("border-t", collapsed ? "p-1 flex flex-col items-center gap-1" : "p-3 space-y-2")}>
          {collapsed ? (
            <>
              <button onClick={toggle} className="p-1.5 text-muted-foreground hover:text-foreground rounded transition-colors" title={dark ? t('layout.light') : t('layout.dark')}>
                {dark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
              </button>
              <button onClick={() => setCollapsed(false)} className="p-1.5 text-muted-foreground hover:text-foreground rounded transition-colors" title={t('layout.expand')}>
                <ChevronsRight className="h-3.5 w-3.5" />
              </button>
            </>
          ) : (
            <>
              <div className="flex items-center justify-between">
                <button
                  onClick={toggle}
                  className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                >
                  {dark ? <Sun className="h-3.5 w-3.5" /> : <Moon className="h-3.5 w-3.5" />}
                  {dark ? t("layout.light") : t("layout.dark")}
                </button>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setCollapsed(true)}
                    className="p-1 text-muted-foreground hover:text-foreground rounded transition-colors"
                    title={t('layout.collapse')}
                  >
                    <ChevronsLeft className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <button
                  onClick={() => { i18nHook.changeLanguage(i18nHook.language === "zh-CN" ? "en" : "zh-CN"); }}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  title={t("layout.switchLanguage")}
                >
                  <Languages className="h-3.5 w-3.5" />
                  {t("layout.switchLanguage")}
                </button>
                <p className="text-xs text-muted-foreground/60">{APP_VERSION}</p>
              </div>
            </>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <ConnectionBanner status={sseStatus} retryAttempt={sseRetryAttempt} />
        <main className="flex-1 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
