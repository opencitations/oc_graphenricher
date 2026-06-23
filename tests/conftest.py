# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from pathlib import Path

import pytest
from oc_ocdm.graph import GraphSet
from oc_ocdm.reader import Reader
from rdflib import Graph

from oc_graphenricher.APIs import Crossref, OpenAlex, ORCID, VIAF, WikiData
from oc_graphenricher.instancematching import InstanceMatching

BASE_IRI = "https://w3id.org/oc/meta/"
RESP_AGENT = "https://w3id.org/oc/meta/prov/pa/2"


@pytest.fixture
def crossref_api():
    return Crossref()


@pytest.fixture
def openalex_api():
    return OpenAlex()


@pytest.fixture
def orcid_api():
    return ORCID()


@pytest.fixture
def test_data_dir():
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def viaf_api():
    return VIAF()


@pytest.fixture
def wikidata_api():
    return WikiData()


@pytest.fixture
def graph_set_from_rdf():
    def load_graph_set(rdf_path):
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

    return load_graph_set


@pytest.fixture
def matched_graph_set(test_data_dir, graph_set_from_rdf, tmp_path):
    matcher = InstanceMatching(
        graph_set_from_rdf(test_data_dir / "test_merge_br.rdf"),
        graph_filename=str(tmp_path / "matched.rdf"),
        provenance_filename=str(tmp_path / "provenance.rdf"),
        debug=True,
    )
    matcher.match()
    return graph_set_from_rdf(tmp_path / "matched.rdf")
