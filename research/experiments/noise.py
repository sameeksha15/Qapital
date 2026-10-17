"""On a noisy IBM chip: the same tuned circuits on noisy copies of an older (Brisbane) and a newer (Fez) IBM chip, with
pruning, readout mitigation and post-selection, on 8- and 10-stock shortlists of every second quarter's problem since
2019 in both markets.

Train on ideal, test on noisy: each circuit is tuned once on the perfect simulator, then sampled on each chip's noise
model. Every result is graded on the full, unpruned score, five ways: perfect simulator; noisy raw; noisy with readout
mitigation; noisy keeping only shots with exactly K stocks (post-selection); and both.
Run from the repo root (about 30 minutes):  python -m research.experiments.noise"""

from datetime import datetime

import pandas as pd

from qapital.core.metrics import brute_force, grade
from qapital.core.schemas import Settings
from qapital.quantum.hamiltonian import build_hamiltonian
from qapital.quantum.noise import calibrate_readout, compare, mitigate_readout, noisy_run
from qapital.quantum.solver import (
    SHOTS,
    _ideal_counts,
    _portfolio_chances,
    _portfolio_counts,
    _tune,
    _tuned_circuit,
    circuit_builder,
)
from research.experiments.common import (
    INVESTOR,
    MARKETS,
    Job,
    problems,
    run_info,
    run_parallel,
    save,
    spread,
)

SIZES = (8, 10)
DEPTHS = (1, 2)
CIRCUITS = (("standard", 1.0), ("xy", 1.0), ("xy", 0.75), ("xy", 0.5), ("xy", 0.25))
CHIPS = ("FakeBrisbane", "FakeFez")
CVAR_ALPHA = 0.25
STAGES = {
    "ideal": ("ideal_p_optimal", "ideal_feasible_rate"),
    "raw": ("noisy_p_optimal", "noisy_feasible_rate"),
    "mitigated": ("mitigated_p_optimal", "mitigated_feasible_rate"),
    "postselected": ("postselected_p_optimal", "postselected_feasible_rate"),
    "both": ("mitigated_postselected_p_optimal", "mitigated_postselected_feasible_rate"),
}
KEYS = ["stocks", "chip", "mixer", "pairs_kept", "depth"]


def jobs() -> list[Job]:
    return [
        {"market": market, "as_of": day, "size": size}
        for market in MARKETS
        for day in problems().dates(market, every=2)
        for size in SIZES
    ]


def task(job: Job) -> list[dict]:
    problem = problems().get(job["market"], job["as_of"], job["size"])
    data = problem.data
    rows = []
    for depth in DEPTHS:
        for mixer, kept in CIRCUITS:
            settings = Settings(**INVESTOR, cvar_alpha=CVAR_ALPHA, mixer=mixer, pairs_kept=kept, depth=depth)
            reference = brute_force(data, settings)
            ham = build_hamiltonian(data, settings)
            build = circuit_builder(data, ham, settings)
            theta, _ = _tune(build, ham, settings)
            ideal = grade(_ideal_counts(build, ham, settings, theta), reference)
            tuned = _tuned_circuit(build, settings, theta)
            for chip in CHIPS:
                run = noisy_run(tuned, SHOTS, settings.seed, chip)
                calibration = calibrate_readout(run, ham.num_qubits, SHOTS)
                mitigated = _portfolio_chances(
                    mitigate_readout(run.counts, calibration, ham.num_qubits), ham.num_stocks
                )
                result = compare(
                    ideal,
                    _portfolio_counts(run.counts, ham.num_stocks),
                    reference,
                    settings.k,
                    chip,
                    mitigated,
                    calibration.average,
                )
                chance = len(reference.best) / len(reference.scores)  # a blind legal guess's chance of a best one
                row = {
                    "market": problem.market,
                    "as_of": problem.as_of,
                    "stocks": job["size"],
                    "legal_portfolios": len(reference.scores),
                    "chip": chip,
                    "mixer": mixer,
                    "pairs_kept": kept,
                    "depth": depth,
                    "gates": run.two_qubit_gates,
                    "readout_error": calibration.average,
                    "postselected_share": result.postselected_share,
                }
                values = result.model_dump()
                for stage, (best, legal) in STAGES.items():
                    row[f"{stage}_lift"] = values[best] / chance
                    row[f"{stage}_legal"] = values[legal]
                rows.append(row)
    return rows


def summarise(runs: pd.DataFrame) -> dict:
    measures = [
        "gates",
        "readout_error",
        "postselected_share",
        *(f"{s}_{m}" for s in STAGES for m in ("lift", "legal")),
    ]
    rows = [
        {**dict(zip(KEYS, values, strict=True)), **{m: spread(group[m]) for m in measures}}
        for values, group in runs.groupby(KEYS)
    ]
    return {"rows": rows, "problems": int(runs.groupby(["market", "as_of"]).ngroups)}


def main() -> None:
    started = datetime.now()
    runs = run_parallel(task, jobs())
    summary = {"all": summarise(runs), **{m: summarise(runs[runs["market"] == m]) for m in MARKETS}}
    info = run_info(
        "On a noisy IBM chip: pruning, readout mitigation and post-selection",
        problems(),
        started,
        sizes=SIZES,
        depths=DEPTHS,
        circuits=CIRCUITS,
        chips=CHIPS,
        cvar_alpha=CVAR_ALPHA,
        shots=SHOTS,
        dates="first trading day of every second quarter from 2019",
        procedure="tune once on the ideal simulator, then sample on each chip noise model (AerSimulator.from_backend)",
        mitigation="two calibration circuits (all 0s, all 1s) on the same physical qubits; each qubit's 2×2 misread "
        "table inverted",
        postselection="keep shots with exactly k stocks",
        lift="chance of the best portfolio divided by a blind legal guess's chance (as qapital.core.metrics.grade)",
    )
    save("noise", runs, info, {"summary": summary, "stages": list(STAGES)})


if __name__ == "__main__":
    main()
