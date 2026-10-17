import { createBrowserRouter, type RouteObject } from "react-router";
import { Layout, NotFound, PageLoading, RouteError } from "./pages/Layout";

// Pages load on demand, so the first visit doesn't download every chart at once.
export const routes: RouteObject[] = [
  {
    element: <Layout />,
    errorElement: <RouteError />,
    hydrateFallbackElement: <PageLoading />,
    children: [
      { index: true, lazy: () => import("./pages/optimise/OptimisePage").then((m) => ({ Component: m.OptimisePage })) },
      { path: "runs/:jobId", lazy: () => import("./pages/RunningPage").then((m) => ({ Component: m.RunningPage })) },
      { path: "results/:resultId", lazy: () => import("./pages/results/ResultPage").then((m) => ({ Component: m.ResultPage })) },
      { path: "backtest", lazy: () => import("./pages/backtest/BacktestPage").then((m) => ({ Component: m.BacktestPage })) },
      { path: "backtest/:resultId", lazy: () => import("./pages/backtest/BacktestResultPage").then((m) => ({ Component: m.BacktestResultPage })) },
      { path: "data", lazy: () => import("./pages/data/DataPage").then((m) => ({ Component: m.DataPage })) },
      { path: "history", lazy: () => import("./pages/HistoryPage").then((m) => ({ Component: m.HistoryPage })) },
      { path: "research", lazy: () => import("./pages/research/ResearchPage").then((m) => ({ Component: m.ResearchPage })) },
      { path: "how", lazy: () => import("./pages/how/HowItWorksPage").then((m) => ({ Component: m.HowItWorksPage })) },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export const router = createBrowserRouter(routes);
