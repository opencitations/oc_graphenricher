# SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from oc_ocdm.reader import Reader
from oc_ocdm.graph import GraphSet
from rdflib import Graph
from oc_graphenricher.instancematching import InstanceMatching

g = Graph()
g = g.parse("tests/fixtures/test_merge_br.rdf", format="nt11")

reader = Reader()
g_set = GraphSet(base_iri='https://w3id.org/oc/meta/')
entities = reader.import_entities_from_graph(g_set, g, enable_validation=False, resp_agent='https://w3id.org/oc/meta/prov/pa/2')

matcher = InstanceMatching(g_set, debug=True)
matcher.match()
