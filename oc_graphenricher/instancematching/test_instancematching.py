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

import os
import unittest
from unittest import TestCase

from oc_ocdm.graph import GraphSet
from oc_ocdm.reader import Reader
from rdflib import Graph

from oc_graphenricher.instancematching import InstanceMatching


class TestInstanceMatching(TestCase):

    def setUp(self) -> None:
        self.test_dir = str(__file__).replace("test_instancematching.py", "")
        g = Graph()
        g = g.parse(self.test_dir + 'test_merge_br.rdf', format='nt11')

        reader = Reader()
        g_set = GraphSet(base_iri='https://w3id.org/oc/meta/')
        reader.import_entities_from_graph(g_set,
                                          g,
                                          enable_validation=False,
                                          resp_agent='https://w3id.org/oc/meta/prov/pa/2')

        matcher = InstanceMatching(g_set,
                                   graph_filename=self.test_dir + "matched.rdf",
                                   provenance_filename=self.test_dir + "provenance.rdf",
                                   debug=True)
        matcher.match()

        g = Graph()
        g = g.parse(self.test_dir + 'matched.rdf', format='nt11')

        reader = Reader()
        self.g_set_new = GraphSet(base_iri='https://w3id.org/oc/meta/')
        reader.import_entities_from_graph(self.g_set_new,
                                          g,
                                          enable_validation=False,
                                          resp_agent='https://w3id.org/oc/meta/prov/pa/2')

    def test_ras_merged(self):
        ids = set()
        for ra in self.g_set_new.get_ra():
            for idd in ra.get_identifiers():
                newliteral = str(idd.get_scheme()) + str(idd.get_literal_value())
                if newliteral in ids:
                    self.fail()
                else:
                    ids.add(idd)


    def test_ids_not_duplicated(self):
        ids = set()
        for idd in self.g_set_new.get_id():
            newliteral = str(idd.get_scheme()) + str(idd.get_literal_value())
            if newliteral != "NoneNone" and newliteral in ids:
                print("Ahia")
                self.fail()
            else:
                ids.add(newliteral)

    def test_orphan_ra(self):
        ras_from_ar = set()
        for ar in self.g_set_new.get_ar():
            ras_from_ar.add(ar.get_is_held_by())

        ras = set()
        for ra in self.g_set_new.get_ra():
            ras.add(ra)

        difference = ras_from_ar.difference(ras)
        if len(difference) > 0:
            print(f"AR Orphans: {[str(d) for d in difference]}")
            self.fail()

    def test_orphan_ar(self):
        ars_from_ar = set()
        for br in self.g_set_new.get_br():
            for ar in br.get_contributors():
                ars_from_ar.add(ar)

        ars = set()
        for ar in self.g_set_new.get_ar():
            ars.add(ar)

        difference = ars.difference(ars_from_ar)
        if len(difference) > 0:
            print(f"Orphans: {[str(d) for d in difference]}")
            self.fail()

    def test_brs_merged(self):
        for br in self.g_set_new.get_br():
            if str(br) == 'http://example.com/br/6' and len(br.get_contributors()) != 0:
                print(br, len(br.get_contributors()))
                self.fail()

    def test_brs_have_only_one_list_of_authors(self):
        for br in self.g_set_new.get_br():
            if str(br) == 'http://example.com/br/3' and len(br.get_contributors()) != 2:
                for ar in br.get_contributors():
                    print(ar, ar.get_is_held_by())
                print(f"Contributors len {len(br.get_contributors())}")
                self.fail()

    def test_remove_files(self):
        os.system(f'rm "{self.test_dir}matched.rdf"')
        os.system(f'rm "{self.test_dir}provenance.rdf"')


if __name__ == '__main__':
    unittest.main()
