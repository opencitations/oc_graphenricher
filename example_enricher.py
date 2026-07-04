# SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
#
# SPDX-License-Identifier: ISC

from oc_ocdm.graph.graph_set import GraphSet
from oc_ocdm.reader import Reader
from rdflib import Graph

from oc_graphenricher.enricher import GraphEnricher
from oc_graphenricher.storage import single_file_storage

g = Graph()
g = g.parse("../data/test_dump.ttl", format="nt11")

reader = Reader()
graph_set = GraphSet(base_iri="https://w3id.org/oc/meta/")
entities = reader.import_entities_from_graph(
    graph_set,
    g,
    enable_validation=False,
    resp_agent="https://w3id.org/oc/meta/prov/pa/2",
)

enricher = GraphEnricher(
    graph_set=graph_set,
    storage=single_file_storage(
        graph_path="enriched.json",
        provenance_path="provenance.json",
    ),
    debug=False,
)
enricher.enrich()
