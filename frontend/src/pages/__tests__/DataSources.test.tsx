import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DataSources } from "../DataSources";
import type { DataSourceSettings } from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  getDataSourceSettings: vi.fn(),
  updateDataSourceSettings: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: apiMock,
}));

const baseSettings: DataSourceSettings = {
  tushare_token_configured: false,
  tushare_token_hint: null,
  baostock_supported: true,
  baostock_installed: true,
  baostock_message: "BaoStock 加载器可用，Python 包已安装。",
  env_path: "/Users/colin/Documents/Vibe-Trading/agent/.env",
};

describe("DataSources page", () => {
  beforeEach(() => {
    apiMock.getDataSourceSettings.mockReset();
    apiMock.updateDataSourceSettings.mockReset();
  });

  it("renders the Chinese data-source workbench", async () => {
    apiMock.getDataSourceSettings.mockResolvedValueOnce(baseSettings);

    render(<DataSources />);

    expect(await screen.findByText("数据源设置")).toBeInTheDocument();
    expect(screen.getByText("A 股数据源与本地缓存")).toBeInTheDocument();
    expect(screen.getByText("免费 / 本地优先")).toBeInTheDocument();
    expect(screen.getByText("凭据管理")).toBeInTheDocument();
    expect(screen.getByText("安全边界")).toBeInTheDocument();
    expect(screen.getByText("模型调用沿用 Codex 登录态，不要求新增模型 API 凭据。")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "刷新状态" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "保存数据源设置" })).toBeInTheDocument();
  });

  it("saves a new Tushare token without showing the token value", async () => {
    apiMock.getDataSourceSettings.mockResolvedValueOnce(baseSettings);
    apiMock.updateDataSourceSettings.mockResolvedValueOnce({
      ...baseSettings,
      tushare_token_configured: true,
      tushare_token_hint: "已保存，明文不会回显。",
    });

    render(<DataSources />);

    await screen.findByText("凭据管理");
    fireEvent.change(screen.getByLabelText("Tushare token"), { target: { value: "ts-demo-secret" } });
    fireEvent.click(screen.getByRole("button", { name: "保存数据源设置" }));

    await waitFor(() => expect(apiMock.updateDataSourceSettings).toHaveBeenCalledWith({
      tushare_token: "ts-demo-secret",
      clear_tushare_token: false,
    }));
    expect(await screen.findByText("数据源设置已保存。")).toBeInTheDocument();
    expect(screen.queryByText("ts-demo-secret")).not.toBeInTheDocument();
    expect(screen.getByText("当前已保存")).toBeInTheDocument();
  });

  it("clears a saved Tushare token explicitly", async () => {
    apiMock.getDataSourceSettings.mockResolvedValueOnce({
      ...baseSettings,
      tushare_token_configured: true,
      tushare_token_hint: "已配置",
    });
    apiMock.updateDataSourceSettings.mockResolvedValueOnce(baseSettings);

    render(<DataSources />);

    await screen.findByText("当前已保存");
    fireEvent.click(screen.getByLabelText("清除已保存的 Tushare token"));

    expect(screen.getByLabelText("Tushare token")).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "保存数据源设置" }));

    await waitFor(() => expect(apiMock.updateDataSourceSettings).toHaveBeenCalledWith({
      tushare_token: undefined,
      clear_tushare_token: true,
    }));
    expect(await screen.findByText("当前未保存")).toBeInTheDocument();
  });

  it("refreshes local data-source status", async () => {
    apiMock.getDataSourceSettings
      .mockResolvedValueOnce(baseSettings)
      .mockResolvedValueOnce({ ...baseSettings, tushare_token_configured: true });

    render(<DataSources />);

    await screen.findByText("当前未保存");
    fireEvent.click(screen.getByRole("button", { name: "刷新状态" }));

    await waitFor(() => expect(apiMock.getDataSourceSettings).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("当前已保存")).toBeInTheDocument();
  });

  it("shows Chinese load and save errors", async () => {
    apiMock.getDataSourceSettings.mockRejectedValueOnce(new Error("本地服务未启动"));

    render(<DataSources />);

    expect(await screen.findByText("数据源状态暂不可用")).toBeInTheDocument();
    expect(screen.getByText("本地服务未启动")).toBeInTheDocument();
  });
});
