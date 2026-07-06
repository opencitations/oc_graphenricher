# SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
# SPDX-FileCopyrightText: 2021 Simone Persiani
# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING, TypeAlias, TypeVar, cast

import Levenshtein
import networkx as nx
from oc_ocdm.graph.entities.bibliographic.bibliographic_resource import BibliographicResource
from oc_ocdm.graph.entities.bibliographic.responsible_agent import ResponsibleAgent
from oc_ocdm.graph.entities.identifier import Identifier
from oc_ocdm.graph.graph_entity import GraphEntity
from oc_ocdm.prov.prov_set import ProvSet

from oc_graphenricher._storage import store_graph_set, store_provenance

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from oc_ocdm.graph.entities.bibliographic.agent_role import AgentRole
    from oc_ocdm.graph.graph_set import GraphSet

    from oc_graphenricher.storage import Storage

LOGGER = logging.getLogger(__name__)
NAME_SIMILARITY_THRESHOLD = 0.95
Entity = TypeVar("Entity")
ManualMergeEntity: TypeAlias = BibliographicResource | ResponsibleAgent | Identifier
IdentifierSignature: TypeAlias = tuple[str, str]


class GraphDeduplicator:
    def __init__(
        self,
        graph_set: GraphSet,
        storage: Storage | None = None,
        *,
        debug: bool = False,
        merge_similar_named_contributors: bool = False,
        preferred_survivors: set[str] | None = None,
    ) -> None:
        """
        Initialize the graph deduplicator.

        The deduplicator merges duplicate entities in a graph set compliant with the OpenCitations Data Model.

        :param graph_set: input graph set
        :param storage: output storage configuration
        :param debug: a bool flag to enable richer output
        :param merge_similar_named_contributors: merge contributor roles with similar author names within merged BRs
        :param preferred_survivors: entity URIs to keep when they appear in duplicate clusters
        """
        self.graph_set = graph_set
        self.storage = storage
        self.debug = debug
        self.merge_similar_named_contributors = merge_similar_named_contributors
        self.preferred_survivors = preferred_survivors if preferred_survivors is not None else set()
        self.modified_entities: set[str] = set()
        self.prov = self.__provenance()

    def deduplicate_and_save(self) -> GraphSet:
        """
        Deduplicate the graph set and save the graph and provenance.

        The process will:
        - deduplicate the Responsible Agents (RAs)
        - deduplicate the Bibliographic Resources (BRs)
        - deduplicate the IDs.

        In the end, this process will produce:
            - the configured graph output without the duplicates.
            - the configured provenance output tracking the changes done.
        """
        self.__deduplicate_responsible_agents()
        self.__save_and_commit()
        self.__deduplicate_bibliographic_resources()
        self.__save_and_commit()
        self.__deduplicate_identifiers()
        self.__save_and_commit()
        return self.graph_set

    def deduplicate(self) -> GraphSet:
        """Deduplicate the graph set without serializing the graph set or provenance."""
        self.deduplicate_responsible_agents()
        self.deduplicate_bibliographic_resources()
        self.deduplicate_identifiers()
        return self.graph_set

    def merge_clusters(self, clusters: Mapping[str, Iterable[str]]) -> GraphSet:
        self.__merge_clusters(clusters)
        self.graph_set.commit_changes()
        return self.graph_set

    def __merge_clusters(self, clusters: Mapping[str, Iterable[str]]) -> None:
        normalized_clusters = self.__manual_merge_clusters(clusters)
        if not normalized_clusters:
            return

        self.__validate_identifier_clusters(normalized_clusters)
        associated_ar_ra = self.__get_association_ar_ra()
        _, id_to_resources = self.__id_maps()

        for surviving_entity, merged_entities in normalized_clusters:
            if isinstance(surviving_entity, ResponsibleAgent):
                for merged_entity in merged_entities:
                    self.__merge_responsible_agent(
                        surviving_entity,
                        self.__as_responsible_agent(merged_entity),
                        associated_ar_ra,
                    )
            elif isinstance(surviving_entity, BibliographicResource):
                self.__merge_bibliographic_resources(
                    surviving_entity,
                    [self.__as_bibliographic_resource(merged_entity) for merged_entity in merged_entities],
                )
            else:
                self.__merge_identifiers(
                    surviving_entity,
                    [self.__as_identifier(merged_entity) for merged_entity in merged_entities],
                    id_to_resources,
                )

        self.modified_entities.update(self.prov.generate_provenance())

    def merge_clusters_and_save(self, clusters: Mapping[str, Iterable[str]]) -> GraphSet:
        self.__merge_clusters(clusters)
        self.__save_and_commit()
        return self.graph_set

    def save(self) -> None:
        """
        Serialize the graph set into the specified RDF file.

        Serialize the provenance in another specified RDF file.
        """
        storage = self.__storage()
        store_graph_set(self.graph_set, storage)
        store_provenance(self.prov, storage)

    def __save_and_commit(self) -> None:
        self.save()
        self.graph_set.commit_changes()
        self.modified_entities.clear()

    def deduplicate_responsible_agents(self) -> None:
        """
        Discover Responsible Agents (RAs) that share the same identifier literal.

        The process creates a graph of duplicate entities, merges each connected component into one RA, updates Agent
        Role references, generates provenance and commits pending changes in the graph set.
        """
        self.__deduplicate_responsible_agents()
        self.graph_set.commit_changes()

    def __deduplicate_responsible_agents(self) -> None:
        associated_ar_ra = self.__get_association_ar_ra()
        clusters = self.__sorted_clusters(
            self.__merge_graph(self.graph_set.get_ra(), "[dedup-RA] Will merge %s and %s due to %s:%s in common"),
        )
        LOGGER.info("[dedup-RA] Number of clusters: %s", len(clusters))

        for cluster_index, cluster in enumerate(clusters):
            entity_first_raw, other_entities_raw = self.__ordered_entities(cluster)
            entity_first = self.__as_responsible_agent(entity_first_raw)
            self.__debug("[dedup-RA] Merging cluster #%s, with %s entities", cluster_index, len(cluster))
            for other_entity_raw in other_entities_raw:
                self.__merge_responsible_agent(
                    entity_first,
                    self.__as_responsible_agent(other_entity_raw),
                    associated_ar_ra,
                )

        self.modified_entities.update(self.prov.generate_provenance())

    def deduplicate_bibliographic_resources(self) -> None:
        """
        Discover Bibliographic Resources (BRs) that share the same identifier literal.

        The process creates a graph of duplicate BRs, merges each connected component into one BR, merges containers and
        publishers where possible, generates provenance and commits pending changes in the graph set.
        """
        self.__deduplicate_bibliographic_resources()
        self.graph_set.commit_changes()

    def __deduplicate_bibliographic_resources(self) -> None:
        clusters = self.__sorted_clusters(
            self.__merge_graph(self.graph_set.get_br(), "[dedup-BR] Will merge %s into %s due to %s:%s in common"),
        )
        LOGGER.info("[dedup-BR] Number of clusters: %s", len(clusters))

        for cluster_index, cluster in enumerate(clusters):
            self.__debug("[dedup-BR] Merging cluster #%s, with %s entities", cluster_index, len(cluster))
            self.__merge_br_cluster(cluster)

        self.modified_entities.update(self.prov.generate_provenance())

    def deduplicate_identifiers(self) -> None:
        """
        Discover duplicate IDs related to Bibliographic Resources and Responsible Agents.

        IDs are duplicates when they share the same schema and literal. The process merges duplicates into one ID,
        substitutes references with the merged ID, generates provenance and commits pending changes in the graph set.
        """
        self.__deduplicate_identifiers()
        self.graph_set.commit_changes()

    def __deduplicate_identifiers(self) -> None:
        literal_to_id, id_to_resources = self.__id_maps()
        for literal, identifiers in literal_to_id.items():
            if len(identifiers) > 1:
                self.__merge_identifier_group(literal, identifiers, id_to_resources)

        self.modified_entities.update(self.prov.generate_provenance())

    def __merge_graph(
        self,
        entities: Iterable[ResponsibleAgent | BibliographicResource],
        debug_message: str,
    ) -> nx.Graph:
        merge_graph: nx.Graph = nx.Graph()
        identifiers: dict[str, dict[str, ResponsibleAgent | BibliographicResource]] = {}
        for entity in entities:
            for identifier in entity.get_identifiers():
                scheme = identifier.get_scheme()
                literal_value = identifier.get_literal_value()
                if scheme is None or literal_value is None:
                    continue
                identifiers.setdefault(scheme, {})
                entity_first = identifiers[scheme].get(literal_value)
                if entity_first is None:
                    identifiers[scheme][literal_value] = entity
                else:
                    merge_graph.add_edge(entity_first, entity)
                    self.__debug(
                        debug_message,
                        entity.res,
                        entity_first.res,
                        scheme.split("/")[-1],
                        literal_value,
                    )
        return merge_graph

    def __sorted_clusters(self, merge_graph: nx.Graph) -> list[set[ResponsibleAgent | BibliographicResource]]:
        return sorted(nx.connected_components(merge_graph), key=len, reverse=True)

    def __manual_merge_clusters(
        self,
        clusters: Mapping[str, Iterable[str]],
    ) -> list[tuple[ManualMergeEntity, list[ManualMergeEntity]]]:
        normalized_clusters: list[tuple[ManualMergeEntity, list[ManualMergeEntity]]] = []
        survivors: set[str] = set()
        merged_to_survivor: dict[str, str] = {}
        container_uris = self.__container_uris_with_members()

        for survivor_uri, merged_uris in clusters.items():
            survivor = self.__manual_survivor(survivor_uri, merged_uris, survivors, merged_to_survivor)
            survivor_type = self.__merge_entity_type(survivor)
            merged_entities = [
                self.__manual_merged_entity(
                    survivor_uri,
                    survivor_type,
                    merged_uri,
                    survivors,
                    merged_to_survivor,
                )
                for merged_uri in merged_uris
            ]

            if not merged_entities:
                message = f"Merge cluster for survivor {survivor_uri} must include at least one merged entity."
                raise ValueError(message)
            self.__validate_container_type_compatibility(survivor, merged_entities, container_uris)
            normalized_clusters.append((survivor, merged_entities))

        return normalized_clusters

    def __container_uris_with_members(self) -> set[str]:
        members: set[str] = set()
        for br in self.graph_set.get_br():
            container = br.get_is_part_of()
            if container is not None:
                members.add(str(container.res))
        return members

    def __validate_container_type_compatibility(
        self,
        survivor: ManualMergeEntity,
        merged_entities: Iterable[ManualMergeEntity],
        container_uris: set[str],
    ) -> None:
        if not isinstance(survivor, BibliographicResource):
            return
        survivor_types = set(self.__specific_types(survivor))
        for merged_entity in merged_entities:
            merged = self.__as_bibliographic_resource(merged_entity)
            merged_types = set(self.__specific_types(merged))
            if not survivor_types or not merged_types or not survivor_types.isdisjoint(merged_types):
                continue
            if str(survivor.res) in container_uris or str(merged.res) in container_uris:
                message = (
                    "Cannot merge bibliographic resources with incompatible types: "
                    f"{survivor.res} is {sorted(survivor_types)}, {merged.res} is {sorted(merged_types)}."
                )
                raise ValueError(message)

    def __validate_identifier_clusters(
        self,
        normalized_clusters: Iterable[tuple[ManualMergeEntity, list[ManualMergeEntity]]],
    ) -> None:
        for surviving_entity, merged_entities in normalized_clusters:
            if not isinstance(surviving_entity, Identifier):
                continue

            surviving_signature = self.__identifier_signature(surviving_entity)
            for merged_entity in merged_entities:
                merged_identifier = self.__as_identifier(merged_entity)
                merged_signature = self.__identifier_signature(merged_identifier)
                if merged_signature != surviving_signature:
                    message = (
                        "Cannot merge identifiers with different scheme/literal: "
                        f"{surviving_entity.res} has {surviving_signature[0]}#{surviving_signature[1]}, "
                        f"{merged_identifier.res} has {merged_signature[0]}#{merged_signature[1]}."
                    )
                    raise ValueError(message)

    @staticmethod
    def __identifier_signature(identifier: Identifier) -> IdentifierSignature:
        scheme = identifier.get_scheme()
        literal = identifier.get_literal_value()
        if scheme is None or literal is None:
            message = f"Cannot merge identifier {identifier.res} without scheme or literal."
            raise ValueError(message)
        return scheme, literal

    def __manual_survivor(
        self,
        survivor_uri: str,
        merged_uris: Iterable[str],
        survivors: set[str],
        merged_to_survivor: dict[str, str],
    ) -> ManualMergeEntity:
        if survivor_uri in merged_to_survivor:
            message = f"Entity {survivor_uri} cannot be both survivor and merged entity."
            raise ValueError(message)
        if survivor_uri in survivors:
            message = f"Duplicate survivor in merge clusters: {survivor_uri}."
            raise ValueError(message)
        if isinstance(merged_uris, str):
            message = f"Merge cluster for survivor {survivor_uri} must be an iterable of entity URIs."
            raise TypeError(message)

        survivors.add(survivor_uri)
        return self.__merge_entity(survivor_uri)

    def __manual_merged_entity(
        self,
        survivor_uri: str,
        survivor_type: str,
        merged_uri: str,
        survivors: set[str],
        merged_to_survivor: dict[str, str],
    ) -> ManualMergeEntity:
        if merged_uri == survivor_uri:
            message = f"Entity {survivor_uri} cannot be merged into itself."
            raise ValueError(message)
        if merged_uri in survivors:
            message = f"Entity {merged_uri} cannot be both survivor and merged entity."
            raise ValueError(message)
        if merged_uri in merged_to_survivor:
            message = f"Entity {merged_uri} is already assigned to survivor {merged_to_survivor[merged_uri]}."
            raise ValueError(message)

        merged_entity = self.__merge_entity(merged_uri)
        merged_entity_type = self.__merge_entity_type(merged_entity)
        if merged_entity_type != survivor_type:
            message = (
                f"Merge cluster for survivor {survivor_uri} mixes entity types: "
                f"{survivor_type} and {merged_entity_type}."
            )
            raise ValueError(message)

        merged_to_survivor[merged_uri] = survivor_uri
        return merged_entity

    def __merge_entity(self, uri: str) -> ManualMergeEntity:
        entity = self.graph_set.get_entity(uri)
        if entity is None:
            message = f"Entity not found in GraphSet: {uri}."
            raise ValueError(message)
        if isinstance(entity, BibliographicResource | ResponsibleAgent | Identifier):
            return entity
        message = f"Entity {uri} has unsupported merge type: {type(entity).__name__}."
        raise ValueError(message)

    @staticmethod
    def __merge_entity_type(entity: ManualMergeEntity) -> str:
        if isinstance(entity, ResponsibleAgent):
            return "ra"
        if isinstance(entity, BibliographicResource):
            return "br"
        return "id"

    def __merge_responsible_agent(
        self,
        entity_first: ResponsibleAgent,
        other_entity: ResponsibleAgent,
        associated_ar_ra: dict[ResponsibleAgent, list[AgentRole]],
    ) -> None:
        self.__debug("\tMerging responsible agent %s in responsible agent %s", other_entity, entity_first)
        entity_first.merge(other_entity, prefer_self=True)
        associated_ars = associated_ar_ra.get(other_entity, [])
        for ar in associated_ars:
            ar.is_held_by(entity_first)
            self.__debug("\tUnset %s as helded by of %s", other_entity, ar)
            self.__debug("\tSet %s as helded by of %s", entity_first, ar)
        self.__deduplicate_contributors_for_bibliographic_resources(
            self.__bibliographic_resources_for_contributors(associated_ars),
        )
        self.__debug("\tMarking to delete: %s", other_entity)

    def __merge_br_cluster(self, cluster: set[ResponsibleAgent | BibliographicResource]) -> None:
        entity_first_raw, other_entities_raw = self.__ordered_entities(cluster)
        self.__merge_bibliographic_resources(
            self.__as_bibliographic_resource(entity_first_raw),
            [self.__as_bibliographic_resource(other_entity) for other_entity in other_entities_raw],
        )

    def __merge_bibliographic_resources(
        self,
        entity_first: BibliographicResource,
        other_entities: Iterable[BibliographicResource],
    ) -> None:
        for other_entity in other_entities:
            # Recompute the survivor's publisher and part-of chain on every iteration: an
            # earlier merge may have filled a previously missing publisher or container, and
            # the next equivalent one must merge into it instead of surviving as a duplicate.
            publisher_first = self.__get_publisher(entity_first)
            entity_first_partofs = self.__get_part_of(entity_first)
            self.__merge_containers(entity_first_partofs, self.__get_part_of(other_entity))
            self.__merge_publisher(publisher_first, other_entity)
            entity_first.merge(other_entity, prefer_self=True)
            self.__deduplicate_contributors_for_bibliographic_resources([entity_first])

    def __merge_containers(
        self,
        entity_first_partofs: list[BibliographicResource],
        partofs: list[BibliographicResource],
    ) -> None:
        second_by_type: dict[str, BibliographicResource] = {}
        for container in partofs:
            for type_iri in self.__specific_types(container):
                second_by_type.setdefault(type_iri, container)

        parent_merged = True
        for first_partof in reversed(entity_first_partofs):  # walk from the top of the hierarchy downward
            second_partof = self.__matching_container(first_partof, second_by_type)
            if second_partof is None or first_partof.res == second_partof.res:
                continue
            if parent_merged and self.__containers_are_equivalent(first_partof, second_partof):
                first_partof.merge(second_partof, prefer_self=True)
                self.__debug("\tMerging container %s in container %s", second_partof, first_partof)
            else:
                parent_merged = False

    @staticmethod
    def __specific_types(container: BibliographicResource) -> list[str]:
        return [type_iri for type_iri in container.get_types() if type_iri != GraphEntity.iri_expression]

    def __matching_container(
        self,
        container: BibliographicResource,
        second_by_type: dict[str, BibliographicResource],
    ) -> BibliographicResource | None:
        for type_iri in self.__specific_types(container):
            if type_iri in second_by_type:
                return second_by_type[type_iri]
        return None

    def __containers_are_equivalent(
        self,
        first: BibliographicResource,
        second: BibliographicResource,
    ) -> bool:
        first_signatures = self.__identifier_signatures(first)
        second_signatures = self.__identifier_signatures(second)
        if first_signatures and second_signatures:
            return not first_signatures.isdisjoint(second_signatures)

        first_number = first.get_number()
        second_number = second.get_number()
        if first_number is not None and second_number is not None:
            return first_number == second_number

        first_title = first.get_title()
        second_title = second.get_title()
        if first_title is not None and second_title is not None:
            return self.__normalized_text(first_title) == self.__normalized_text(second_title)

        return False

    @staticmethod
    def __identifier_signatures(entity: BibliographicResource | ResponsibleAgent) -> set[IdentifierSignature]:
        signatures: set[IdentifierSignature] = set()
        for identifier in entity.get_identifiers():
            scheme = identifier.get_scheme()
            literal = identifier.get_literal_value()
            if scheme is not None and literal is not None:
                signatures.add((scheme, literal))
        return signatures

    @staticmethod
    def __normalized_text(value: str) -> str:
        return " ".join(value.casefold().split())

    def __merge_publisher(self, publisher_first: AgentRole | None, entity: BibliographicResource) -> None:
        publisher = self.__get_publisher(entity)
        if (
            publisher is not None
            and publisher_first is not None
            and publisher != publisher_first
            and self.__publishers_are_equivalent(publisher_first, publisher)
        ):
            publisher_first.merge(publisher, prefer_self=True)
            self.__debug("\tMerging publisher %s in publisher %s", publisher, publisher_first)

    def __publishers_are_equivalent(self, first: AgentRole, second: AgentRole) -> bool:
        first_agent = first.get_is_held_by()
        second_agent = second.get_is_held_by()
        if first_agent is None or second_agent is None:
            return False
        first_signatures = self.__identifier_signatures(first_agent)
        second_signatures = self.__identifier_signatures(second_agent)
        if first_signatures and second_signatures:
            return not first_signatures.isdisjoint(second_signatures)
        first_name = self.__agent_full_name(first_agent)
        second_name = self.__agent_full_name(second_agent)
        if first_name and second_name:
            return first_name == second_name
        return False

    def __agent_full_name(self, agent: ResponsibleAgent) -> str:
        name = agent.get_name()
        if name is not None:
            return self.__normalized_text(name)
        parts = [part for part in (agent.get_given_name(), agent.get_family_name()) if part is not None]
        return self.__normalized_text(" ".join(parts)) if parts else ""

    def __bibliographic_resources_for_contributors(
        self,
        contributors: Iterable[AgentRole],
    ) -> list[BibliographicResource]:
        contributor_uris = {str(contributor.res) for contributor in contributors}
        if not contributor_uris:
            return []
        return [
            br
            for br in sorted(self.graph_set.get_br(), key=str)
            if any(str(contributor.res) in contributor_uris for contributor in br.get_contributors())
        ]

    def __deduplicate_contributors_for_bibliographic_resources(
        self,
        bibliographic_resources: Iterable[BibliographicResource],
    ) -> None:
        for bibliographic_resource in bibliographic_resources:
            already_merged = self.__merge_same_ra_contributors(bibliographic_resource)
            if self.merge_similar_named_contributors:
                self.__merge_similar_named_contributors(bibliographic_resource, already_merged)
            self.__remove_contributors_without_ra(bibliographic_resource)

    def __merge_same_ra_contributors(self, entity_first: BibliographicResource) -> set[AgentRole]:
        contributors_by_agent_role: dict[tuple[str, str], list[AgentRole]] = {}
        for contributor in self.__author_contributors(entity_first):
            responsible_agent = contributor.get_is_held_by()
            role_type = contributor.get_role_type()
            if responsible_agent is None or role_type is None:
                continue
            key = (str(responsible_agent.res), role_type)
            contributors_by_agent_role.setdefault(key, []).append(contributor)

        already_merged: set[AgentRole] = set()
        for contributors in contributors_by_agent_role.values():
            ordered_contributors = sorted(contributors, key=str)
            surviving_contributor = ordered_contributors[0]
            for merged_contributor in ordered_contributors[1:]:
                self.__debug(
                    "\tRemoving agent role %s from bibliographic resource %s because both point to the same RA",
                    merged_contributor,
                    entity_first,
                )
                self.__merge_contributor(entity_first, surviving_contributor, merged_contributor)
                already_merged.add(surviving_contributor)
                already_merged.add(merged_contributor)
        return already_merged

    def __merge_similar_named_contributors(
        self,
        entity_first: BibliographicResource,
        already_merged: set[AgentRole],
    ) -> None:
        already_merged_uris = {str(contributor.res) for contributor in already_merged}
        contributors = [
            contributor
            for contributor in sorted(self.__author_contributors(entity_first), key=str)
            if str(contributor.res) not in already_merged_uris and contributor.get_role_type() is not None
        ]
        merged_contributor_uris: set[str] = set()
        for ar1_index, ar1 in enumerate(contributors):
            if str(ar1.res) in merged_contributor_uris:
                continue
            ar1_name = self.__agent_name(ar1)
            for ar2 in contributors[ar1_index + 1 :]:
                if str(ar2.res) in merged_contributor_uris or ar1.get_role_type() != ar2.get_role_type():
                    continue
                ar2_name = self.__agent_name(ar2)
                name_similarity = self.__name_similarity(ar1_name, ar2_name)
                if name_similarity > NAME_SIMILARITY_THRESHOLD:
                    self.__merge_contributor(entity_first, ar1, ar2)
                    merged_contributor_uris.add(str(ar2.res))
                    self.__debug(
                        "\tRemoving agent role %s from bibliographic resource %s because it merged to %s",
                        ar2,
                        entity_first,
                        ar1,
                    )

    def __remove_contributors_without_ra(self, entity_first: BibliographicResource) -> None:
        for ar in self.__author_contributors(entity_first):
            if ar.to_be_deleted or ar.get_is_held_by() is None:
                entity_first.remove_contributor(ar)

    def __merge_contributor(
        self,
        entity_first: BibliographicResource,
        surviving_contributor: AgentRole,
        merged_contributor: AgentRole,
    ) -> None:
        surviving_responsible_agent = surviving_contributor.get_is_held_by()
        surviving_contributor.merge(merged_contributor)
        if surviving_responsible_agent is not None:
            surviving_contributor.is_held_by(surviving_responsible_agent)
        entity_first.remove_contributor(merged_contributor)
        if str(surviving_contributor.res) not in {str(ar.res) for ar in entity_first.get_contributors()}:
            entity_first.has_contributor(surviving_contributor)

    def __author_contributors(self, br: BibliographicResource) -> list[AgentRole]:
        return [
            contributor
            for contributor in br.get_contributors()
            if contributor.get_role_type() != GraphEntity.iri_publisher
        ]

    def __agent_name(self, ar: AgentRole) -> str:
        responsible_agent = ar.get_is_held_by()
        if responsible_agent is None:
            return ""
        given_name = responsible_agent.get_given_name()
        family_name = responsible_agent.get_family_name()
        name_parts = []
        if given_name is not None:
            name_parts.append(given_name)
        if family_name is not None:
            name_parts.append(family_name)
        return " ".join(name_parts)

    @staticmethod
    def __name_similarity(left: str, right: str) -> float:
        left_normalized = " ".join(left.casefold().split())
        right_normalized = " ".join(right.casefold().split())
        if left_normalized == "" or right_normalized == "":
            return 0.0
        max_length = max(len(left_normalized), len(right_normalized))
        return 1 - Levenshtein.distance(left_normalized, right_normalized) / max_length

    def __id_maps(
        self,
    ) -> tuple[
        dict[str, list[Identifier]],
        dict[Identifier, list[BibliographicResource | ResponsibleAgent]],
    ]:
        literal_to_id: dict[str, list[Identifier]] = {}
        id_to_resources: dict[Identifier, list[BibliographicResource | ResponsibleAgent]] = {
            identifier: [] for identifier in self.graph_set.get_id()
        }
        entities: list[BibliographicResource | ResponsibleAgent] = list(self.graph_set.get_br())
        entities.extend(list(self.graph_set.get_ra()))

        for entity in entities:
            for identifier in entity.get_identifiers():
                scheme = identifier.get_scheme()
                value = identifier.get_literal_value()
                if scheme is None or value is None:
                    continue
                literal = f"{scheme}#{value}"
                id_to_resources[identifier].append(entity)
                literal_to_id.setdefault(literal, []).append(identifier)
        return literal_to_id, id_to_resources

    def __merge_identifier_group(
        self,
        literal: str,
        identifiers: list[Identifier],
        id_to_resources: dict[Identifier, list[BibliographicResource | ResponsibleAgent]],
    ) -> None:
        schema, value = literal.split("#", maxsplit=1)
        merged_identifier, other_identifiers = self.__ordered_entities(identifiers)
        self.__debug(
            "[dedup-ID] Will merge %s identifiers into %s because they share literal %s and schema %s",
            len(identifiers) - 1,
            merged_identifier,
            value,
            schema,
        )
        for actual_id in other_identifiers:
            self.__merge_identifier(merged_identifier, actual_id, id_to_resources)

    def __merge_identifiers(
        self,
        surviving_identifier: Identifier,
        merged_identifiers: Iterable[Identifier],
        id_to_resources: dict[Identifier, list[BibliographicResource | ResponsibleAgent]],
    ) -> None:
        for merged_identifier in merged_identifiers:
            self.__merge_identifier(surviving_identifier, merged_identifier, id_to_resources)

    def __merge_identifier(
        self,
        surviving_identifier: Identifier,
        merged_identifier: Identifier,
        id_to_resources: dict[Identifier, list[BibliographicResource | ResponsibleAgent]],
    ) -> None:
        surviving_identifier.merge(merged_identifier)
        self.__replace_identifier(merged_identifier, surviving_identifier, id_to_resources[merged_identifier])
        merged_identifier.mark_as_to_be_deleted()

    def __ordered_entities(self, entities: Iterable[Entity]) -> tuple[Entity, list[Entity]]:
        entities_by_key = {str(entity): entity for entity in entities}
        sorted_keys = sorted(entities_by_key)
        if not sorted_keys:
            message = "Cannot order an empty entity group."
            raise ValueError(message)
        surviving_key = self.__surviving_key(entities_by_key, sorted_keys)
        return entities_by_key[surviving_key], [entities_by_key[key] for key in sorted_keys if key != surviving_key]

    def __surviving_key(self, entities_by_key: Mapping[str, Entity], sorted_keys: list[str]) -> str:
        cluster_keys = set(sorted_keys)
        preferred_keys = sorted(cluster_keys & self.preferred_survivors)
        if len(preferred_keys) > 1:
            message = f"Conflicting preferred survivors for merge cluster {sorted_keys}: {preferred_keys}."
            raise ValueError(message)
        if preferred_keys:
            return preferred_keys[0]
        return min(
            sorted_keys,
            key=lambda key: self.__survivor_sort_key(entities_by_key[key], key),
        )

    @classmethod
    def __survivor_sort_key(cls, entity: object, entity_key: str) -> tuple[int | str, ...]:
        quality = cls.__entity_quality(entity)
        return (*[-value for value in quality], entity_key)

    @staticmethod
    def __entity_quality(entity: object) -> tuple[int, ...]:
        if isinstance(entity, BibliographicResource):
            pub_date = entity.get_pub_date()
            return (
                int(entity.get_title() is not None),
                len(pub_date) if pub_date is not None else 0,
                int(entity.get_subtitle() is not None),
                int(entity.get_is_part_of() is not None),
                int(entity.get_number() is not None),
                int(entity.get_edition() is not None),
                len(entity.get_types()),
            )
        if isinstance(entity, ResponsibleAgent):
            name_parts = [
                entity.get_name(),
                entity.get_given_name(),
                entity.get_family_name(),
            ]
            return (
                sum(name is not None for name in name_parts),
                sum(len(name) for name in name_parts if name is not None),
            )
        if isinstance(entity, Identifier):
            return (
                int(entity.get_scheme() is not None),
                int(entity.get_literal_value() is not None),
            )
        return (0,)

    def __storage(self) -> Storage:
        if self.storage is None:
            message = "storage is required to save deduplicated graph and provenance."
            raise ValueError(message)
        if self.storage.modified_entities is not None:
            return self.storage
        return replace(self.storage, modified_entities=set(self.modified_entities))

    def __provenance(self) -> ProvSet:
        if self.storage is None:
            return ProvSet(self.graph_set, self.graph_set.base_iri)
        return ProvSet(
            self.graph_set,
            self.graph_set.base_iri,
            info_dir=self.storage.info_dir,
            wanted_label=self.storage.wanted_label,
            custom_counter_handler=self.storage.counter_handler,
            supplier_prefix=self.storage.supplier_prefix,
        )

    def __replace_identifier(
        self,
        actual_id: Identifier,
        merged_identifier: Identifier,
        entities: list[BibliographicResource | ResponsibleAgent],
    ) -> None:
        for entity in entities:
            entity.remove_identifier(actual_id)
            if merged_identifier not in entity.get_identifiers():
                entity.has_identifier(merged_identifier)

    @staticmethod
    def __get_part_of(br: BibliographicResource) -> list[BibliographicResource]:
        """
        Given a Bibliographic Resource (BR), walk the full 'part-of' chain.

        :param br: a Bibliographic Resource (BR)
        :return partofs: a list that contains the Bibliographic Resources (BRs) of the hierarchy
        """
        partofs = []
        entity = br
        ended = False
        while not ended:
            partof = entity.get_is_part_of()
            if partof is not None:
                partofs.append(partof)
                entity = partof
            else:
                ended = True
        return partofs

    @staticmethod
    def __get_publisher(br: BibliographicResource) -> AgentRole | None:
        """Given a Bibliographic Resource (BR), return the Agent Role (AR) that is a publisher."""
        for ar in br.get_contributors():
            role = ar.get_role_type()
            if role == GraphEntity.iri_publisher:
                return ar
        return None

    def __get_association_ar_ra(self) -> dict[ResponsibleAgent, list[AgentRole]]:
        """
        Return all the ARs associated to the same RA.

        :return association: a dictionary having Responsible Agent (RA) as key, and a list of Agent Role (AR) as value
        """
        association: dict[ResponsibleAgent, list[AgentRole]] = {}
        for ar in self.graph_set.get_ar():
            responsible_agent = ar.get_is_held_by()
            if responsible_agent is not None:
                association.setdefault(responsible_agent, []).append(ar)
        return association

    def __debug(self, message: str, *args: object) -> None:
        if self.debug:
            LOGGER.debug(message, *args)

    def __as_responsible_agent(
        self,
        entity: ManualMergeEntity,
    ) -> ResponsibleAgent:
        return cast("ResponsibleAgent", entity)

    def __as_bibliographic_resource(
        self,
        entity: ManualMergeEntity,
    ) -> BibliographicResource:
        return cast("BibliographicResource", entity)

    def __as_identifier(
        self,
        entity: ManualMergeEntity,
    ) -> Identifier:
        return cast("Identifier", entity)


__all__ = [
    "GraphDeduplicator",
]
