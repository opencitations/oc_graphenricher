## [2.1.12](https://github.com/opencitations/oc_graphenricher/compare/v2.1.11...v2.1.12) (2026-07-10)


### Bug Fixes

* **deduplication:** index identifier references [release] ([a03add8](https://github.com/opencitations/oc_graphenricher/commit/a03add86ff079a5e55df24c14968066023d340db))

## [2.1.11](https://github.com/opencitations/oc_graphenricher/compare/v2.1.10...v2.1.11) (2026-07-07)


### Bug Fixes

* **deduplication:** keep one br contributor chain in manual merges [release] ([80f7006](https://github.com/opencitations/oc_graphenricher/commit/80f7006ae2818d1e0211c6a5dfd4f820f2b59623))

## [2.1.10](https://github.com/opencitations/oc_graphenricher/compare/v2.1.9...v2.1.10) (2026-07-07)


### Bug Fixes

* **deduplication:** order merge clusters before mutation [release] ([9c0a1ea](https://github.com/opencitations/oc_graphenricher/commit/9c0a1eab569a580a9f308842d78316018f8bc894))

## [2.1.9](https://github.com/opencitations/oc_graphenricher/compare/v2.1.8...v2.1.9) (2026-07-06)


### Bug Fixes

* **deduplication:** collapse duplicate same-agent publisher roles [release] ([0f0f0fc](https://github.com/opencitations/oc_graphenricher/commit/0f0f0fc5eef615b3713f986f7fe5016fabf0d148))

## [2.1.8](https://github.com/opencitations/oc_graphenricher/compare/v2.1.7...v2.1.8) (2026-07-06)


### Bug Fixes

* **deduplication:** splice duplicate contributor out of the author order [release] ([5252604](https://github.com/opencitations/oc_graphenricher/commit/525260410f97bd117cc8c5ac6e944bf7930d8c02))

## [2.1.7](https://github.com/opencitations/oc_graphenricher/compare/v2.1.6...v2.1.7) (2026-07-06)


### Bug Fixes

* **deduplication:** merge duplicate container contributors [release] ([b2158df](https://github.com/opencitations/oc_graphenricher/commit/b2158df65519db9f2d0d3a32f7ca6f1e4d2db07a))

## [2.1.6](https://github.com/opencitations/oc_graphenricher/compare/v2.1.5...v2.1.6) (2026-07-06)


### Bug Fixes

* **deduplication:** Reject manual BR merges that would collapse a typed container into an incompatible BR type [release] ([ed7ead3](https://github.com/opencitations/oc_graphenricher/commit/ed7ead33ab5a5b435790e5c84eabb4c29b967203))

## [2.1.5](https://github.com/opencitations/oc_graphenricher/compare/v2.1.4...v2.1.5) (2026-07-06)


### Bug Fixes

* **deduplication:** keep distinct publisher roles [release] ([e1aa5cd](https://github.com/opencitations/oc_graphenricher/commit/e1aa5cdf29700ec5662b69631a545f843826d128))

## [2.1.4](https://github.com/opencitations/oc_graphenricher/compare/v2.1.3...v2.1.4) (2026-07-06)


### Bug Fixes

* **deduplication:** avoid merging distinct containers [release] ([3a1da2f](https://github.com/opencitations/oc_graphenricher/commit/3a1da2f0e8b36d8f627e559e53df23d60db0e1bf))

## [2.1.3](https://github.com/opencitations/oc_graphenricher/compare/v2.1.2...v2.1.3) (2026-07-05)


### Bug Fixes

* **deduplication:** preserve more informative duplicate survivor [release] ([732e864](https://github.com/opencitations/oc_graphenricher/commit/732e8648d4faeb02573211d17520ed2ad0fe1a7f))

## [2.1.2](https://github.com/opencitations/oc_graphenricher/compare/v2.1.1...v2.1.2) (2026-07-04)


### Bug Fixes

* **deduplication:** harden manual and agent merges [release] ([acd2392](https://github.com/opencitations/oc_graphenricher/commit/acd2392231f3234681fa1eadc38925d9fc6d2c7b))

## [2.1.1](https://github.com/opencitations/oc_graphenricher/compare/v2.1.0...v2.1.1) (2026-07-04)


### Bug Fixes

* **deduplication:** remove deleted entities from directory output [release] ([e7a351e](https://github.com/opencitations/oc_graphenricher/commit/e7a351e17363d5482e939889ca1dd27a644a422b))

# [2.1.0](https://github.com/opencitations/oc_graphenricher/compare/v2.0.0...v2.1.0) (2026-07-04)


### Features

* **deduplication:** add guided merge clusters [release] ([fcccca2](https://github.com/opencitations/oc_graphenricher/commit/fcccca2ecaead6755914729c6e2945eb55a078ed))

# [2.0.0](https://github.com/opencitations/oc_graphenricher/compare/v1.0.1...v2.0.0) (2026-07-04)


* feat!: rename instance matching API to deduplication [release] ([535db22](https://github.com/opencitations/oc_graphenricher/commit/535db22f3c556067c6d5d21dc1bc43de236a67c2))


### Features

* move provenance settings into storage ([f4084a6](https://github.com/opencitations/oc_graphenricher/commit/f4084a6448c4f2981f30ea0ab7698864b2897db2))


### BREAKING CHANGES

* `InstanceMatching` is replaced by `GraphDeduplicator` in `oc_graphenricher.deduplication`. `match()` is replaced by `deduplicate_and_save()`, `GraphEnricher` now takes `graph_set` instead of `g_set`, `serialize_in_the_middle` is replaced by `checkpoint_interval`, and `WikiData` is renamed to `Wikidata`.

## [1.0.1](https://github.com/opencitations/oc_graphenricher/compare/v1.0.0...v1.0.1) (2026-07-03)


### Bug Fixes

* **instancematching:** disable name-based contributor merging by default ([cb61db3](https://github.com/opencitations/oc_graphenricher/commit/cb61db3c069e25ff45bbdcf32f4879473e9e46ad))
* **instancematching:** preserve contributor roles during br merges ([e0a9e75](https://github.com/opencitations/oc_graphenricher/commit/e0a9e7538939917a5d1d37ee84fd6c81ec4ba4b7))

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
