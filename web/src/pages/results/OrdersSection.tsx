import { Fragment, useState } from "react";
import type { Allocation, FullResult } from "../../api/types";
import { ChevronIcon } from "../../components/icons";
import { Fact, Note, Section, Segmented, Td, Th, Ticker } from "../../components/ui";
import { money, percent, shortName } from "../../lib/format";

const SIZINGS = {
  equal: { label: "Equal money", note: "The same amount in each stock: what the optimiser's score assumes." },
  "lowest-risk": { label: "Lowest-risk split", note: "The same stocks, with the split that makes the whole portfolio swing least." },
} as const;

/** The portfolio as whole shares for the investor's money: every order, every charge, and what's left over. */
export function OrdersSection({ result, currency }: { result: FullResult; currency: string }) {
  const allocations = result.allocations ?? [];
  const [sizing, setSizing] = useState<Allocation["sizing"]>("equal");
  const allocation = allocations.find((a) => a.sizing === sizing) ?? allocations[0];

  if (!allocation) {
    return (
      <Section id="orders" number="02" title="Orders and costs" stacked>
        <Note>This result was made before orders were added.</Note>
      </Section>
    );
  }
  const buys = allocation.orders.filter((o) => o.side === "buy");
  const sells = allocation.orders.filter((o) => o.side === "sell");
  const tickers = Object.keys(allocation.weights);

  return (
    <Section id="orders" number="02" title="Orders and costs" stacked
             note={`Whole shares at the last price${result.costs ? `, charged as ${result.costs.model}` : ""}. Sales come first and pay for the buys; leftover cash buys extra shares of whatever is furthest below its target.`}>
      <Segmented value={sizing} onChange={setSizing}
                 options={allocations.map((a) => ({ value: a.sizing, label: SIZINGS[a.sizing].label }))} />
      <p className="mt-3 text-sm text-ink-2">{SIZINGS[allocation.sizing].note}</p>

      <dl className="mt-8 grid gap-x-10 gap-y-6 sm:grid-cols-2 xl:grid-cols-4">
        <Fact term="Invested after trading" value={money(allocation.invested, currency)} detail={`${tickers.length} stocks`} />
        <Fact term="Trading costs" value={money(allocation.costs, currency, 2)}
              detail={allocation.invested > 0 ? `${percent(allocation.costs / allocation.invested, 3)} of the money invested` : undefined} />
        <Fact term="Cash left over" value={money(allocation.cash_left, currency, 2)} detail="too little for one more share" />
        <Fact term="Expected return · volatility" value={`${percent(allocation.expected_return)} · ${percent(allocation.volatility)}`} detail="per year, with these weights" />
      </dl>

      <div className="mt-10">
        <div className="min-w-0 overflow-x-auto">
          <table className="w-full min-w-150 border-t border-ink text-sm">
            <thead className="border-b border-rule">
              <tr><Th>Order</Th><Th>Stock</Th><Th numeric>Shares</Th><Th numeric>Price</Th><Th numeric>Value</Th><Th numeric>Charges</Th></tr>
            </thead>
            <tbody>
              {[...sells, ...buys].map((order) => <OrderRow key={`${order.side}-${order.ticker}`} order={order} currency={currency} />)}
              {allocation.orders.length === 0 && <tr><Td colSpan={6} className="text-muted">Nothing to trade: you already hold this portfolio.</Td></tr>}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-muted">Select an order to see each charge.</p>
        </div>
        <div className="mt-10 grid gap-x-12 gap-y-8 sm:grid-cols-2">
          <div>
          <h3 className="text-xs font-medium text-muted">Target split</h3>
          <ul className="mt-3 space-y-3">
            {tickers.map((ticker) => (
              <li key={ticker}>
                <div className="flex justify-between text-sm"><Ticker className="text-ink">{shortName(ticker)}</Ticker><span className="tabular-nums text-ink-2">{percent(allocation.weights[ticker])}</span></div>
                <div className="mt-1 h-1 rounded-full bg-rule"><div className="h-full rounded-full bg-signal" style={{ width: `${100 * allocation.weights[ticker]}%` }} /></div>
                <p className="mt-1 text-xs text-muted">{allocation.shares[ticker] ?? 0} shares after trading</p>
              </li>
            ))}
          </ul>
          </div>
          <div>
          <h3 className="text-xs font-medium text-muted">By sector</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {Object.entries(allocation.sector_exposure).map(([sector, share]) => (
              <li key={sector} className="flex justify-between gap-3"><span className="truncate text-ink-2">{sector}</span><span className="tabular-nums text-ink">{percent(share, 0)}</span></li>
            ))}
          </ul>
          </div>
        </div>
      </div>
    </Section>
  );
}

function OrderRow({ order, currency }: { order: Allocation["orders"][number]; currency: string }) {
  const [open, setOpen] = useState(false);
  return (
    <Fragment>
      <tr className="cursor-pointer border-b border-rule hover:bg-paper-2" onClick={() => setOpen(!open)}>
        <Td>
          <button type="button" aria-expanded={open} className="inline-flex items-center gap-1.5" onClick={(event) => {
            event.stopPropagation();
            setOpen(!open);
          }}>
            <ChevronIcon className={`h-3.5 w-3.5 text-muted transition-transform ${open ? "rotate-90" : ""}`} />
            <span className={order.side === "buy" ? "text-good" : "text-bad"}>{order.side === "buy" ? "Buy" : "Sell"}</span>
          </button>
        </Td>
        <Td><Ticker className="text-ink">{shortName(order.ticker)}</Ticker></Td>
        <Td numeric>{order.shares.toLocaleString("en-US")}</Td>
        <Td numeric>{money(order.price, currency, 2)}</Td>
        <Td numeric className="text-ink">{money(order.value, currency)}</Td>
        <Td numeric className="text-ink">{money(order.cost, currency, 2)}</Td>
      </tr>
      {open && (
        <tr className="border-b border-rule bg-paper-2/60">
          <Td colSpan={6}>
            <ul className="space-y-1 pl-6 text-xs">
              {order.costs.map((line) => (
                <li key={line.name} className="flex justify-between gap-4"><span className="text-ink-2">{line.name}</span><span className="tabular-nums text-ink">{money(line.amount, currency, 2)}</span></li>
              ))}
              {order.costs.length === 0 && <li className="text-ink-2">No charges on this order.</li>}
            </ul>
          </Td>
        </tr>
      )}
    </Fragment>
  );
}
