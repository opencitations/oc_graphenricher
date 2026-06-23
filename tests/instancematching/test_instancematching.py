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

EXPECTED_BR_CONTRIBUTOR_COUNTS = {
    "http://example.com/br/1": 0,
    "http://example.com/br/2": 0,
    "http://example.com/br/3": 2,
    "http://example.com/br/7": 2,
}

EXPECTED_IDS = [
    "http://purl.org/spar/datacite/crossrefpub1",
    "http://purl.org/spar/datacite/doibr3_issue_doi",
    "http://purl.org/spar/datacite/doibr3_volume_doi",
    "http://purl.org/spar/datacite/doibr6_issue_doi",
    "http://purl.org/spar/datacite/doibr6_volume_doi",
    "http://purl.org/spar/datacite/doidoi1",
    "http://purl.org/spar/datacite/doidoi4",
    "http://purl.org/spar/datacite/orcidorcid1",
    "http://purl.org/spar/datacite/orcidorcid_author_1",
    "http://purl.org/spar/datacite/viafviaf1",
]

EXPECTED_RA_IDENTIFIERS = [
    "http://purl.org/spar/datacite/crossrefpub1",
    "http://purl.org/spar/datacite/orcidorcid1",
    "http://purl.org/spar/datacite/orcidorcid_author_1",
    "http://purl.org/spar/datacite/viafviaf1",
]


def identifier_key(identifier):
    return f"{identifier.get_scheme()}{identifier.get_literal_value()}"


def test_ras_merged(matched_graph_set):
    identifiers = sorted(
        identifier_key(identifier)
        for ra in matched_graph_set.get_ra()
        for identifier in ra.get_identifiers()
    )
    assert identifiers == EXPECTED_RA_IDENTIFIERS


def test_ids_not_duplicated(matched_graph_set):
    identifiers = sorted(
        identifier_key(identifier)
        for identifier in matched_graph_set.get_id()
        if identifier_key(identifier) != "NoneNone"
    )
    assert identifiers == EXPECTED_IDS


def test_agent_roles_reference_existing_responsible_agents(matched_graph_set):
    held_responsible_agents = {ar.get_is_held_by() for ar in matched_graph_set.get_ar()}
    responsible_agents = set(matched_graph_set.get_ra())
    orphan_responsible_agents = sorted(str(ra) for ra in held_responsible_agents.difference(responsible_agents))

    assert orphan_responsible_agents == []


def test_bibliographic_resources_reference_existing_agent_roles(matched_graph_set):
    agent_roles_from_brs = sorted(str(ar) for br in matched_graph_set.get_br() for ar in br.get_contributors())
    agent_roles = sorted(str(ar) for ar in matched_graph_set.get_ar())

    assert agent_roles_from_brs == agent_roles


def test_brs_merged(matched_graph_set):
    bibliographic_resources = sorted(str(br) for br in matched_graph_set.get_br())
    assert bibliographic_resources == [
        "http://example.com/br/1",
        "http://example.com/br/2",
        "http://example.com/br/3",
        "http://example.com/br/7",
    ]


def test_brs_have_only_one_list_of_authors(matched_graph_set):
    contributor_counts_by_br = {
        str(br): len(br.get_contributors())
        for br in matched_graph_set.get_br()
    }
    assert contributor_counts_by_br == EXPECTED_BR_CONTRIBUTOR_COUNTS
