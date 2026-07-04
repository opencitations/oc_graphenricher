# SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from collections.abc import Iterable
from pathlib import Path

import pytest
from oc_ocdm.counter_handler import CounterHandler
from oc_ocdm.graph.entities.bibliographic.bibliographic_resource import BibliographicResource
from oc_ocdm.graph.entities.bibliographic.responsible_agent import ResponsibleAgent
from oc_ocdm.graph.entities.identifier import Identifier
from oc_ocdm.graph.graph_set import GraphSet

from oc_graphenricher.deduplication import GraphDeduplicator
from oc_graphenricher.storage import single_file_storage
from tests.helpers import BASE_IRI, RESP_AGENT, add_id, load_graph_set

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
    entities: Iterable[BibliographicResource | ResponsibleAgent | Identifier],
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
