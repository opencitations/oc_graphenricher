# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from __future__ import annotations

from typing import TYPE_CHECKING

from oc_ocdm.graph.graph_set import GraphSet

from oc_graphenricher.APIs import ORCID, VIAF, AuthorTuple, Crossref, IdentifierTuple, OpenAlex, WikiData
from oc_graphenricher.enricher import GraphEnricher
from tests.helpers import BASE_IRI, RESP_AGENT, add_id, load_graph_set

if TYPE_CHECKING:
    from pathlib import Path

    from oc_ocdm.graph.entities.bibliographic.bibliographic_resource import BibliographicResource
    from oc_ocdm.graph.entities.bibliographic.responsible_agent import ResponsibleAgent

EXPECTED_ADDED_IDENTIFIERS = 8
EXPECTED_BR_COUNT_WITH_SKIPPED_TYPES = 3


class EnrichmentCrossref(Crossref):
    def query_journal(self, issn: str) -> list[str]:
        return [issn, "2222-2222"]

    def query(self, fullnames: list[tuple[str | None, str | None]], title: str, year: str | None) -> str:
        del fullnames, title, year
        return "10.555/example"

    def query_publisher(self, doi: str) -> str:
        del doi
        return "9999"


class EnrichmentORCID(ORCID):
    def query(self, authors: list[AuthorTuple], identifiers: list[IdentifierTuple]) -> list[AuthorTuple]:
        del identifiers
        given_name, family_name, _orcid, responsible_agent = authors[0]
        return [(given_name, family_name, "0000-0001-2345-6789", responsible_agent)]


class EnrichmentVIAF(VIAF):
    def query(self, given_name: str, family_name: str, title: str) -> str:
        del given_name, family_name, title
        return "123456"


class EnrichmentWikiData(WikiData):
    def query(self, entity: str, schema: str) -> str | None:
        del entity
        if schema == "doi":
            return "QBR"
        if schema in {"orcid", "viaf"}:
            return "QRA"
        return None


class EnrichmentOpenAlex(OpenAlex):
    def query(self, entity: str, schema: str) -> list[str] | None:
        del entity
        if schema == "doi":
            return ["W123"]
        return None


class NoResultCrossref(Crossref):
    def query_journal(self, issn: str) -> list[str] | None:
        del issn

    def query(self, fullnames: list[tuple[str | None, str | None]], title: str, year: str | None) -> str | None:
        del fullnames, title, year

    def query_publisher(self, doi: str) -> str | None:
        del doi


class NoResultORCID(ORCID):
    def query(self, authors: list[AuthorTuple], identifiers: list[IdentifierTuple]) -> list[AuthorTuple] | None:
        del authors, identifiers


class NoResultVIAF(VIAF):
    def query(self, given_name: str, family_name: str, title: str) -> str | None:
        del given_name, family_name, title


class NoResultWikiData(WikiData):
    def query(self, entity: str, schema: str) -> str | None:
        del entity, schema


class NoResultOpenAlex(OpenAlex):
    def query(self, entity: str, schema: str) -> list[str] | None:
        del entity, schema


class FailingCrossref(Crossref):
    def query_journal(self, issn: str) -> list[str]:
        del issn
        raise AssertionError

    def query(self, fullnames: list[tuple[str | None, str | None]], title: str, year: str | None) -> str:
        del fullnames, title, year
        raise AssertionError

    def query_publisher(self, doi: str) -> str:
        del doi
        raise AssertionError


class FailingORCID(ORCID):
    def query(self, authors: list[AuthorTuple], identifiers: list[IdentifierTuple]) -> list[AuthorTuple]:
        del authors, identifiers
        raise AssertionError


class FailingVIAF(VIAF):
    def query(self, given_name: str, family_name: str, title: str) -> str:
        del given_name, family_name, title
        raise AssertionError


class FailingWikiData(WikiData):
    def query(self, entity: str, schema: str) -> str:
        del entity, schema
        raise AssertionError


class FailingOpenAlex(OpenAlex):
    def query(self, entity: str, schema: str) -> list[str]:
        del entity, schema
        raise AssertionError


def test_enrich_adds_missing_identifiers_and_serializes_graphs(tmp_path: Path) -> None:
    graph_set = _graph_set_with_missing_identifiers()
    enricher = _enricher(tmp_path, graph_set, debug=True)
    enricher.crossref_api = EnrichmentCrossref()
    enricher.orcid_api = EnrichmentORCID()
    enricher.viaf_api = EnrichmentVIAF()
    enricher.wikidata_api = EnrichmentWikiData()
    enricher.openalex_api = EnrichmentOpenAlex()

    enricher.enrich()

    enriched_graph_set = load_graph_set(tmp_path / "enriched.rdf")

    assert enricher.new_id_found == EXPECTED_ADDED_IDENTIFIERS
    assert (tmp_path / "enriched.rdf").exists() is True
    assert (tmp_path / "provenance.rdf").exists() is True
    assert len(list(enriched_graph_set.get_br())) == EXPECTED_BR_COUNT_WITH_SKIPPED_TYPES
    assert _br_identifiers_by_title(enriched_graph_set) == {
        "A deterministic enrichment test": ["10.555/example", "1111-1111", "2222-2222", "QBR", "W123"],
    }
    assert _ra_identifiers_by_name(enriched_graph_set) == {
        "Ada Lovelace": ["0000-0001-2345-6789", "123456", "QRA"],
        "Test Publisher": ["9999"],
    }


def test_enrich_leaves_graph_unchanged_when_metadata_and_apis_do_not_resolve(tmp_path: Path) -> None:
    graph_set = _graph_set_without_resolvable_metadata()
    enricher = _enricher(tmp_path, graph_set)
    enricher.crossref_api = NoResultCrossref()
    enricher.orcid_api = NoResultORCID()
    enricher.viaf_api = NoResultVIAF()
    enricher.wikidata_api = NoResultWikiData()
    enricher.openalex_api = NoResultOpenAlex()

    enricher.enrich()

    enriched_graph_set = load_graph_set(tmp_path / "enriched.rdf")

    assert enricher.new_id_found == 0
    assert _br_identifiers_by_title(enriched_graph_set) == {
        "No DOI result": ["3333-3333"],
    }
    assert _ra_identifiers_by_name(enriched_graph_set) == {
        "None None": [],
        "Unresolved Publisher": [],
    }


def test_enrich_does_not_query_when_identifiers_are_already_present(tmp_path: Path) -> None:
    graph_set = _graph_set_with_existing_identifiers()
    enricher = _enricher(tmp_path, graph_set)
    enricher.crossref_api = FailingCrossref()
    enricher.orcid_api = FailingORCID()
    enricher.viaf_api = FailingVIAF()
    enricher.wikidata_api = FailingWikiData()
    enricher.openalex_api = FailingOpenAlex()

    enricher.enrich()

    enriched_graph_set = load_graph_set(tmp_path / "enriched.rdf")

    assert enricher.new_id_found == 0
    assert _br_identifiers_by_title(enriched_graph_set) == {
        "Already enriched": ["10.555/existing", "QEXISTING", "WEXISTING"],
    }
    assert _ra_identifiers_by_name(enriched_graph_set) == {
        "Ada Lovelace": ["0000-0001-2345-6789", "123456", "QRA"],
        "Test Publisher": ["9999"],
    }


def _enricher(tmp_path: Path, graph_set: GraphSet, *, debug: bool = False) -> GraphEnricher:
    return GraphEnricher(
        graph_set,
        graph_filename=str(tmp_path / "enriched.rdf"),
        provenance_filename=str(tmp_path / "provenance.rdf"),
        debug=debug,
    )


def _graph_set_with_missing_identifiers() -> GraphSet:
    graph_set = GraphSet(BASE_IRI)

    issue = graph_set.add_br(RESP_AGENT)
    issue.create_issue()

    volume = graph_set.add_br(RESP_AGENT)
    volume.create_volume()

    article = graph_set.add_br(RESP_AGENT)
    article.create_journal_article()
    article.has_title("A deterministic enrichment test")
    article.has_pub_date("2020")
    add_id(article, "1111-1111", "issn", graph_set)

    author = graph_set.add_ra(RESP_AGENT)
    author.has_given_name("Ada")
    author.has_family_name("Lovelace")
    author_role = graph_set.add_ar(RESP_AGENT)
    author_role.create_author()
    author_role.is_held_by(author)
    article.has_contributor(author_role)

    publisher = graph_set.add_ra(RESP_AGENT)
    publisher.has_name("Test Publisher")
    publisher_role = graph_set.add_ar(RESP_AGENT)
    publisher_role.create_publisher()
    publisher_role.is_held_by(publisher)
    article.has_contributor(publisher_role)

    graph_set.commit_changes()
    return graph_set


def _graph_set_without_resolvable_metadata() -> GraphSet:
    graph_set = GraphSet(BASE_IRI)

    article = graph_set.add_br(RESP_AGENT)
    article.create_journal_article()
    article.has_title("No DOI result")
    article.has_pub_date("2020")
    add_id(article, "3333-3333", "issn", graph_set)

    author = graph_set.add_ra(RESP_AGENT)
    author_role = graph_set.add_ar(RESP_AGENT)
    author_role.create_author()
    author_role.is_held_by(author)
    article.has_contributor(author_role)

    orphan_author_role = graph_set.add_ar(RESP_AGENT)
    orphan_author_role.create_author()
    article.has_contributor(orphan_author_role)

    publisher = graph_set.add_ra(RESP_AGENT)
    publisher.has_name("Unresolved Publisher")
    publisher_role = graph_set.add_ar(RESP_AGENT)
    publisher_role.create_publisher()
    publisher_role.is_held_by(publisher)
    article.has_contributor(publisher_role)

    graph_set.commit_changes()
    return graph_set


def _graph_set_with_existing_identifiers() -> GraphSet:
    graph_set = GraphSet(BASE_IRI)

    article = graph_set.add_br(RESP_AGENT)
    article.create_journal_article()
    article.has_title("Already enriched")
    article.has_pub_date("2020")
    add_id(article, "10.555/existing", "doi", graph_set)
    add_id(article, "QEXISTING", "wikidata", graph_set)
    add_id(article, "WEXISTING", "openalex", graph_set)

    author = graph_set.add_ra(RESP_AGENT)
    author.has_given_name("Ada")
    author.has_family_name("Lovelace")
    add_id(author, "0000-0001-2345-6789", "orcid", graph_set)
    add_id(author, "123456", "viaf", graph_set)
    add_id(author, "QRA", "wikidata", graph_set)
    author_role = graph_set.add_ar(RESP_AGENT)
    author_role.create_author()
    author_role.is_held_by(author)
    article.has_contributor(author_role)

    publisher = graph_set.add_ra(RESP_AGENT)
    publisher.has_name("Test Publisher")
    add_id(publisher, "9999", "crossref", graph_set)
    publisher_role = graph_set.add_ar(RESP_AGENT)
    publisher_role.create_publisher()
    publisher_role.is_held_by(publisher)
    article.has_contributor(publisher_role)

    graph_set.commit_changes()
    return graph_set


def _br_identifiers_by_title(graph_set: GraphSet) -> dict[str, list[str]]:
    return {title: _identifier_values(br) for br in graph_set.get_br() if (title := br.get_title()) is not None}


def _ra_identifiers_by_name(graph_set: GraphSet) -> dict[str, list[str]]:
    return {_responsible_agent_name(ra): _identifier_values(ra) for ra in graph_set.get_ra()}


def _responsible_agent_name(responsible_agent: ResponsibleAgent) -> str:
    name = responsible_agent.get_name()
    if name is not None:
        return name
    return f"{responsible_agent.get_given_name()} {responsible_agent.get_family_name()}"


def _identifier_values(entity: BibliographicResource | ResponsibleAgent) -> list[str]:
    values = []
    for identifier in entity.get_identifiers():
        literal = identifier.get_literal_value()
        if literal is not None:
            values.append(literal)
    return sorted(values)
