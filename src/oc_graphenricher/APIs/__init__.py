# SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
# SPDX-FileCopyrightText: 2021 Simone Persiani
# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from __future__ import annotations

import json
import logging
import unicodedata
from abc import ABC, abstractmethod
from http import HTTPStatus
from pathlib import Path
from time import sleep
from typing import cast
from urllib.parse import quote

import Levenshtein
import requests
import requests_cache
from oc_ocdm.graph.graph_entity import GraphEntity
from requests.exceptions import RequestException

LOGGER = logging.getLogger(__name__)

USER_AGENT = "GraphEnricher (via OpenCitations - http://opencitations.net; mailto:contact@opencitations.net)"
CROSSREF_ROWS = 4
TITLE_KEYWORD_LIMIT = 4
CROSSREF_TITLE_THRESHOLD = 0.8
YEAR_LENGTH = 4
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_BACKOFF_FACTOR = 1.0
RETRY_STATUS_CODES = {
    HTTPStatus.TOO_MANY_REQUESTS,
    HTTPStatus.INTERNAL_SERVER_ERROR,
    HTTPStatus.BAD_GATEWAY,
    HTTPStatus.SERVICE_UNAVAILABLE,
    HTTPStatus.GATEWAY_TIMEOUT,
}

JsonDict = dict[str, object]
AuthorTuple = tuple[str | None, str | None, str | None, object]
IdentifierTuple = tuple[str | None, str | None]


def _default_headers(content_type: str | None = None) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    if content_type is not None:
        headers["Content-Type"] = content_type
    return headers


def _normalize_ascii(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ASCII", "ignore").decode("utf-8")


def _get_with_retries(
    url: str,
    headers: dict[str, str],
    timeout: float,
    label: str,
    params: dict[str, str] | None = None,
    max_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
) -> requests.Response | None:
    last_error: object = "no attempts"
    for attempt in range(max_attempts):
        try:
            if params is None:
                response = requests.get(url, headers=headers, timeout=timeout)
            else:
                response = requests.get(url, headers=headers, timeout=timeout, params=params)
        except RequestException as error:
            last_error = error
        else:
            if response.status_code == HTTPStatus.OK:
                return response
            if response.status_code not in RETRY_STATUS_CODES:
                return None
            last_error = HTTPStatus(response.status_code)

        if attempt + 1 < max_attempts:
            sleep(backoff_factor * 2**attempt)

    LOGGER.warning("%s retry attempts exhausted for %s: %r", label, url, last_error)
    return None


class QueryInterface(ABC):
    def __init__(self) -> None:
        """
        Initialize the query interface.

        The interface installs the shared requests cache used by concrete query backends.
        """
        requests_cache.install_cache("GraphEnricher_cache")

    @abstractmethod
    def query(self, *args: object, **kwargs: object) -> object:
        raise NotImplementedError


class VIAF(QueryInterface):
    def __init__(self) -> None:
        """
        Initialize the VIAF query backend.

        The backend extracts VIAF identifiers for authors by querying viaf.org.
        """
        super().__init__()
        self.headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        self.api_url = (
            'http://www.viaf.org/viaf/search?local.title+all+"{}"&query=local.names+all+"{}"'
            "&sortKeys=holdingscount&recordSchema=BriefVIAF"
        )

    def query(self, given_name: str, family_name: str, title: str) -> str | None:
        """
        Having specified the author's names and the title of a paper, extract a VIAF.

        :param given_name: author's given name
        :param family_name: author's family name
        :param title: paper's title
        :return: VIAF, if exists, otherwise None
        """
        name = f"{given_name} {family_name}".strip()
        query = self.api_url.format(quote(title), quote(name))
        response = _get_with_retries(query, self.headers, 60, "[GraphEnricher-VIAF]")
        if response is None:
            return None

        data = response.json()
        response_data = data["searchRetrieveResponse"]
        number_of_records = response_data["numberOfRecords"]["content"]
        if int(number_of_records) != 1:
            return None

        record_data = response_data["records"]["record"]["recordData"]
        return str(record_data["v:VIAFCluster"]["v:viafID"]["content"])


class Wikidata(QueryInterface):
    def __init__(self) -> None:
        """
        Initialize the Wikidata query backend.

        The backend queries Wikidata by means of another identifier and checks whether a related entity exists.
        """
        super().__init__()
        self.headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        self.api_url = "https://query.wikidata.org/sparql"
        self.base_query = """
        SELECT ?item WHERE {{
              ?item p:{property} ?x.
              ?x ps:{property} "{literal}".
        }} LIMIT 1
        """
        self.schema_properties = {
            "doi": "P356",
            "issn": "P236",
            "orcid": "P496",
            "viaf": "P214",
            "pmid": "P698",
            "pmcid": "P932",
        }

    def query(self, entity: str, schema: str) -> str | None:
        """
        Query Wikidata, given the literal of an identifier and its schema.

        :param entity: the literal of the given identifier
        :param schema: the schema of the given identifier
        :return: Wikidata ID if found, otherwise None
        """
        if schema not in self.schema_properties:
            return None

        literal = entity.upper() if schema == "doi" else entity
        query = self.base_query.format(property=self.schema_properties[schema], literal=literal)
        response = _get_with_retries(
            self.api_url,
            self.headers,
            60,
            "[GraphEnricher-Wikidata]",
            params={"format": "json", "query": query},
        )
        if response is None:
            return None

        try:
            data = response.json()
            return data["results"]["bindings"][0]["item"]["value"].split("/")[-1]
        except IndexError:
            return None


class Crossref(QueryInterface):
    def __init__(
        self,
        crossref_min_similarity_score: float = 0.95,
        max_iteration: int = DEFAULT_RETRY_ATTEMPTS,
        sec_to_wait: float = DEFAULT_BACKOFF_FACTOR,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        *,
        is_json: bool = True,
    ) -> None:
        """
        Initialize the Crossref query backend.

        The backend extracts DOIs, ISSNs, and publisher IDs.
        """
        super().__init__()

        self.max_iteration = max_iteration
        self.sec_to_wait = sec_to_wait
        self.headers = headers if headers is not None else _default_headers()
        self.timeout = timeout
        self.is_json = is_json
        self.crossref_min_similarity_score = crossref_min_similarity_score
        self.__crossref_doi_url = "https://api.crossref.org/works/"
        self.__crossref_journal_url = "https://api.crossref.org/journals/"
        stopwords_path = Path(__file__).with_name("stopwords-it.txt")
        with stopwords_path.open(encoding="utf-8") as stopwords_file:
            self.stoplist = {line.strip() for line in stopwords_file}

    def _cleaning_title(self, title: str) -> str:
        """
        Clean a given title, filtering the words according to a stoplist.

        :param title: the title string
        :return: the cleaned title
        """
        keywords = [word for word in title.split(" ") if word not in self.stoplist]
        return " ".join(keywords[:TITLE_KEYWORD_LIMIT])

    def query_journal(self, issn: str) -> list[str] | None:
        """
        Query Crossref to get a list of other ISSNs for an ISSN.

        :param issn: the ISSN of the bibliographic entity
        :return: a list that contains any other ISSN found, otherwise an empty list
        """
        query = self.__crossref_journal_url + issn
        response = _get_with_retries(
            query,
            self.headers,
            self.timeout,
            "[GraphEnricher-Crossref]",
            max_attempts=self.max_iteration,
            backoff_factor=self.sec_to_wait,
        )
        if response is None:
            return None

        data = response.json()
        new_issn = cast("list[str]", data["message"]["ISSN"])
        if issn in new_issn:
            new_issn.remove(issn)
        return new_issn

    def query_publisher(self, doi: str) -> str | None:
        """
        Extract the identifier of a publisher starting from a given DOI.

        :param doi: the DOI of the paper
        :return: a string representing the ID of the publisher, otherwise None
        """
        url_cr = self.__crossref_doi_url + doi
        response = _get_with_retries(
            url_cr,
            self.headers,
            self.timeout,
            "[GraphEnricher-Crossref-publisher]",
            max_attempts=self.max_iteration,
            backoff_factor=self.sec_to_wait,
        )
        if response is None:
            return None

        data = response.json()
        return str(data["message"]["member"])

    def query(self, fullnames: list[tuple[str | None, str | None]], title: str, year: str | None) -> str | None:
        """
        Extract the DOI, given authors, title and year of publication.

        :param fullnames: a list composed of a tuple of <name, family_name> (e.g.: [ ("Gabriele", "Pisciotta") ]
        :param title: the title of the paper
        :param year: a string that represent the year of publication
        :return: the DOI found, otherwise None
        """
        author_query, exist_author, name, surname = self.__author_query(fullnames)
        query = f"query.bibliographic={self._cleaning_title(title)}{author_query}"
        query += f"&rows={CROSSREF_ROWS}&select=DOI,title,author,issued"
        url_cr = f"https://api.crossref.org/works?{query}"
        response = _get_with_retries(
            url_cr,
            self.headers,
            self.timeout,
            "[GraphEnricher-Crossref]",
            max_attempts=self.max_iteration,
            backoff_factor=self.sec_to_wait,
        )
        if response is None:
            return None

        data = response.json()
        return self.__best_doi(data, title, year, exist_author=exist_author, name=name, surname=surname)

    def __author_query(self, fullnames: list[tuple[str | None, str | None]]) -> tuple[str, bool, str, str]:
        query = ""
        exist_author = False
        name = ""
        surname = ""
        for fullname in fullnames:
            name, surname = self.__normalized_fullname(fullname)
            if name or surname:
                exist_author = True
                query += f"&query.author={name} {surname}".rstrip()
        return query, exist_author, name, surname

    def __normalized_fullname(self, fullname: tuple[str | None, str | None]) -> tuple[str, str]:
        name = fullname[0].lower() if fullname[0] is not None else ""
        surname = fullname[1].lower() if fullname[1] is not None else ""
        return name, surname

    def __best_doi(
        self,
        data: JsonDict,
        title: str,
        year: str | None,
        *,
        exist_author: bool,
        name: str,
        surname: str,
    ) -> str | None:
        doi = None
        message = cast("JsonDict", data["message"])
        items = cast("list[JsonDict]", message["items"])
        if items:
            possible = [
                (
                    *self.__score_crossref_item(
                        item,
                        title,
                        year,
                        exist_author=exist_author,
                        name=name,
                        surname=surname,
                    ),
                    item,
                )
                for item in items
            ]
            best_title, best_authors, _best_year, best_item = sorted(possible, key=lambda item: item[:3])[-1]
            if best_title > CROSSREF_TITLE_THRESHOLD and (not exist_author or best_authors >= 1) and "DOI" in best_item:
                doi = str(best_item["DOI"])
        return doi

    def __score_crossref_item(
        self,
        item: JsonDict,
        title: str,
        year: str | None,
        *,
        exist_author: bool,
        name: str,
        surname: str,
    ) -> tuple[float, int, int]:
        point_year = self.__year_score(item, year)
        point_authors = self.__author_score(item, exist_author=exist_author, name=name, surname=surname)
        point_title = self.__title_score(item, title)
        return point_title, point_authors, point_year

    def __year_score(self, item: JsonDict, year: str | None) -> int:
        year_int = self.__year_int(year)
        if year_int is None or "issued" not in item:
            return 0
        issued = cast("JsonDict", item["issued"])
        if "date-parts" not in issued:
            return 0
        date_parts = cast("list[list[int | None]]", issued["date-parts"])
        if not date_parts or not date_parts[0] or date_parts[0][0] is None:
            return 0
        return 3 if int(date_parts[0][0]) == year_int else 0

    def __year_int(self, year: str | None) -> int | None:
        if year is None:
            return None
        year_string = str(year)
        if "-" in year_string:
            for element_of_year in year_string.split("-"):
                if len(element_of_year) == YEAR_LENGTH:
                    year_string = element_of_year
                    break
        return int(year_string)

    def __author_score(self, item: JsonDict, *, exist_author: bool, name: str, surname: str) -> int:
        if not exist_author or "author" not in item:
            return 0
        point_authors = 0
        authors = cast("list[JsonDict]", item["author"])
        for author in authors:
            if "family" not in author:
                continue
            family = cast("str", author["family"]).lower()
            if "given" not in author:
                if family == surname:
                    point_authors += 1
                continue
            given = cast("str", author["given"]).lower()
            if family == surname and given == name:
                point_authors += 2
            elif family == surname and name and given and given[0] == name[0]:
                point_authors += 1
        return point_authors

    def __title_score(self, item: JsonDict, title: str) -> float:
        if "title" not in item:
            return 0
        title_values = cast("list[str]", item["title"])
        if not title_values:
            return 0
        return Levenshtein.ratio(title, title_values[0].lower())


class ORCID(QueryInterface):
    def __init__(
        self,
        max_iteration: int = DEFAULT_RETRY_ATTEMPTS,
        sec_to_wait: float = DEFAULT_BACKOFF_FACTOR,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        repok: object = None,
        reperr: object = None,
        *,
        is_json: bool = True,
    ) -> None:
        """
        Initialize the ORCID query backend.

        The backend extracts ORCID identifiers.
        """
        del repok, reperr
        super().__init__()

        self.max_iteration = max_iteration
        self.sec_to_wait = sec_to_wait
        self.headers = headers if headers is not None else _default_headers("application/json")
        self.timeout = timeout
        self.is_json = is_json
        self.__orcid_api_url = "https://pub.orcid.org/v2.1/search?q="
        self.__personal_url = "https://pub.orcid.org/v2.1/%s/personal-details"

    def query(self, authors: list[AuthorTuple], identifiers: list[IdentifierTuple]) -> list[AuthorTuple] | None:
        """
        Given a list of authors and a list of identifiers, returns the ORCIDs in the list of authors.

        :param authors: a list of tuples in the following form [ (name, family_name, ORCID, ar_object) ]
        :param identifiers: a list of identifiers of the bibliographic resource
        :return: the authors list enriched with the ORCID identifier
        """
        if len(identifiers) == 0:
            return None

        records = self._get_orcid_records(identifiers, authors)
        to_return: dict[tuple[str | None, str | None], str] = {}
        if records is not None:
            records_data = cast("JsonDict", records)
            results = cast("list[JsonDict]", records_data["result"])
            for record in results:
                orcid_identifier = cast("JsonDict", record["orcid-identifier"])
                orcid_id = str(orcid_identifier["path"])
                self.__collect_matching_orcid(authors, to_return, orcid_id)

        return [(author[0], author[1], to_return.get((author[0], author[1])), author[3]) for author in authors]

    def _get_orcid_records(
        self,
        identifiers: list[IdentifierTuple],
        family_names: list[AuthorTuple],
    ) -> JsonDict | str | None:
        identifier_query = self.__identifier_query(identifiers)
        family_query = self.__family_query(family_names)
        if identifier_query and family_query:
            cur_query = f"{identifier_query} AND ({family_query})"
        elif identifier_query:
            cur_query = identifier_query
        else:
            cur_query = family_query

        if cur_query == "":
            return None

        query_url = self.__orcid_api_url + quote(cur_query)
        return self.__get_data(query_url)

    def __collect_matching_orcid(
        self,
        authors: list[AuthorTuple],
        to_return: dict[tuple[str | None, str | None], str],
        orcid_id: str,
    ) -> None:
        personal_details = self.__get_data(self.__personal_url % orcid_id.upper())
        if personal_details is None:
            return

        personal_data = cast("JsonDict", personal_details)
        name = cast("JsonDict", personal_data["name"])
        given_names = cast("JsonDict", name["given-names"])
        family_name_data = cast("JsonDict", name["family-name"])
        given_name = str(given_names["value"]).lower()
        family_name = str(family_name_data["value"]).lower()

        for author in authors:
            if self.__matches_author(author, given_name, family_name) and to_return.get((author[0], author[1])) is None:
                to_return[(author[0], author[1])] = orcid_id.upper()

    def __matches_author(self, author: AuthorTuple, given_name: str, family_name: str) -> bool:
        if author[2] is not None or author[1] is None:
            return False
        if author[1].lower() not in family_name:
            return False
        return author[0] is None or author[0].lower() in given_name

    def __identifier_query(self, identifiers: list[IdentifierTuple]) -> str:
        terms = []
        for scheme, value in identifiers:
            if value is None:
                continue
            if scheme == GraphEntity.iri_doi:
                terms.extend(self.__doi_terms(value))
            elif scheme == GraphEntity.iri_isbn:
                terms.append(f'isbn:"{value}"')
            elif scheme == GraphEntity.iri_pmid:
                terms.append(f'pmid-self:"{value}"')
        if not terms:
            return ""
        return f"({' OR '.join(terms)})"

    def __doi_terms(self, doi_string: str) -> list[str]:
        terms = [f'doi-self:"{doi_string}"']
        doi_string_l = doi_string.lower()
        doi_string_u = doi_string.upper()
        if doi_string_l != doi_string:
            terms.append(f'doi-self:"{doi_string_l}"')
        if doi_string_u != doi_string:
            terms.append(f'doi-self:"{doi_string_u}"')
        return terms

    def __family_query(self, family_names: list[AuthorTuple]) -> str:
        terms = []
        for given_names, family_name, _orcid, _entity in family_names:
            if family_name is None:
                continue
            term = f'family-name:"{_normalize_ascii(family_name)}"'
            if given_names:
                term += f' AND given-names:"{_normalize_ascii(given_names)}"'
            terms.append(term)
        return " OR ".join(terms)

    def __get_data(self, get_url: str) -> JsonDict | str | None:
        """
        Send requests.

        :param get_url: the URL to query
        :return: results if found, otherwise None
        """
        response = _get_with_retries(
            get_url,
            self.headers,
            self.timeout,
            "[GraphEnricher-ORCID]",
            max_attempts=self.max_iteration,
            backoff_factor=self.sec_to_wait,
        )
        if response is None:
            return None
        if self.is_json:
            return cast("JsonDict", json.loads(response.text))
        return response.text


class OpenAlex(QueryInterface):
    def __init__(self) -> None:
        super().__init__()
        self.headers = {"User-Agent": USER_AGENT}
        self.api_url_works = "https://api.openalex.org/works"
        self.api_url_sources = "https://api.openalex.org/sources"

    def query(self, entity: str, schema: str) -> list[str] | None:
        schema = schema.lower()
        query = self.__query_url(entity, schema)
        result = None
        if query is None:
            LOGGER.warning("[GraphEnricher-OpenAlex]:The specified schema '%s' is not supported", schema)
        else:
            response = _get_with_retries(query, self.headers, 60, "[GraphEnricher-OpenAlex]")
            if response is not None:
                result = self.__response_results(response)
        return result

    def __response_results(self, response: requests.Response) -> list[str] | None:
        data = response.json()
        results = cast("list[JsonDict]", data["results"])
        if not results:
            return None
        return [str(result["id"]).replace("https://openalex.org/", "") for result in results]

    def __query_url(self, entity: str, schema: str) -> str | None:
        if schema in {"doi", "pmid", "pmcid"}:
            return f"{self.api_url_works}?filter={schema}:{entity}&select=id"
        if schema == "issn":
            return f"{self.api_url_sources}?filter={schema}:{entity}&select=id"
        return None
