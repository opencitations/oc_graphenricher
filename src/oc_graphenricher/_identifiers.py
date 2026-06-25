# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from __future__ import annotations

from typing import TYPE_CHECKING

from oc_ocdm.graph.graph_entity import GraphEntity

if TYPE_CHECKING:
    from collections.abc import Iterator

    from oc_ocdm.graph.entities.bibliographic_entity import BibliographicEntity


BR_API_SCHEMAS = {
    GraphEntity.iri_doi: "doi",
    GraphEntity.iri_issn: "issn",
    GraphEntity.iri_pmid: "pmid",
    GraphEntity.iri_pmcid: "pmcid",
}


def valid_identifiers(entity: BibliographicEntity) -> Iterator[tuple[str, str]]:
    for identifier in entity.get_identifiers():
        scheme = identifier.get_scheme()
        literal = identifier.get_literal_value()
        if scheme is not None and literal is not None:
            yield scheme, literal


def supported_br_identifiers(entity: BibliographicEntity) -> Iterator[tuple[str, str]]:
    for scheme, literal in valid_identifiers(entity):
        schema = BR_API_SCHEMAS.get(scheme)
        if schema is not None:
            yield schema, literal
