<p align="center">

  <h2 align="center">GraphEnricher</h3>
  <p align="center">
    A tool to enrich any <a href="http://opencitations.net/model">OCDM</a> compliant Knowledge Graph, finding new identifiers
and deduplicating entities.
</p>

<!-- TABLE OF CONTENTS -->
  <summary><h2 style="display: inline-block">Table of Contents</h2></summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgements">Acknowledgements</a></li>
  </ol>



<!-- ABOUT THE PROJECT -->
## About The Project

This tool is divided in two part: an Enricher component responsible to find new identifiers and adding them to the 
graph set, and an InstanceMatching component responsible to deduplicate any entity that share the same identifier.
### Enricher
The enricher iterates each BR contained in the graph set.
For each BR (avoiding issues and journals), get the list of the identifiers already
contained in the graph set and check if it already has a DOI, an ISSN and a Wikidata ID:
- If an ISSN is specified, it query Crossref to extract other ISSNs
- If there's no DOI, it query Crossref to get one by means of all the other data extracted
- If there's no Wikidata ID, it query Wikidata to get one by means of all the other identifiers

Any new identifier found will be added to the BR.
  
Then, for each AR related to the BR, get the list of all the identifier already contained and:
- If doesn't have an ORCID, it query Crossref to get it
- If doesn't have a VIAF, it query VIAF to get it
- If doesn't have a Wikidata ID, it query Wikidata by means of all the other identifier to get one
- If the AR is related to a publisher, it query Crossref to get its ID by means of its DOI

Any new identifier found will be added to the AR.

In the end it will store a new graph set and its provenance.

NB: Even if it's not possible to have an identifier duplicated for the same entity, it's possible that in
the whole graph set you could find different identifiers that share the same schema and literal. For this
purpose, you should use the **instancematching** module after that you've enriched the graph set.

Actually there are 4 external API involved:
- Crossref (DOI, ISSN)
- ORCID
- VIAF
- WikiData 

It's possible, anyway, to extend the class QueryInterface to add any other useful API.

### Instance Matching
The instance matching process is articulated in three sequential step:
- match the ARs
- match the BRs
- match the IDs

#### Matching the ARs 
Discover all the ARs that share the same identifier's literal, creating a graph of them.
Then merge each connected component (cluster of ARs linked by the same identifier) into one.

For each couple of AR that are going to be merged, substitute the references of the AR that will no longer
exist, by removing the AR  from each of its referred BR and add, instead, the merged one)

If the RA linked by the AR that will no longer exist is not linked by any other AR, then
it will be marked as to be deleted, otherwise not.

In the end, generate the provenance and commit pending changes in the graph set

#### Matching the BRs

Discover all the BRs that share the same identifier's literal, creating a graph of them.
Then merge each connected component (cluster of Be RA associated to the Rs linked by the same identifier) into one.
For each couple of BR that are going to be merged, merge also:
 - their containers by matching the proper type (issue of BR1 -> issue of BR2)
 - their publisher

NB: when two BRs are merged, you'll have the union of their ARs. You could have duplicates if the duplicates 
don't have any ID in common or if the method `instance_matching_ar` wasn't called before.

In the end, generate the provenance and commit pending changes in the graph set

#### Matching the IDs
Discover all the IDs that share the same schema and literal, then merge all into one
and substitute all the reference with the merged one.

In the end, generate the provenance and commit pending changes in the graph set

<!-- GETTING STARTED -->
## Getting Started

To get a local copy up and running follow these simple steps:
1. install python >= 3.8:

```sudo apt install python3```

2. clone this repository: 
```
git clone https://github.com/opencitations/oc_graphenricher`
cd ./oc_graphenricher
```
3. install poetry:

```pip install poetry```

4 install all the dependencies:

``` poetry install```

5. build the package:

```poetry build```

6. install the package:

```    pip install ./dist/oc_graphenricher-<VERSION>.tar.gz```



<!-- USAGE EXAMPLES -->
## Usage
It's supposed to accept only graph set objects. To create one:

```
g = Graph()
g = g.parse('../data/test_dump.ttl', format='nt11')

reader = Reader()
g_set = GraphSet(base_iri='https://w3id.org/oc/meta/')
entities = reader.import_entities_from_graph(g_set, g, enable_validation=False, resp_agent='https://w3id.org/oc/meta/prov/pa/2')
```
At this point, to run the enrichment phase:
```
enricher = GraphEnricher(g_set)
enricher.enrich()
```
Then, having serialized the enriched graph set, and having read it again as the
`g_set` object, to run the deduplication step do:

```
matcher = InstanceMatching(g_set)
matcher.match()
```

Those two functionalities are available with `main_enricher.py` and `main_instancematching.py`.





<!-- LICENSE -->
## License

Distributed under the ISC License. See `LICENSE` for more information.



<!-- CONTACT -->
## Contact

Gabriele Pisciotta - [@GaPisciotta](https://twitter.com/GaPisciotta) - ga.pisciotta@gmail.com

Project Link: [https://github.com/opencitations/oc_graphenricher](https://github.com/opencitations/oc_graphenricher)



<!-- ACKNOWLEDGEMENTS -->
## Acknowledgements
This project has been developed as part of the 
[Wikipedia Citations in Wikidata](https://meta.wikimedia.org/wiki/Wikicite/grant/Wikipedia_Citations_in_Wikidata) 
research project, under the supervision of prof. Silvio Peroni.




<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
