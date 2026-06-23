# SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
#
# SPDX-License-Identifier: ISC

from oc_ocdm.reader import Reader
from oc_ocdm.graph import GraphSet
from rdflib import Graph
from oc_graphenricher.enricher import GraphEnricher

g = Graph()
g = g.parse('../data/test_dump.ttl', format='nt11')

reader = Reader()
g_set = GraphSet(base_iri='https://w3id.org/oc/meta/')
entities = reader.import_entities_from_graph(g_set, g, enable_validation=False, resp_agent='https://w3id.org/oc/meta/prov/pa/2')

enricher = GraphEnricher(g_set, debug=False)
enricher.enrich()

