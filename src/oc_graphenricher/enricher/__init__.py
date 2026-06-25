# SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
# SPDX-FileCopyrightText: 2021 Simone Persiani
# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
# SPDX-FileCopyrightText: 2026 Ilaria De Dominicis <ilaria.dedominicis2@studio.unibo.it>
#
# SPDX-License-Identifier: ISC

from __future__ import annotations

import contextlib
import logging
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import requests_cache
from oc_ocdm.graph.entities.bibliographic.responsible_agent import ResponsibleAgent
from oc_ocdm.graph.graph_entity import GraphEntity
from oc_ocdm.prov.prov_set import ProvSet
from tqdm import tqdm
from tqdm.contrib import DummyTqdmFile

from oc_graphenricher._identifiers import supported_br_identifiers
from oc_graphenricher._storage import store_graph_set, store_provenance
from oc_graphenricher.APIs import ORCID, VIAF, Crossref, OpenAlex, WikiData

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from typing import Protocol, TextIO

    from oc_ocdm.graph.entities.bibliographic.bibliographic_resource import BibliographicResource
    from oc_ocdm.graph.graph_set import GraphSet

    class IdentifierLike(Protocol):
        def get_literal_value(self) -> str | None: ...


LOGGER = logging.getLogger(__name__)
SERIALIZE_INTERVAL = 50


class GraphEnricher:
    def __init__(
        self,
        g_set: GraphSet,
        graph_filename: str = "enriched.rdf",
        provenance_filename: str = "provenance.rdf",
        info_dir: str = "",
        *,
        debug: bool = False,
        serialize_in_the_middle: bool = False,
        use_wikidata: bool = True,
        use_viaf: bool = True,
        use_orcid: bool = True,
    ) -> None:
        """
        Initialize the enricher.

        The enricher adds missing identifiers to entities in an OCDM graph set.

        :param g_set: graph set to be enriched.
        :param graph_filename: file name of the enriched graph set that will be serialized
        :param provenance_filename: file name of the provenance that will be serialized
        :param info_dir: the path to the counters directory
        :param debug: a bool flag to enable richer output
        :param serialize_in_the_middle: a bool flag to enable the serialization each 50 Bibliographic Resources (BRs)
        processed (the resulting file will be always overwritten, this may slow the whole process)
        :param use_wikidata: a bool flag to enable or disable Wikidata queries (default: True)
        :param use_viaf: a bool flag to enable or disable VIAF queries (default: True)
        :param use_orcid: a bool flag to enable or disable ORCID queries (default: True)
        """
        requests_cache.install_cache("GraphEnricher_cache")

        self.resp_agent = "https://w3id.org/oc/meta/prov/pa/2"
        self.crossref_api = Crossref()
        self.orcid_api = ORCID()
        self.viaf_api = VIAF()
        self.wikidata_api = WikiData()
        self.openalex_api = OpenAlex()
        self.g_set = g_set
        self.debug = debug
        self.new_id_found = 0
        self.graph_filename = graph_filename
        self.provenance_filename = provenance_filename
        self.info_dir = info_dir
        self.serialize_in_the_middle = serialize_in_the_middle
        self.use_wikidata = use_wikidata
        self.use_viaf = use_viaf
        self.use_orcid = use_orcid

    def enrich(self) -> None:
        """
        Iterate over each BR contained in the graph set.

        For each BR, excluding journal issues and journal volumes, it reads the identifiers already contained in the
        graph set and checks whether the BR already has a DOI, ISSN, Wikidata ID, and OpenAlex ID:

        - If an ISSN is available, it queries Crossref to extract related ISSNs.
        - If no DOI is available and the title is usable, it queries Crossref to find one from the BR metadata.
        - If no Wikidata ID is available, it queries Wikidata by using the BR identifiers.
        - If no OpenAlex ID is available, it queries OpenAlex by using the BR identifiers.

        Any new identifier found is added to the BR.

        Then, for each AR related to the BR, it reads the identifiers already contained in the graph set and:

        - If an author does not have an ORCID, it queries ORCID to find one.
        - If an author does not have a VIAF, it queries VIAF to find one from the author name and BR title.
        - If an author does not have a Wikidata ID, it queries Wikidata by using the author identifiers found so far.
        - If a publisher does not have a Crossref ID, it queries Crossref to find one from the BR DOI.

        Any new identifier found is added to the AR.

        In the end it will store a new graph set and its provenance.

        NB: Even if it's not possible to have an identifier duplicated for the same entity, it's possible that in
        the whole graph set you could find different identifiers that share the same schema and literal. For this
        purpose, you should use the `instancematching` module after that you've enriched the graph set.
        """
        with self.__std_out_err_redirect_tqdm() as orig_stdout:
            progress_bar = tqdm(self.g_set.get_br(), file=orig_stdout, dynamic_ncols=True)
            for br_counter, br in enumerate(progress_bar, start=1):
                progress_bar.set_description(desc=f"New ID found: {self.new_id_found}")
                self.__serialize_intermediate(br_counter)
                if self.__is_journal_issue_or_volume(br):
                    continue
                has_doi = self.__enrich_bibliographic_resource(br)
                self.__enrich_contributors(br, has_doi)

            self.__serialize_graphs()

    def __serialize_intermediate(self, br_counter: int) -> None:
        if br_counter % SERIALIZE_INTERVAL != 0 or not self.serialize_in_the_middle:
            return
        store_graph_set(self.g_set, self.graph_filename)

    def __is_journal_issue_or_volume(self, br: BibliographicResource) -> bool:
        return GraphEntity.iri_journal_issue in br.get_types() or GraphEntity.iri_journal_volume in br.get_types()

    def __enrich_bibliographic_resource(self, br: BibliographicResource) -> str | None:
        has_doi, has_issn, has_wikidata, has_openalex = self.__br_identifiers(br)
        self.__add_missing_issns(br, has_issn)
        has_doi = self.__add_missing_doi(br, has_doi)
        if self.use_wikidata and len(has_wikidata) == 0:
            self.__add_wikidata_to_br(br)
        if has_openalex is None:
            self.__add_openalex_to_br(br)
        return has_doi

    def __br_identifiers(self, br: BibliographicResource) -> tuple[str | None, list[str], list[str], str | None]:
        has_doi = None
        has_issn = []
        has_wikidata = []
        has_openalex = None
        for identifier in br.get_identifiers():
            literal = identifier.get_literal_value()
            if literal is None:
                continue
            if identifier.get_scheme() == br.iri_doi:
                has_doi = literal
            elif identifier.get_scheme() == br.iri_issn:
                has_issn.append(literal)
            elif identifier.get_scheme() == br.iri_wikidata:
                has_wikidata.append(literal)
            elif identifier.get_scheme() == br.iri_openalex:
                has_openalex = literal
        return has_doi, has_issn, has_wikidata, has_openalex

    def __add_missing_issns(self, br: BibliographicResource, has_issn: list[str]) -> None:
        for issn in has_issn:
            result = self.crossref_api.query_journal(issn)
            if not result:
                continue
            for literal in result:
                if literal not in has_issn:
                    self._add_id(br, literal, "issn", f"its ISSN {issn}")
            break

    def __add_missing_doi(self, br: BibliographicResource, has_doi: str | None) -> str | None:
        title = br.get_title()
        if has_doi is not None or not title or title.strip().lower() == "unknown":
            return has_doi
        result = self.crossref_api.query([], title, br.get_pub_date())
        if result:
            self._add_id(br, result, "doi", "Crossref query")
            return result
        return has_doi

    def __add_wikidata_to_br(self, br: BibliographicResource) -> None:
        for schema, literal in supported_br_identifiers(br):
            result = self.wikidata_api.query(literal, schema)
            if result:
                self._add_id(br, result, "wikidata", f"its {schema.upper()} {literal}")
                break

    def __add_openalex_to_br(self, br: BibliographicResource) -> None:
        for schema, literal in supported_br_identifiers(br):
            result = self.openalex_api.query(literal, schema)
            if result:
                for openalex_id in result:
                    self._add_id(br, openalex_id, "openalex", f"its {schema.upper()} {literal}")

    def __enrich_contributors(self, br: BibliographicResource, has_doi: str | None) -> None:
        publisher_has_crossrefid = False
        for ar in br.get_contributors():
            role = ar.get_role_type()
            ra = ar.get_is_held_by()
            if ra is None:
                continue
            if role == GraphEntity.iri_author:
                self.__enrich_author(br, ra)
            if role == GraphEntity.iri_publisher:
                publisher_has_crossrefid = self.__enrich_publisher(
                    ra,
                    has_doi,
                    publisher_has_crossrefid=publisher_has_crossrefid,
                )

    def __enrich_author(self, br: BibliographicResource, ra: ResponsibleAgent) -> None:
        has_orcid, has_viaf, has_wikidata, author_id_found = self.__author_identifiers(br, ra)
        if self.use_orcid and has_orcid is None:
            self.__add_orcid_to_author(br, ra, author_id_found)
        if self.use_viaf and not has_viaf:
            self.__add_viaf_to_author(br, ra, author_id_found)
        if self.use_wikidata and not has_wikidata:
            self.__add_wikidata_to_author(ra, author_id_found)

    def __author_identifiers(
        self,
        br: BibliographicResource,
        ra: ResponsibleAgent,
    ) -> tuple[str | None, str | None, str | None, list[tuple[str | None, str]]]:
        has_orcid = None
        has_viaf = None
        has_wikidata = None
        author_id_found = []
        for author_identifier in ra.get_identifiers():
            scheme = author_identifier.get_scheme()
            literal = author_identifier.get_literal_value()
            if scheme is None:
                continue
            if ra.iri_orcid in scheme:
                has_orcid = literal
                author_id_found.append((literal, "orcid"))
            if br.iri_viaf in scheme:
                has_viaf = literal
                author_id_found.append((literal, "viaf"))
            if br.iri_wikidata in scheme:
                has_wikidata = literal
            if has_viaf is not None and has_orcid is not None and has_wikidata is not None:
                break
        return has_orcid, has_viaf, has_wikidata, author_id_found

    def __add_orcid_to_author(
        self,
        br: BibliographicResource,
        ra: ResponsibleAgent,
        author_id_found: list[tuple[str | None, str]],
    ) -> None:
        result = self.orcid_api.query(
            [(ra.get_given_name(), ra.get_family_name(), None, ra)],
            [(identifier.get_scheme(), identifier.get_literal_value()) for identifier in br.get_identifiers()],
        )
        if not result:
            return
        for _given_name, _family_name, orcid, responsible_agent in result:
            if orcid is not None and isinstance(responsible_agent, ResponsibleAgent):
                self._add_id(responsible_agent, orcid, "orcid")
                author_id_found.append((orcid, "orcid"))

    def __add_viaf_to_author(
        self,
        br: BibliographicResource,
        ra: ResponsibleAgent,
        author_id_found: list[tuple[str | None, str]],
    ) -> None:
        given = ra.get_given_name()
        family = ra.get_family_name()
        if not given and not family:
            return
        viaf = self.viaf_api.query(given or "", family or "", br.get_title() or "")
        if viaf is not None:
            self._add_id(ra, viaf, "viaf")
            author_id_found.append((viaf, "viaf"))

    def __add_wikidata_to_author(
        self,
        ra: ResponsibleAgent,
        author_id_found: list[tuple[str | None, str]],
    ) -> None:
        for literal, schema in author_id_found:
            if literal is None:
                continue
            result = self.wikidata_api.query(literal, schema)
            if result:
                self._add_id(ra, result, "wikidata", f"its {schema.upper()} {literal}")
                break

    def __enrich_publisher(
        self,
        ra: ResponsibleAgent,
        has_doi: str | None,
        *,
        publisher_has_crossrefid: bool,
    ) -> bool:
        if publisher_has_crossrefid or has_doi is None:
            return publisher_has_crossrefid
        for publisher_id in ra.get_identifiers():
            scheme = publisher_id.get_scheme()
            if scheme is not None and GraphEntity.iri_crossref in scheme:
                return True
        crossref_id = self.crossref_api.query_publisher(has_doi)
        if crossref_id:
            self._add_id(ra, crossref_id, "crossref")
        return False

    def __serialize_graphs(self) -> None:
        store_graph_set(self.g_set, self.graph_filename)
        prov = ProvSet(self.g_set, self.g_set.base_iri, info_dir=self.info_dir)
        prov.generate_provenance()
        store_provenance(prov, self.provenance_filename)

    def _add_id(
        self,
        entity: BibliographicResource | ResponsibleAgent,
        literal: str,
        schema: str,
        by_means_of: str | None = None,
    ) -> None:
        """
        Add a new identifier to an entity.

        :param entity: a bibliographic resource or an agent role
        :param literal: the literal value of the identifier
        :param schema: the schema of the identifier
        :param by_means_of: an optional string that let you specify the API used
        """
        old_identifiers = entity.get_identifiers()
        if self.__has_identifier(entity, literal):
            if self.debug:
                LOGGER.debug("Identifier %s already present", literal)
            return

        self.new_id_found += 1

        new_id = self.g_set.add_id(self.resp_agent)
        create_identifier = {
            "issn": new_id.create_issn,
            "doi": new_id.create_doi,
            "orcid": new_id.create_orcid,
            "viaf": new_id.create_viaf,
            "crossref": new_id.create_crossref,
            "wikidata": new_id.create_wikidata,
            "openalex": new_id.create_openalex,
        }
        create_identifier[schema](literal)
        entity.has_identifier(new_id)

        if self.debug:
            self.__log_new_identifier(schema, literal, old_identifiers, entity, by_means_of)

    def __has_identifier(self, entity: BibliographicResource | ResponsibleAgent, literal: str) -> bool:
        return any(identifier.get_literal_value() == literal for identifier in entity.get_identifiers())

    def __log_new_identifier(
        self,
        schema: str,
        literal: str,
        old_identifiers: Iterable[IdentifierLike],
        entity: BibliographicResource | ResponsibleAgent,
        by_means_of: str | None,
    ) -> None:
        message = f"[{datetime.now(timezone.utc).strftime('%Y/%m/%d %H:%M:%S')}] FOUND {schema}: {literal}"
        if by_means_of is not None:
            message += f", by means of {by_means_of}"

        LOGGER.debug(message)
        LOGGER.debug("OLD: %s", [identifier.get_literal_value() for identifier in old_identifiers])
        LOGGER.debug("NEW: %s", [identifier.get_literal_value() for identifier in entity.get_identifiers()])

    @contextlib.contextmanager
    def __std_out_err_redirect_tqdm(self) -> Iterator[TextIO]:
        """Redirect stdout and stderr through the TQDM progress bar."""
        orig_out_err = sys.stdout, sys.stderr
        try:
            sys.stdout, sys.stderr = map(DummyTqdmFile, orig_out_err)
            yield orig_out_err[0]
        finally:
            sys.stdout, sys.stderr = orig_out_err
