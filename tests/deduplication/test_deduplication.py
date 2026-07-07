# SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from collections.abc import Iterable
from pathlib import Path

import orjson
import pytest
from oc_ocdm.counter_handler import CounterHandler
from oc_ocdm.graph.entities.bibliographic.agent_role import AgentRole
from oc_ocdm.graph.entities.bibliographic.bibliographic_resource import BibliographicResource
from oc_ocdm.graph.entities.bibliographic.responsible_agent import ResponsibleAgent
from oc_ocdm.graph.entities.identifier import Identifier
from oc_ocdm.graph.graph_set import GraphSet

from oc_graphenricher.deduplication import GraphDeduplicator
from oc_graphenricher.storage import directory_storage, single_file_storage
from tests.helpers import BASE_IRI, RESP_AGENT, add_id, load_graph_set

# br/4 and br/5 are BR6's volume and issue: they carry DOIs that conflict with
# BR3's volume/issue DOIs, so the container safeguard keeps them distinct even
# though the two papers (br/3 and br/6) are merged.
EXPECTED_BR_CONTRIBUTOR_COUNTS = {
    "http://example.com/br/1": 0,
    "http://example.com/br/2": 0,
    "http://example.com/br/3": 2,
    "http://example.com/br/4": 0,
    "http://example.com/br/5": 0,
    "http://example.com/br/7": 1,
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


def test_ras_merged(deduplicated_graph_set: GraphSet) -> None:
    identifiers = sorted(
        identifier_key(identifier) for ra in deduplicated_graph_set.get_ra() for identifier in ra.get_identifiers()
    )
    assert identifiers == EXPECTED_RA_IDENTIFIERS


def test_ids_not_duplicated(deduplicated_graph_set: GraphSet) -> None:
    identifiers = sorted(
        identifier_key(identifier)
        for identifier in deduplicated_graph_set.get_id()
        if identifier_key(identifier) != "NoneNone"
    )
    assert identifiers == EXPECTED_IDS


def test_agent_roles_reference_existing_responsible_agents(deduplicated_graph_set: GraphSet) -> None:
    held_responsible_agents = {ar.get_is_held_by() for ar in deduplicated_graph_set.get_ar()}
    responsible_agents = set(deduplicated_graph_set.get_ra())
    orphan_responsible_agents = sorted(str(ra) for ra in held_responsible_agents.difference(responsible_agents))

    assert orphan_responsible_agents == []


def test_bibliographic_resources_reference_existing_agent_roles(deduplicated_graph_set: GraphSet) -> None:
    agent_roles_from_brs = sorted(str(ar) for br in deduplicated_graph_set.get_br() for ar in br.get_contributors())
    agent_roles = sorted(str(ar) for ar in deduplicated_graph_set.get_ar())

    assert agent_roles_from_brs == agent_roles


def test_brs_merged(deduplicated_graph_set: GraphSet) -> None:
    bibliographic_resources = sorted(str(br) for br in deduplicated_graph_set.get_br())
    assert bibliographic_resources == [
        "http://example.com/br/1",
        "http://example.com/br/2",
        "http://example.com/br/3",
        "http://example.com/br/4",
        "http://example.com/br/5",
        "http://example.com/br/7",
    ]


def test_brs_have_only_one_list_of_authors(deduplicated_graph_set: GraphSet) -> None:
    contributor_counts_by_br = {str(br): len(br.get_contributors()) for br in deduplicated_graph_set.get_br()}
    assert contributor_counts_by_br == EXPECTED_BR_CONTRIBUTOR_COUNTS


def test_deduplication_keeps_distinct_named_authors_by_default_when_duplicate_brs_merge(tmp_path: Path) -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = _add_article_with_shared_doi(graph_set, "First")
    second_br = _add_article_with_shared_doi(graph_set, "Second")
    _add_author(graph_set, first_br)
    _add_author(graph_set, second_br)
    orphan_author = graph_set.add_ar(RESP_AGENT)
    orphan_author.create_author()
    second_br.has_contributor(orphan_author)
    graph_set.commit_changes()

    deduplicated_graph_set = _deduplicate_graph_set(graph_set, tmp_path)

    assert [str(br) for br in deduplicated_graph_set.get_br()] == ["https://w3id.org/oc/meta/br/1"]
    assert _agent_role_uris_from_brs(deduplicated_graph_set) == [
        "https://w3id.org/oc/meta/ar/1",
        "https://w3id.org/oc/meta/ar/2",
    ]
    assert [_author_names(br) for br in deduplicated_graph_set.get_br()] == [["Ada Lovelace", "Ada Lovelace"]]
    assert _dangling_agent_role_uris_from_brs(deduplicated_graph_set) == []


def test_deduplication_keeps_valid_agent_role_when_duplicate_brs_share_responsible_agent(tmp_path: Path) -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = _add_article_with_shared_doi(graph_set, "First")
    second_br = _add_article_with_shared_doi(graph_set, "Second")
    responsible_agent = graph_set.add_ra(RESP_AGENT)
    responsible_agent.has_given_name("Ada")
    responsible_agent.has_family_name("Lovelace")
    _add_author_with_responsible_agent(graph_set, first_br, responsible_agent)
    _add_author_with_responsible_agent(graph_set, second_br, responsible_agent)
    graph_set.commit_changes()

    deduplicated_graph_set = _deduplicate_graph_set(graph_set, tmp_path)

    assert [str(br) for br in deduplicated_graph_set.get_br()] == ["https://w3id.org/oc/meta/br/1"]
    assert _agent_role_uris(deduplicated_graph_set) == ["https://w3id.org/oc/meta/ar/1"]
    assert _agent_role_uris_from_brs(deduplicated_graph_set) == ["https://w3id.org/oc/meta/ar/1"]
    assert [_author_names(br) for br in deduplicated_graph_set.get_br()] == [["Ada Lovelace"]]


def test_deduplication_merges_case_insensitive_named_contributors_when_enabled(tmp_path: Path) -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = _add_article_with_shared_doi(graph_set, "First")
    second_br = _add_article_with_shared_doi(graph_set, "Second")
    _add_author(graph_set, first_br, "Ada", "Lovelace")
    _add_author(graph_set, second_br, "ada", "lovelace")
    graph_set.commit_changes()

    deduplicated_graph_set = _deduplicate_graph_set(graph_set, tmp_path, merge_similar_named_contributors=True)

    assert [str(br) for br in deduplicated_graph_set.get_br()] == ["https://w3id.org/oc/meta/br/1"]
    assert _agent_role_uris(deduplicated_graph_set) == ["https://w3id.org/oc/meta/ar/1"]
    assert _agent_role_uris_from_brs(deduplicated_graph_set) == ["https://w3id.org/oc/meta/ar/1"]


def test_deduplicate_runs_without_storage() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = _add_article_with_shared_doi(graph_set, "First")
    _add_article_with_shared_doi(graph_set, "Second")
    graph_set.commit_changes()

    deduplicated_graph_set = GraphDeduplicator(graph_set).deduplicate()

    assert deduplicated_graph_set is graph_set
    assert _entity_uris_with_triples(deduplicated_graph_set.get_br()) == [str(first_br)]


def test_save_without_storage_fails() -> None:
    deduplicator = GraphDeduplicator(GraphSet(BASE_IRI))

    with pytest.raises(ValueError, match="storage is required"):
        deduplicator.save()


def test_preferred_survivor_keeps_requested_bibliographic_resource() -> None:
    graph_set = GraphSet(BASE_IRI)
    _add_article_with_shared_doi(graph_set, "First")
    second_br = _add_article_with_shared_doi(graph_set, "Second")
    graph_set.commit_changes()

    GraphDeduplicator(
        graph_set,
        preferred_survivors={str(second_br)},
    ).deduplicate()

    assert _entity_uris_with_triples(graph_set.get_br()) == [str(second_br)]


def test_deduplicate_keeps_more_informative_bibliographic_resource_without_preference() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = _add_article_with_shared_doi(graph_set, "Shared title")
    first_br.has_pub_date("2020")
    second_br = _add_article_with_shared_doi(graph_set, "Shared title")
    second_br.has_subtitle("Detailed subtitle")
    second_br.has_pub_date("2020-05-12")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).deduplicate_bibliographic_resources()

    assert _entity_uris_with_triples(graph_set.get_br()) == [str(second_br)]
    assert second_br.get_pub_date() == "2020-05-12"
    assert second_br.get_subtitle() == "Detailed subtitle"


def test_deduplicate_keeps_more_informative_responsible_agent_without_preference() -> None:
    graph_set = GraphSet(BASE_IRI)
    _add_responsible_agent_with_orcid(graph_set, "A.", "Lovelace")
    second_ra = _add_responsible_agent_with_orcid(graph_set, "Ada", "Lovelace")
    second_ra.has_name("Ada Lovelace")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).deduplicate_responsible_agents()

    assert _entity_uris_with_triples(graph_set.get_ra()) == [str(second_ra)]
    assert second_ra.get_name() == "Ada Lovelace"


def test_preferred_survivor_keeps_requested_responsible_agent() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_ra = _add_responsible_agent_with_orcid(graph_set, "Ada", "Lovelace")
    second_ra = _add_responsible_agent_with_orcid(graph_set, "A.", "Lovelace")
    author_role = graph_set.add_ar(RESP_AGENT)
    author_role.create_author()
    author_role.is_held_by(first_ra)
    graph_set.commit_changes()

    deduplicated_graph_set = GraphDeduplicator(
        graph_set,
        preferred_survivors={str(second_ra)},
    ).deduplicate()

    assert _entity_uris_with_triples(deduplicated_graph_set.get_ra()) == [str(second_ra)]
    assert [str(ar.get_is_held_by()) for ar in deduplicated_graph_set.get_ar()] == [str(second_ra)]


def test_preferred_survivor_keeps_requested_identifier() -> None:
    graph_set = GraphSet(BASE_IRI)
    br = _add_article_with_shared_doi(graph_set, "First")
    add_id(br, "10.555/shared", "doi", graph_set)
    second_identifier = sorted(br.get_identifiers(), key=str)[1]
    graph_set.commit_changes()

    GraphDeduplicator(
        graph_set,
        preferred_survivors={str(second_identifier)},
    ).deduplicate()

    assert _entity_uris_with_triples(graph_set.get_id()) == [str(second_identifier)]
    assert [str(identifier) for identifier in br.get_identifiers()] == [str(second_identifier)]


def test_preferred_survivor_ignores_uri_outside_cluster() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = _add_article_with_shared_doi(graph_set, "First")
    _add_article_with_shared_doi(graph_set, "Second")
    graph_set.commit_changes()

    GraphDeduplicator(
        graph_set,
        preferred_survivors={"https://w3id.org/oc/meta/br/999"},
    ).deduplicate()

    assert _entity_uris_with_triples(graph_set.get_br()) == [str(first_br)]


def test_preferred_survivor_rejects_conflicting_cluster_preferences() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = _add_article_with_shared_doi(graph_set, "First")
    second_br = _add_article_with_shared_doi(graph_set, "Second")
    graph_set.commit_changes()

    deduplicator = GraphDeduplicator(
        graph_set,
        preferred_survivors={str(first_br), str(second_br)},
    )

    with pytest.raises(ValueError, match="Conflicting preferred survivors"):
        deduplicator.deduplicate()


def test_merge_clusters_merges_responsible_agents_with_distinct_identifiers() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_ra = graph_set.add_ra(RESP_AGENT)
    first_ra.has_name("Ada Lovelace")
    add_id(first_ra, "0000-0002-1825-0097", "orcid", graph_set)
    second_ra = graph_set.add_ra(RESP_AGENT)
    second_ra.has_name("A. Lovelace")
    add_id(second_ra, "123456", "viaf", graph_set)
    author_role = graph_set.add_ar(RESP_AGENT)
    author_role.create_author()
    author_role.is_held_by(second_ra)
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_ra): [str(second_ra)]})

    assert _entity_uris_with_triples(graph_set.get_ra()) == [str(first_ra)]
    assert sorted(identifier_key(identifier) for identifier in first_ra.get_identifiers()) == [
        "http://purl.org/spar/datacite/orcid0000-0002-1825-0097",
        "http://purl.org/spar/datacite/viaf123456",
    ]
    assert first_ra.get_name() == "Ada Lovelace"
    assert [str(author_role.get_is_held_by())] == [str(first_ra)]


def test_merge_clusters_preserves_responsible_agent_functional_values_and_fills_missing_values() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_ra = graph_set.add_ra(RESP_AGENT)
    first_ra.has_name("Ada Lovelace")
    first_ra.has_given_name("Augusta")
    second_ra = graph_set.add_ra(RESP_AGENT)
    second_ra.has_name("A. Lovelace")
    second_ra.has_given_name("Ada")
    second_ra.has_family_name("Lovelace")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_ra): [str(second_ra)]})

    assert _entity_uris_with_triples(graph_set.get_ra()) == [str(first_ra)]
    assert first_ra.get_name() == "Ada Lovelace"
    assert first_ra.get_given_name() == "Augusta"
    assert first_ra.get_family_name() == "Lovelace"


def test_deduplicate_responsible_agents_merges_duplicate_contributors_after_ra_merge() -> None:
    graph_set = GraphSet(BASE_IRI)
    br = graph_set.add_br(RESP_AGENT)
    br.create_journal_article()
    br.has_title("Paper")
    first_ra = _add_responsible_agent_with_orcid(graph_set, "Ada", "Lovelace")
    second_ra = _add_responsible_agent_with_orcid(graph_set, "A.", "Lovelace")
    first_author_role = graph_set.add_ar(RESP_AGENT)
    first_author_role.create_author()
    first_author_role.is_held_by(first_ra)
    br.has_contributor(first_author_role)
    second_author_role = graph_set.add_ar(RESP_AGENT)
    second_author_role.create_author()
    second_author_role.is_held_by(second_ra)
    br.has_contributor(second_author_role)
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).deduplicate_responsible_agents()

    assert _entity_uris_with_triples(graph_set.get_ra()) == [str(first_ra)]
    assert _entity_uris_with_triples(graph_set.get_ar()) == [str(first_author_role)]
    assert _agent_role_uris_from_brs(graph_set) == [str(first_author_role)]
    assert [str(first_author_role.get_is_held_by())] == [str(first_ra)]


def _has_next_chain_has_cycle(agent_roles: Iterable[AgentRole]) -> bool:
    surviving = [ar for ar in agent_roles if list(ar.g.triples((None, None, None)))]
    for start in surviving:
        seen: set[str] = set()
        current: AgentRole | None = start
        while current is not None:
            key = str(current.res)
            if key in seen:
                return True
            seen.add(key)
            current = current.get_next()
    return False


def test_deduplicate_contributors_keeps_author_chain_acyclic_after_ra_merge() -> None:
    graph_set = GraphSet(BASE_IRI)
    br = graph_set.add_br(RESP_AGENT)
    br.create_journal_article()
    br.has_title("Paper")
    surviving_ra = graph_set.add_ra(RESP_AGENT)
    surviving_ra.has_given_name("Ada")
    surviving_ra.has_family_name("Lovelace")
    middle_ra = graph_set.add_ra(RESP_AGENT)
    middle_ra.has_given_name("Alan")
    middle_ra.has_family_name("Turing")
    duplicate_ra = graph_set.add_ra(RESP_AGENT)
    duplicate_ra.has_given_name("Ada")
    duplicate_ra.has_family_name("Lovelace")
    first_role = graph_set.add_ar(RESP_AGENT)
    first_role.create_author()
    first_role.is_held_by(surviving_ra)
    middle_role = graph_set.add_ar(RESP_AGENT)
    middle_role.create_author()
    middle_role.is_held_by(middle_ra)
    last_role = graph_set.add_ar(RESP_AGENT)
    last_role.create_author()
    last_role.is_held_by(duplicate_ra)
    first_role.has_next(middle_role)
    middle_role.has_next(last_role)
    br.has_contributor(first_role)
    br.has_contributor(middle_role)
    br.has_contributor(last_role)
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(surviving_ra): [str(duplicate_ra)]})

    assert not _has_next_chain_has_cycle(graph_set.get_ar())
    surviving_roles = _entity_uris_with_triples(graph_set.get_ar())
    assert surviving_roles == sorted([str(first_role), str(middle_role)])


def test_deduplicate_adjacent_duplicate_contributors_avoids_self_loop_after_ra_merge() -> None:
    graph_set = GraphSet(BASE_IRI)
    br = graph_set.add_br(RESP_AGENT)
    br.create_journal_article()
    br.has_title("Paper")
    surviving_ra = graph_set.add_ra(RESP_AGENT)
    surviving_ra.has_given_name("Ada")
    surviving_ra.has_family_name("Lovelace")
    duplicate_ra = graph_set.add_ra(RESP_AGENT)
    duplicate_ra.has_given_name("Ada")
    duplicate_ra.has_family_name("Lovelace")
    first_role = graph_set.add_ar(RESP_AGENT)
    first_role.create_author()
    first_role.is_held_by(surviving_ra)
    second_role = graph_set.add_ar(RESP_AGENT)
    second_role.create_author()
    second_role.is_held_by(duplicate_ra)
    first_role.has_next(second_role)
    br.has_contributor(first_role)
    br.has_contributor(second_role)
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(surviving_ra): [str(duplicate_ra)]})

    assert not _has_next_chain_has_cycle(graph_set.get_ar())
    surviving_roles = _entity_uris_with_triples(graph_set.get_ar())
    assert surviving_roles == [str(first_role)]
    remaining_role = next(ar for ar in graph_set.get_ar() if list(ar.g.triples((None, None, None))))
    assert remaining_role.get_next() is None


def test_merge_clusters_merges_only_requested_bibliographic_resources() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = graph_set.add_br(RESP_AGENT)
    first_br.create_journal_article()
    first_br.has_title("First")
    add_id(first_br, "10.555/first", "doi", graph_set)
    second_br = graph_set.add_br(RESP_AGENT)
    second_br.create_journal_article()
    second_br.has_title("Second")
    add_id(second_br, "10.555/second", "doi", graph_set)
    untouched_first_br = _add_article_with_shared_doi(graph_set, "Untouched first")
    untouched_second_br = _add_article_with_shared_doi(graph_set, "Untouched second")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_br): [str(second_br)]})

    assert _entity_uris_with_triples(graph_set.get_br()) == [
        str(first_br),
        str(untouched_first_br),
        str(untouched_second_br),
    ]
    assert sorted(identifier_key(identifier) for identifier in first_br.get_identifiers()) == [
        "http://purl.org/spar/datacite/doi10.555/first",
        "http://purl.org/spar/datacite/doi10.555/second",
    ]


def test_merge_clusters_preserves_bibliographic_resource_functional_values_and_fills_missing_values() -> None:
    graph_set = GraphSet(BASE_IRI)
    surviving_container = graph_set.add_br(RESP_AGENT)
    surviving_container.create_issue()
    merged_container = graph_set.add_br(RESP_AGENT)
    merged_container.create_volume()
    first_br = graph_set.add_br(RESP_AGENT)
    first_br.create_journal_article()
    first_br.has_title("Surviving title")
    first_br.has_pub_date("2020")
    first_br.has_number("S1")
    first_br.is_part_of(surviving_container)
    add_id(first_br, "10.555/first", "doi", graph_set)
    second_br = graph_set.add_br(RESP_AGENT)
    second_br.create_journal_article()
    second_br.has_title("Merged title")
    second_br.has_subtitle("Merged subtitle")
    second_br.has_pub_date("2021")
    second_br.has_number("M1")
    second_br.has_edition("2")
    second_br.is_part_of(merged_container)
    add_id(second_br, "10.555/second", "doi", graph_set)
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_br): [str(second_br)]})

    assert _entity_uris_with_triples(graph_set.get_br()) == [
        str(surviving_container),
        str(merged_container),
        str(first_br),
    ]
    assert first_br.get_title() == "Surviving title"
    assert first_br.get_subtitle() == "Merged subtitle"
    assert str(first_br.get_is_part_of()) == str(surviving_container)
    assert first_br.get_pub_date() == "2020"
    assert first_br.get_number() == "S1"
    assert first_br.get_edition() == "2"
    assert sorted(identifier_key(identifier) for identifier in first_br.get_identifiers()) == [
        "http://purl.org/spar/datacite/doi10.555/first",
        "http://purl.org/spar/datacite/doi10.555/second",
    ]


def _article_in_container(
    graph_set: GraphSet,
    container: BibliographicResource,
    title: str,
) -> BibliographicResource:
    article = graph_set.add_br(RESP_AGENT)
    article.create_journal_article()
    article.has_title(title)
    article.is_part_of(container)
    return article


def test_merge_clusters_merges_containers_with_matching_sequence_number() -> None:
    graph_set = GraphSet(BASE_IRI)
    surviving_issue = graph_set.add_br(RESP_AGENT)
    surviving_issue.create_issue()
    surviving_issue.has_number("3")
    merged_issue = graph_set.add_br(RESP_AGENT)
    merged_issue.create_issue()
    merged_issue.has_number("3")
    first_br = _article_in_container(graph_set, surviving_issue, "First")
    second_br = _article_in_container(graph_set, merged_issue, "Second")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_br): [str(second_br)]})

    assert _entity_uris_with_triples(graph_set.get_br()) == [str(surviving_issue), str(first_br)]
    assert str(first_br.get_is_part_of()) == str(surviving_issue)


def test_merge_clusters_keeps_containers_with_different_sequence_number() -> None:
    graph_set = GraphSet(BASE_IRI)
    surviving_volume = graph_set.add_br(RESP_AGENT)
    surviving_volume.create_volume()
    surviving_volume.has_number("5")
    merged_volume = graph_set.add_br(RESP_AGENT)
    merged_volume.create_volume()
    merged_volume.has_number("7")
    first_br = _article_in_container(graph_set, surviving_volume, "First")
    second_br = _article_in_container(graph_set, merged_volume, "Second")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_br): [str(second_br)]})

    assert _entity_uris_with_triples(graph_set.get_br()) == [
        str(surviving_volume),
        str(merged_volume),
        str(first_br),
    ]
    assert str(first_br.get_is_part_of()) == str(surviving_volume)


def test_merge_clusters_keeps_containers_with_conflicting_identifiers() -> None:
    graph_set = GraphSet(BASE_IRI)
    surviving_issue = graph_set.add_br(RESP_AGENT)
    surviving_issue.create_issue()
    add_id(surviving_issue, "10.555/issue-a", "doi", graph_set)
    merged_issue = graph_set.add_br(RESP_AGENT)
    merged_issue.create_issue()
    add_id(merged_issue, "10.555/issue-b", "doi", graph_set)
    first_br = _article_in_container(graph_set, surviving_issue, "First")
    second_br = _article_in_container(graph_set, merged_issue, "Second")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_br): [str(second_br)]})

    assert _entity_uris_with_triples(graph_set.get_br()) == [
        str(surviving_issue),
        str(merged_issue),
        str(first_br),
    ]


def test_merge_clusters_merges_containers_that_share_an_identifier() -> None:
    graph_set = GraphSet(BASE_IRI)
    surviving_issue = graph_set.add_br(RESP_AGENT)
    surviving_issue.create_issue()
    surviving_issue.has_number("5")
    add_id(surviving_issue, "10.555/issue", "doi", graph_set)
    merged_issue = graph_set.add_br(RESP_AGENT)
    merged_issue.create_issue()
    merged_issue.has_number("7")
    add_id(merged_issue, "10.555/issue", "doi", graph_set)
    first_br = _article_in_container(graph_set, surviving_issue, "First")
    second_br = _article_in_container(graph_set, merged_issue, "Second")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_br): [str(second_br)]})

    assert _entity_uris_with_triples(graph_set.get_br()) == [str(surviving_issue), str(first_br)]


def test_merge_clusters_merges_journals_with_matching_title() -> None:
    graph_set = GraphSet(BASE_IRI)
    surviving_journal = graph_set.add_br(RESP_AGENT)
    surviving_journal.create_journal()
    surviving_journal.has_title("Journal of Testing")
    merged_journal = graph_set.add_br(RESP_AGENT)
    merged_journal.create_journal()
    merged_journal.has_title("journal of testing")
    first_br = _article_in_container(graph_set, surviving_journal, "First")
    second_br = _article_in_container(graph_set, merged_journal, "Second")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_br): [str(second_br)]})

    assert _entity_uris_with_triples(graph_set.get_br()) == [str(surviving_journal), str(first_br)]


def test_merge_clusters_keeps_journals_with_different_title() -> None:
    graph_set = GraphSet(BASE_IRI)
    surviving_journal = graph_set.add_br(RESP_AGENT)
    surviving_journal.create_journal()
    surviving_journal.has_title("Nature")
    merged_journal = graph_set.add_br(RESP_AGENT)
    merged_journal.create_journal()
    merged_journal.has_title("Science")
    first_br = _article_in_container(graph_set, surviving_journal, "First")
    second_br = _article_in_container(graph_set, merged_journal, "Second")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_br): [str(second_br)]})

    assert _entity_uris_with_triples(graph_set.get_br()) == [
        str(surviving_journal),
        str(merged_journal),
        str(first_br),
    ]


def test_merge_clusters_does_not_merge_equal_numbered_volumes_across_different_journals() -> None:
    graph_set = GraphSet(BASE_IRI)
    surviving_journal = graph_set.add_br(RESP_AGENT)
    surviving_journal.create_journal()
    surviving_journal.has_title("Nature")
    merged_journal = graph_set.add_br(RESP_AGENT)
    merged_journal.create_journal()
    merged_journal.has_title("Science")
    surviving_volume = graph_set.add_br(RESP_AGENT)
    surviving_volume.create_volume()
    surviving_volume.has_number("5")
    surviving_volume.is_part_of(surviving_journal)
    merged_volume = graph_set.add_br(RESP_AGENT)
    merged_volume.create_volume()
    merged_volume.has_number("5")
    merged_volume.is_part_of(merged_journal)
    first_br = _article_in_container(graph_set, surviving_volume, "First")
    second_br = _article_in_container(graph_set, merged_volume, "Second")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_br): [str(second_br)]})

    assert _entity_uris_with_triples(graph_set.get_br()) == [
        str(surviving_journal),
        str(merged_journal),
        str(surviving_volume),
        str(merged_volume),
        str(first_br),
    ]


def test_merge_clusters_keeps_container_shared_by_survivor_and_merged_entity() -> None:
    graph_set = GraphSet(BASE_IRI)
    shared_issue = graph_set.add_br(RESP_AGENT)
    shared_issue.create_issue()
    shared_issue.has_number("3")
    first_br = _article_in_container(graph_set, shared_issue, "First")
    second_br = _article_in_container(graph_set, shared_issue, "Second")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_br): [str(second_br)]})

    assert _entity_uris_with_triples(graph_set.get_br()) == [str(shared_issue), str(first_br)]
    assert str(first_br.get_is_part_of()) == str(shared_issue)


def _add_publisher(
    graph_set: GraphSet,
    br: BibliographicResource,
    *,
    identifier: str | None = None,
    name: str | None = None,
) -> AgentRole:
    agent = graph_set.add_ra(RESP_AGENT)
    if name is not None:
        agent.has_name(name)
    if identifier is not None:
        add_id(agent, identifier, "crossref", graph_set)
    role = graph_set.add_ar(RESP_AGENT)
    role.create_publisher()
    role.is_held_by(agent)
    br.has_contributor(role)
    return role


def test_merge_clusters_merges_publishers_that_share_an_identifier() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = graph_set.add_br(RESP_AGENT)
    first_br.create_journal_article()
    second_br = graph_set.add_br(RESP_AGENT)
    second_br.create_journal_article()
    surviving_publisher = _add_publisher(graph_set, first_br, identifier="crossref-1")
    _add_publisher(graph_set, second_br, identifier="crossref-1")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_br): [str(second_br)]})

    assert _entity_uris_with_triples(graph_set.get_ar()) == [str(surviving_publisher)]


def test_merge_clusters_keeps_publishers_with_conflicting_identifiers() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = graph_set.add_br(RESP_AGENT)
    first_br.create_journal_article()
    second_br = graph_set.add_br(RESP_AGENT)
    second_br.create_journal_article()
    surviving_publisher = _add_publisher(graph_set, first_br, identifier="crossref-1")
    merged_publisher = _add_publisher(graph_set, second_br, identifier="crossref-2")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_br): [str(second_br)]})

    assert _entity_uris_with_triples(graph_set.get_ar()) == sorted(
        [str(surviving_publisher), str(merged_publisher)],
    )


def test_merge_clusters_merges_publishers_with_matching_name() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = graph_set.add_br(RESP_AGENT)
    first_br.create_journal_article()
    second_br = graph_set.add_br(RESP_AGENT)
    second_br.create_journal_article()
    surviving_publisher = _add_publisher(graph_set, first_br, name="ACME Press")
    _add_publisher(graph_set, second_br, name="acme press")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_br): [str(second_br)]})

    assert _entity_uris_with_triples(graph_set.get_ar()) == [str(surviving_publisher)]


def test_merge_clusters_merges_equivalent_containers_when_survivor_starts_without_container() -> None:
    graph_set = GraphSet(BASE_IRI)
    surviving_article = graph_set.add_br(RESP_AGENT)
    surviving_article.create_journal_article()
    surviving_article.has_title("Survivor")
    first_journal = graph_set.add_br(RESP_AGENT)
    first_journal.create_journal()
    add_id(first_journal, "1234-5678", "issn", graph_set)
    first_merged = _article_in_container(graph_set, first_journal, "First")
    second_journal = graph_set.add_br(RESP_AGENT)
    second_journal.create_journal()
    add_id(second_journal, "1234-5678", "issn", graph_set)
    second_merged = _article_in_container(graph_set, second_journal, "Second")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters(
        {str(surviving_article): [str(first_merged), str(second_merged)]},
    )

    assert _entity_uris_with_triples(graph_set.get_br()) == sorted(
        [str(surviving_article), str(first_journal)],
    )
    assert str(surviving_article.get_is_part_of()) == str(first_journal)


def test_merge_clusters_keeps_survivor_publisher_responsible_agent() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = graph_set.add_br(RESP_AGENT)
    first_br.create_journal_article()
    second_br = graph_set.add_br(RESP_AGENT)
    second_br.create_journal_article()
    surviving_publisher = _add_publisher(graph_set, first_br, identifier="crossref-1")
    surviving_agent = surviving_publisher.get_is_held_by()
    _add_publisher(graph_set, second_br, identifier="crossref-1")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(first_br): [str(second_br)]})

    assert _entity_uris_with_triples(graph_set.get_ar()) == [str(surviving_publisher)]
    assert str(surviving_publisher.get_is_held_by()) == str(surviving_agent)


def _journal_with_issn(graph_set: GraphSet, issn: str) -> BibliographicResource:
    journal = graph_set.add_br(RESP_AGENT)
    journal.create_journal()
    add_id(journal, issn, "issn", graph_set)
    return journal


def _add_role_held_by(
    graph_set: GraphSet,
    br: BibliographicResource,
    agent: ResponsibleAgent,
    *,
    editor: bool = False,
) -> AgentRole:
    role = graph_set.add_ar(RESP_AGENT)
    if editor:
        role.create_editor()
    else:
        role.create_publisher()
    role.is_held_by(agent)
    br.has_contributor(role)
    return role


def test_merge_clusters_merges_cascaded_container_publishers_held_by_the_same_agent() -> None:
    # The publisher's responsible agent is loaded without a name or identifier, as
    # happens when the merge closure omits the agent two hops behind the role.
    graph_set = GraphSet(BASE_IRI)
    agent = graph_set.add_ra(RESP_AGENT)
    first_journal = _journal_with_issn(graph_set, "1234-5678")
    surviving_publisher = _add_role_held_by(graph_set, first_journal, agent)
    surviving_article = _article_in_container(graph_set, first_journal, "Survivor")
    second_journal = _journal_with_issn(graph_set, "1234-5678")
    _add_role_held_by(graph_set, second_journal, agent)
    merged_article = _article_in_container(graph_set, second_journal, "Merged")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(surviving_article): [str(merged_article)]})

    assert _entity_uris_with_triples(graph_set.get_br()) == sorted(
        [str(surviving_article), str(first_journal)],
    )
    assert _entity_uris_with_triples(graph_set.get_ar()) == [str(surviving_publisher)]


def test_merge_clusters_merges_cascaded_container_publishers_that_share_an_identifier() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_journal = _journal_with_issn(graph_set, "1234-5678")
    surviving_publisher = _add_publisher(graph_set, first_journal, identifier="crossref-1")
    surviving_article = _article_in_container(graph_set, first_journal, "Survivor")
    second_journal = _journal_with_issn(graph_set, "1234-5678")
    _add_publisher(graph_set, second_journal, identifier="crossref-1")
    merged_article = _article_in_container(graph_set, second_journal, "Merged")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(surviving_article): [str(merged_article)]})

    assert _entity_uris_with_triples(graph_set.get_ar()) == [str(surviving_publisher)]


def test_merge_clusters_keeps_cascaded_container_publishers_with_conflicting_identifiers() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_journal = _journal_with_issn(graph_set, "1234-5678")
    surviving_publisher = _add_publisher(graph_set, first_journal, identifier="crossref-1")
    surviving_article = _article_in_container(graph_set, first_journal, "Survivor")
    second_journal = _journal_with_issn(graph_set, "1234-5678")
    merged_publisher = _add_publisher(graph_set, second_journal, identifier="crossref-2")
    merged_article = _article_in_container(graph_set, second_journal, "Merged")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(surviving_article): [str(merged_article)]})

    assert _entity_uris_with_triples(graph_set.get_ar()) == sorted(
        [str(surviving_publisher), str(merged_publisher)],
    )


def test_merge_clusters_deduplicates_repeated_publisher_roles_after_ra_merge() -> None:
    graph_set = GraphSet(BASE_IRI)
    surviving_agent = graph_set.add_ra(RESP_AGENT)
    add_id(surviving_agent, "crossref-1", "crossref", graph_set)
    duplicate_agent = graph_set.add_ra(RESP_AGENT)
    add_id(duplicate_agent, "crossref-1", "crossref", graph_set)
    journal = _journal_with_issn(graph_set, "1234-5678")
    surviving_publisher = _add_role_held_by(graph_set, journal, surviving_agent)
    _add_role_held_by(graph_set, journal, duplicate_agent)
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(surviving_agent): [str(duplicate_agent)]})

    assert _entity_uris_with_triples(graph_set.get_ar()) == [str(surviving_publisher)]


def test_merge_clusters_deduplicates_repeated_publisher_roles_on_merged_container() -> None:
    graph_set = GraphSet(BASE_IRI)
    agent = graph_set.add_ra(RESP_AGENT)
    first_journal = _journal_with_issn(graph_set, "1234-5678")
    surviving_publisher = _add_role_held_by(graph_set, first_journal, agent)
    surviving_article = _article_in_container(graph_set, first_journal, "Survivor")
    second_journal = _journal_with_issn(graph_set, "1234-5678")
    _add_role_held_by(graph_set, second_journal, agent)
    _add_role_held_by(graph_set, second_journal, agent)
    merged_article = _article_in_container(graph_set, second_journal, "Merged")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(surviving_article): [str(merged_article)]})

    assert _entity_uris_with_triples(graph_set.get_ar()) == [str(surviving_publisher)]


def test_merge_clusters_merges_cascaded_container_editors_held_by_the_same_agent() -> None:
    graph_set = GraphSet(BASE_IRI)
    journal = _journal_with_issn(graph_set, "1234-5678")
    agent = graph_set.add_ra(RESP_AGENT)

    first_volume = graph_set.add_br(RESP_AGENT)
    first_volume.create_volume()
    first_volume.has_number("5")
    first_volume.is_part_of(journal)
    surviving_editor = _add_role_held_by(graph_set, first_volume, agent, editor=True)
    surviving_article = _article_in_container(graph_set, first_volume, "Survivor")

    second_volume = graph_set.add_br(RESP_AGENT)
    second_volume.create_volume()
    second_volume.has_number("5")
    second_volume.is_part_of(journal)
    _add_role_held_by(graph_set, second_volume, agent, editor=True)
    merged_article = _article_in_container(graph_set, second_volume, "Merged")
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(surviving_article): [str(merged_article)]})

    assert _entity_uris_with_triples(graph_set.get_br()) == sorted(
        [str(surviving_article), str(journal), str(first_volume)],
    )
    assert _entity_uris_with_triples(graph_set.get_ar()) == [str(surviving_editor)]


def test_merge_clusters_merges_identifiers_and_rewrites_references() -> None:
    graph_set = GraphSet(BASE_IRI)
    br = graph_set.add_br(RESP_AGENT)
    br.create_journal_article()
    surviving_identifier = graph_set.add_id(RESP_AGENT)
    surviving_identifier.create_doi("10.555/first")
    br.has_identifier(surviving_identifier)
    merged_identifier = graph_set.add_id(RESP_AGENT)
    merged_identifier.create_doi("10.555/first")
    br.has_identifier(merged_identifier)
    graph_set.commit_changes()

    GraphDeduplicator(graph_set).merge_clusters({str(surviving_identifier): [str(merged_identifier)]})

    assert _entity_uris_with_triples(graph_set.get_id()) == [str(surviving_identifier)]
    assert [str(identifier) for identifier in br.get_identifiers()] == [str(surviving_identifier)]
    assert surviving_identifier.get_literal_value() == "10.555/first"


def test_merge_clusters_rejects_identifier_cluster_with_different_signature_before_mutation() -> None:
    graph_set = GraphSet(BASE_IRI)
    br = graph_set.add_br(RESP_AGENT)
    br.create_journal_article()
    surviving_identifier = graph_set.add_id(RESP_AGENT)
    surviving_identifier.create_doi("10.555/first")
    br.has_identifier(surviving_identifier)
    merged_identifier = graph_set.add_id(RESP_AGENT)
    merged_identifier.create_viaf("10.555/first")
    br.has_identifier(merged_identifier)
    graph_set.commit_changes()

    with pytest.raises(ValueError, match="different scheme/literal"):
        GraphDeduplicator(graph_set).merge_clusters({str(surviving_identifier): [str(merged_identifier)]})

    assert _entity_uris_with_triples(graph_set.get_id()) == [str(surviving_identifier), str(merged_identifier)]
    assert sorted(str(identifier) for identifier in br.get_identifiers()) == [
        str(surviving_identifier),
        str(merged_identifier),
    ]
    assert surviving_identifier.get_literal_value() == "10.555/first"
    assert merged_identifier.get_literal_value() == "10.555/first"


def test_merge_clusters_and_save_writes_graph_and_provenance(tmp_path: Path) -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = _add_article_with_shared_doi(graph_set, "First")
    second_br = _add_article_with_shared_doi(graph_set, "Second")
    graph_set.commit_changes()
    graph_path = tmp_path / "merged.rdf"
    provenance_path = tmp_path / "provenance.rdf"

    GraphDeduplicator(
        graph_set,
        single_file_storage(
            graph_path,
            provenance_path,
            output_format="nt11",
            zip_output=False,
        ),
    ).merge_clusters_and_save({str(first_br): [str(second_br)]})

    loaded_graph_set = load_graph_set(graph_path)

    assert graph_path.exists()
    assert provenance_path.exists()
    assert _entity_uris_with_triples(loaded_graph_set.get_br()) == [str(first_br)]


def test_merge_clusters_and_save_removes_deleted_entities_from_existing_directory_storage(tmp_path: Path) -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = _add_article_with_shared_doi(graph_set, "First")
    second_br = _add_article_with_shared_doi(graph_set, "Second")
    graph_set.commit_changes()
    output_dir = tmp_path / "ocdm"
    storage = directory_storage(output_dir, supplier_prefix="060", zip_output=False)
    deduplicator = GraphDeduplicator(graph_set, storage)
    deduplicator.save()

    deduplicator.merge_clusters_and_save({str(first_br): [str(second_br)]})

    graph_path = output_dir / "br" / "060" / "10000" / "1000.json"
    data = orjson.loads(graph_path.read_bytes())
    entity_uris = sorted(entity["@id"] for graph in data for entity in graph.get("@graph", []))

    assert entity_uris == [str(first_br)]


def test_deduplicate_and_save_removes_deleted_entities_from_directory_storage(tmp_path: Path) -> None:
    graph_set = GraphSet(BASE_IRI)
    first_br = _add_article_with_shared_doi(graph_set, "First")
    _add_article_with_shared_doi(graph_set, "Second")
    graph_set.commit_changes()
    output_dir = tmp_path / "ocdm"

    GraphDeduplicator(
        graph_set,
        directory_storage(output_dir, supplier_prefix="060", zip_output=False),
    ).deduplicate_and_save()

    graph_path = output_dir / "br" / "060" / "10000" / "1000.json"
    data = orjson.loads(graph_path.read_bytes())
    entity_uris = sorted(entity["@id"] for graph in data for entity in graph.get("@graph", []))

    assert entity_uris == [str(first_br)]


def test_merge_clusters_rejects_missing_entity_before_mutation() -> None:
    graph_set = GraphSet(BASE_IRI)
    br = _add_article_with_shared_doi(graph_set, "First")
    graph_set.commit_changes()

    with pytest.raises(ValueError, match="Entity not found"):
        GraphDeduplicator(graph_set).merge_clusters({str(br): ["https://w3id.org/oc/meta/br/999"]})

    assert _entity_uris_with_triples(graph_set.get_br()) == [str(br)]


def test_merge_clusters_rejects_mixed_entity_types_before_mutation() -> None:
    graph_set = GraphSet(BASE_IRI)
    br = _add_article_with_shared_doi(graph_set, "First")
    ra = _add_responsible_agent_with_orcid(graph_set, "Ada", "Lovelace")
    graph_set.commit_changes()

    with pytest.raises(ValueError, match="mixes entity types"):
        GraphDeduplicator(graph_set).merge_clusters({str(br): [str(ra)]})

    assert _entity_uris_with_triples(graph_set.get_br()) == [str(br)]
    assert _entity_uris_with_triples(graph_set.get_ra()) == [str(ra)]


def test_merge_clusters_rejects_incompatible_bibliographic_resource_types_before_mutation() -> None:
    graph_set = GraphSet(BASE_IRI)
    article = graph_set.add_br(RESP_AGENT)
    article.create_journal_article()
    add_id(article, "Q1", "wikidata", graph_set)
    journal = graph_set.add_br(RESP_AGENT)
    journal.create_journal()
    add_id(journal, "Q1", "wikidata", graph_set)
    child = _article_in_container(graph_set, journal, "Child")
    graph_set.commit_changes()

    with pytest.raises(ValueError, match="incompatible types"):
        GraphDeduplicator(graph_set).merge_clusters({str(article): [str(journal)]})

    assert _entity_uris_with_triples(graph_set.get_br()) == sorted(
        [str(article), str(journal), str(child)],
    )
    assert str(child.get_is_part_of()) == str(journal)


def test_merge_clusters_rejects_self_merge_before_mutation() -> None:
    graph_set = GraphSet(BASE_IRI)
    br = _add_article_with_shared_doi(graph_set, "First")
    graph_set.commit_changes()

    with pytest.raises(ValueError, match="cannot be merged into itself"):
        GraphDeduplicator(graph_set).merge_clusters({str(br): [str(br)]})

    assert _entity_uris_with_triples(graph_set.get_br()) == [str(br)]


def test_merge_clusters_rejects_entity_assigned_to_multiple_clusters() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_ra = _add_responsible_agent_with_orcid(graph_set, "Ada", "Lovelace")
    second_ra = _add_responsible_agent_with_orcid(graph_set, "A.", "Lovelace")
    third_ra = _add_responsible_agent_with_orcid(graph_set, "Augusta", "Lovelace")
    graph_set.commit_changes()

    with pytest.raises(ValueError, match="already assigned"):
        GraphDeduplicator(graph_set).merge_clusters(
            {
                str(first_ra): [str(second_ra)],
                str(third_ra): [str(second_ra)],
            },
        )

    assert _entity_uris_with_triples(graph_set.get_ra()) == [str(first_ra), str(second_ra), str(third_ra)]


def test_merge_clusters_rejects_entity_as_survivor_and_merged_entity() -> None:
    graph_set = GraphSet(BASE_IRI)
    first_ra = _add_responsible_agent_with_orcid(graph_set, "Ada", "Lovelace")
    second_ra = _add_responsible_agent_with_orcid(graph_set, "A.", "Lovelace")
    third_ra = _add_responsible_agent_with_orcid(graph_set, "Augusta", "Lovelace")
    graph_set.commit_changes()

    with pytest.raises(ValueError, match="cannot be both survivor and merged entity"):
        GraphDeduplicator(graph_set).merge_clusters(
            {
                str(first_ra): [str(second_ra)],
                str(second_ra): [str(third_ra)],
            },
        )

    assert _entity_uris_with_triples(graph_set.get_ra()) == [str(first_ra), str(second_ra), str(third_ra)]


def test_merge_clusters_orders_container_clusters_before_cascading_article_clusters() -> None:
    graph_set = GraphSet(BASE_IRI)
    canonical_journal = _journal_with_issn(graph_set, "1111-1111")
    cascaded_journal = _journal_with_issn(graph_set, "1111-1111")
    merged_journal = _journal_with_issn(graph_set, "1111-1111")
    surviving_article = _article_in_container(graph_set, canonical_journal, "Duplicated")
    merged_article = _article_in_container(graph_set, cascaded_journal, "Duplicated")
    sibling_article = _article_in_container(graph_set, merged_journal, "Sibling")
    graph_set.commit_changes()

    # The article cluster comes first in the mapping: its container cascade merges
    # cascaded_journal into canonical_journal and deletes it, so the journal
    # cluster would otherwise merge merged_journal into a deleted survivor,
    # leaving sibling_article's partOf dangling.
    GraphDeduplicator(graph_set).merge_clusters(
        {
            str(surviving_article): [str(merged_article)],
            str(cascaded_journal): [str(merged_journal)],
        },
    )

    assert _entity_uris_with_triples(graph_set.get_br()) == sorted(
        [str(canonical_journal), str(surviving_article), str(sibling_article)],
    )
    assert str(sibling_article.get_is_part_of()) == str(canonical_journal)


def test_merge_clusters_orders_identifier_clusters_before_bibliographic_resource_clusters() -> None:
    graph_set = GraphSet(BASE_IRI)
    surviving_br = _add_article_with_shared_doi(graph_set, "First")
    merged_br = _add_article_with_shared_doi(graph_set, "Second")
    third_br = _add_article_with_shared_doi(graph_set, "Third")
    merged_br_identifier = merged_br.get_identifiers()[0]
    third_br_identifier = third_br.get_identifiers()[0]
    graph_set.commit_changes()

    # The BR cluster comes first in the mapping: merging it deduplicates the
    # shared DOI and deletes one of the two identifier copies, which is the
    # survivor of the identifier cluster, so third_br's reference would
    # otherwise be redirected onto a deleted identifier.
    GraphDeduplicator(graph_set).merge_clusters(
        {
            str(surviving_br): [str(merged_br)],
            str(merged_br_identifier): [str(third_br_identifier)],
        },
    )

    surviving_identifiers = _entity_uris_with_triples(graph_set.get_id())
    assert len(surviving_identifiers) == 1
    assert [str(identifier) for identifier in surviving_br.get_identifiers()] == surviving_identifiers
    assert [str(identifier) for identifier in third_br.get_identifiers()] == surviving_identifiers


def test_merge_clusters_rejects_cluster_entity_already_deleted() -> None:
    graph_set = GraphSet(BASE_IRI)
    surviving_br = _add_article_with_shared_doi(graph_set, "First")
    merged_br = _add_article_with_shared_doi(graph_set, "Second")
    graph_set.commit_changes()
    surviving_br.mark_as_to_be_deleted()

    with pytest.raises(ValueError, match="is deleted"):
        GraphDeduplicator(graph_set).merge_clusters({str(surviving_br): [str(merged_br)]})


def test_provenance_configuration_is_forwarded_to_prov_set() -> None:
    counter_handler = _CounterHandler()
    storage = single_file_storage(
        "deduplicated.rdf",
        "provenance.rdf",
        supplier_prefix="060",
        wanted_label=False,
        counter_handler=counter_handler,
    )

    deduplicator = GraphDeduplicator(
        GraphSet(BASE_IRI),
        storage=storage,
    )

    assert deduplicator.prov.supplier_prefix == "060"
    assert deduplicator.prov.wanted_label is False
    assert deduplicator.prov.counter_handler is counter_handler


def _add_article_with_shared_doi(graph_set: GraphSet, title: str) -> BibliographicResource:
    br = graph_set.add_br(RESP_AGENT)
    br.create_journal_article()
    br.has_title(title)
    add_id(br, "10.555/shared", "doi", graph_set)
    return br


def _deduplicate_graph_set(
    graph_set: GraphSet,
    tmp_path: Path,
    *,
    merge_similar_named_contributors: bool = False,
) -> GraphSet:
    deduplicator = GraphDeduplicator(
        graph_set,
        single_file_storage(
            tmp_path / "deduplicated.rdf",
            tmp_path / "provenance.rdf",
            output_format="nt11",
            zip_output=False,
        ),
        debug=True,
        merge_similar_named_contributors=merge_similar_named_contributors,
    )
    deduplicator.deduplicate_and_save()
    return load_graph_set(tmp_path / "deduplicated.rdf")


def _add_author(
    graph_set: GraphSet,
    br: BibliographicResource,
    given_name: str = "Ada",
    family_name: str = "Lovelace",
) -> None:
    responsible_agent = graph_set.add_ra(RESP_AGENT)
    responsible_agent.has_given_name(given_name)
    responsible_agent.has_family_name(family_name)
    _add_author_with_responsible_agent(graph_set, br, responsible_agent)


def _add_author_with_responsible_agent(
    graph_set: GraphSet,
    br: BibliographicResource,
    responsible_agent: ResponsibleAgent,
) -> None:
    author = graph_set.add_ar(RESP_AGENT)
    author.create_author()
    author.is_held_by(responsible_agent)
    br.has_contributor(author)


def _add_responsible_agent_with_orcid(
    graph_set: GraphSet,
    given_name: str,
    family_name: str,
) -> ResponsibleAgent:
    responsible_agent = graph_set.add_ra(RESP_AGENT)
    responsible_agent.has_given_name(given_name)
    responsible_agent.has_family_name(family_name)
    add_id(responsible_agent, "0000-0002-1825-0097", "orcid", graph_set)
    return responsible_agent


def _author_names(br: BibliographicResource) -> list[str]:
    names = []
    for contributor in br.get_contributors():
        responsible_agent = contributor.get_is_held_by()
        if responsible_agent is not None:
            names.append(f"{responsible_agent.get_given_name()} {responsible_agent.get_family_name()}")
    return sorted(names)


def _agent_role_uris(graph_set: GraphSet) -> list[str]:
    return sorted(str(ar) for ar in graph_set.get_ar())


def _agent_role_uris_from_brs(graph_set: GraphSet) -> list[str]:
    return sorted(str(ar) for br in graph_set.get_br() for ar in br.get_contributors())


def _dangling_agent_role_uris_from_brs(graph_set: GraphSet) -> list[str]:
    agent_role_uris = set(_agent_role_uris(graph_set))
    return sorted(uri for uri in _agent_role_uris_from_brs(graph_set) if uri not in agent_role_uris)


def _entity_uris_with_triples(
    entities: Iterable[BibliographicResource | ResponsibleAgent | Identifier | AgentRole],
) -> list[str]:
    return sorted(str(entity) for entity in entities if list(entity.g.triples((None, None, None))))


class _CounterHandler(CounterHandler):
    def increment_counter(
        self,
        entity_short_name: str,
        prov_short_name: str = "",
        identifier: int = 1,
        supplier_prefix: str = "",
    ) -> int:
        del entity_short_name, prov_short_name, identifier, supplier_prefix
        return 1

    def read_counter(
        self,
        entity_short_name: str,
        prov_short_name: str = "",
        identifier: int = 1,
        supplier_prefix: str = "",
    ) -> int:
        del entity_short_name, prov_short_name, identifier, supplier_prefix
        return 1

    def set_counter(
        self,
        new_value: int,
        entity_short_name: str,
        prov_short_name: str = "",
        identifier: int = 1,
        supplier_prefix: str = "",
    ) -> None:
        del new_value, entity_short_name, prov_short_name, identifier, supplier_prefix

    def increment_metadata_counter(self, entity_short_name: str, dataset_name: str | None) -> int:
        del entity_short_name, dataset_name
        return 1

    def read_metadata_counter(self, entity_short_name: str, dataset_name: str | None) -> int:
        del entity_short_name, dataset_name
        return 1

    def set_metadata_counter(self, new_value: int, entity_short_name: str, dataset_name: str | None) -> None:
        del new_value, entity_short_name, dataset_name
