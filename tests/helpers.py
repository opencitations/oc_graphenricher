# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from pathlib import Path

from oc_ocdm.graph.entities.bibliographic_entity import BibliographicEntity
from oc_ocdm.graph.graph_set import GraphSet
from oc_ocdm.reader import Reader
from rdflib import Graph

BASE_IRI = "https://w3id.org/oc/meta/"
RESP_AGENT = "https://w3id.org/oc/meta/prov/pa/2"


def load_graph_set(rdf_path: Path) -> GraphSet:
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


def add_id(
    entity: BibliographicEntity,
    literal: str,
    schema: str,
    graph_set: GraphSet,
    resp_agent: str = RESP_AGENT,
) -> None:
    identifier = graph_set.add_id(resp_agent)
    create_identifier = {
        "issn": identifier.create_issn,
        "doi": identifier.create_doi,
        "orcid": identifier.create_orcid,
        "viaf": identifier.create_viaf,
        "crossref": identifier.create_crossref,
        "wikidata": identifier.create_wikidata,
        "openalex": identifier.create_openalex,
    }
    create_identifier[schema](literal)
    entity.has_identifier(identifier)
