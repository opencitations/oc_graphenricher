# SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
# SPDX-FileCopyrightText: 2021 Simone Persiani
# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import Levenshtein
import networkx as nx
from oc_ocdm.graph.graph_entity import GraphEntity
from oc_ocdm.prov.prov_set import ProvSet
from oc_ocdm.storer import Storer

if TYPE_CHECKING:
    from oc_ocdm.abstract_entity import AbstractEntity
    from oc_ocdm.abstract_set import AbstractSet
    from oc_ocdm.graph.entities.bibliographic.agent_role import AgentRole
    from oc_ocdm.graph.entities.bibliographic.bibliographic_resource import BibliographicResource
    from oc_ocdm.graph.entities.bibliographic.responsible_agent import ResponsibleAgent
    from oc_ocdm.graph.entities.identifier import Identifier
    from oc_ocdm.graph.graph_set import GraphSet

LOGGER = logging.getLogger(__name__)
NAME_SIMILARITY_THRESHOLD = 0.95


class InstanceMatching:
    def __init__(
        self,
        g_set: GraphSet,
        graph_filename: str = "matched.rdf",
        provenance_filename: str = "provenance.rdf",
        info_dir: str = "",
        *,
        debug: bool = False,
    ) -> None:
        """
        Initialize the matcher.

        The matcher deduplicates entities in a graph set compliant with the OpenCitations Data Model.

        :param g_set: input graph set
        :param graph_filename: file name of the enriched graph set that will be serialized
        :param provenance_filename: file name of the provenance that will be serialized
        :param info_dir: the path to the counters directory
        :param debug: a bool flag to enable richer output
        """
        self.g_set = g_set
        self.graph_filename = graph_filename
        self.provenance_filename = provenance_filename
        self.debug = debug
        self.prov = ProvSet(self.g_set, self.g_set.base_iri, info_dir=info_dir)

    def match(self) -> GraphSet:
        """
        Start the matching process.

        The process will:
        - match the Responsible Agents (RAs)
        - match the Bibliographic Resources (BRs)
        - match the IDs.

        In the end, this process will produce:
            - `matched.rdf` that will contain the graph set specified previously without the duplicates.
            - `provenance.rdf` that will contain the provenance, tracking record of all the changes done.
        """
        self.instance_matching_ra()
        self.instance_matching_br()
        self.instance_matching_id()
        self.save()
        return self.g_set

    def save(self) -> None:
        """
        Serialize the graph set into the specified RDF file.

        Serialize the provenance in another specified RDF file.
        """
        gs_storer = Storer(cast("AbstractSet[AbstractEntity]", self.g_set), output_format="nt11")
        gs_storer.store_graphs_in_file(self.graph_filename, "")

        prov_storer = Storer(cast("AbstractSet[AbstractEntity]", self.prov), output_format="nquads")
        prov_storer.store_graphs_in_file(self.provenance_filename, "")

    def instance_matching_ra(self) -> None:
        """
        Discover Responsible Agents (RAs) that share the same identifier literal.

        The process creates a graph of matching entities, merges each connected component into one RA, updates Agent
        Role references, generates provenance and commits pending changes in the graph set.
        """
        associated_ar_ra = self.__get_association_ar_ra()
        clusters = self.__sorted_clusters(self.__ra_merge_graph())
        LOGGER.info("[IM-RA] Number of clusters: %s", len(clusters))

        for cluster_index, cluster in enumerate(clusters):
            entity_first, other_entities = self.__ordered_cluster(cluster)
            self.__debug("[IM-RA] Merging cluster #%s, with %s entities", cluster_index, len(cluster))
            for other_entity in other_entities:
                self.__merge_responsible_agent(entity_first, other_entity, associated_ar_ra)

        self.prov.generate_provenance()
        self.g_set.commit_changes()

    def instance_matching_br(self) -> None:
        """
        Discover Bibliographic Resources (BRs) that share the same identifier literal.

        The process creates a graph of matching BRs, merges each connected component into one BR, merges containers and
        publishers where possible, generates provenance and commits pending changes in the graph set.
        """
        clusters = self.__sorted_clusters(self.__br_merge_graph())
        LOGGER.info("[IM-BR] Number of clusters: %s", len(clusters))

        for cluster_index, cluster in enumerate(clusters):
            self.__debug("[IM-BR] Merging cluster #%s, with %s entities", cluster_index, len(cluster))
            self.__merge_br_cluster(cluster)

        self.prov.generate_provenance()
        self.g_set.commit_changes()

    def instance_matching_id(self) -> None:
        """
        Discover duplicate IDs related to Bibliographic Resources and Responsible Agents.

        IDs are duplicates when they share the same schema and literal. The process merges duplicates into one ID,
        substitutes references with the merged ID, generates provenance and commits pending changes in the graph set.
        """
        literal_to_id, id_to_resources = self.__id_maps()
        for literal, identifiers in literal_to_id.items():
            if len(identifiers) > 1:
                self.__merge_identifier_group(literal, identifiers, id_to_resources)

        self.prov.generate_provenance()
        self.g_set.commit_changes()

    def __ra_merge_graph(self) -> nx.Graph:
        merge_graph: nx.Graph = nx.Graph()
        identifiers: dict[str, dict[str, ResponsibleAgent]] = {}
        for ra in self.g_set.get_ra():
            for identifier in ra.get_identifiers():
                scheme = identifier.get_scheme()
                literal_value = identifier.get_literal_value()
                if scheme is None or literal_value is None:
                    continue
                identifiers.setdefault(scheme, {})
                ra_first = identifiers[scheme].get(literal_value)
                if ra_first is None:
                    identifiers[scheme][literal_value] = ra
                else:
                    merge_graph.add_edge(ra_first, ra)
                    self.__debug(
                        "[IM-RA] Will merge %s and %s due to %s:%s in common",
                        ra.res,
                        ra_first.res,
                        scheme.split("/")[-1],
                        literal_value,
                    )
        return merge_graph

    def __br_merge_graph(self) -> nx.Graph:
        merge_graph: nx.Graph = nx.Graph()
        identifiers: dict[str, dict[str, BibliographicResource]] = {}
        for br in self.g_set.get_br():
            for identifier in br.get_identifiers():
                scheme = identifier.get_scheme()
                literal_value = identifier.get_literal_value()
                if scheme is None or literal_value is None:
                    continue
                identifiers.setdefault(scheme, {})
                br_first = identifiers[scheme].get(literal_value)
                if br_first is None:
                    identifiers[scheme][literal_value] = br
                else:
                    merge_graph.add_edge(br_first, br)
                    self.__debug(
                        "[IM-BR] Will merge %s into %s due to %s:%s in common",
                        br.res,
                        br_first.res,
                        scheme.split("/")[-1],
                        literal_value,
                    )
        return merge_graph

    def __sorted_clusters(self, merge_graph: nx.Graph) -> list[set[ResponsibleAgent | BibliographicResource]]:
        return sorted(nx.connected_components(merge_graph), key=len, reverse=True)

    def __ordered_cluster(
        self,
        cluster: set[ResponsibleAgent | BibliographicResource],
    ) -> tuple[ResponsibleAgent | BibliographicResource, list[ResponsibleAgent | BibliographicResource]]:
        entities_by_key = {str(entity): entity for entity in cluster}
        sorted_keys = sorted(entities_by_key)
        entity_first = entities_by_key[sorted_keys[0]]
        return entity_first, [entities_by_key[key] for key in sorted_keys[1:]]

    def __merge_responsible_agent(
        self,
        entity_first: ResponsibleAgent | BibliographicResource,
        other_entity: ResponsibleAgent | BibliographicResource,
        associated_ar_ra: dict[ResponsibleAgent, list[AgentRole]],
    ) -> None:
        responsible_agent = self.__as_responsible_agent(entity_first)
        other_responsible_agent = self.__as_responsible_agent(other_entity)
        self.__debug("\tMerging responsible agent %s in responsible agent %s", other_entity, responsible_agent)
        responsible_agent.merge(other_responsible_agent)
        associated_ars = associated_ar_ra.get(other_responsible_agent)
        if associated_ars is not None:
            for ar in associated_ars:
                ar.is_held_by(responsible_agent)
                self.__debug("\tUnset %s as helded by of %s", other_responsible_agent, ar)
                self.__debug("\tSet %s as helded by of %s", responsible_agent, ar)
        self.__debug("\tMarking to delete: %s", other_responsible_agent)

    def __merge_br_cluster(self, cluster: set[ResponsibleAgent | BibliographicResource]) -> None:
        entity_first_raw, other_entities_raw = self.__ordered_cluster(cluster)
        entity_first = self.__as_bibliographic_resource(entity_first_raw)
        publisher_first = self.__get_publisher(entity_first)
        entity_first_partofs = self.__get_part_of(entity_first)

        for other_entity_raw in other_entities_raw:
            other_entity = self.__as_bibliographic_resource(other_entity_raw)
            self.__merge_containers(entity_first_partofs, self.__get_part_of(other_entity))
            self.__merge_publisher(publisher_first, other_entity)
            entity_first.merge(other_entity)
            already_merged = self.__merge_same_ra_contributors(entity_first)
            self.__merge_similar_named_contributors(entity_first, already_merged)
            self.__remove_contributors_without_ra(entity_first)

    def __merge_containers(
        self,
        entity_first_partofs: list[BibliographicResource],
        partofs: list[BibliographicResource],
    ) -> None:
        for first_partof in entity_first_partofs:
            first_types = first_partof.get_types()
            first_types.remove(GraphEntity.iri_expression)
            for second_partof in partofs:
                second_types = second_partof.get_types()
                second_types.remove(GraphEntity.iri_expression)
                intersection_of_types = set(second_types).intersection(set(first_types))
                if intersection_of_types:
                    first_partof.merge(second_partof)
                    self.__debug(
                        "\tMerging container %s in container %s (%s)",
                        second_partof,
                        first_partof,
                        intersection_of_types,
                    )

    def __merge_publisher(self, publisher_first: AgentRole | None, entity: BibliographicResource) -> None:
        publisher = self.__get_publisher(entity)
        if publisher is not None and publisher_first is not None and publisher != publisher_first:
            publisher_first.merge(publisher)
            self.__debug("\tMerging publisher %s in publisher %s", publisher, publisher_first)

    def __merge_same_ra_contributors(self, entity_first: BibliographicResource) -> set[AgentRole]:
        contributors = self.__author_contributors(entity_first)
        already_merged: set[AgentRole] = set()
        for ar1 in contributors:
            for ar2 in contributors:
                if self.__same_responsible_agent(ar1, ar2):
                    self.__debug(
                        "\tRemoving agent role %s from bibliographic resource %s because both point to the same RA",
                        ar2,
                        entity_first,
                    )
                    ar1.merge(ar2)
                    entity_first.remove_contributor(ar2)
                    already_merged.add(ar1)
                    already_merged.add(ar2)
        return already_merged

    def __same_responsible_agent(self, ar1: AgentRole, ar2: AgentRole) -> bool:
        return (
            ar1 != ar2
            and ar1.get_is_held_by() is not None
            and ar2.get_is_held_by() is not None
            and ar1.get_is_held_by() == ar2.get_is_held_by()
        )

    def __merge_similar_named_contributors(
        self,
        entity_first: BibliographicResource,
        already_merged: set[AgentRole],
    ) -> None:
        contributors = set(self.__author_contributors(entity_first)).difference(already_merged)
        merged_contributors: set[AgentRole] = set()
        for ar1 in contributors:
            if ar1 in merged_contributors:
                continue
            ar1_name = self.__agent_name(ar1)
            for ar2 in contributors:
                if ar1 == ar2 or ar2 in merged_contributors:
                    continue
                ar2_name = self.__agent_name(ar2)
                name_similarity = 1 - Levenshtein.distance(ar1_name, ar2_name)
                if ar1_name != "" and ar2_name != "" and name_similarity > NAME_SIMILARITY_THRESHOLD:
                    ar1.merge(ar2)
                    entity_first.remove_contributor(ar2)
                    merged_contributors.add(ar2)
                    self.__debug(
                        "\tRemoving agent role %s from bibliographic resource %s because it merged to %s",
                        ar2,
                        entity_first,
                        ar1,
                    )

    def __remove_contributors_without_ra(self, entity_first: BibliographicResource) -> None:
        for ar in self.__author_contributors(entity_first):
            if ar.get_is_held_by() is None:
                entity_first.remove_contributor(ar)

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

    def __id_maps(
        self,
    ) -> tuple[
        dict[str, list[Identifier]],
        dict[Identifier, list[BibliographicResource | ResponsibleAgent]],
    ]:
        literal_to_id: dict[str, list[Identifier]] = {}
        id_to_resources: dict[Identifier, list[BibliographicResource | ResponsibleAgent]] = {}
        entities: list[BibliographicResource | ResponsibleAgent] = list(self.g_set.get_br())
        entities.extend(list(self.g_set.get_ra()))

        for entity in entities:
            for identifier in entity.get_identifiers():
                scheme = identifier.get_scheme()
                value = identifier.get_literal_value()
                if scheme is None or value is None:
                    continue
                literal = f"{scheme}#{value}"
                id_to_resources.setdefault(identifier, []).append(entity)
                literal_to_id.setdefault(literal, []).append(identifier)
        return literal_to_id, id_to_resources

    def __merge_identifier_group(
        self,
        literal: str,
        identifiers: list[Identifier],
        id_to_resources: dict[Identifier, list[BibliographicResource | ResponsibleAgent]],
    ) -> None:
        schema, value = literal.split("#", maxsplit=1)
        merged_identifier = identifiers[0]
        self.__debug(
            "[IM-ID] Will merge %s identifiers into %s because they share literal %s and schema %s",
            len(identifiers) - 1,
            merged_identifier,
            value,
            schema,
        )
        for actual_id in identifiers[1:]:
            merged_identifier.merge(actual_id)
            self.__replace_identifier(actual_id, merged_identifier, id_to_resources[actual_id])
            actual_id.mark_as_to_be_deleted()

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
        for ar in self.g_set.get_ar():
            responsible_agent = ar.get_is_held_by()
            if responsible_agent is not None:
                association.setdefault(responsible_agent, []).append(ar)
        return association

    def __get_association_ar_br(self) -> dict[AgentRole, list[BibliographicResource]]:
        """
        Return all the Bibliographic Resources (BRs) associated to the same AR.

        :return association: a dictionary having Agent Role (AR) as key, and a list of Bibliographic Resource (BR)
        """
        association: dict[AgentRole, list[BibliographicResource]] = {}
        for br in self.g_set.get_br():
            for ar in br.get_contributors():
                if ar.get_is_held_by() is not None:
                    association.setdefault(ar, []).append(br)
        return association

    def __debug(self, message: str, *args: object) -> None:
        if self.debug:
            LOGGER.debug(message, *args)

    def __as_responsible_agent(
        self,
        entity: ResponsibleAgent | BibliographicResource,
    ) -> ResponsibleAgent:
        return cast("ResponsibleAgent", entity)

    def __as_bibliographic_resource(
        self,
        entity: ResponsibleAgent | BibliographicResource,
    ) -> BibliographicResource:
        return cast("BibliographicResource", entity)
