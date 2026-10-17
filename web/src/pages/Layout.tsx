import { useEffect } from "react";
import { isRouteErrorResponse, Link, Outlet, ScrollRestoration, useLocation, useNavigate, useNavigation, useRouteError } from "react-router";
import { useConnection } from "../api/connection";
import { useDataStatus } from "../api/queries";
import { Header } from "../components/Header";
import { ButtonLink, Container, Loading, Note } from "../components/ui";
import { APP_NAME, day } from "../lib/format";

/** Old #page addresses from the first version of the site. */
const OLD_ADDRESSES: Record<string, string> = { "#optimise": "/", "#research": "/research", "#how": "/how" };

export function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const navigation = useNavigation();

  useEffect(() => {
    const target = location.pathname === "/" ? OLD_ADDRESSES[location.hash] : undefined;
    if (target && target !== "/") navigate(target, { replace: true });
  }, [location, navigate]);

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded focus:bg-paper focus:px-3 focus:py-2 focus:text-ink">
        Skip to content
      </a>
      <Header />
      <main id="main" className="flex-1">
        {navigation.state === "loading" && navigation.location.pathname !== location.pathname
          ? <Container><Loading>Opening the page…</Loading></Container>
          : <Outlet />}
      </main>
      <Footer />
      <ScrollRestoration />
    </div>
  );
}

function Footer() {
  const { state } = useConnection();
  const status = useDataStatus();
  const snapshot = status.data?.snapshot;
  return (
    <footer className="border-t border-rule bg-paper-2/60">
      <Container className="flex flex-col gap-3 py-8 text-xs leading-relaxed text-muted sm:flex-row sm:justify-between">
        <p className="max-w-xl">
          {APP_NAME} is a research demonstration of quantum optimisation on real market data. It is not investment advice;
          past returns don't predict future ones.
        </p>
        <p className="sm:text-right">
          {snapshot ? <>Prices up to <Link to="/data" className="underline underline-offset-2 hover:text-ink">{day(snapshot.end)}</Link></> : "Prices loading"}
          {" · "}{state === "live" ? "live engine" : "saved runs"}
        </p>
      </Container>
    </footer>
  );
}

/** Shown while the first page of a visit loads. */
export function PageLoading() {
  return <Container><Loading>Opening the page…</Loading></Container>;
}

export function NotFound() {
  return (
    <Container className="py-20">
      <Note tone="warn" title="There's no page here">Check the address, or start from the optimiser.</Note>
      <ButtonLink to="/" variant="primary" arrow className="mt-8">Go to the optimiser</ButtonLink>
    </Container>
  );
}

export function RouteError() {
  const error = useRouteError();
  const message = isRouteErrorResponse(error) ? `${error.status} ${error.statusText}` : (error as Error)?.message ?? "Unknown error";
  return (
    <div className="flex min-h-screen flex-col">
      <Container className="py-20">
        <Note tone="bad" title="Something went wrong on this page">
          {message}. Reloading usually helps; if it doesn't, start again from the optimiser.
        </Note>
        <a href="/" className="mt-8 inline-block text-sm text-accent underline underline-offset-4">Go to the optimiser</a>
      </Container>
    </div>
  );
}
