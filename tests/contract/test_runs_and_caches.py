"""Runs, document states, the extraction cache and resolution decisions (protocols.md §2)."""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Literal

import pytest

from tenetrag.protocols import DocumentState, QueryError, RunRecord, RunStatus, Verdict
from tests.support.contract.backends import ContractStores
from tests.support.contract.writes import corpus_writes


def _run(run_id: str) -> RunRecord:
    return RunRecord(
        run_id=run_id,
        status=RunStatus.RUNNING,
        started_at=None,
        finished_at=None,
        stage_hashes={"extract": "a" * 64, "resolve": "b" * 64},
        prompt_versions={"extract": "1"},
        pack="enterprise-docs",
        pack_version="1",
        pack_hash="c" * 64,
        stats={},
    )


def _verdict(pair_key: str, verdict: str, method: Literal["llm", "reviewer"]) -> Verdict:
    model = "fake-chat" if method == "llm" else None
    return Verdict(pair_key=pair_key, verdict=verdict, method=method, model=model, run_id="run-1")


def _started(run: RunRecord) -> datetime:
    assert run.started_at is not None, f"run {run.run_id} has no started_at"
    return run.started_at


def _unstamped(run: RunRecord) -> RunRecord:
    """The run without what the store sets: times, status and stats."""
    return dataclasses.replace(
        run, started_at=None, finished_at=None, status=RunStatus.RUNNING, stats={}
    )


def test_runs_round_trip(stores: ContractStores) -> None:
    graph = stores.graph
    graph.begin_run(_run("run-a"))
    graph.begin_run(_run("run-b"))

    graph.finish_run("run-a", RunStatus.COMPLETED, {"documents": 3, "errors": []})

    runs = graph.get_runs(10)
    assert sorted(run.run_id for run in runs) == ["run-a", "run-b"]
    assert runs == sorted(runs, key=lambda run: (-_started(run).timestamp(), run.run_id))
    by_id = {run.run_id: run for run in runs}
    finished, running = by_id["run-a"], by_id["run-b"]
    assert finished.status is RunStatus.COMPLETED
    assert finished.stats == {"documents": 3, "errors": []}
    assert finished.finished_at is not None
    assert finished.finished_at >= _started(finished)
    assert (running.status, running.finished_at) == (RunStatus.RUNNING, None)
    assert _unstamped(running) == _run("run-b")
    assert _unstamped(finished) == _run("run-a")
    assert len(graph.get_runs(1)) == 1


def test_run_limits_and_errors(stores: ContractStores) -> None:
    for limit in (0, 1001):
        with pytest.raises(ValueError, match="limit is"):
            stores.graph.get_runs(limit)
    with pytest.raises(QueryError, match="no-such-run"):
        stores.graph.finish_run("no-such-run", RunStatus.FAILED, {})
    stores.graph.begin_run(_run("run-a"))
    with pytest.raises(ValueError, match="running"):
        stores.graph.finish_run("run-a", RunStatus.RUNNING, {})


def test_document_states(stores: ContractStores) -> None:
    writes = corpus_writes(["D1", "D2"], with_vectors=False)

    stores.graph.write_documents(writes)

    assert stores.graph.document_states() == {
        write.document.doc_id: DocumentState(
            content_hash=write.document.content_hash,
            pipeline_hash=write.document.pipeline_hash,
            run_id=write.document.run_id,
        )
        for write in writes
    }


def test_cache_put_replaces(stores: ContractStores) -> None:
    stores.graph.put_cached_extractions({"key-1": b"one", "key-2": b"two"})

    assert stores.graph.get_cached_extractions(["key-1", "key-3"]) == {"key-1": b"one"}
    stores.graph.put_cached_extractions({"key-1": b"uno"})
    assert stores.graph.get_cached_extractions(["key-2", "key-1"]) == {
        "key-1": b"uno",
        "key-2": b"two",
    }
    assert stores.graph.get_cached_extractions([]) == {}


def test_reviewer_verdict_stays(stores: ContractStores) -> None:
    graph = stores.graph
    graph.put_resolution_decisions([_verdict("a|b", "same", "reviewer")])
    graph.put_resolution_decisions([_verdict("a|b", "different", "llm")])
    graph.put_resolution_decisions([_verdict("c|d", "same", "llm")])
    graph.put_resolution_decisions([_verdict("c|d", "different", "llm")])
    graph.put_resolution_decisions([_verdict("e|f", "same", "llm")])
    graph.put_resolution_decisions([_verdict("e|f", "different", "reviewer")])

    decisions = graph.get_resolution_decisions(["a|b", "c|d", "e|f", "x|y"])

    assert decisions == {
        "a|b": _verdict("a|b", "same", "reviewer"),
        "c|d": _verdict("c|d", "different", "llm"),
        "e|f": _verdict("e|f", "different", "reviewer"),
    }
