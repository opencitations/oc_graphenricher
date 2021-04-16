Tutorial
============================================
The OC GraphEnricher is supposed to accept only graph set objects.
To create one:

    .. code-block:: python

        from oc_ocdm.reader import Reader
        from oc_ocdm.graph import GraphSet
        from rdflib import Graph

        g = Graph()
        g = g.parse('../data/test_dump.ttl', format='nt11')

        reader = Reader()
        g_set = GraphSet(base_iri='https://w3id.org/oc/meta/')
        entities = reader.import_entities_from_graph(g_set, g, enable_validation=False, resp_agent='https://w3id.org/oc/meta/prov/pa/2')

Enrichment
########
At this point, to run the enrichment phase:

    .. code-block:: python

        from oc_graphenricher.enricher import Enricher

        enricher = GraphEnricher(g_set)
        enricher.enrich()

You'll see the progress bar with an estimate of the time needed and the average time spent
for each Bibliographic Resource (BR) enriched.

Deduplication
########
Then, having serialized the enriched graph set, and having read it again as the
`g_set` object, to run the deduplication step do:

    .. code-block:: python

        from oc_graphenricher.instancematching import InstanceMatching

        matcher = InstanceMatching(g_set)
        matcher.match()

The match method will run sequentially:
- deduplication of Responsible Agents (RAs)
- deduplication of Bibliographic Resources (BRs)
- deduplication of Identifiers (IDs)
- save to file

If you need to, you can also deduplicate one of those independently of each other.

To deduplicate Responsible Agents (RAs):

    .. code-block:: python

        from oc_graphenricher.instancematching import InstanceMatching

        matcher = InstanceMatching(g_set)
        matcher.instance_matching_ra()
        matcher.save()


To deduplicate Bibliographic Resources (BRs):

    .. code-block:: python

        from oc_graphenricher.instancematching import InstanceMatching

        matcher = InstanceMatching(g_set)
        matcher.instance_matching_br()
        matcher.save()


To deduplicate Identifiers (IDs):

    .. code-block:: python

        from oc_graphenricher.instancematching import InstanceMatching

        matcher = InstanceMatching(g_set)
        matcher.instance_matching_id()
        matcher.save()
