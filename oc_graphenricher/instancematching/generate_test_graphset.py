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

from oc_ocdm import Storer
from oc_ocdm.graph import GraphSet
from oc_ocdm.support import create_date


def add_one_author_with_single_id(type, literal):

    sp = gs.add_ra(ra)
    sp.has_given_name("othername")
    sp.has_family_name("otherfamilyname")

    sp_author = gs.add_ar(ra)
    sp_author.is_held_by(sp)

    add_id(sp, literal, type, gs)
    sp_author.create_author()
    return sp_author

def add_one_author_with_two_id(type, literal):

    sp = gs.add_ra(ra)
    sp.has_given_name("othername")
    sp.has_family_name("otherfamilyname")

    sp_author = gs.add_ar(ra)
    sp_author.is_held_by(sp)

    add_id(sp, 'orcid_author_1', 'orcid', gs)
    add_id(sp, literal, type, gs)

    sp_author.create_author()

    return sp_author

def add_article():
    my_paper = gs.add_br(ra)
    my_paper.has_title("test")
    my_paper.has_pub_date("2020")
    iso_date_string = create_date([2020, 5, 1])
    my_paper.has_pub_date(iso_date_string)
    add_id(my_paper, 'doi4', 'doi', gs)
    my_paper.create_journal_article()
    return my_paper

def add_br_with_one_author(name):
    ####
    # author
    ####
    sp = gs.add_ra(ra)
    sp.has_given_name("name")
    sp.has_family_name("familyname")
    #
    sp_author = gs.add_ar(ra)
    sp_author.is_held_by(sp)
    sp_author.create_author()
    add_id(sp, "orcid1", 'orcid', gs)
    #####

    ####
    # publisher
    ####
    sp = gs.add_ra(ra)
    sp.has_name("Pub")
    #
    sp_pub = gs.add_ar(ra)
    sp_pub.is_held_by(sp)
    sp_pub.create_publisher()

    add_id(sp, "pub1", 'crossref', gs)
    #####

    ####
    # volume
    ####
    my_volume = gs.add_br(ra)
    my_volume.has_title(name+"_volume")
    my_volume.has_pub_date("2020")
    add_id(my_volume, name+'_volume_doi','doi', gs)
    my_volume.create_volume()

    ####
    # issue
    ####
    my_issue = gs.add_br(ra)
    my_issue.has_title(name+"_issue")
    add_id(my_issue, name+'_issue_doi','doi', gs)
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
    iso_date_string = create_date([2020, 5, 1])
    my_paper.has_pub_date(iso_date_string)
    add_id(my_paper, 'doi1', 'doi', gs)
    my_paper.create_journal_article()
    #####

def add_id(entity, literal, schema, g_set):

    new_id = g_set.add_id("http://responsible_agent/")
    if schema == 'issn':
        new_id.create_issn(literal)
    elif schema == 'doi':
        new_id.create_doi(literal)
    elif schema == 'orcid':
        new_id.create_orcid(literal)
    elif schema == 'viaf':
        new_id.create_viaf(literal)
    elif schema == 'crossref':
        new_id.create_crossref(literal)
    elif schema == 'wikidata':
        new_id.create_wikidata(literal)

    entity.has_identifier(new_id)


ra = "http://responsible_agent/"
gs = GraphSet("http://example.com/")

add_br_with_one_author("BR3")
add_br_with_one_author("BR6")

paper = add_article()
author1 = add_one_author_with_single_id('orcid', 'orcid_author_1')
author2 = add_one_author_with_two_id('viaf', 'viaf1')
paper.has_contributor(author1)
paper.has_contributor(author2)
gs.commit_changes()
gs_storer = Storer(gs, output_format="nt11")
gs_storer.store_graphs_in_file("./test_merge_br.rdf", "")