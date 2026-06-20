import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { EventRecords } from "../EventRecords";

describe("Event records page", () => {
  it("explains the objective record layer and keeps legacy drill-down links", () => {
    render(
      <MemoryRouter>
        <EventRecords />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "事件记录库" })).toBeInTheDocument();
    expect(screen.getByText("只记录事实、来源和事后影响，不直接给买入建议。")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /事件雷达/ })).toHaveAttribute("href", "/event-radar");
    expect(screen.getByRole("link", { name: /事件反应/ })).toHaveAttribute("href", "/event-reactions");
  });
});
