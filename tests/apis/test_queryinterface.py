# SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

import json
from http import HTTPStatus
from pathlib import Path
from typing import cast

import pytest
import requests
from oc_ocdm.graph.graph_entity import GraphEntity
from requests.exceptions import ReadTimeout

from oc_graphenricher import APIs
from oc_graphenricher.APIs import ORCID, VIAF, AuthorTuple, Crossref, IdentifierTuple, OpenAlex, Wikidata

Snapshot = dict[str, object]
SNAPSHOTS = cast(
    "dict[str, Snapshot]",
    json.loads(
        (Path(__file__).parents[1] / "fixtures" / "api_responses" / "queryinterface.json").read_text(
            encoding="utf-8",
        ),
    ),
)


class JsonResponse:
    def __init__(
        self,
        data: object,
        status_code: HTTPStatus | int = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.data = data
        self.status_code = int(status_code)
        self.headers = headers if headers is not None else {}
        self.text = data if isinstance(data, str) else json.dumps(data)

    def json(self) -> object:
        return self.data


def _snapshot_response(snapshot_name: str) -> JsonResponse:
    snapshot = SNAPSHOTS[snapshot_name]
    response = cast("Snapshot", snapshot["response"])
    return JsonResponse(
        response["body"],
        cast("int", response["status_code"]),
        cast("dict[str, str]", response["headers"]),
    )


def _assert_snapshot_request(
    snapshot_name: str,
    url: str,
    headers: dict[str, str],
    params: dict[str, str] | None,
) -> None:
    snapshot = SNAPSHOTS[snapshot_name]
    request = cast("Snapshot", snapshot["request"])

    assert request["method"] == "GET"
    assert url == request["url"]
    assert headers == request["headers"]
    actual_params = {}
    if params is not None:
        actual_params = params
    assert actual_params == request["params"]


def _mock_snapshot_get(monkeypatch: pytest.MonkeyPatch, snapshot_names: list[str]) -> list[str]:
    pending = snapshot_names.copy()

    def fake_get(
        url: str,
        headers: dict[str, str],
        timeout: float,
        params: dict[str, str] | None = None,
    ) -> JsonResponse:
        del timeout
        if not pending:
            message = f"Unexpected HTTP request: {url}"
            raise AssertionError(message)

        snapshot_name = pending.pop(0)
        _assert_snapshot_request(snapshot_name, url, headers, params)
        return _snapshot_response(snapshot_name)

    monkeypatch.setattr(requests, "get", fake_get)
    return pending


def test_unmocked_http_request_fails() -> None:
    with pytest.raises(AssertionError, match="External HTTP request blocked"):
        requests.get("https://example.org/", timeout=1)


def test_crossref_doi(monkeypatch: pytest.MonkeyPatch) -> None:
    pending = _mock_snapshot_get(monkeypatch, ["crossref_doi"])

    assert (
        Crossref().query(
            [("Stacey", "Willcox-Pidgeon")],
            "PW 1927 Reviewing the national swimming and water safety education framework: "  # noqa: RUF001
            "a drowning prevention strategy",
            "2018",
        )
        == "10.1136/injuryprevention-2018-safety.431"
    )
    assert pending == []


def test_crossref_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    pending = _mock_snapshot_get(monkeypatch, ["crossref_journal"])

    assert Crossref().query_journal("0008-4026") == ["1480-3305"]
    assert pending == []


def test_crossref_publisher(monkeypatch: pytest.MonkeyPatch) -> None:
    pending = _mock_snapshot_get(monkeypatch, ["crossref_publisher"])

    assert Crossref().query_publisher("10.1007/978-3-030-00668-6_4") == "297"
    assert pending == []


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


def test_orcid(monkeypatch: pytest.MonkeyPatch) -> None:
    pending = _mock_snapshot_get(monkeypatch, ["orcid_search", "orcid_personal_details"])
    authors: list[AuthorTuple] = [("Silvio", "Peroni", None, None)]
    identifiers: list[IdentifierTuple] = [(GraphEntity.iri_doi, "10.32388/LAKK5Q")]

    assert ORCID().query(authors, identifiers) == [("Silvio", "Peroni", "0000-0003-0530-4305", None)]
    assert pending == []


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


def test_viaf(monkeypatch: pytest.MonkeyPatch) -> None:
    pending = _mock_snapshot_get(monkeypatch, ["viaf"])
    title = "A Smart City Data Model based on Semantics Best Practice and Principles"

    assert VIAF().query("Silvio", "Peroni", title) == "309649450"
    assert pending == []


@pytest.mark.parametrize(
    ("snapshot_name", "entity", "schema", "expected"),
    [
        ("wikidata_doi", "10.1002/(ISSN)1098-2353", "doi", "Q59755"),
        ("wikidata_issn", "0009-4722", "issn", "Q1119421"),
        ("wikidata_orcid", "0000-0002-7398-5483", "orcid", "Q5345"),
        ("wikidata_viaf", "24715915", "viaf", "Q1228"),
        ("wikidata_pmid", "12344444", "pmid", "Q78273175"),
        ("wikidata_pmcid", "3083595", "pmcid", "Q54919067"),
    ],
)
def test_wikidata(
    monkeypatch: pytest.MonkeyPatch,
    snapshot_name: str,
    entity: str,
    schema: str,
    expected: str,
) -> None:
    pending = _mock_snapshot_get(monkeypatch, [snapshot_name])

    assert Wikidata().query(entity, schema) == expected
    assert pending == []


def test_wikidata_unsupported_schema() -> None:
    assert Wikidata().query("literal", "unsupported") is None


@pytest.mark.parametrize(
    ("snapshot_name", "entity", "schema", "expected"),
    [
        ("openalex_doi", "10.1111/j.1749-6632.1958.tb54685.x", "doi", ["W1985052597"]),
        ("openalex_issn", "0014-2980", "issn", ["S126191069"]),
        ("openalex_pmid", "21603045", "pmid", ["W2991792334"]),
    ],
)
def test_openalex(
    monkeypatch: pytest.MonkeyPatch,
    snapshot_name: str,
    entity: str,
    schema: str,
    expected: list[str],
) -> None:
    pending = _mock_snapshot_get(monkeypatch, [snapshot_name])

    assert OpenAlex().query(entity, schema) == expected
    assert pending == []


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
