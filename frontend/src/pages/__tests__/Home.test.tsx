import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Home } from "../Home";

describe("A-share dashboard home", () => {
  it("renders the Chinese A-share product shell", () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );

    expect(screen.getByText("A 股事件驱动策略驾驶舱")).toBeInTheDocument();
    expect(screen.getByText("事件记录库")).toBeInTheDocument();
    expect(screen.getByText("板块及股票分析")).toBeInTheDocument();
    expect(screen.getByText("策略实验室")).toBeInTheDocument();
    expect(screen.getByText("聚宽导出")).toBeInTheDocument();
    expect(screen.getByText("每日工作流")).toBeInTheDocument();
    expect(screen.getByText("核心研究链路已按“事件记录库”和“板块及股票分析”两层组织，策略输出保持研究与模拟边界。")).toBeInTheDocument();
  });

  it("does not render legacy multi-market examples", () => {
    const { container } = render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );

    expect(container.textContent).not.toMatch(/crypto|AAPL|BTC|options|美股|港股|加密货币|期权/i);
    expect(container.textContent).not.toMatch(/等待 PR|后续模块接入/);
    expect(container.textContent).not.toMatch(/事件雷达|板块雷达|事件反应|候选股票池/);
  });
});
