# SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from pathlib import Path

from oc_ocdm.graph.entities.bibliographic.bibliographic_resource import BibliographicResource
from oc_ocdm.graph.entities.identifier import Identifier
from oc_ocdm.graph.graph_set import GraphSet
from oc_ocdm.reader import Reader
from rdflib import Graph

from oc_graphenricher.instancematching import InstanceMatching

BASE_IRI = "https://w3id.org/oc/meta/"
RESP_AGENT = "https://w3id.org/oc/meta/prov/pa/2"
EXPECTED_BR_CONTRIBUTOR_COUNTS = {
    "http://example.com/br/1": 0,
    "http://example.com/br/2": 0,
    "http://example.com/br/3": 2,
    "http://example.com/br/7": 2,
}

EXPECTED_IDS = [
    "http://purl.org/spar/datacite/crossrefpub1",
    "http://purl.org/spar/datacite/doibr3_issue_doi",
    "http://purl.org/spar/datacite/doibr3_volume_doi",
    "http://purl.org/spar/datacite/doibr6_issue_doi",
    "http://purl.org/spar/datacite/doibr6_volume_doi",
    "http://purl.org/spar/datacite/doidoi1",
    "http://purl.org/spar/datacite/doidoi4",
    "http://purl.org/spar/datacite/orcidorcid1",
    "http://purl.org/spar/datacite/orcidorcid_author_1",
    "http://purl.org/spar/datacite/viafviaf1",
]

EXPECTED_RA_IDENTIFIERS = [
    "http://purl.org/spar/datacite/crossrefpub1",
    "http://purl.org/spar/datacite/orcidorcid1",
    "http://purl.org/spar/datacite/orcidorcid_author_1",
    "http://purl.org/spar/datacite/viafviaf1",
]


def identifier_key(identifier: Identifier) -> str:
    return f"{identifier.get_scheme()}{identifier.get_literal_value()}"


def test_ras_merged(matched_graph_set: GraphSet) -> None:
    identifiers = sorted(
        identifier_key(identifier) for ra in matched_graph_set.get_ra() for identifier in ra.get_identifiers()
    )
    assert identifiers == EXPECTED_RA_IDENTIFIERS


def test_ids_not_duplicated(matched_graph_set: GraphSet) -> None:
    identifiers = sorted(
        identifier_key(identifier)
        for identifier in matched_graph_set.get_id()
        if identifier_key(identifier) != "NoneNone"
    )
    assert identifiers == EXPECTED_IDS


def test_agent_roles_reference_existing_responsible_agents(matched_graph_set: GraphSet) -> None:
    held_responsible_agents = {ar.get_is_held_by() for ar in matched_graph_set.get_ar()}
    responsible_agents = set(matched_graph_set.get_ra())
    orphan_responsible_agents = sorted(str(ra) for ra in held_responsible_agents.difference(responsible_agents))

    assert orphan_responsible_agents == []


def test_bibliographic_resources_reference_existing_agent_roles(matched_graph_set: GraphSet) -> None:
    agent_roles_from_brs = sorted(str(ar) for br in matched_graph_set.get_br() for ar in br.get_contributors())
    agent_roles = sorted(str(ar) for ar in matched_graph_set.get_ar())

    assert agent_roles_from_brs == agent_roles


def test_brs_merged(matched_graph_set: GraphSet) -> None:
    bibliographic_resources = sorted(str(br) for br in matched_graph_set.get_br())
    assert bibliographic_resources == [
        "http://example.com/br/1",
        "http://example.com/br/2",
        "http://example.com/br/3",
        "http://example.com/br/7",
    ]


def test_brs_have_only_one_list_of_authors(matched_graph_set: GraphSet) -> None:
    contributor_counts_by_br = {str(br): len(br.get_contributors()) for br in matched_graph_set.get_br()}
    assert contributor_counts_by_br == EXPECTED_BR_CONTRIBUTOR_COUNTS


def test_matching_keeps_one_named_author_when_duplicate_brs_merge(tmp_path: Path) -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = _add_article_with_shared_doi(graph_set, "First")
    second_br = _add_article_with_shared_doi(graph_set, "Second")
    _add_author(graph_set, first_br)
    _add_author(graph_set, second_br)
    orphan_author = graph_set.add_ar(RESP_AGENT)
    orphan_author.create_author()
    second_br.has_contributor(orphan_author)
    graph_set.commit_changes()

    matcher = InstanceMatching(
        graph_set,
        graph_filename=str(tmp_path / "matched.rdf"),
        provenance_filename=str(tmp_path / "provenance.rdf"),
        debug=True,
    )
    matcher.match()

    matched_graph_set = _load_graph_set(tmp_path / "matched.rdf")

    assert [str(br) for br in matched_graph_set.get_br()] == ["https://w3id.org/oc/meta/br/1"]
    assert [_author_names(br) for br in matched_graph_set.get_br()] == [["Ada Lovelace"]]


def _add_article_with_shared_doi(graph_set: GraphSet, title: str) -> BibliographicResource:
    br = graph_set.add_br(RESP_AGENT)
    br.create_journal_article()
    br.has_title(title)
    identifier = graph_set.add_id(RESP_AGENT)
    identifier.create_doi("10.555/shared")
    br.has_identifier(identifier)
    return br


def _add_author(graph_set: GraphSet, br: BibliographicResource) -> None:
    responsible_agent = graph_set.add_ra(RESP_AGENT)
    responsible_agent.has_given_name("Ada")
    responsible_agent.has_family_name("Lovelace")
    author = graph_set.add_ar(RESP_AGENT)
    author.create_author()
    author.is_held_by(responsible_agent)
    br.has_contributor(author)


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


def _author_names(br: BibliographicResource) -> list[str]:
    names = []
    for contributor in br.get_contributors():
        responsible_agent = contributor.get_is_held_by()
        if responsible_agent is not None:
            names.append(f"{responsible_agent.get_given_name()} {responsible_agent.get_family_name()}")
    return sorted(names)
