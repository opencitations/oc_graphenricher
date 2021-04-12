"""
Copyright 2021 Gabriele Pisciotta - ga.pisciotta@gmail.com

Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted,
provided that the above copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN
AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
OF THIS SOFTWARE.
"""

__author__ = "Gabriele Pisciotta"

import networkx as nx
from oc_ocdm import Storer
from oc_ocdm.graph import GraphSet
from oc_ocdm.graph.entities.bibliographic.agent_role import AgentRole
from oc_ocdm.graph.entities.bibliographic.bibliographic_resource import BibliographicResource
from oc_ocdm.graph.entities.bibliographic.responsible_agent import ResponsibleAgent
from oc_ocdm.graph.graph_entity import GraphEntity
from oc_ocdm.prov import ProvSet
from rdflib import URIRef



class InstanceMatching:
    def __init__(self, g_set: GraphSet,
                 graph_filename="matched.rdf",
                 provenance_filename="provenance.rdf",
                 resp_agent='https://w3id.org/oc/meta/prov/pa/4',
                 debug=False):

        self.g_set = g_set
        self.graph_filename = graph_filename
        self.provenance_filename = provenance_filename
        self.debug = debug
        self.resp_agent = resp_agent
        self.prov = ProvSet(self.g_set, self.resp_agent)

    def match(self):
        """ Start the matching process that will do, in sequence:
        - match the ARs
        - match the BRs
        - match the IDs

        In the end, this process will produce:
            - `matched.rdf` that will contain the graph set specified previously without the duplicates.
            - `provenance.rdf` that will contain the provenance, tracking record of all the changes done.
        """
        self.instance_matching_ar()
        self.instance_matching_br()
        self.instance_matching_ids()
        self.save()
        return self.g_set

    def save(self):
        """ Serialize the graph set into the specified RDF file,
        and the provenance in another specified RDF file.
        """
        gs_storer = Storer(self.g_set, output_format="nt11")
        gs_storer.store_graphs_in_file(self.graph_filename, "")

        prov_storer = Storer(self.prov, output_format="nquads")
        prov_storer.store_graphs_in_file(self.provenance_filename, "")

    def instance_matching_ar(self):
        """ Discover all the ARs that share the same identifier's literal, creating a graph of them.
        Then merge each connected component (cluster of ARs linked by the same identifier) into one.
        For each couple of AR that are going to be merged, substitute the references of the AR that
        will no longer exist, by removing the AR from each of its referred BR and add, instead, the merged one)

        If the RA linked by the AR that will no longer exist is not linked by any other AR, then
        it will be marked as to be deleted, otherwise not.

        In the end, generate the provenance and commit pending changes in the graph set"""

        merge_graph: nx.Graph = nx.Graph()

        associated_ar_ra = self.__get_association_ar_ra()
        associated_ar_br = self.__get_association_ar_br()
        identifiers = {}

        for ar in self.g_set.get_ar():
            role = ar.get_role_type()

            # Extract Authors and Publishers, with their info and their identifiers
            if role == GraphEntity.iri_author or role == GraphEntity.iri_publisher:
                for i in ar.get_identifiers():

                    if identifiers.get(i.get_scheme()) is None:
                        identifiers[i.get_scheme()] = {}

                    ra_first: ResponsibleAgent = identifiers[i.get_scheme()].get(i.get_literal_value())
                    if ra_first is None:
                        identifiers[i.get_scheme()][i.get_literal_value()] = ar
                    else:
                        merge_graph.add_edge(ra_first, ar)
                        if self.debug:
                            print("[IM-RA] Will merge {} and {} due to {}:{} in common".format(ar.res,
                                                                                               ra_first.res,
                                                                                               i.get_scheme().split(
                                                                                                   "/")[-1],
                                                                                               i.get_literal_value()))

        # Get the connected components of the graph (clusters of "to-be-merged"):
        clusters = sorted(nx.connected_components(merge_graph), key=len, reverse=True)
        print("[IM-RA] N° of clusters: {}".format(len(clusters)))

        for n, cluster in enumerate(clusters):
            clusters_dict = {}
            clusters_str_list = []
            for k in cluster:
                clusters_dict[str(k)] = k
                clusters_str_list.append(str(k))
            clusters_str_list.sort()

            entity_first: AgentRole = clusters_dict[clusters_str_list[0]]
            if self.debug:
                print("[IM-RA] Merging cluster #{}, with {} entities".format(n, len(cluster)))

            for entity in clusters_str_list[1:]:
                other_entity = clusters_dict[entity]
                if self.debug:
                    print(f"\tMerging agent role {entity} in agent role {entity_first}")

                # The other entity has been merged in the first entity: at this point we need to change all the
                # occurrencies of the other entity with the first entity by looking at all the BRs referred
                if associated_ar_br.get(other_entity) is not None:
                    for other_br in associated_ar_br.get(other_entity):
                        other_br.remove_contributor(other_entity)
                        other_br.has_contributor(entity_first)
                        if self.debug:
                            print(f"\tUnset {other_entity} as contributor of {other_br}")
                            print(f"\tSet {entity_first} as contributor of {other_br} ")

                ra_to_delete = entity_first.get_is_held_by()
                entity_first.merge(other_entity)

                if entity_first.get_is_held_by() != ra_to_delete:
                    if associated_ar_ra.get(ra_to_delete) is not None and len(associated_ar_ra.get(ra_to_delete)) == 1:
                        ra_to_delete.mark_as_to_be_deleted()
                    else:
                        other_entity.mark_as_to_be_deleted(False)
                other_entity.mark_as_to_be_deleted()

                if self.debug:
                    print(f"\tMarking to delete: {other_entity} ")

        self.prov.generate_provenance()
        self.g_set.commit_changes()

    def instance_matching_br(self):
        """ Discover all the BRs that share the same identifier's literal, creating a graph of them.
        Then merge each connected component (cluster of Be RA associated to the Rs linked by the same identifier) into one.
        For each couple of BR that are going to be merged, merge also:
            - their containers by matching the proper type (issue of BR1 -> issue of BR2)
            - their publisher

        NB: when two BRs are merged, you'll have the union of their ARs. You could have duplicates if the duplicates
        don't have any ID in common or if the method `instance_matching_ar` wasn't called before.


        In the end, generate the provenance and commit pending changes in the graph set"""
        merge_graph: nx.Graph = nx.Graph()

        identifiers = {}
        for br in self.g_set.get_br():

            for i in br.get_identifiers():
                if identifiers.get(i.get_scheme()) is None:
                    identifiers[i.get_scheme()] = {}

                br_first: BibliographicResource = identifiers[i.get_scheme()].get(i.get_literal_value())
                if br_first is None:
                    identifiers[i.get_scheme()][i.get_literal_value()] = br
                else:
                    merge_graph.add_edge(br_first, br)
                    if self.debug:
                        print("[IM-BR] Will merge {} into {} due to {}:{} in common".format(br.res,
                                                                                            br_first.res,
                                                                                            i.get_scheme().split("/")[
                                                                                                -1],
                                                                                            i.get_literal_value()))

        # Get the connected components of the graph (clusters of "to-be-merge"):
        clusters = sorted(nx.connected_components(merge_graph), key=len, reverse=True)
        print("[IM-BR] N° of clusters: {}".format(len(clusters)))

        for n, cluster in enumerate(clusters):
            clusters_dict = {}
            clusters_str_list = []
            for k in cluster:
                clusters_dict[str(k)] = k
                clusters_str_list.append(str(k))
            clusters_str_list.sort()

            entity_first: BibliographicResource = clusters_dict[clusters_str_list[0]]
            publisher_first: ResponsibleAgent = self.__get_publisher(entity_first)
            entity_first_partofs = self.__get_part_of(entity_first)
            if self.debug:
                print("[IM-BR] Merging cluster #{}, with {} entities".format(n, len(cluster)))

            entity: BibliographicResource
            for entity in clusters_str_list[1:]:
                entity = clusters_dict[entity]

                # Merge containers
                partofs = self.__get_part_of(entity)
                p1: BibliographicResource;
                p2: BibliographicResource
                for p1 in entity_first_partofs:
                    p1types = p1.get_types()
                    p1types.remove(URIRef('http://purl.org/spar/fabio/Expression'))
                    for p2 in partofs:
                        p2types = p2.get_types()
                        p2types.remove(URIRef('http://purl.org/spar/fabio/Expression'))
                        intersection_of_types = set(p2types).intersection(set(p1types))
                        if intersection_of_types is not None and len(intersection_of_types) != 0:
                            p1.merge(p2)
                            if self.debug:
                                print(f"\tMerging container {p2} in container {p1} ({intersection_of_types})")

                # Merge publisher
                publisher = self.__get_publisher(entity)
                if publisher is not None and publisher_first is not None and publisher != publisher_first:
                    publisher_first.merge(publisher)
                    if self.debug:
                        print(f"\tMerging publisher {publisher} in publisher {publisher_first}")

                # Merge authors
                # contributors = entity.get_contributors()

                # Merging the two BRs
                entity_first.merge(entity)

                # for ar in contributors:
                #    print(f"\tRemoving agent role {ar} from bibliographic resource {entity_first}")
                #    entity_first.remove_contributor(ar)

        self.prov.generate_provenance()
        self.g_set.commit_changes()

    def instance_matching_ids(self):
        """ Discover all the IDs that share the same schema and literal, then merge all into one
         and substitute all the reference with the merged one.
         In the end, generate the provenance and commit pending changes in the graph set"""
        literal_to_id = {}
        id_to_resources = {}

        entities = list(self.g_set.get_br())
        entities.extend(list(self.g_set.get_ar()))

        for e in entities:
            for i in e.get_identifiers():
                literal = i.get_scheme() + "#" + i.get_literal_value()

                if i in id_to_resources:
                    id_to_resources[i].append(e)
                else:
                    id_to_resources[i] = [e]

                if literal in literal_to_id:
                    literal_to_id[literal].append(i)
                else:
                    literal_to_id[literal] = [i]

        for k, v in literal_to_id.items():
            if len(v) > 1:
                schema, lit = k.split('#')
                print(
                    f"[IM-ID] Will merge {len(v) - 1} identifiers into {v[0]} because they share literal {lit} and schema {schema}")
                for actual_id in v[1:]:
                    v[0].merge(actual_id)
                    entities = id_to_resources[actual_id]

                    # Remove, from all the entities, the ID that has been merged
                    # Setting, instead, the merged one as new ID
                    for e in entities:
                        e.remove_identifier(actual_id)
                        if v[0] not in e.get_identifiers():
                            e.has_identifier(v[0])

                    actual_id.mark_as_to_be_deleted()

        self.prov.generate_provenance()
        self.g_set.commit_changes()

    @staticmethod
    def __get_part_of(br):
        """ Given a BR in input (e.g.: a journal article), walk the full 'part-of' chain.
        Returns a list of BR that are the hierarchy of of containers  (e.g: given an article-> [issue, journal])"""
        partofs = []
        e = br
        ended = False
        while not ended:
            partof = e.get_is_part_of()
            if partof is not None:
                partofs.append(partof)
                e = partof
            else:
                ended = True
        return partofs

    @staticmethod
    def __get_publisher(br):
        """ Given a BR as input, returns the AR that is a publisher """
        for ar in br.get_contributors():
            role = ar.get_role_type()
            if role == GraphEntity.iri_publisher:
                return ar

    def __get_association_ar_ra(self):
        """ Returns the dictionary:
                key-> RA
                value-> list of AR

            This let you take all the ARs associated to the same RA
            """
        association = {}
        for ar in self.g_set.get_ar():
            if ar.get_is_held_by() is not None and ar.get_is_held_by() not in association:
                association[ar.get_is_held_by()] = [ar]
            elif ar.get_is_held_by() is not None and ar.get_is_held_by() in association:
                association[ar.get_is_held_by()].append(ar)
        return association

    def __get_association_ar_br(self):
        """ Returns the dictionary:
                key-> AR
                value-> list of BR

            This let you take all the BRs associated to the same AR
            """
        association = {}
        for br in self.g_set.get_br():
            for ar in br.get_contributors():
                if ar.get_is_held_by() is not None and ar not in association:
                    association[ar] = [br]
                elif ar.get_is_held_by() is not None and ar in association:
                    association[ar].append(br)
        return association
