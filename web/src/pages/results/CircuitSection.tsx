import { Link } from "react-router";
import type { FullResult, NoiseComparison } from "../../api/types";
import { SHOTS } from "../../api/types";
import { ConvergenceChart } from "../../components/charts/ConvergenceChart";
import { LayerChart } from "../../components/charts/LayerChart";
import { SamplesChart } from "../../components/charts/SamplesChart";
import { CountUp, DrawIn } from "../../components/motion";
import { Note, Section, Stat, StatStrip, Subsection, Td, Th } from "../../components/ui";
import { percent, times, whole } from "../../lib/format";

export function CircuitSection({ result }: { result: FullResult }) {
  const { quantum, optimal } = result;
  const best = optimal?.shortlist_best?.stocks ?? optimal?.best.stocks ?? quantum.chosen;
  const stocks = quantum.num_qubits - quantum.num_slack_qubits;
  const warm = quantum.warm_start_alone;

  return (
    <Section id="circuit" number="04" title="Inside the quantum circuit" stacked
             note={`Each stock is a qubit. A classical optimiser tunes the circuit's knobs, then the circuit runs ${whole(SHOTS)} times; each run produces one portfolio.`}>
      <StatStrip>
        <Stat label="qubits" value={<CountUp value={quantum.num_qubits} format={whole} />}
              detail={quantum.num_slack_qubits ? `${stocks} stocks + ${quantum.num_slack_qubits} helpers` : "one per stock"} />
        <Stat label="two-qubit gates" value={<CountUp value={quantum.two_qubit_gates} format={whole} />} detail="on a fake IBM Brisbane chip" />
        <Stat label="circuit depth" value={<CountUp value={quantum.circuit_depth} format={whole} />} detail="time steps on that chip" />
        <Stat label="shots on the best" value={<CountUp value={quantum.p_optimal} format={(v) => percent(v)} />}
              detail={optimal?.num_valid_shortlist ? `blind guess: ${percent(1 / optimal.num_valid_shortlist, 2)}` : undefined} />
      </StatStrip>

      {warm && (
        <div className="mt-10">
          <Note title="Warm start: what the quantum layers added">
            The classical starting point alone would hit the best portfolio {times(warm.lift_over_random)} as often as random
            guessing ({percent(warm.p_optimal)} of shots); after the quantum layers, {times(quantum.lift_over_random)}
            ({percent(quantum.p_optimal)}).
          </Note>
        </div>
      )}

      <Subsection title={`What ${whole(SHOTS)} shots produced`}
                  note="The 20 most frequent portfolios. Orange is the best one on the circuit's shortlist; grey bars break a rule. The thin line is how often blind guessing would land on any one of them.">
        <SamplesChart quantum={quantum} best={best} numValid={optimal?.num_valid_shortlist} shots={SHOTS} />
      </Subsection>

      <div className="grid gap-x-12 xl:grid-cols-2">
        <Subsection title="Watch the circuit think" note="Starting from its first state, each layer moves probability towards good portfolios. It plays once when it comes into view.">
          <LayerChart quantum={quantum} />
        </Subsection>
        <Subsection title="How the knobs were tuned"
                    note="The objective after every optimiser step; layers are tuned one after another. With CVaR it is the average of the best shots only, so it sits below the plain average.">
          <DrawIn><ConvergenceChart values={quantum.convergence} best={optimal?.shortlist_best?.score ?? quantum.score} bestLabel="best possible on the shortlist" /></DrawIn>
        </Subsection>
      </div>

      <div className="mt-12">
        {quantum.noise ? <NoiseTable noise={quantum.noise} /> : (
          <Note title="This run used the perfect (noise-free) simulator">
            The gate counts above are for a real chip's wiring. Switch on “Also run on a noisy IBM chip” to see the same
            circuit on a copy of a real chip's errors, or see <Link to="/research" className="text-ink underline underline-offset-4 hover:text-signal">Research</Link>.
          </Note>
        )}
      </div>

      {result.pruning && (
        <Subsection title="Pruning study" note="The same problem with fewer stock links kept in the circuit. Fewer links means fewer gates; every level is still graded on the full problem.">
          <div className="overflow-x-auto">
            <table className="w-full min-w-120 border-t border-ink text-sm">
              <thead className="border-b border-rule"><tr><Th>Links kept</Th><Th numeric>Two-qubit gates</Th><Th numeric>Perfect simulator</Th><Th numeric>Noisy chip</Th><Th numeric>Noisy, post-selected</Th></tr></thead>
              <tbody>
                {result.pruning.map((row) => (
                  <tr key={row.kept} className="border-b border-rule">
                    <Td>{percent(row.kept, 0)}</Td><Td numeric>{whole(row.gates)}</Td><Td numeric>{times(row.ideal)}</Td>
                    <Td numeric>{times(row.noisy)}</Td><Td numeric>{times(row.noisy_postselected)}</Td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs text-muted">Each cell: how many times more often than random guessing the circuit lands on the best portfolio.</p>
          </div>
        </Subsection>
      )}
    </Section>
  );
}

function NoiseTable({ noise }: { noise: NoiseComparison }) {
  const rows: [string, number, number | null | undefined, number | null | undefined][] = [
    ["Perfect simulator", noise.ideal_p_optimal, noise.ideal_feasible_rate, noise.ideal_approx_ratio],
    ["Noisy chip, raw", noise.noisy_p_optimal, noise.noisy_feasible_rate, noise.noisy_approx_ratio],
    ["Noisy, readout mitigated", noise.mitigated_p_optimal ?? NaN, noise.mitigated_feasible_rate, noise.mitigated_approx_ratio],
    ["Noisy, only shots with exactly K stocks", noise.postselected_p_optimal, noise.postselected_feasible_rate, noise.postselected_approx_ratio],
    ["Mitigated and post-selected", noise.mitigated_postselected_p_optimal ?? NaN, noise.mitigated_postselected_feasible_rate, noise.mitigated_postselected_approx_ratio],
  ];
  return (
    <div>
      <h3 className="font-serif text-xl text-ink">Perfect simulator vs a noisy {noise.chip ?? "IBM"} chip</h3>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink-2">
        The same tuned circuit, sampled on a copy of a real chip's errors.
        {noise.readout_error != null && ` The chip misread a qubit ${percent(noise.readout_error)} of the time on average; mitigation undoes that part.`}
        {noise.postselected_share != null && ` ${percent(noise.postselected_share)} of noisy shots held exactly the right number of stocks.`}
      </p>
      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-120 border-t border-ink text-sm">
          <thead className="border-b border-rule"><tr><Th>Run</Th><Th numeric>Shots on the best</Th><Th numeric>Legal shots</Th><Th numeric>Quality (approx. ratio)</Th></tr></thead>
          <tbody>
            {rows.filter(([, best]) => !Number.isNaN(best)).map(([name, best, legal, quality]) => (
              <tr key={name} className="border-b border-rule">
                <Td className="text-ink">{name}</Td><Td numeric>{percent(best)}</Td>
                <Td numeric>{legal != null ? percent(legal) : "–"}</Td><Td numeric>{quality != null ? quality.toFixed(3) : "–"}</Td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
