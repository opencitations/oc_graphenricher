# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from pathlib import Path

import pytest
from oc_ocdm.graph.graph_set import GraphSet
from oc_ocdm.reader import Reader
from rdflib import Graph

from oc_graphenricher.instancematching import InstanceMatching

BASE_IRI = "https://w3id.org/oc/meta/"
RESP_AGENT = "https://w3id.org/oc/meta/prov/pa/2"
TEST_DATA_DIR = Path(__file__).parent / "fixtures"


def _load_graph_set(rdf_path: Path) -> GraphSet:
    graph = Graph()
    graph.parse(rdf_path, format="nt11")

    reader = Reader()
    graph_set = GraphSet(base_iri=BASE_IRI)
    reader.import_entities_from_graph(
        graph_set,
        graph,
        enable_validation=False,
        resp_agent=RESP_AGENT,
    )
    return graph_set


@pytest.fixture
def matched_graph_set(tmp_path: Path) -> GraphSet:
    matcher = InstanceMatching(
        _load_graph_set(TEST_DATA_DIR / "test_merge_br.rdf"),
        graph_filename=str(tmp_path / "matched.rdf"),
        provenance_filename=str(tmp_path / "provenance.rdf"),
        debug=True,
    )
    matcher.match()
    return _load_graph_set(tmp_path / "matched.rdf")
