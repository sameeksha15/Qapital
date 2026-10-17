import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "@fontsource/libre-caslon-text/400.css";
import "@fontsource/libre-caslon-text/400-italic.css";
import "@fontsource/libre-caslon-text/700.css";
import "@fontsource/libre-franklin/400.css";
import "@fontsource/libre-franklin/500.css";
import "@fontsource/libre-franklin/600.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";
import { ConnectionProvider } from "./api/connection";
import { router } from "./router";
import { DraftProvider } from "./state/draft";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5 * 60 * 1000, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ConnectionProvider apiUrl={import.meta.env.VITE_API_URL || undefined}>
        <DraftProvider>
          <RouterProvider router={router} />
        </DraftProvider>
      </ConnectionProvider>
    </QueryClientProvider>
  </StrictMode>,
);
