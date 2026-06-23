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

from oc_ocdm.graph.graph_entity import GraphEntity


def test_crossref_doi(crossref_api):
    assert crossref_api.query(
        [("Stacey", "Willcox-Pidgeon")],
        "PW 1927 Reviewing the national swimming and water safety education framework: "
        "a drowning prevention strategy",
        2018,
    ) == "10.1136/injuryprevention-2018-safety.431"


def test_crossref_journal(crossref_api):
    assert crossref_api.query_journal("0008-4026")[0] == "1480-3305"


def test_orcid(orcid_api):
    authors = [("Silvio", "Peroni", None, None)]
    identifiers = [(GraphEntity.iri_doi, "10.32388/LAKK5Q")]
    assert orcid_api.query(authors, identifiers)[0][2] == "0000-0003-0530-4305"


def test_viaf(viaf_api):
    title = "A Smart City Data Model based on Semantics Best Practice and Principles"
    assert viaf_api.query("Silvio", "Peroni", title) == "309649450"


def test_wikidata_doi(wikidata_api):
    assert wikidata_api.query("10.1002/(ISSN)1098-2353", "doi") == "Q59755"


def test_wikidata_issn(wikidata_api):
    assert wikidata_api.query("0009-4722", "issn") == "Q1119421"


def test_wikidata_orcid(wikidata_api):
    assert wikidata_api.query("0000-0002-7398-5483", "orcid") == "Q5345"


def test_wikidata_viaf(wikidata_api):
    assert wikidata_api.query("24715915", "viaf") == "Q1228"


def test_wikidata_pmid(wikidata_api):
    assert wikidata_api.query("12344444", "pmid") == "Q78273175"


def test_wikidata_pmcid(wikidata_api):
    assert wikidata_api.query("3083595", "pmcid") == "Q54919067"


def test_openalex_doi(openalex_api):
    assert openalex_api.query("10.1111/j.1749-6632.1958.tb54685.x", "doi") == ["W1985052597"]


def test_openalex_issn(openalex_api):
    assert openalex_api.query("0014-2980", "issn") == ["S126191069"]


def test_openalex_pmid(openalex_api):
    assert openalex_api.query("21603045", "pmid") == ["W2991792334"]
