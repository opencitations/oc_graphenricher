# SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

import json
from http import HTTPStatus

import pytest
import requests
from oc_ocdm.graph.graph_entity import GraphEntity
from requests.exceptions import ReadTimeout

from oc_graphenricher import APIs
from oc_graphenricher.APIs import ORCID, VIAF, AuthorTuple, Crossref, IdentifierTuple, JsonDict, OpenAlex, WikiData


class JsonResponse:
    def __init__(self, data: JsonDict, status_code: HTTPStatus = HTTPStatus.OK) -> None:
        self.data = data
        self.status_code = status_code
        self.headers: dict[str, str] = {}
        self.text = json.dumps(data)

    def json(self) -> JsonDict:
        return self.data


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


def test_crossref_publisher(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, headers: dict[str, str], timeout: int) -> JsonResponse:
        del url, headers, timeout
        return JsonResponse({"message": {"member": "297"}})

    monkeypatch.setattr(requests, "get", fake_get)

    assert Crossref().query_publisher("10.1007/978-3-030-00668-6_4") == "297"


def test_crossref_publisher_retries_service_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        JsonResponse({}, HTTPStatus.SERVICE_UNAVAILABLE),
        JsonResponse({}, HTTPStatus.SERVICE_UNAVAILABLE),
        JsonResponse({"message": {"member": "297"}}),
    ]
    sleep_values = []

    def fake_get(url: str, headers: dict[str, str], timeout: int) -> JsonResponse:
        del url, headers, timeout
        return responses.pop(0)

    def fake_sleep(seconds: float) -> None:
        sleep_values.append(seconds)

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(APIs, "sleep", fake_sleep)

    assert Crossref(max_iteration=3, sec_to_wait=0.5).query_publisher("10.1007/978-3-030-00668-6_4") == "297"
    assert responses == []
    assert sleep_values == [0.5, 1.0]


def test_crossref_journal_not_found_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    sleep_values = []

    def fake_get(url: str, headers: dict[str, str], timeout: int) -> JsonResponse:
        nonlocal calls
        del url, headers, timeout
        calls += 1
        return JsonResponse({}, HTTPStatus.NOT_FOUND)

    def fake_sleep(seconds: float) -> None:
        sleep_values.append(seconds)

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(APIs, "sleep", fake_sleep)

    assert Crossref().query_journal("0000-0000") is None
    assert calls == 1
    assert sleep_values == []


def test_crossref_journal_non_ok_status_returns_none_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    sleep_values = []

    def fake_get(url: str, headers: dict[str, str], timeout: int) -> JsonResponse:
        nonlocal calls
        del url, headers, timeout
        calls += 1
        return JsonResponse({}, HTTPStatus.BAD_REQUEST)

    def fake_sleep(seconds: float) -> None:
        sleep_values.append(seconds)

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(APIs, "sleep", fake_sleep)

    assert Crossref().query_journal("not-an-issn") is None
    assert calls == 1
    assert sleep_values == []


def test_crossref_selects_best_doi_from_response_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, headers: dict[str, str], timeout: int) -> JsonResponse:
        del url, headers, timeout
        return JsonResponse(
            {
                "message": {
                    "items": [
                        {"title": ["target title"], "author": [{"family": "Doe"}], "issued": {"date-parts": [[2018]]}},
                        {"title": ["target title"], "author": [{"family": "Other"}], "issued": {}},
                        {"title": [], "author": [{"given": "J.", "family": "Doe"}], "issued": {"date-parts": [[]]}},
                        {"author": [{"family": "Doe"}], "issued": {"date-parts": [[2020]]}},
                        {
                            "DOI": "10.555/best",
                            "title": ["target title"],
                            "author": [{"given": "Jane", "family": "Doe"}],
                            "issued": {"date-parts": [[2020]]},
                        },
                    ],
                },
            },
        )

    monkeypatch.setattr(requests, "get", fake_get)

    assert Crossref().query([("Jane", "Doe")], "target title", "2019-2020") == "10.555/best"


def test_orcid() -> None:
    authors: list[AuthorTuple] = [("Silvio", "Peroni", None, None)]
    identifiers: list[IdentifierTuple] = [(GraphEntity.iri_doi, "10.32388/LAKK5Q")]
    assert ORCID().query(authors, identifiers) == [("Silvio", "Peroni", "0000-0003-0530-4305", None)]


def test_orcid_without_identifiers() -> None:
    assert ORCID().query([], []) is None


def test_orcid_returns_unmatched_author_after_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    sleep_values = []

    def fake_get(url: str, headers: dict[str, str], timeout: int) -> JsonResponse:
        nonlocal calls
        del url, headers, timeout
        calls += 1
        raise ReadTimeout

    def fake_sleep(seconds: float) -> None:
        sleep_values.append(seconds)

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(APIs, "sleep", fake_sleep)

    authors: list[AuthorTuple] = [("Ada", "Lovelace", None, None)]
    identifiers: list[IdentifierTuple] = [(GraphEntity.iri_doi, "10.555/example")]
    assert ORCID().query(authors, identifiers) == [("Ada", "Lovelace", None, None)]
    assert calls == APIs.DEFAULT_RETRY_ATTEMPTS
    assert sleep_values == [1.0, 2.0]


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


def test_wikidata_unsupported_schema() -> None:
    assert WikiData().query("literal", "unsupported") is None


def test_openalex_doi() -> None:
    assert OpenAlex().query("10.1111/j.1749-6632.1958.tb54685.x", "doi") == ["W1985052597"]


def test_openalex_issn() -> None:
    assert OpenAlex().query("0014-2980", "issn") == ["S126191069"]


def test_openalex_pmid() -> None:
    assert OpenAlex().query("21603045", "pmid") == ["W2991792334"]


@pytest.mark.parametrize(
    "status_code",
    [
        HTTPStatus.TOO_MANY_REQUESTS,
        HTTPStatus.INTERNAL_SERVER_ERROR,
        HTTPStatus.BAD_GATEWAY,
        HTTPStatus.SERVICE_UNAVAILABLE,
        HTTPStatus.GATEWAY_TIMEOUT,
    ],
)
def test_openalex_retries_retryable_status_codes(
    monkeypatch: pytest.MonkeyPatch,
    status_code: HTTPStatus,
) -> None:
    responses = [
        JsonResponse({}, status_code),
        JsonResponse({"results": [{"id": "https://openalex.org/W123"}]}),
    ]
    sleep_values = []

    def fake_get(url: str, headers: dict[str, str], timeout: int) -> JsonResponse:
        del url, headers, timeout
        return responses.pop(0)

    def fake_sleep(seconds: float) -> None:
        sleep_values.append(seconds)

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(APIs, "sleep", fake_sleep)

    assert OpenAlex().query("10.555/example", "doi") == ["W123"]
    assert responses == []
    assert sleep_values == [1.0]


def test_openalex_unsupported_schema() -> None:
    assert OpenAlex().query("literal", "unsupported") is None
