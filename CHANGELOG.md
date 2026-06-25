# 1.0.0 (2026-06-25)


* feat!: add storage factories for single-file and OCDM directory output ([5f20d94](https://github.com/opencitations/oc_graphenricher/commit/5f20d941d95f765c42c45507ce95b9ee28b59e93))
* fix(lint)!: make boolean flags keyword-only ([4511a34](https://github.com/opencitations/oc_graphenricher/commit/4511a34754b38e35c0a5a2c7ee8ee32ecce3a2ce))


### Bug Fixes

* adapt instance matching to oc-ocdm 11 ([45019ec](https://github.com/opencitations/oc_graphenricher/commit/45019ec69c680b6bd0ff8eea4710a1e988d75d96))
* **apis:** retry transient api failures ([9c23cbf](https://github.com/opencitations/oc_graphenricher/commit/9c23cbf7728d00320c8bc15c4828c48f41646d15))
* **deps:** update dependency declarations ([5d1a8b9](https://github.com/opencitations/oc_graphenricher/commit/5d1a8b9687e16bc0c376e70effa3a8502b6a1f06))
* **instancematching:** avoid self-merging named contributors ([1e8e38b](https://github.com/opencitations/oc_graphenricher/commit/1e8e38bf1730a865c11706e3d51f7c6d0acf6563))
* skip incomplete graph identifiers and add style/type linting ([5d38ded](https://github.com/opencitations/oc_graphenricher/commit/5d38ded51f874b97bb28efd2687bc78e0bb9b7c2))


### BREAKING CHANGES

* GraphEnricher and InstanceMatching now require a storage factory, either single_file_storage or directory_storage. The graph_filename and provenance_filename constructor parameters were removed.
* GraphEnricher, InstanceMatching, Crossref, and ORCID no longer accept their boolean flags as positional arguments. Pass debug, serialize_in_the_middle, use_wikidata, use_viaf, use_orcid, and is_json by keyword.
