import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import i18n from "@/i18n";
import { Layout } from "../Layout";

function renderLayout() {
  window.localStorage.setItem("qa-sidebar", "expanded");
  window.localStorage.setItem("i18nextLng", "zh-CN");
  i18n.changeLanguage("zh-CN");

  const router = createMemoryRouter([
    {
      element: <Layout />,
      children: [{ path: "/", element: <div>页面内容</div> }],
    },
  ]);
  return render(<RouterProvider router={router} />);
}

describe("Layout A-share navigation", () => {
  it("renders the PR-02 Chinese A-share navigation shell", () => {
    renderLayout();

    expect(screen.getByText("A 股策略中台")).toBeInTheDocument();
    for (const label of [
      "A 股驾驶舱",
      "事件雷达",
      "板块雷达",
      "事件反应",
      "候选股票池",
      "策略实验室",
      "回测结果",
      "风控组合",
      "交易计划",
      "聚宽导出",
      "每日工作流",
      "数据源设置",
      "系统设置",
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByRole("button", { name: "切换语言" })).toBeInTheDocument();
    expect(screen.queryByText("English")).not.toBeInTheDocument();
  });

  it("hides legacy generic trading routes from the sidebar", () => {
    renderLayout();

    expect(screen.queryByText("智能体")).not.toBeInTheDocument();
    expect(screen.queryByText("运行时")).not.toBeInTheDocument();
    expect(screen.queryByText("Alpha 动物园")).not.toBeInTheDocument();
    expect(screen.queryByText("相关性矩阵")).not.toBeInTheDocument();
    expect(screen.queryByText("Sessions")).not.toBeInTheDocument();
  });
});
