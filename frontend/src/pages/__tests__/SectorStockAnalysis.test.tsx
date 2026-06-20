import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SectorStockAnalysis } from "../SectorStockAnalysis";

describe("Sector and stock analysis page", () => {
  it("explains the analysis layer and keeps legacy drill-down links", () => {
    render(
      <MemoryRouter>
        <SectorStockAnalysis />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "板块及股票分析" })).toBeInTheDocument();
    expect(screen.getByText("基于事件记录库沉淀的数据，判断当前哪些板块正在升温。")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /板块雷达/ })).toHaveAttribute("href", "/sector-radar");
    expect(screen.getByRole("link", { name: /候选股票池/ })).toHaveAttribute("href", "/candidate-pool");
    expect(screen.getByRole("link", { name: /策略实验室/ })).toHaveAttribute("href", "/strategy-lab");
  });
});
