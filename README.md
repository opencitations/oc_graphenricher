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
The enricher iterates each Bibliographic Resources (BRs) contained in the graph set.
For each Bibliographic Resources (BRs) (avoiding issues and journals), get the list of the identifiers already
contained in the graph set and check if it already has a DOI, an ISSN and a Wikidata ID:
- If an ISSN is specified, it query Crossref to extract other ISSNs
- If there's no DOI, it query Crossref to get one by means of all the other data extracted
- If there's no Wikidata ID, it query Wikidata to get one by means of all the other identifiers

Any new identifier found will be added to the Bibliographic Resource (BR).
  
Then, for each Agent Role (AR) related to the Bibliographic Resource (BR), get the list of all the identifier already contained in its linked Responsible Agent (RA) and:
- If doesn't have an ORCID, it query ORCID to get it
- If doesn't have a VIAF, it query VIAF to get it
- If doesn't have a Wikidata ID, it query Wikidata by means of all the other identifier to get one
- If the Responsible Agent (RA) is related to a publisher, it query Crossref to get its ID by means of its DOI

Any new identifier found will be added to the RA related to the AR.

In the end it will store a new graph set and its provenance.

NB: even if it's not possible to have an identifier duplicated for the same entity, it's possible that in
the whole graph set you could find different identifiers that share the same schema and literal. For this
purpose, you should use the **instancematching** module after that you've enriched the graph set.

### APIs and identifiers
Actually there are 4 external API involved:
- Crossref 
- ORCID
- VIAF
- WikiData 

and we can discover the following indentifiers:
- DOI
- ISSN
- Crossref's publisher ID
- ORCID
- VIAF
- Wikidata ID (by means of any other identifier, e.g.: PMID, VIAF, DOI, ...)

It's possible, anyway, to extend the class QueryInterface to add any other useful API.

### Instance Matching
The instance matching process is articulated in three sequential step:
- match the Responsible Agents (RAs)
- match the Bibliographic Resources (BRs) 
- match the IDs

#### Matching the Responsible Agents (RAs) 
Discover all the Responsible Agents (RAs)  that share the same identifier's literal, creating a graph of
them. Then merge each connected component (cluster of Responsible Agents (RAs)  linked by the same identifier)
into one.
For each couple of Responsible Agent (RA) that are going to be merged, substitute the references of the
Responsible Agent (RA) that will no longer exist, by removing the Responsible Agent (RA)
from each of its referred Agent Role (AR) and add, instead, the merged one)

If the Responsible Agent (RA) linked by the Agent Role (AR) that will no longer exist is not linked by any
other Agent Role (AR), then it will be marked as to be deleted, otherwise not.

In the end, generate the provenance and commit pending changes in the graph set

#### Matching the Bibliographic Resources (BRs) 

Discover all the Bibliographic Resources (BRs)  that share the same identifier's literal, creating a graph of them.
Then merge each connected component (cluster of Bibliographi Resources (BR) linked by the same identifier) into one.
For each couple of Bibliographic Resources (BRs) that are going to be merged, merge also:
 - their containers by matching the proper type (issue of BR1 -> issue of BR2)
 - their publisher

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

2. Install oc_graphenricher via pip:
```
pip install oc-graphenricher
```

### Installing from the sources
1. Having already installed python, you can also install GraphEnricher via cloning this repository: 
```
git clone https://github.com/opencitations/oc_graphenricher`
cd ./oc_graphenricher
```
2. install poetry:

```pip install poetry```

3. install all the dependencies:

``` poetry install```

4. build the package:

```poetry build```

5. install the package:

```    pip install ./dist/oc_graphenricher-<VERSION>.tar.gz```

6. run the tests (from the root of the project):

```
poetry run test
```

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

### Enrichment
At this point, to run the enrichment phase:
```
from oc_graphenricher.enricher import Enricher

enricher = GraphEnricher(g_set)
enricher.enrich()
```
You'll see the progress bar with an estimate of the time needed and the average time spent
for each Bibliographic Resource (BR) enriched. 

### Deduplication 
Then, having serialized the enriched graph set, and having read it again as the
`g_set` object, to run the deduplication step do:

```
from oc_graphenricher.instancematching import InstanceMatching

matcher = InstanceMatching(g_set)
matcher.match()
```

The match method will run sequentially:
- deduplication of Responsible Agents (RAs)
- deduplication of Bibliographic Resources (BRs)
- deduplication of Identifiers (IDs)
- save to file

If you need to, you can also deduplicate one of those independently of each other.

To deduplicate Responsible Agents (RAs):
```
from oc_graphenricher.instancematching import InstanceMatching

matcher = InstanceMatching(g_set)
matcher.instance_matching_ra()
matcher.save()
```

To deduplicate Bibliographic Resources (BRs):
```
from oc_graphenricher.instancematching import InstanceMatching

matcher = InstanceMatching(g_set)
matcher.instance_matching_br()
matcher.save()
```
To deduplicate Identifiers (IDs):
```
from oc_graphenricher.instancematching import InstanceMatching

matcher = InstanceMatching(g_set)
matcher.instance_matching_id()
matcher.save()
```





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
