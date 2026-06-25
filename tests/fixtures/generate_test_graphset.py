# SPDX-FileCopyrightText: 2021 Gabriele Pisciotta <ga.pisciotta@gmail.com>
# SPDX-FileCopyrightText: 2026 Arcangelo Massari <arcangelo.massari@unibo.it>
#
# SPDX-License-Identifier: ISC

from pathlib import Path
from typing import cast

from oc_ocdm.graph.entities.bibliographic.agent_role import AgentRole
from oc_ocdm.graph.entities.bibliographic.bibliographic_resource import BibliographicResource
from oc_ocdm.graph.graph_set import GraphSet
from oc_ocdm.support.support import create_date

from oc_graphenricher._storage import store_graph_set
from oc_graphenricher.storage import single_file_storage
from tests.helpers import add_id


def add_one_author_with_single_id(schema: str, literal: str) -> AgentRole:
    sp = gs.add_ra(ra)
    sp.has_given_name("othername")
    sp.has_family_name("otherfamilyname")

    sp_author = gs.add_ar(ra)
    sp_author.is_held_by(sp)

    add_id(sp, literal, schema, gs, resp_agent=ra)
    sp_author.create_author()
    return sp_author


def add_one_author_with_two_id(schema: str, literal: str) -> AgentRole:
    sp = gs.add_ra(ra)
    sp.has_given_name("othername")
    sp.has_family_name("otherfamilyname")

    sp_author = gs.add_ar(ra)
    sp_author.is_held_by(sp)

    add_id(sp, "orcid_author_1", "orcid", gs, resp_agent=ra)
    add_id(sp, literal, schema, gs, resp_agent=ra)

    sp_author.create_author()

    return sp_author


def add_article() -> BibliographicResource:
    my_paper = gs.add_br(ra)
    my_paper.has_title("test")
    my_paper.has_pub_date("2020")
    iso_date_string = cast("str", create_date([2020, 5, 1]))
    my_paper.has_pub_date(iso_date_string)
    add_id(my_paper, "doi4", "doi", gs, resp_agent=ra)
    my_paper.create_journal_article()
    return my_paper


def add_br_with_one_author(name: str) -> None:
    ####
    # author
    ####
    sp = gs.add_ra(ra)
    sp.has_given_name("name")
    sp.has_family_name("familyname")
    sp_author = gs.add_ar(ra)
    sp_author.is_held_by(sp)
    sp_author.create_author()
    add_id(sp, "orcid1", "orcid", gs, resp_agent=ra)
    #####

    ####
    # publisher
    ####
    sp = gs.add_ra(ra)
    sp.has_name("Pub")
    sp_pub = gs.add_ar(ra)
    sp_pub.is_held_by(sp)
    sp_pub.create_publisher()

    add_id(sp, "pub1", "crossref", gs, resp_agent=ra)
    #####

    ####
    # volume
    ####
    my_volume = gs.add_br(ra)
    my_volume.has_title(name + "_volume")
    my_volume.has_pub_date("2020")
    add_id(my_volume, name + "_volume_doi", "doi", gs, resp_agent=ra)
    my_volume.create_volume()

    ####
    # issue
    ####
    my_issue = gs.add_br(ra)
    my_issue.has_title(name + "_issue")
    add_id(my_issue, name + "_issue_doi", "doi", gs, resp_agent=ra)
    my_issue.is_part_of(my_volume)
    my_issue.create_issue()

    ####
    # paper
    ####
    my_paper = gs.add_br(ra)
    my_paper.has_title(name)
    my_paper.has_pub_date("2020")
    my_paper.has_contributor(sp_author)
    my_paper.has_contributor(sp_pub)
    my_paper.is_part_of(my_issue)
    iso_date_string = cast("str", create_date([2020, 5, 1]))
    my_paper.has_pub_date(iso_date_string)
    add_id(my_paper, "doi1", "doi", gs, resp_agent=ra)
    my_paper.create_journal_article()
    #####


ra = "http://responsible_agent/"
gs = GraphSet("http://example.com/")

add_br_with_one_author("BR3")
add_br_with_one_author("BR6")

paper = add_article()
author1 = add_one_author_with_single_id("orcid", "orcid_author_1")
author2 = add_one_author_with_two_id("viaf", "viaf1")
paper.has_contributor(author1)
paper.has_contributor(author2)
gs.commit_changes()
store_graph_set(
    gs,
    single_file_storage(
        Path(__file__).with_name("test_merge_br.rdf"),
        "",
        output_format="nt11",
        zip_output=False,
    ),
)
