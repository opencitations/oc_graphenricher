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

__author__ = 'Gabriele Pisciotta'

import json
import os
import re
import sys
import time
import unicodedata
from abc import ABC, abstractmethod
from time import sleep
from urllib.parse import quote

import Levenshtein
import requests
import requests_cache
from oc_ocdm.graph.graph_entity import GraphEntity
from requests.exceptions import ReadTimeout, ConnectTimeout


class QueryInterface(ABC):
    """
    This class is a sort of interface that you can implement in your own class
    """
    def __init__(self):
        requests_cache.install_cache('GraphEnricher_cache')

    @abstractmethod
    def query(self, entity):
        raise NotImplementedError


class VIAF(QueryInterface):
    """
    This class let you extract the VIAF of an author, by querying the viaf.org API
    """
    def __init__(self):
        super().__init__()
        self.headers = {
            "User-Agent": "GraphEnricher (via OpenCitations - http://opencitations.net;  mailto:contact@opencitations.net)",
            "Accept": "application/json"}
        self.api_url = 'http://www.viaf.org/viaf/search?local.title+all+"{}"&query=local.names+all+"{}"&sortKeys=holdingscount&recordSchema=BriefVIAF'

    def query(self, given_name: str, family_name: str, title: str):
        """
        Having specified the author's names and the title of a paper, extract a VIAF

        :param given_name: author's given name
        :param family_name: author's family name
        :param title: paper's title
        :return: VIAF, if exists, otherwise None
        """
        try:
            name = f"{given_name} {family_name}".strip()
            query = self.api_url.format(quote(title), quote(name))
            r_cr = requests.get(query, headers=self.headers, timeout=60)
            hdrs_cr = r_cr.headers
            try:
                r = r_cr.json()
                if int(r['searchRetrieveResponse']['numberOfRecords']) != 1:
                    return None
                else:
                    return r['searchRetrieveResponse']['records'][0]['record']['recordData']['viafID']['#text']

            except Exception as ex1:
                if hdrs_cr["content-type"] == 'text/plain' or hdrs_cr["content-type"] == 'text/html':
                    r = r_cr.text
                    if "503" in r:
                        time.sleep(5.0)
                        solution = self.query(given_name, family_name, title)
                        return solution
                    else:
                        print("[GraphEnricher-VIAF]:" + repr(ex1) + "__" + query + "__" + r)
                else:
                    print(
                        "[GraphEnricher-VIAF]:" + repr(ex1) + "__" + query + "__" + hdrs_cr["content-type"])

        except Exception as ex0:
            if "ConnectTimeout" in repr(ex0):
                print("[GraphEnricher-Crossref]:" + repr(ex0) + "__" + query)
                time.sleep(5.0)
                solution = self.query(given_name, family_name, title)
                return solution


class WikiData(QueryInterface):
    """
    This class let you query WikiData by means of another identifier, in order to check the existance of a related
    entity on WikiData
    """
    def __init__(self):
        super().__init__()
        self.headers = {
            "User-Agent": "GraphEnricher (via OpenCitations - http://opencitations.net;  mailto:contact@opencitations.net)",
            "Accept": "application/json"}
        self.api_url = 'https://query.wikidata.org/sparql'
        self.base_query = '''
        SELECT ?item WHERE {{
              ?item p:{property} ?x.
              ?x ps:{property} "{literal}".
        }} LIMIT 1
        '''
        self.doi_property = "P356"
        self.issn_property = "P236"
        self.orcid_property = "P496"
        self.viaf_property = "P214"
        self.pmid_property = "P698"
        self.pmcid_property = "P932"

    def query(self, entity:str, schema: str):
        """
        Method to query WikiData, given the literal of an identifier and its schema

        :param entity: the literal of the given identifier
        :param schema: the schema of the given identifier
        :return: Wikidata ID if found, otherwise None
        """
        if schema == 'doi':
            query = self.base_query.format(property=self.doi_property, literal=entity.upper())
        elif schema == 'issn':
            query = self.base_query.format(property=self.issn_property, literal=entity)
        elif schema == 'orcid':
            query = self.base_query.format(property=self.orcid_property, literal=entity)
        elif schema == 'viaf':
            query = self.base_query.format(property=self.viaf_property, literal=entity)
        elif schema == 'pmid':
            query = self.base_query.format(property=self.pmid_property, literal=entity)
        elif schema == 'pmcid':
            query = self.base_query.format(property=self.pmcid_property, literal=entity)

        r = requests.get(self.api_url, headers=self.headers, timeout=60, params={'format': 'json', 'query': query})
        headers = r.headers

        try:
            data = r.json()
            return data['results']['bindings'][0]['item']['value'].split("/")[-1]
        except IndexError:
            return None
        except Exception as ex1:

            if headers["content-type"] == 'text/plain' or headers["content-type"] == 'text/html':
                r = r.text

                if "503" in r:
                    time.sleep(5.0)
                    solution = self.query(entity, schema)
                    return solution
                else:
                    # ex1.with_traceback()
                    print("[GraphEnricher-WikiData]:" + repr(ex1) + "__" + query + "__" + r)
            else:
                # ex1.with_traceback()
                print("[GraphEnricher-WikiData]:" + repr(ex1) + "__" + query + "__" + headers["content-type"])


class Crossref(QueryInterface):
    """
    This class let you query Crossref in order to extract DOIs, ISSNs and publishers' IDs
    """
    def __init__(self,
                 crossref_min_similarity_score=0.95,
                 max_iteration=6,
                 sec_to_wait=10,
                 headers={"User-Agent": "GraphEnricher (via OpenCitations - http://opencitations.net; "
                                        "mailto:contact@opencitations.net)"},
                 timeout=30,
                 is_json=True):

        super().__init__()

        self.max_iteration = max_iteration
        self.sec_to_wait = sec_to_wait
        self.headers = headers
        self.timeout = timeout
        self.is_json = is_json
        self.crossref_min_similarity_score = crossref_min_similarity_score
        self.__crossref_doi_url = 'https://api.crossref.org/works/'
        self.__crossref_entry_url = 'https://api.crossref.org/works?query.bibliographic='
        self.__crossref_journal_url = 'https://api.crossref.org/journals/'
        self.stoplist = set([line.strip() for line in
                             open(os.path.join(str(__file__).replace("__init__.py", ""), "stopwords-it.txt"))])

    def _cleaning_title(self, title:str):

        """ Clean a given title, filtering the words according to a stoplist
        and extracting a subset of the keywords

        :param title: the title string
        :return: the cleaned title
        """
        n = 4
        keywords = [w for w in title.split(" ") if w not in self.stoplist]
        keywords = " ".join(keywords[:n])
        return keywords

    @staticmethod
    def _cleaning_name(name_raw: str):
        """ Clean the name of an author
        :param name_raw: the name string
        :return: the cleaned name
        """
        name_clean = u"".join([c for c in unicodedata.normalize("NFKD", name_raw) if not unicodedata.combining(c)])
        name_clean = name_clean.lower()
        name_clean = re.sub(r"[^\w\d\s]", "", name_clean)
        return name_clean

    def query_journal(self, issn: str):
        """ Query Crossref to get a list of any other ISSN known, related to an entity described by an ISSN to give
        in input. The list of ISSNs returned will be cleaned from the ISSN already known.

        :param issn: the ISSN of the bibliographic entity
        :return: a list that contains any other ISSN found, otherwise an empty list
        """
        query = self.__crossref_journal_url + issn
        try:
            r_cr = requests.get(query, headers=self.headers, timeout=60)
            hdrs_cr = r_cr.headers

            try:
                r = r_cr.json()
                if r["message"]["ISSN"]:
                    new_issn = r["message"]["ISSN"]
                    if issn in new_issn:
                        new_issn.remove(issn)
                    return new_issn

            except Exception as ex1:
                if hdrs_cr["content-type"] == 'text/plain' or hdrs_cr["content-type"] == 'text/html':
                    r = r_cr.text
                    if "Resource not found" in r:
                        return None
                    if "503" in r:
                        time.sleep(5.0)
                        solution = self.query_journal(issn)
                        return solution
                    else:
                        # ex1.with_traceback()
                        print("[GraphEnricher-Crossref]:" + repr(ex1) + "__" + query + "__" + r)
                else:
                    # ex1.with_traceback()
                    print("[GraphEnricher-Crossref]:" + repr(ex1) + "__" + query + "__" + hdrs_cr["content-type"])

        except Exception as ex0:
            # ex0.with_traceback()
            if "ConnectTimeout" in repr(ex0):
                print("[GraphEnricher-Crossref]:" + repr(ex0) + "__" + query)
                time.sleep(5.0)
                solution = self.query_journal(issn)
                return solution

    def query_publisher(self, doi:str):
        """ Method to extract the identifier of a publisher starting from a given DOI.
        :param doi: the DOI of the paper
        :return: a string representing the ID of the publisher, otherwise None
        """
        url_cr = self.__crossref_doi_url + doi
        try:
            r_cr = requests.get(url_cr, headers=self.headers, timeout=60)
            hdrs_cr = r_cr.headers

            try:
                r = r_cr.json()
                if "message" in r and "member" in r["message"]:
                    return r["message"]["member"]

            except Exception as ex1:
                # ex1.with_traceback()
                if hdrs_cr["content-type"] == 'text/plain' or hdrs_cr["content-type"] == 'text/html':
                    r = r_cr.text
                    if "503" in r:
                        time.sleep(5.0)
                        solution = self.query_publisher(doi)
                        return solution
                    else:
                        print("[GraphEnricher-Crossref-publisher]:" + repr(ex1) + "__" + url_cr + "__" + r)
                else:
                    print("[GraphEnricher-Crossref-publisher]:" + repr(ex1) + "__" + url_cr + "__" + hdrs_cr[
                        "content-type"])

        except Exception as ex0:
            # ex0.with_traceback()
            if "ConnectTimeout" in repr(ex0):
                print("[GraphEnricher-Crossref-publisher]:" + repr(ex0) + "__" + url_cr)
                time.sleep(5.0)
                solution = self.query_publisher(doi)
                return solution

    def query(self, fullnames: list, title: str, year: str):
        """
        Method to extract the DOI, given the names of the authors, the title of the paper and the year of publication
        :param fullnames: a list composed of a tuple of <name, family_name> (e.g.: [ ("Gabriele", "Pisciotta") ]
        :param title: the title of the paper
        :param year: a string that represent the year of publication
        :return: the DOI found, otherwise None
        """
        keywords = self._cleaning_title(title)
        query = f"query.bibliographic={keywords}"
        exist_author = False
        if fullnames is not None:
            for fullname in fullnames:
                if isinstance(fullname, str):
                    surname = self._cleaning_name(fullname[0].split(" ")[-1])
                    name = self._cleaning_name(fullname[1].split(" ")[0])
                else:
                    surname = ""
                    name = ""
                    separator = ""
                    if fullname[0] is not None:
                        name += fullname[0].lower()
                        separator = " "
                    if fullname[1] is not None:
                        surname += fullname[1].lower()
                    exist_author = True
                    query += f"&query.author={name}{separator}{surname}"

        query += f"&rows=4&select=DOI,title,author,issued"
        url_cr = f"https://api.crossref.org/works?{query}"

        try:
            r_cr = requests.get(url_cr, headers=self.headers, timeout=60)
            hdrs_cr = r_cr.headers

            try:
                r = r_cr.json()
                possible = []
                if "message" in r and "items" in r["message"]:
                    if r["message"]["items"]:
                        idx = 0
                        while idx < len(r["message"]["items"]):
                            point_year = 0
                            point_authors = 0
                            point_title = 0
                            if year is not None:

                                if "-" in str(year):
                                    year_tokens = str(year).split("-")
                                    for element_of_year in year_tokens:
                                        if len(element_of_year) == 4:
                                            year = int(element_of_year)
                                            break
                                year = int(year)

                                if "issued" in r["message"]["items"][idx].keys():
                                    if "date-parts" in r["message"]["items"][idx]["issued"].keys():
                                        if r["message"]["items"][idx]["issued"]["date-parts"][0][0] is not None:
                                            paper_year = int(r["message"]["items"][idx]["issued"]["date-parts"][0][0])
                                            if paper_year == year:
                                                point_year += 3
                            if exist_author:
                                if "author" in r["message"]["items"][idx].keys():

                                    for n in r["message"]["items"][idx]["author"]:
                                        if "family" in n.keys():
                                            if "given" in n.keys():
                                                if n["family"].lower() == surname and n["given"].lower() == name:
                                                    point_authors += 2
                                                elif n["family"].lower() == surname and n["given"].lower()[0] == name[
                                                    0]:
                                                    point_authors += 1
                                            elif n["family"].lower() == surname:
                                                point_authors += 1

                            if "title" in r["message"]["items"][idx].keys():
                                title_pub = r["message"]["items"][idx]["title"][0].lower()
                                point_title = Levenshtein.ratio(title, title_pub)

                            possible.append((point_title, point_authors, point_year, idx))
                            idx += 1

                        sort = sorted(possible)

                        if sort[-1][0] > 0.8:
                            if exist_author and sort[-1][1] < 1:
                                return None
                            # if year is not None and sort[-1][2] < 1:
                            #    return None
                            res = r["message"]["items"][sort[-1][3]]
                            return res["DOI"]

            except Exception as ex1:
                # ex1.with_traceback()
                if hdrs_cr["content-type"] == 'text/plain' or hdrs_cr["content-type"] == 'text/html':
                    r = r_cr.text
                    if "503" in r:
                        time.sleep(5.0)
                        solution = self.query(fullnames, title, year)
                        return solution
                    else:
                        print("[GraphEnricher-Crossref-std1]:" + repr(ex1) + "__" + url_cr + "__" + r)
                else:
                    print("[GraphEnricher-Crossref-std2]:" + repr(ex1) + "__" + url_cr + "__" + hdrs_cr["content-type"])

        except Exception as ex0:
            # ex0.with_traceback()
            if "ConnectTimeout" in repr(ex0):
                print("[GraphEnricher-Crossref]:" + repr(ex0) + "__" + url_cr)
                time.sleep(5.0)
                solution = self.query(fullnames, title, year)
                return solution


class ORCID(QueryInterface):
    """
    This class let you query ORCID in order to extract ORCID IDs
    """
    def __init__(self,
                 max_iteration=6,
                 sec_to_wait=10,
                 headers={"User-Agent": "GraphEnricher (via OpenCitations - http://opencitations.net; "
                                        "mailto:contact@opencitations.net)",
                          "Content-Type": "application/json"},
                 timeout=30,
                 repok=None,
                 reperr=None,
                 is_json=True):
        super().__init__()

        self.max_iteration = max_iteration
        self.sec_to_wait = sec_to_wait
        self.headers = headers
        self.timeout = timeout
        self.is_json = is_json
        self.__orcid_api_url = 'https://pub.orcid.org/v2.1/search?q='
        self.__personal_url = "https://pub.orcid.org/v2.1/%s/personal-details"

    def query(self, authors: list, identifiers: list):
        """
        Given a list of authors and a list of identifiers, returns the ORCIDs in the list of authors

        :param authors: a list of tuples in the following form [ (name, family_name, ORCID, ar_object) ]
        :param identifiers: a list of identifiers of the bibliographic resource
        :return: the authors list enriched with the ORCID identifier
        """
        to_return = {}

        if len(identifiers) == 0:
            return None

        returned_orcids = 0

        records = self._get_orcid_records(identifiers, authors)
        if records is not None:

            for orcid_id in self.__dict_get(records, ["result", "orcid-identifier", "path"]):
                personal_details = self.__get_data(self.__personal_url % orcid_id)

                if personal_details is not None:
                    given_name = self.__dict_get(personal_details, ["name", "given-names", "value"])
                    family_name = self.__dict_get(personal_details, ["name", "family-name", "value"])

                    for a in authors:
                        if a[2] is None:

                            if to_return.get((a[0], a[1])) is None and a[1] is not None and family_name is not None:
                                if a[1].lower() in family_name:
                                    to_return[(a[0], a[1])] = orcid_id

                                    if a[0] is not None and given_name is not None:
                                        if a[0].lower() in given_name:
                                            to_return[(a[0], a[1])] = orcid_id

        authors_to_return = []
        for a in authors:
            orcid = to_return.get((a[0], a[1]))
            if orcid is not None:
                returned_orcids += 1
            authors_to_return.append((a[0], a[1], orcid, a[3]))

        return authors_to_return

    def _get_orcid_records(self, identifiers: list, family_names: list =[]):
        cur_query = ""

        i_counter = 0

        for i in identifiers:
            if i[0] == GraphEntity.iri_doi:
                if i[1] is None:
                    continue
                if i_counter == 0:
                    cur_query += "("

                if i_counter >= 1:
                    cur_query += " OR "

                doi_string = i[1]
                cur_query += "doi-self:\"%s\"" % doi_string
                doi_string_l = doi_string.lower()
                doi_string_u = doi_string.upper()

                if doi_string_l != doi_string or doi_string_u != doi_string:
                    if doi_string_l != doi_string:
                        cur_query += " OR doi-self:\"%s\"" % doi_string_l
                    if doi_string_u != doi_string:
                        cur_query += " OR doi-self:\"%s\"" % doi_string_u

            elif i[0] == GraphEntity.iri_isbn:
                if i_counter == 0:
                    cur_query += "("
                if i_counter >= 1:
                    cur_query += " OR "
                isbn_string = i[1]
                cur_query += "isbn:\"%s\"" % isbn_string

            elif i[0] == GraphEntity.iri_pmid:

                if i_counter == 0:
                    cur_query += "( "
                if i_counter >= 1:
                    cur_query += " OR "
                pmid_string = i[1]
                cur_query += "pmid-self:\"%s\"" % pmid_string
            else:
                continue

            i_counter += 1

        if i_counter > 0:
            cur_query += ") "
        if family_names:
            first_name = True
            for idx, full_name in enumerate(family_names):
                family_name = full_name[1]
                given_names = full_name[0]
                if family_name is not None:
                    if first_name:
                        first_name = False
                        if len(identifiers) and cur_query != "":
                            cur_query += "AND ("
                    elif cur_query != "":
                        cur_query += " OR "
                    if family_name:
                        cur_query += "family-name:\"%s\"" % \
                                     unicodedata.normalize('NFKD', "" + family_name). \
                                         encode("ASCII", "ignore").decode("utf-8")
                    if given_names:
                        cur_query += " AND "
                        cur_query += "given-names:\"%s\"" % \
                                     unicodedata.normalize('NFKD', "" + given_names). \
                                         encode("ASCII", "ignore").decode("utf-8")

            # close query if has started with the doi thing
            if len(identifiers):
                cur_query += ")"

        if cur_query != "":
            self.__last_query_done = self.__orcid_api_url + quote(cur_query)
            returned_data = self.__get_data(self.__orcid_api_url + quote(cur_query))
            return returned_data
        else:
            return None

    def __dict_get(self, d, key_list):
        if key_list:
            if type(d) is dict:
                k = key_list[0]
                if k in d:
                    return self.__dict_get(d[k], key_list[1:])
                else:
                    return None
            elif type(d) is list:
                result = []
                for item in d:
                    value = [self.__dict_get(item, key_list)]
                    if value is not None:
                        result += value
                return result
            else:
                return None
        else:
            return d.lower()

    @staticmethod
    def __dict_add(d):
        result = {}
        for k in d:
            value = d[k]
            if value is not None:
                result[k] = value
        return result

    def __get_data(self, get_url):
        """
        Method to send requests
        :param get_url: the URL to query
        :return: results if found, otherwise None
        """
        tentative = 0
        error_no_200 = False
        error_read = False
        error_connection = False
        error_generic = False
        errors = []
        while tentative < self.max_iteration:
            if tentative != 0:
                sleep(self.sec_to_wait)
            tentative += 1

            try:
                response = requests.get(get_url, headers=self.headers, timeout=self.timeout)
                if response.status_code == 200:
                    if self.is_json:
                        return json.loads(response.text)
                    else:
                        return response.text
                else:
                    err_string = "We got an HTTP error when retrieving data (HTTP status code: %s)." % \
                                 str(response.status_code)
                    if not error_no_200:
                        error_no_200 = True
                    if response.status_code == 404:
                        # print(err_string + " However, the process could continue anyway.")
                        # If the resource has not found, we can break the process immediately,
                        # by returning None so as to allow the callee to continue (or not) the process
                        return None
                    else:
                        errors += [err_string]

            except ReadTimeout as e:
                if not error_read:
                    error_read = True
                    errors += ["A timeout error happened when reading results from the API "
                               "when retrieving data. %s" % e]
            except ConnectTimeout as e:
                if not error_connection:
                    error_connection = True
                    errors += ["A timeout error happened when connecting to the API "
                               "when retrieving data. %s" % e]
            except Exception:
                if not error_generic:
                    error_generic = True
                    errors += ["A generic error happened when trying to use the API "
                               "when retrieving data. %s" % sys.exc_info()[0]]

        # If the process comes here, no valid result has been returned
        print(" | ".join(errors) + "\n\tRequested URL: " + get_url)
