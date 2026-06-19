import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WelcomeScreen } from "../WelcomeScreen";

describe("WelcomeScreen", () => {
  const onExample = vi.fn();

  beforeEach(() => onExample.mockClear());

  it("renders the title", () => {
    render(<WelcomeScreen onExample={onExample} />);
    expect(screen.getByText("A 股事件驱动策略中台")).toBeInTheDocument();
  });

  it("renders capability chips", () => {
    render(<WelcomeScreen onExample={onExample} />);
    expect(screen.getByText("A 股事件研究")).toBeInTheDocument();
    expect(screen.getByText("交易计划草稿")).toBeInTheDocument();
    expect(screen.getByText("聚宽复制准备")).toBeInTheDocument();
  });

  it("renders example categories", () => {
    render(<WelcomeScreen onExample={onExample} />);
    expect(screen.getByText("A 股研究回测")).toBeInTheDocument();
    expect(screen.getByText("事件驱动研究")).toBeInTheDocument();
    expect(screen.getByText("研究协同")).toBeInTheDocument();
  });

  it("calls onExample with prompt when an example button is clicked", async () => {
    render(<WelcomeScreen onExample={onExample} />);
    const user = userEvent.setup();
    await user.click(screen.getByText("贵州茅台趋势回测"));
    expect(onExample).toHaveBeenCalledTimes(1);
    expect(onExample).toHaveBeenCalledWith(
      expect.stringContaining("600519.SH"),
    );
  });

  it("renders the helper text", () => {
    render(<WelcomeScreen onExample={onExample} />);
    expect(screen.getByText("输入一个 A 股研究任务即可开始。")).toBeInTheDocument();
    expect(screen.getByText("试试这些 A 股研究任务：")).toBeInTheDocument();
  });
});
