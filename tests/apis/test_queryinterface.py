# SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from oc_ocdm.graph.graph_entity import GraphEntity

from oc_graphenricher.APIs import ORCID, VIAF, AuthorTuple, Crossref, IdentifierTuple, OpenAlex, WikiData


def test_crossref_doi() -> None:
    assert (
        Crossref().query(
            [("Stacey", "Willcox-Pidgeon")],
            "PW 1927 Reviewing the national swimming and water safety education framework: "  # noqa: RUF001
            "a drowning prevention strategy",
            "2018",
        )
        == "10.1136/injuryprevention-2018-safety.431"
    )


def test_crossref_journal() -> None:
    assert Crossref().query_journal("0008-4026") == ["1480-3305"]


def test_orcid() -> None:
    authors: list[AuthorTuple] = [("Silvio", "Peroni", None, None)]
    identifiers: list[IdentifierTuple] = [(GraphEntity.iri_doi, "10.32388/LAKK5Q")]
    assert ORCID().query(authors, identifiers) == [("Silvio", "Peroni", "0000-0003-0530-4305", None)]


def test_viaf() -> None:
    title = "A Smart City Data Model based on Semantics Best Practice and Principles"
    assert VIAF().query("Silvio", "Peroni", title) == "309649450"


def test_wikidata_doi() -> None:
    assert WikiData().query("10.1002/(ISSN)1098-2353", "doi") == "Q59755"


def test_wikidata_issn() -> None:
    assert WikiData().query("0009-4722", "issn") == "Q1119421"


def test_wikidata_orcid() -> None:
    assert WikiData().query("0000-0002-7398-5483", "orcid") == "Q5345"


def test_wikidata_viaf() -> None:
    assert WikiData().query("24715915", "viaf") == "Q1228"


def test_wikidata_pmid() -> None:
    assert WikiData().query("12344444", "pmid") == "Q78273175"


def test_wikidata_pmcid() -> None:
    assert WikiData().query("3083595", "pmcid") == "Q54919067"


def test_openalex_doi() -> None:
    assert OpenAlex().query("10.1111/j.1749-6632.1958.tb54685.x", "doi") == ["W1985052597"]


def test_openalex_issn() -> None:
    assert OpenAlex().query("0014-2980", "issn") == ["S126191069"]


def test_openalex_pmid() -> None:
    assert OpenAlex().query("21603045", "pmid") == ["W2991792334"]
