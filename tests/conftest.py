# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from pathlib import Path

import pytest
import requests
import requests_cache
from oc_ocdm.graph.graph_set import GraphSet

from oc_graphenricher.deduplication import GraphDeduplicator
from oc_graphenricher.storage import single_file_storage
from tests.helpers import load_graph_set

TEST_DATA_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def block_external_http(monkeypatch: pytest.MonkeyPatch) -> None:
    requests_cache.uninstall_cache()

    def install_cache_noop(*args: object, **kwargs: object) -> None:
        del args, kwargs

    def blocked_request(self: requests.sessions.Session, method: str, url: str, **kwargs: object) -> None:
        del self, kwargs
        message = f"External HTTP request blocked during tests: {method} {url}"
        raise AssertionError(message)

    monkeypatch.setattr(requests_cache, "install_cache", install_cache_noop)
    monkeypatch.setattr(requests.sessions.Session, "request", blocked_request)


@pytest.fixture
def deduplicated_graph_set(tmp_path: Path) -> GraphSet:
    deduplicator = GraphDeduplicator(
        load_graph_set(TEST_DATA_DIR / "test_merge_br.rdf"),
        single_file_storage(
            tmp_path / "deduplicated.rdf",
            tmp_path / "provenance.rdf",
            output_format="nt11",
            zip_output=False,
        ),
        debug=True,
    )
    deduplicator.deduplicate_and_save()
    return load_graph_set(tmp_path / "deduplicated.rdf")
