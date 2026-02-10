# CHANGELOG


## v1.4.3 (2026-02-10)

- fix: fix semantic-release config and add comprehensive plugin documentation (#173)


## v1.4.2 (2026-02-03)

- fix: simplify feature flags (#172)


## v1.4.1 (2026-02-01)

- fix: lower privileges for pipeline (#171)


## v1.4.0 (2026-02-01)

- feat: implement feature flags system with config refactor (#169)


## v1.3.1 (2026-01-29)

- fix: can use domains which are not specified in config (#170)


## v1.3.0 (2026-01-23)

- feat: added attachments support in notifiers (#164)


## v1.2.2 (2026-01-18)

- fix: styling fixes for left panel (#158)


## v1.2.1 (2026-01-15)

- fix: page allows back lack of language - it has default (#157)


## v1.2.0 (2026-01-12)

- feat: better returns and linting (#156)


## v1.1.0 (2026-01-05)

- feat: add plugin translation support with security and stability fixes (#135)


## v1.0.1 (2025-10-16)

- fix: Add OpenTelemetry logging instrumentation for trace context propagation (#127)


## v1.0.0 (2025-10-13)

- feat: introduce telemetry support (#120)
- docs: add documentation (#118)


## v0.4.3 (2025-10-02)

### Bug Fixes

- Upload to repository added ([#105](https://github.com/platzky/platzky/pull/105),
  [`43c4c7c`](https://github.com/platzky/platzky/commit/43c4c7c14997aef8fe7c45761706e4a3c8821f26))


## v0.4.2 (2025-10-02)

### Bug Fixes

- Fix semantic release ([#104](https://github.com/platzky/platzky/pull/104),
  [`ef9326d`](https://github.com/platzky/platzky/commit/ef9326d9d3303c45c51e2d64d18af28c479cb77d))


## v0.4.1 (2025-09-30)

### Bug Fixes

- Fixed publishing in pipeline ([#101](https://github.com/platzky/platzky/pull/101),
  [`9adce07`](https://github.com/platzky/platzky/commit/9adce079fe056c2f93678991e2fba8a141c787e3))


## v0.4.0 (2025-09-30)

### Bug Fixes

- Clean up naming ([#96](https://github.com/platzky/platzky/pull/96),
  [`c649f87`](https://github.com/platzky/platzky/commit/c649f87a403095405a1a83e5d6506716858fe973))

- Fix semantic release ([#99](https://github.com/platzky/platzky/pull/99),
  [`ae9a76c`](https://github.com/platzky/platzky/commit/ae9a76c54e815780cb71865ba73ef8e68c2d6a9a))

- Release test fix ([#100](https://github.com/platzky/platzky/pull/100),
  [`7a93082`](https://github.com/platzky/platzky/commit/7a93082b28f28296e7ae91e5b7b5aa8b5cc3d450))

### Chores

- Added semantic-release version to pipeline ([#97](https://github.com/platzky/platzky/pull/97),
  [`6606434`](https://github.com/platzky/platzky/commit/6606434d89b6901bcdc672a95fb95f74f7e87d1f))

- Changelog fix ([#98](https://github.com/platzky/platzky/pull/98),
  [`22339f8`](https://github.com/platzky/platzky/commit/22339f8c014e4e4f79a7be20c6dce19e3db4aeb6))

- Fix semantic release ([#94](https://github.com/platzky/platzky/pull/94),
  [`a27df36`](https://github.com/platzky/platzky/commit/a27df3637bc24bff0fcc7001e8a7a2b34d94f8b2))

* chore: fix semantic release

* fix pipeline

- Fix semantic release ([#95](https://github.com/platzky/platzky/pull/95),
  [`83c349a`](https://github.com/platzky/platzky/commit/83c349a65125ea8c92b8f0b08505135d9941c85f))

* chore: fix semantic release

* removed pypi token

### Features

- Introducing mongodb as one of db ([#93](https://github.com/platzky/platzky/pull/93),
  [`f6ad94a`](https://github.com/platzky/platzky/commit/f6ad94a0e316e4dce99cf5e8d31904f3d667fee8))


## v0.3.6 (2025-06-05)

- fix: fixed issue with not displaying plugins in the admin panel


## v0.3.5 (2025-06-01)

- fix: fake login and whole engine now uses csrf


## v0.3.4 (2025-06-01)


## v0.3.3 (2025-05-26)

- feat: added support for using github as database


## v0.3.2 (2025-05-18)

- feat: Fake login functionality introduced


## v0.3.1 (2025-03-16)

- feat: Added a new plugin loading mechanism to manage and process plugins effectively.


## v0.3.0 (2025-02-19)

- removed deprecated plugins import (now they are only loaded if they are installed)


## v0.2.18 (2025-02-06)

- fix: UTF emails working


## v0.2.17 (2025-02-05)

- fix: fixed dynamic css


## v0.2.16 (2025-02-05)

- feature: added app_description for applications


## v0.2.15 (2025-02-02)

- fix: plugins loading


## v0.2.14 (2025-02-02)

- fix: plugins loading


## v0.2.13 (2024-11-30)

- feat: added handling multiple languages in menu


## v0.2.12 (2024-11-20)

- feat: added feature flags


## v0.2.11 (2024-10-29)

- feat: add alt text for language icons
- fix: insufficient sidebar responsiveness
- feat: add alt text for link in logo


## v0.2.10 (2024-10-13)

### Bug Fixes

- Adds some zIndex to ensure that left panel is always on top
  ([#12](https://github.com/platzky/platzky/pull/12),
  [`99dc24f`](https://github.com/platzky/platzky/commit/99dc24f50745b299a00de5fd1ddcf152b584049f))

- Broken iframe attr ([#11](https://github.com/platzky/platzky/pull/11),
  [`20087da`](https://github.com/platzky/platzky/commit/20087dab2aeb454cc3e832c6e851ae84daddf410))

### Features

- Add proper html lang ([#9](https://github.com/platzky/platzky/pull/9),
  [`da5ecfc`](https://github.com/platzky/platzky/commit/da5ecfc763977b74979eed459bf812070e4c97b2))

closes Problematy/goodmap#90

- Change color of language change selection ([#5](https://github.com/platzky/platzky/pull/5),
  [`005b142`](https://github.com/platzky/platzky/commit/005b142dcee62414a43bea30a67a5712bec7a55e))

closes Problematy/goodmap#131

- Change size of title bar in the subpages ([#6](https://github.com/platzky/platzky/pull/6),
  [`60dffe9`](https://github.com/platzky/platzky/commit/60dffe918e63b3926b6a1740cd970e0e8afe390e))

Closes #132

- Reduce top bar height ([#8](https://github.com/platzky/platzky/pull/8),
  [`0f8aa87`](https://github.com/platzky/platzky/commit/0f8aa87addefc10edf838716641afec5a535d47a))

closes Problematy/goodmap#125


## v0.2.9 (2024-09-27)

- fix: sitemap gives proper links for blog posts


## v0.2.8 (2024-09-26)

### Bug Fixes

- Sitemap no longer crashes ([#40](https://github.com/platzky/platzky/pull/40),
  [`90fc436`](https://github.com/platzky/platzky/commit/90fc436018c570fff65acb6e2afb3199ed639bed))


## v0.2.7 (2024-09-26)

- fix: add alt text for logo
- fix: removed leaflet dependency


## v0.2.6 (2024-08-24)

- feature: add support for favicons


## v0.2.5 (2024-07-25)

- fix: plugin loader now loads plugins when db is set to graphql


## v0.2.4 (2024-07-23)

- fix: set default page title as app name
- fix: added missing google tag manager plugin
- fix: fixed hreflang and html lang


## v0.2.3 (2024-07-17)

- fix: added necessary interface for platzky


## v0.2.2 (2024-05-30)

- fix: fixed standardization of comments in gql db


## v0.2.1 (2024-05-28)

- fix: moved pydantic to requirements
- fix: removed questions from core logic


## v0.2.0 (2024-05-27)

- made config file stricter
- created DB dynamic loading
- introduced models for webpage
- improved better plugin loader
