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

from unittest import TestCase
from oc_graphenricher.APIs import *

class TestAPI(TestCase):
    def setUp(self) -> None:
        self.crossref_API = Crossref()
        self.orcid_API = ORCID()
        self.viaf_API = VIAF()
        self.wikidata_API = WikiData()

    def test_crossref_doi(self):
        if self.crossref_API.query([("Stacey", "Willcox-Pidgeon")],
                                   "PW 1927 Reviewing the national swimming and water safety education framework: "
                                   "a drowning prevention strategy",
                                   2018) != '10.1136/injuryprevention-2018-safety.431':
            self.fail()

    def test_crossref_journal(self):
        if self.crossref_API.query_journal("0008-4026")[0] != '1480-3305':
            self.fail()

    def test_ORCID(self):
        authors = [("Silvio", "Peroni", None, None)]
        identifiers = [(GraphEntity.iri_doi, "10.32388/LAKK5Q")]
        if self.orcid_API.query(authors, identifiers)[0][2] != '0000-0003-0530-4305':
            self.fail()

    def test_VIAF(self):
        given_name = "Silvio"
        family_name = "Peroni"
        title = "A Smart City Data Model based on Semantics Best Practice and Principles"
        if self.viaf_API.query(given_name, family_name, title) != '309649450':
            self.fail()
            
    def test_Wikidata_doi(self):
        if self.wikidata_API.query("10.1002/(ISSN)1098-2353", 'doi') != 'Q59755':
            self.fail()

    def test_Wikidata_issn(self):
        if self.wikidata_API.query("0009-4722", 'issn') != 'Q1119421':
            self.fail()

    def test_Wikidata_orcid(self):
        if self.wikidata_API.query("0000-0002-7398-5483", 'orcid') != 'Q5345':
            self.fail()

    def test_Wikidata_viaf(self):
        if self.wikidata_API.query("24715915", 'viaf') != 'Q1228':
            self.fail()

    def test_Wikidata_pmid(self):
        if self.wikidata_API.query("15774072", 'pmid') != 'Q21092898':
            self.fail()

    def test_Wikidata_pmcid(self):
        if self.wikidata_API.query("2981558", 'pmcid') != 'Q21089993':
            self.fail()
