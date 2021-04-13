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

import contextlib
import datetime
import sys

import requests_cache
from oc_ocdm import Storer
from oc_ocdm.graph import GraphSet
from oc_ocdm.graph.graph_entity import GraphEntity
from oc_ocdm.graph.entities.bibliographic.bibliographic_resource import BibliographicResource
from oc_ocdm.prov import ProvSet
from tqdm import tqdm
from tqdm.contrib import DummyTqdmFile

from oc_graphenricher.APIs import Crossref, ORCID, VIAF, WikiData


class GraphEnricher:
    """
    The GraphEnricher class is the one responsible to enrich all the entities in a given graph set compliant to
    the OpenCitations Data Model (OCDM). You have to specify in input the graph set, the output file name of the
    enriched graph and the provenance file name. It's also possible to specify a debug flag to get more details
    about the enrichment process.
    """
    def __init__(self,
                 g_set: GraphSet,
                 graph_filename: str = "enriched.rdf",
                 provenance_filename: str = "provenance.rdf",
                 debug: bool = False):
        """

        :param g_set: graph set to be enriched
        :param graph_filename: file name of the enriched graph set that will be serialized
        :param provenance_filename: file name of the provenance that will be serialized
        :param debug: a bool flag to enable richer output
        """
        
        requests_cache.install_cache('GraphEnricher_cache')

        self.resp_agent = 'https://w3id.org/oc/meta/prov/pa/2'
        self.crossref_api = Crossref()
        self.orcid_api = ORCID()
        self.viaf_api = VIAF()
        self.wikidata_api = WikiData()
        self.g_set = g_set
        self.debug = debug
        self.new_id_found = 0
        self.graph_filename = graph_filename
        self.provenance_filename = provenance_filename

    def enrich(self):
        """ The enricher iterates each BR contained in the graph set.
        For each BR (avoiding issues and journals), get the list of the identifiers already
        contained in the graph set and check if it already has a DOI, an ISSN and a Wikidata ID:
            - If an ISSN is specified, it query Crossref to extract other ISSNs.
            - If there's no DOI, it query Crossref to get one by means of all the other data extracted
            - If there's no Wikidata ID, it query Wikidata to get one by means of all the other identifiers
        Any new identifier found will be added to the BR.

        Then, for each AR related to the BR, get the list of all the identifier already contained and:
            - If doesn't have an ORCID, it query ORCID to get it
            - If doesn't have a VIAF, it query VIAF to get it
            - If doesn't have a Wikidata ID, it query Wikidata by means of all the other identifier to get one
            - If the AR is related to a publisher, it query Crossref to get its ID by means of its DOI
        Any new identifier found will be added to the AR.

        In the end it will store a new graph set and its provenance.

        NB: Even if it's not possible to have an identifier duplicated for the same entity, it's possible that in
        the whole graph set you could find different identifiers that share the same schema and literal. For this
        purpose, you should use the `instancematching` module after that you've enriched the graph set.
        """
        br_enriched_counter = 0
        with self.__std_out_err_redirect_tqdm() as orig_stdout:

            progress_bar = tqdm(self.g_set.get_br(), file=orig_stdout, dynamic_ncols=True)
            for br in progress_bar:
                progress_bar.set_description(desc=f"New ID found: {self.new_id_found}")

                br_enriched_counter += 1
                if br_enriched_counter % 50 == 0 and not self.debug:
                        gs_storer = Storer(self.g_set, output_format="nt11")
                        gs_storer.store_graphs_in_file("enriched.rdf", "")

                if GraphEntity.iri_journal_issue in br.get_types() or GraphEntity.iri_journal_volume in br.get_types():
                    continue

                authors = []
                publisher_has_crossrefid = False

                # Extract br's identifiers
                has_doi = None
                has_issn = []
                has_wikidata = []
                for i in br.get_identifiers():
                    if i.get_scheme() == br.iri_doi:
                        has_doi = i.get_literal_value()
                    elif i.get_scheme() == br.iri_issn:
                        has_issn.append(i.get_literal_value())
                    elif i.get_scheme() == br.iri_wikidata:
                        has_wikidata.append(i.get_literal_value())


                # Get more ISSNs
                if len(has_issn) > 0:
                    for issn in has_issn:
                        res = self.crossref_api.query_journal(issn)
                        if res:
                            for r in res:
                                # To avoid to add already present ISSNs
                                if r not in has_issn:
                                    self._add_id(br, r, 'issn', "its ISSN {}".format(issn))
                            break

                # If no DOI try to get it
                if has_doi is None:
                    res = self.crossref_api.query(authors, br.get_title(), br.get_pub_date())
                    if res:
                        self._add_id(br, res, 'doi', "Crossref query")
                        has_doi = res

                # If it hasn't a Wikidata ID, extract br's identifiers and search on wikidata for that IDs
                if len(has_wikidata) == 0:
                    for i in br.get_identifiers():
                        if i.get_scheme() == br.iri_doi:
                            res = self.wikidata_api.query(i.get_literal_value(), 'doi')
                            if res:
                                self._add_id(br, res, 'wikidata', "its DOI".format(i.get_literal_value()))
                                break
                        elif i.get_scheme() == br.iri_issn:
                            res = self.wikidata_api.query(i.get_literal_value(), 'issn')
                            if res:
                                self._add_id(br, res, 'wikidata', "its ISSN {}".format(i.get_literal_value()))
                                break
                        elif i.get_scheme() == br.iri_pmid:
                            res = self.wikidata_api.query(i.get_literal_value(), 'pmid')
                            if res:
                                self._add_id(br, res, 'wikidata', "its PMID {}".format(i.get_literal_value()))
                                break
                        elif i.get_scheme() == br.iri_pmcid:
                            res = self.wikidata_api.query(i.get_literal_value(), 'pmcid')
                            if res:
                                self._add_id(br, res, 'wikidata',  "its PMCID {}".format(i.get_literal_value()))
                                break

                for ar in br.get_contributors():
                    role = ar.get_role_type()
                    a = ar.get_is_held_by()

                    # Extract Authors, with their info and their identifiers
                    if role == GraphEntity.iri_author:
                        authors.append((a.get_given_name(), a.get_family_name(), a))
                        has_orcid = None
                        has_viaf = None
                        has_wikidata = None

                        author_id_found = []
                        for author_identifier in a.get_identifiers():
                            if a.iri_orcid in author_identifier.get_scheme():
                                has_orcid = author_identifier.get_literal_value()
                                author_id_found.append((author_identifier.get_literal_value(), 'orcid'))
                            if br.iri_viaf in author_identifier.get_scheme():
                                has_viaf = author_identifier.get_literal_value()
                                author_id_found.append((author_identifier.get_literal_value(), 'viaf'))
                            if br.iri_wikidata in author_identifier.get_scheme():
                                has_wikidata = author_identifier.get_literal_value()

                            if has_viaf is not None and has_orcid is not None and has_wikidata is not None:
                                break

                        if has_orcid is None:
                            res = self.orcid_api.query(
                                [(a.get_given_name(), a.get_family_name(), None, a)],
                                [(x.get_scheme(), x.get_literal_value()) for x in br.get_identifiers()])

                            if res:
                                for res_tuple in res:
                                    given_name, family_name, orcid, a = res_tuple
                                    if orcid is not None:
                                        self._add_id(a, orcid, 'orcid')
                                        author_id_found.append((orcid, 'orcid'))

                        # Search for the author on Wikidata
                        if not has_viaf:
                            viaf = self.viaf_api.query(a.get_given_name(), a.get_family_name(), br.get_title())
                            if viaf is not None:
                                self._add_id(a, viaf, 'viaf')
                                author_id_found.append((viaf, 'viaf'))

                        # If the author doesn't have Wikidata ID
                        if not has_wikidata:
                            for literal, scheme in author_id_found:
                                res = self.wikidata_api.query(literal, scheme)
                                if res:
                                    self._add_id(a, res, 'wikidata', "its {} {}".format(scheme.upper(), literal))
                                    break


                    # Get Publisher and its identifiers
                    if role == GraphEntity.iri_publisher:

                        for publisher_id in a.get_identifiers():
                            if GraphEntity.iri_crossref in publisher_id.get_scheme():
                                publisher_has_crossrefid = True
                                break

                        # If crossref-id not found, search it
                        if not publisher_has_crossrefid and has_doi is not None:
                            crossref_id = self.crossref_api.query_publisher(has_doi)
                            if crossref_id:
                                self._add_id(a, crossref_id, 'crossref')

            gs_storer = Storer(self.g_set, output_format="nt11")
            gs_storer.store_graphs_in_file(self.graph_filename, "")

            prov = ProvSet(self.g_set, self.resp_agent)
            prov.generate_provenance()

            prov_storer = Storer(prov, output_format="nquads")
            prov_storer.store_graphs_in_file(self.provenance_filename, "")


    def _add_id(self, entity: BibliographicResource, literal: str, schema: str, by_means_of: str=None):
        """ Method that let you add a new identifier to an entity,
        having specified the literal value, the schema and optionally the API used

        :param entity: a bibliographic resource
        :param literal: the literal value of the identifier
        :param schema: the schema of the identifier
        :param by_means_of: an optional string that let you specify the API used
        """

        old_identifiers = entity.get_identifiers()

        # Check if the ID is already associated to the entity
        for i in old_identifiers:
            if i.get_literal_value() == literal:
                if self.debug:
                    print("Identifier {} already present".format(literal))
                return

        self.new_id_found += 1

        new_id = self.g_set.add_id(self.resp_agent)
        if schema == 'issn':
            new_id.create_issn(literal)
        elif schema == 'doi':
            new_id.create_doi(literal)
        elif schema == 'orcid':
            new_id.create_orcid(literal)
        elif schema == 'viaf':
            new_id.create_viaf(literal)
        elif schema == 'crossref':
            new_id.create_crossref(literal)
        elif schema == 'wikidata':
            new_id.create_wikidata(literal)

        entity.has_identifier(new_id)

        if self.debug:

            # To pretty print it with tqdm's write()
            to_print = "[{}] FOUND {}: {}".format(datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S'), schema, literal)
            if by_means_of is not None:
                to_print += ", by means of {}".format(by_means_of)

            print(to_print)
            print("\tOLD: {}".format([x.get_literal_value() for x in old_identifiers]))
            print("\tNEW : {}".format([x.get_literal_value() for x in entity.get_identifiers()]))

    @contextlib.contextmanager
    def __std_out_err_redirect_tqdm(self):
        """ This method is used to print messages with the TQDM progress bar"""
        orig_out_err = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = map(DummyTqdmFile, orig_out_err)
            yield orig_out_err[0]
        except Exception as exc:
            raise exc
        finally:
            sys.stdout, sys.stderr = orig_out_err
