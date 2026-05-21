# Changelog

## [1.6.0](https://github.com/mtopcu1/loco-llm/compare/v1.5.0...v1.6.0) (2026-05-21)


### Features

* **dashboard:** instance chat test, UX fixes, and workflow hardening ([39b78db](https://github.com/mtopcu1/loco-llm/commit/39b78db6dd1c24093690a8cee6e32fbda1fd163c))
* **dashboard:** instance chat test, UX fixes, and workflow hardening ([91cc3b8](https://github.com/mtopcu1/loco-llm/commit/91cc3b8f7c6a629b8070789501739cf433fbd411))
* **install:** add --commit ref flag and fix hermes path resolution ([511099d](https://github.com/mtopcu1/loco-llm/commit/511099db726bbcab6e5e02a9beac99c8d8a1dffb))
* **update:** refresh current ref by default and add --stable ([c327079](https://github.com/mtopcu1/loco-llm/commit/c327079cfdde48eee2223258c097ff64652f8559))


### Bug Fixes

* **ci:** align workflow tests with pytest job rename ([65a8e01](https://github.com/mtopcu1/loco-llm/commit/65a8e01030ae258e72855ec783aee1043ecf1eb1))
* **ci:** avoid hanging job stream on terminal jobs ([1254b82](https://github.com/mtopcu1/loco-llm/commit/1254b820fea86989d063026c80059e6b6dbd9bfa))
* **ci:** parallelize pytest and finish under runner cutoff ([44b0116](https://github.com/mtopcu1/loco-llm/commit/44b0116c993c4f96c17c2f4a7caf73ae01985e1f))
* **ci:** regenerate openapi client and update JobsTray test ([c4617e5](https://github.com/mtopcu1/loco-llm/commit/c4617e5967d494b7edf98809bdc0efb570c62ada))
* **ci:** run pytest serial on runner to avoid xdist cancel ([1b74a74](https://github.com/mtopcu1/loco-llm/commit/1b74a745ef65dc4341c4372603fd6f4e60587005))
* **ci:** shard pytest into core and webapi jobs ([a053320](https://github.com/mtopcu1/loco-llm/commit/a0533203e742019a67350ebf4036aca07d1c047f))
* **dashboard:** install full dashboard extra including prometheus-client ([6e64109](https://github.com/mtopcu1/loco-llm/commit/6e641098db40f6bf64c2e44e3165fb2baabcbee0))
* **jobs:** isolate subprocess groups so cancel does not kill pytest ([1c3846e](https://github.com/mtopcu1/loco-llm/commit/1c3846e1c8bd508590b1cb12bc8ca054238ccb0b))
* **tests:** shorten job cancel subprocess sleep for CI ([52af429](https://github.com/mtopcu1/loco-llm/commit/52af4291c78313a81f9b7d36c03bbe952c31c2ec))

## [1.5.0](https://github.com/mtopcu1/loco-llm/compare/v1.4.0...v1.5.0) (2026-05-20)


### Features

* **setup:** chain-only onboarding with improved doctor hints ([beb7217](https://github.com/mtopcu1/loco-llm/commit/beb721733d93accd679549ccd840d753f1824a74))
* **setup:** chain-only onboarding, docs refresh, and No/Yes buttons ([8ec40aa](https://github.com/mtopcu1/loco-llm/commit/8ec40aa7764b2a3c58b659e1a9826f78641ab8fb))
* **wizards:** replace Y/n prompts with No/Yes buttons ([0e842b4](https://github.com/mtopcu1/loco-llm/commit/0e842b4294c1773ff10508813adce5c3b2673d91))


### Bug Fixes

* **advisor:** exit non-zero when no recommendations apply ([5517242](https://github.com/mtopcu1/loco-llm/commit/5517242dd757fe3a02018ebe0258433442a89dba))


### Documentation

* streamline README; add docs/CLI.md and docs/GLOSSARY.md; move discipline to CONTRIBUTING.md; refresh INSTALLATION, DASHBOARD, and index. ([beb7217](https://github.com/mtopcu1/loco-llm/commit/beb721733d93accd679549ccd840d753f1824a74))

## [1.4.0](https://github.com/mtopcu1/loco-llm/compare/v1.3.0...v1.4.0) (2026-05-20)


### Features

* **install:** adopt hermes ~/.loco layout and loco CLI ([9564abf](https://github.com/mtopcu1/loco-llm/commit/9564abf2353c436d90b074b42f11ad2ec4af5872))
* **install:** hermes ~/.loco layout, loco CLI, and setup UX ([8a0519a](https://github.com/mtopcu1/loco-llm/commit/8a0519a31d16ed72661433c60998faef971360aa))


### Bug Fixes

* **cli:** setup and update ux from interactive audit ([54076c9](https://github.com/mtopcu1/loco-llm/commit/54076c91394e7427c218ccc74e2338fca7ba84e8))
* repair config discovery and ci test fixtures for hermes layout ([101ac01](https://github.com/mtopcu1/loco-llm/commit/101ac01fa2fd4f3310d44c69ead0052adb21a059))
* **tests:** align integration tests with hermes data/configs layout ([4682048](https://github.com/mtopcu1/loco-llm/commit/4682048a5bd07cb9e1ea0fe5cb8670672b0e2dc5))

## [1.3.0](https://github.com/mtopcu1/loco-llm/compare/v1.2.0...v1.3.0) (2026-05-20)


### Features

* **dashboard:** Config detail Params tab uses ParamGrid (replaces JSON dump) ([9c7450e](https://github.com/mtopcu1/loco-llm/commit/9c7450ea37360868612469b0644f65ae684bc9d5))
* **dashboard:** live metrics pipeline (Plan 4/5) ([#22](https://github.com/mtopcu1/loco-llm/issues/22)) ([698a41b](https://github.com/mtopcu1/loco-llm/commit/698a41bcbc39392b04827a5383e03edc71928b50))
* **dashboard:** new-config wizard shell (5-step state machine) ([78b1897](https://github.com/mtopcu1/loco-llm/commit/78b1897218b3769cf0c3b35536e1b0c74de10734))
* **dashboard:** NewConfigPage delegates to the 5-step wizard ([d732f88](https://github.com/mtopcu1/loco-llm/commit/d732f88334d769a287c9bf8f4764ff57fea8c954))
* **dashboard:** param grid and new-config wizard (Plan 3/5) ([f256115](https://github.com/mtopcu1/loco-llm/commit/f2561152b347b01c46b3f7bcb5e1b314271cb46c))
* **dashboard:** ParamGrid (the flagship form) — filter, suggestions, bulk actions, dirty tracking ([c5cba32](https://github.com/mtopcu1/loco-llm/commit/c5cba3273a860fcc9503c7c1bc1188f269107824))
* **dashboard:** ParamRow with enabled/key/value/suggestion/lock/description columns ([cb7ff18](https://github.com/mtopcu1/loco-llm/commit/cb7ff188755a9ac85e0c27727d8a30c9f75bd2fa))
* **dashboard:** ParamValueInput dispatches on param type (string/int/bool/path/enum) ([be747a3](https://github.com/mtopcu1/loco-llm/commit/be747a3b446e8d67ee2b8a16dedf4142da1b6dd9))
* **dashboard:** pure-functional ParamCell helpers (filter/suggestion/reset/diff) ([5f2e6e6](https://github.com/mtopcu1/loco-llm/commit/5f2e6e6cfe206bff969a46ab6a4b8b2b22d03713))
* **dashboard:** security hardening and update notifier (Plan 5/5) ([#23](https://github.com/mtopcu1/loco-llm/issues/23)) ([6c0479d](https://github.com/mtopcu1/loco-llm/commit/6c0479de7c83b70b5b8c3fc4a54c8a6c01a68383))
* **dashboard:** useParamGridState reducer hook (toggle/set/filter/suggestions/reset) ([a920517](https://github.com/mtopcu1/loco-llm/commit/a920517c88207ffff4d0c834601f448b1ba773a6))
* **dashboard:** wizard step 1 — pick runtime ([0c0886f](https://github.com/mtopcu1/loco-llm/commit/0c0886f1e55f7e6501b642f7f57dcf35a931bc20))
* **dashboard:** wizard step 2 — pick model (optional, filtered by runtime format) ([95458d9](https://github.com/mtopcu1/loco-llm/commit/95458d99df3e62788f4eaf1bbe641d0d4cb3d4ad))
* **dashboard:** wizard step 3 — params via ParamGrid with advisor ([f78a323](https://github.com/mtopcu1/loco-llm/commit/f78a323a3602dbdb55ccec9a2f6d606f16d53cec))
* **dashboard:** wizard step 4 — review with id uniqueness check ([9e9c80f](https://github.com/mtopcu1/loco-llm/commit/9e9c80fae1390635e45a1b3191417586e245e196))
* **dashboard:** wizard step 5 — save + redirect on success ([5aa9f5c](https://github.com/mtopcu1/loco-llm/commit/5aa9f5ca85e5853a47e0ca9ba5a4fc7dec40621e))


### Bug Fixes

* **dashboard:** export ParamGridHandle via forwardRef for wizard step 3 ([5d30f7c](https://github.com/mtopcu1/loco-llm/commit/5d30f7ce70632123858b3b979eac8fe24f62c9ff))
* **dashboard:** seed wizard params on step 3 for reliable navigation ([3e7b33c](https://github.com/mtopcu1/loco-llm/commit/3e7b33ccf51e5df8e5b5e52d54cfff271f9b4575))

## [1.2.0](https://github.com/mtopcu1/loco-llm/compare/v1.1.0...v1.2.0) (2026-05-20)


### Features

* **dashboard:** `llm dashboard serve` (background + foreground, readiness wait, browser auto-open) ([5532710](https://github.com/mtopcu1/loco-llm/commit/5532710e4b00ae8d3a2ef4366c4f1f44f0c4d27d))
* **dashboard:** app shell (Layout/Header/Sidebar), status pill, error card, useSSE hook ([4d1a20c](https://github.com/mtopcu1/loco-llm/commit/4d1a20cfa2ea63deb9ac03f13aaf618cc86b743d))
* **dashboard:** centralized error→toast mapping by ErrorCode ([2aa73e9](https://github.com/mtopcu1/loco-llm/commit/2aa73e9a53737a1e48ab4849d7e191add1e78007))
* **dashboard:** Configs list + detail (Overview/Params/Validate/Raw YAML, read-only) ([664e143](https://github.com/mtopcu1/loco-llm/commit/664e14308bc96d1c773631d5297248cc9a4cbb38))
* **dashboard:** core install lifecycle helpers (dist_hash, .installed, server-pid) ([3365e33](https://github.com/mtopcu1/loco-llm/commit/3365e3377d3bda1a4ace66ecd3736934c37aa858))
* **dashboard:** Disk page (data root summary + per-model usage) ([81dee0b](https://github.com/mtopcu1/loco-llm/commit/81dee0b57d982e0eb191f8641975de7ce4828924))
* **dashboard:** Doctor page with per-scope check results ([f77c3c4](https://github.com/mtopcu1/loco-llm/commit/f77c3c4799d24117289f6f5caff487b323b869b7))
* **dashboard:** editable Settings form built from KEY_REGISTRY ([a8b3c0b](https://github.com/mtopcu1/loco-llm/commit/a8b3c0b37c415e4fc5a83e18480e667bede7c9dd))
* **dashboard:** enable model pull/add/uninstall with form validation ([12c3201](https://github.com/mtopcu1/loco-llm/commit/12c3201d92a865755003caa303b28109132c3772))
* **dashboard:** enable runtime install/rebuild/uninstall mutations with error toasts ([07c3bad](https://github.com/mtopcu1/loco-llm/commit/07c3badd45b8c2e02b02d8043bba6fd3fa295abc))
* **dashboard:** History page with filters and live SSE updates ([031bd07](https://github.com/mtopcu1/loco-llm/commit/031bd07c4ddb53ccb726f7cddbfa69e56c7b4fc3))
* **dashboard:** implement `llm dashboard install` (python deps + npm build + .installed) ([8d4ca41](https://github.com/mtopcu1/loco-llm/commit/8d4ca4192ff11f3aaf9d2ada4b7b1cd9002878bb))
* **dashboard:** implement `llm dashboard stop` and `uninstall [--purge]` ([2b6f2d9](https://github.com/mtopcu1/loco-llm/commit/2b6f2d97234ca9f69594f392bdbba74deaf8f5a9))
* **dashboard:** Instance page with live log streaming (read-only) ([134781e](https://github.com/mtopcu1/loco-llm/commit/134781e64170099a251da68dab81f5d8633d125c))
* **dashboard:** instance start/stop/switch controls ([53b8b1c](https://github.com/mtopcu1/loco-llm/commit/53b8b1c0d798646af12b2eb2224f40e14cdb270f))
* **dashboard:** Jobs tray in sidebar + JobDetailSheet with streaming log ([673c474](https://github.com/mtopcu1/loco-llm/commit/673c474b7447384712883fa04af5516be6a3d30c))
* **dashboard:** Models list + detail pages (read-only) ([d95ea80](https://github.com/mtopcu1/loco-llm/commit/d95ea80208d4a350ba091ac60a9360b1282a43c4))
* **dashboard:** mutations and jobs system (Plan 2/5) ([f80aa77](https://github.com/mtopcu1/loco-llm/commit/f80aa77ba5baa320a6b79617fc4ea5693230f23c))
* **dashboard:** Overview page (read-only) + Vitest+msw test infra ([ae09c1d](https://github.com/mtopcu1/loco-llm/commit/ae09c1d2ae25e04f743c01a31f1e1d0372a361cf))
* **dashboard:** raw config form for create/edit + delete (param grid arrives in Plan 3) ([0bc5fdf](https://github.com/mtopcu1/loco-llm/commit/0bc5fdfac875ce924a53a6e52d1c2d898560dda5))
* **dashboard:** Runtimes list + detail pages (read-only) ([9a208db](https://github.com/mtopcu1/loco-llm/commit/9a208dba89e79480afbcded5fc072b7dbb7f41f5))
* **dashboard:** scaffold Vite + React 19 + TS + Tailwind v4 + shadcn/ui ([d76cd00](https://github.com/mtopcu1/loco-llm/commit/d76cd00a96d7069c3fb4e71681b5084da779d3f3))
* **dashboard:** Settings page (read-only stored + resolved view) ([c57d424](https://github.com/mtopcu1/loco-llm/commit/c57d424e5711d0b640a1184b179c36d8c00de608))
* **dashboard:** typed API client generated from OpenAPI schema ([6522037](https://github.com/mtopcu1/loco-llm/commit/6522037d2f90fc747748005caba00644490f43e9))
* **dashboard:** useJobs/useJob/useStartJob hooks with SSE-into-Query integration ([81e4938](https://github.com/mtopcu1/loco-llm/commit/81e49382eab5a4ff38039b094da7781dca9d463a))
* **dashboard:** web dashboard MVP (Plan 1/5) ([7877253](https://github.com/mtopcu1/loco-llm/commit/787725314db17042ee6bc563b6b531541db37846))
* **dashboard:** wire llm dashboard subcommand group with status stub ([e36111a](https://github.com/mtopcu1/loco-llm/commit/e36111a0ec3995466482fa3071a457c51e1bafb7))
* **dashboard:** wire TanStack Router/Query, Zustand store, sonner toaster ([31ed8ee](https://github.com/mtopcu1/loco-llm/commit/31ed8ee4b60942a29108650580159d725870c899))
* **disk:** per-model disk usage and data-root capacity scan ([1292315](https://github.com/mtopcu1/loco-llm/commit/129231509b9809d522d2629d6933ee6c26dd1d6e))
* **doctor:** add `dashboard` scope (node/npm, install record, dist integrity, server pid) ([2af345a](https://github.com/mtopcu1/loco-llm/commit/2af345acd2d54a41f7b5353678f396bea64ef116))
* **jobs:** in-memory job registry with per-job log file and SSE fan-out ([8e387f0](https://github.com/mtopcu1/loco-llm/commit/8e387f0ca133679b90814a902950e69614fdc668))
* **setup:** offer optional dashboard install at end of `llm setup` chain ([d6ff269](https://github.com/mtopcu1/loco-llm/commit/d6ff269de25f953a0481c0235e9bb4c3e9b8d9e9))
* **update:** rebuild dashboard after `llm update` when version drifts (best-effort) ([2822faf](https://github.com/mtopcu1/loco-llm/commit/2822faf27f4aa1e51c256f599e7d4f7bc42a870a))
* **webapi:** /api/jobs list/get/stream/cancel routes ([6ace4cf](https://github.com/mtopcu1/loco-llm/commit/6ace4cf449938d447f673fc0ebb23196f707c74b))
* **webapi:** extend ErrorCode enum for mutation paths ([6019356](https://github.com/mtopcu1/loco-llm/commit/6019356d568d61a776c83b5d9ce6c244eb229ba0))
* **webapi:** FastAPI factory + health + version routes + middleware wiring ([6c8d13a](https://github.com/mtopcu1/loco-llm/commit/6c8d13a0205518841cb9dcc22778055562abcd37))
* **webapi:** GET /api/disk ([81182ee](https://github.com/mtopcu1/loco-llm/commit/81182ee3e22da2ac08073136ddaa91a7e2c38347))
* **webapi:** GET /api/doctor with all scopes ([9cb234f](https://github.com/mtopcu1/loco-llm/commit/9cb234fe37b5521778b8fe5c87c30841d152de3b))
* **webapi:** GET /api/history + SSE history stream ([85c64e5](https://github.com/mtopcu1/loco-llm/commit/85c64e5ed5bc4332d43ae727bfe9c8bb85768d6f))
* **webapi:** GET /api/instance + SSE state + SSE logs (read-only) ([216686c](https://github.com/mtopcu1/loco-llm/commit/216686cabec25ca3aaea067283a9fc8be4d117db))
* **webapi:** GET /api/models and /api/models/{id} ([4bd96e3](https://github.com/mtopcu1/loco-llm/commit/4bd96e37e2b7ed5404c2545e9c36c5c8b6dccb1b))
* **webapi:** GET /api/overview aggregate ([098a0c9](https://github.com/mtopcu1/loco-llm/commit/098a0c93fd7ee353435bcd7b1f37e2ef3383cced))
* **webapi:** GET /api/runtimes and /api/runtimes/{id} ([49a6d2e](https://github.com/mtopcu1/loco-llm/commit/49a6d2e26a0ef9e3a7f40f30a11e63a0c91888de))
* **webapi:** GET /api/settings (stored + resolved + registry) ([16aceb9](https://github.com/mtopcu1/loco-llm/commit/16aceb934828a4dfe9d68919fe9733873f6d3dbe))
* **webapi:** GET configs (list, detail, params, validate) ([d64b838](https://github.com/mtopcu1/loco-llm/commit/d64b83850b9f5a7fdbf1bf2ba19aa16f11c9e8f2))
* **webapi:** host-header allow-list, security headers, request-id middleware ([a4db6fb](https://github.com/mtopcu1/loco-llm/commit/a4db6fb0e60585f5ef78f61d27d02c2086689a1c))
* **webapi:** in-process EventHub for SSE fan-out ([a22aec6](https://github.com/mtopcu1/loco-llm/commit/a22aec663d6b5d401bf38c5b689418d17a2d91cc))
* **webapi:** OpenAPI exporter + regen-api-client.sh with --check mode ([2549c76](https://github.com/mtopcu1/loco-llm/commit/2549c7606a5613630a26f57626ef19ba9e25d932))
* **webapi:** POST /api/instance/start|stop|switch (async start, sync stop, fg-mode refusals) ([1d8ce0b](https://github.com/mtopcu1/loco-llm/commit/1d8ce0b9aa20da83be3aaeb96ad546f7416968b5))
* **webapi:** POST /api/models/pull|add + DELETE (sync) ([ee58724](https://github.com/mtopcu1/loco-llm/commit/ee5872471a4e89fde589cfa95158509d9e79de6c))
* **webapi:** POST /api/runtimes/{id}/install|rebuild + DELETE (sync uninstall) ([4a3c920](https://github.com/mtopcu1/loco-llm/commit/4a3c920f42adbb49062b7c42c864ee94c5c51120))
* **webapi:** POST/PUT/DELETE /api/configs with validation + in-use refusal ([d4cd760](https://github.com/mtopcu1/loco-llm/commit/d4cd760affd151a2d5af18d4a69bdfbe998872d0))
* **webapi:** PUT /api/settings/{key} with validation against KEY_REGISTRY ([599eed9](https://github.com/mtopcu1/loco-llm/commit/599eed94016a01d2614529d1d3fe74d4bbc86dab))
* **webapi:** SPA serving with index.html fallback and not-built JSON 503 ([786d58c](https://github.com/mtopcu1/loco-llm/commit/786d58c83e509dddf27423d97346ed8cec35277b))
* **webapi:** uniform ApiError response shape with ErrorCode enum ([34cad46](https://github.com/mtopcu1/loco-llm/commit/34cad46033443e7f2fdb15950ab9cddf62237dff))


### Bug Fixes

* **ci:** install dashboard extras in main pytest job and drop uv.lock cache ([e6d5967](https://github.com/mtopcu1/loco-llm/commit/e6d59675058c4c1868855a84efc26e5347a6c596))
* **ci:** regen-api-client use absolute temp paths for openapi-typescript ([1ed0a67](https://github.com/mtopcu1/loco-llm/commit/1ed0a675df154c55193effa8d136e87aaf7c28f9))
* **ci:** use uv run python in regen-api-client.sh for venv-aware OpenAPI export ([8cf5bb1](https://github.com/mtopcu1/loco-llm/commit/8cf5bb1fed73143ed4b63782f92ed66d213583de))


### Documentation

* **dashboard:** user-facing install/serve guide + frontend dev README ([123e331](https://github.com/mtopcu1/loco-llm/commit/123e3310998b4476c6b7f487bb7999c78888c994))
* **plan:** web dashboard hardening and polish (Plan 5/5) ([10fa1b6](https://github.com/mtopcu1/loco-llm/commit/10fa1b6f43bbde38e4b59da83eac1b7bd37f2ca6))
* **plan:** web dashboard live metrics (Plan 4/5) ([53cdb43](https://github.com/mtopcu1/loco-llm/commit/53cdb430ffc81bd63739addc92fc14fae7fa548c))
* **plan:** web dashboard mutations and jobs (Plan 2/5) ([fc38f97](https://github.com/mtopcu1/loco-llm/commit/fc38f9751aa43eab5c2e829e1836b51309d46ea1))
* **plan:** web dashboard MVP (Plan 1/5) implementation plan ([603f1fa](https://github.com/mtopcu1/loco-llm/commit/603f1fa5daa557694f148d8665f02690862102ca))
* **plan:** web dashboard param grid and new-config wizard (Plan 3/5) ([cc093e6](https://github.com/mtopcu1/loco-llm/commit/cc093e6f6616d9c380fc2b26947f5d6ac7db34ec))
* **spec:** web dashboard design ([d2cfa6f](https://github.com/mtopcu1/loco-llm/commit/d2cfa6fc3b3f014a303f486f70721bdf81aa4968))

## [1.1.0](https://github.com/mtopcu1/loco-llm/compare/v1.0.1...v1.1.0) (2026-05-19)


### Features

* **config:** save opt-in serve params only ([87892a1](https://github.com/mtopcu1/loco-llm/commit/87892a1f0b3b62e470da9af12eebdae45ee42eca))
* **param-grid:** add Ctrl+F live filter in config setup ([be4b109](https://github.com/mtopcu1/loco-llm/commit/be4b10942b34e6237923fbdc87a360732db82410))
* **param-grid:** add enabled and locked flags to ParamCell ([8819025](https://github.com/mtopcu1/loco-llm/commit/88190255d2ee920bbd414a2b1df9d9301ac06af6))
* **param-grid:** filter enabled param values on save ([9cbf6b2](https://github.com/mtopcu1/loco-llm/commit/9cbf6b2e1b3b87a9801cef57299ce28c388b4298))
* **param-grid:** initialize optional params disabled without catalog defaults ([6275090](https://github.com/mtopcu1/loco-llm/commit/6275090fe790c153d0db3fe59230ffaa9815ea8b))
* **param-grid:** plain fallback opt-in param semantics ([1645d35](https://github.com/mtopcu1/loco-llm/commit/1645d354d29456e2b7809669761c073931e203e7))
* **param-grid:** space toggles enable; show suggestion column ([d68a6e1](https://github.com/mtopcu1/loco-llm/commit/d68a6e11cbf0aeb3ec054c230fc005bb1fbe1a40))
* **runtime:** build install uses opt-in param grid ([f3b0722](https://github.com/mtopcu1/loco-llm/commit/f3b0722f5d7dc1ee97f0c4f3af7dacf21c89bc80))


### Bug Fixes

* **doctor:** use empty build params when uninstalled ([5398f7e](https://github.com/mtopcu1/loco-llm/commit/5398f7e93fd4e3915e6755e9d8e049dea8e9d302))
* **setup:** treat empty HF URL prompt as skip ([48637b3](https://github.com/mtopcu1/loco-llm/commit/48637b34e79653eeb7066405ec2a5f6038fe4670))
* **tests:** enable build param in TUI runtime install test ([c6e405d](https://github.com/mtopcu1/loco-llm/commit/c6e405d7399ebeeb2a33ff8efa616bc08ae86848))


### Documentation

* document opt-in serve and build params ([22a76b7](https://github.com/mtopcu1/loco-llm/commit/22a76b79baa8011f780a7b02d26fa036beb5c445))
* **plan:** serve and build param opt-in implementation plan ([af0f2af](https://github.com/mtopcu1/loco-llm/commit/af0f2afe4dd065876b7e24399fc75adab60bedb8))
* **spec:** serve and build param opt-in design ([eaf4f2d](https://github.com/mtopcu1/loco-llm/commit/eaf4f2d773d1a0ec0257ee35e42ce88a4d5fd13d))

## [1.0.1](https://github.com/mtopcu1/loco-llm/compare/v1.0.0...v1.0.1) (2026-05-19)


### Bug Fixes

* **update:** pass managed venv python to uv pip during dep sync ([f25cea4](https://github.com/mtopcu1/loco-llm/commit/f25cea4caeb5e5a709a9fb69af23aaec214f904c))
* **update:** pass managed venv python to uv pip during dep sync ([de9f64d](https://github.com/mtopcu1/loco-llm/commit/de9f64dec33b71aff829137d35d5c518948aa446))

## [1.0.0](https://github.com/mtopcu1/loco-llm/compare/v0.3.2...v1.0.0) (2026-05-19)


### ⚠ BREAKING CHANGES

* llm update no longer reads from PyPI or installs a scaffold tarball.

### Features

* **cli:** warn when running off a release tag ([4d5ee57](https://github.com/mtopcu1/loco-llm/commit/4d5ee57a8492439b608dd573908f43cb64e0671a))
* **install:** curl-installable git-clone installer with uv editable install ([3d8bd1c](https://github.com/mtopcu1/loco-llm/commit/3d8bd1cc0b0889af7503ced3bed8c52122d952a3))
* rewrite llm update as git-tag-based with re-anchor semantics ([bd361a5](https://github.com/mtopcu1/loco-llm/commit/bd361a54ff2572695c70eb8849417ea452f72bbb))


### Documentation

* document git-clone install and tag-based update flow ([06d4e5f](https://github.com/mtopcu1/loco-llm/commit/06d4e5f9c43326e24fe09819e92f739fdd2cf50c))
* **plan:** git-tag distribution implementation plan ([44a5e42](https://github.com/mtopcu1/loco-llm/commit/44a5e4228ee3cdfae6577ed0e4b1d987c75eecd9))
* **spec:** git-tag distribution design supersedes PyPI model ([481089b](https://github.com/mtopcu1/loco-llm/commit/481089b688c17f26b5849880259adb312125ee82))

## [0.3.2](https://github.com/mtopcu1/loco-llm/compare/v0.3.1...v0.3.2) (2026-05-19)


### Bug Fixes

* **ci:** inline version sync check in release-pr-check ([59ab3c8](https://github.com/mtopcu1/loco-llm/commit/59ab3c83d7552ceb4de3ef20a202af58ca46aaaa))
* **ci:** inline version sync check in release-pr-check ([4ff2a88](https://github.com/mtopcu1/loco-llm/commit/4ff2a884243572595808f7a04516bc491fe6e35f))

## [0.3.1](https://github.com/mtopcu1/loco-llm/compare/v0.3.0...v0.3.1) (2026-05-19)


### Bug Fixes

* **tests:** drop static version assertion and sync manifest check ([#5](https://github.com/mtopcu1/loco-llm/issues/5)) ([136745d](https://github.com/mtopcu1/loco-llm/commit/136745d12f88aa789ee0b1c56935b0f0c085aa17))

## [0.3.0](https://github.com/mtopcu1/local-llm-scaffold/compare/v0.2.0...v0.3.0) (2026-05-19)


### Features

* **0.2:** param grid wizard, llamacpp/vllm runtime params ([70a0c1f](https://github.com/mtopcu1/local-llm-scaffold/commit/70a0c1fb307e4e94c62f98f15f62760a595c50cb))
* **0.2:** wizards, advisor, and setup chain ([71f974d](https://github.com/mtopcu1/local-llm-scaffold/commit/71f974d10e4121b00bfda1c85f34f59902417260))
* add Python package skeleton and CLI smoke test ([a7b4b4c](https://github.com/mtopcu1/local-llm-scaffold/commit/a7b4b4ca76fe0c613963c98d090070ad275be35d))
* **assets:** layered scaffold and user asset discovery ([9a2a20c](https://github.com/mtopcu1/local-llm-scaffold/commit/9a2a20c465eedf3e6092763ae3d93c96f73af647))
* **assets:** wire commands to scaffold and user layers ([7e84f9d](https://github.com/mtopcu1/local-llm-scaffold/commit/7e84f9d66bef78d5d26f776a533b5b8ed6ff37cb))
* **cli:** remove top-level build/pull ([a7c19ea](https://github.com/mtopcu1/local-llm-scaffold/commit/a7c19eaf7900d5bb9e4b4c83e003791ca6a8658f))
* **cli:** wire lifecycle commands, stub packages, and docs ([73b9662](https://github.com/mtopcu1/local-llm-scaffold/commit/73b9662643618d796289486c65749e79cb7b8630))
* complete LocalLLM Milestone 1 (CLI foundation) ([7f41997](https://github.com/mtopcu1/local-llm-scaffold/commit/7f4199745b14c43c1ec92bc6acd04c6d02a69935))
* **config-resolve:** expand ${model_path} from registry ([e693861](https://github.com/mtopcu1/local-llm-scaffold/commit/e6938613992cd7b34a99a6f2e91e5ec11e59cb3d))
* **config-resolve:** strict errors when ${model_path} cant resolve ([fb991a9](https://github.com/mtopcu1/local-llm-scaffold/commit/fb991a97b25ac7a887447489b7f11c725f8ff061))
* **core:** add lightweight version parser and comparator ([070a100](https://github.com/mtopcu1/local-llm-scaffold/commit/070a1009701d13726e2d09822e7f4cdb8f1351c6))
* **core:** add Paths loader for paths.yaml ([c7b8ead](https://github.com/mtopcu1/local-llm-scaffold/commit/c7b8ead9998d980bdcd7ab1d0dfa5d8e71bd78ed))
* distributed install, llm update, and layered assets (v0.3.0) ([e5a45d5](https://github.com/mtopcu1/local-llm-scaffold/commit/e5a45d5d577bbdc728db07f06f836b0ae00cb54d))
* **doctor:** add runtime requirement helpers ([1b57f75](https://github.com/mtopcu1/local-llm-scaffold/commit/1b57f75a29a9b1e321fa653cd053111915d7a485))
* **doctor:** add scoped CLI checks ([1b27078](https://github.com/mtopcu1/local-llm-scaffold/commit/1b270784f0a693adef6a6530d311723a4f82eff9))
* **doctor:** render grouped requirements ([c866617](https://github.com/mtopcu1/local-llm-scaffold/commit/c866617cf158bd9e132692f4017aec943c8708f4))
* **hf-client:** fetch repo revision metadata ([7cf4dfb](https://github.com/mtopcu1/local-llm-scaffold/commit/7cf4dfbf1d40bb61dbd54c83f32b3581016bf018))
* **hf-url:** parse bare HF repo URLs ([52f90d8](https://github.com/mtopcu1/local-llm-scaffold/commit/52f90d8930a4c0c5b9d634776b41214474839141))
* **hf-url:** parse blob/ and resolve/ file URLs ([1f68a63](https://github.com/mtopcu1/local-llm-scaffold/commit/1f68a638e8f7f52bbacef0781d8736584b4c32f0))
* **hf-url:** parse tree/&lt;rev&gt; URLs ([ad91cc8](https://github.com/mtopcu1/local-llm-scaffold/commit/ad91cc857da0394d317fae55720859a2693307e2))
* **install-record:** file_sha256 and stable schema_hash helpers ([5e6d7d0](https://github.com/mtopcu1/local-llm-scaffold/commit/5e6d7d09538c8832d7874e149ad8a38bc5f836a9))
* **install-record:** InstallRecord dataclass + JSON read/write ([ed75515](https://github.com/mtopcu1/local-llm-scaffold/commit/ed755155ff00c960ecd6cea85c7e7058dc4ef21d))
* **install:** add public install, dev install, and v0.2 migration scripts ([f2a1ae7](https://github.com/mtopcu1/local-llm-scaffold/commit/f2a1ae7e5cd69a9ae7b3ab3b1c23c0ef5d6c3b0c))
* **install:** auto-invoke llm setup on first install ([9e1bec3](https://github.com/mtopcu1/local-llm-scaffold/commit/9e1bec3440d9955dd83f047fd684a8ac30a66a7c))
* **lifecycle:** add module skeleton with state paths and record ([b4533a9](https://github.com/mtopcu1/local-llm-scaffold/commit/b4533a9c135499de3d593841e15e931fa1f74ffb))
* **lifecycle:** append_history writes one JSON object per line ([dbaf8e9](https://github.com/mtopcu1/local-llm-scaffold/commit/dbaf8e9a294ce2246bde0ca450e5fef1e0cb89ee))
* **lifecycle:** is_alive(pid) probe with POSIX kill(0) semantics ([a2b0b4d](https://github.com/mtopcu1/local-llm-scaffold/commit/a2b0b4d996eab0b0b1ffc37cac64fee37885b6c3))
* **lifecycle:** read/write/clear running.json with atomic replace ([1af4346](https://github.com/mtopcu1/local-llm-scaffold/commit/1af4346a440eb6065dcc1a23684ccd59383ce87b))
* **lifecycle:** reconcile drops stale fg/bg/systemd records ([16260e9](https://github.com/mtopcu1/local-llm-scaffold/commit/16260e99b2f7374200ab85819bd99699dde873a4))
* **model-cmd:** `add <id> <path>` for local weights with symlink default ([242252a](https://github.com/mtopcu1/local-llm-scaffold/commit/242252abb13ee878a5b333dcc8bdbe6ed17e13fa))
* **model-cmd:** pull &lt;hf-url&gt; resolves, downloads, verifies, registers ([cd97638](https://github.com/mtopcu1/local-llm-scaffold/commit/cd9763889a80ae1fc1855cb02430910c9e9aca38))
* **model-cmd:** uninstall with optional --purge ([0ce78b6](https://github.com/mtopcu1/local-llm-scaffold/commit/0ce78b67952ff5d927a1a9716a3923062ab99b66))
* **model-registry:** atomic load/write of registry.json ([01e866c](https://github.com/mtopcu1/local-llm-scaffold/commit/01e866c1a7e4de829ff998e7a55173f44ecc648d))
* **model-registry:** dataclasses + entry encode/decode ([76baede](https://github.com/mtopcu1/local-llm-scaffold/commit/76baededefb0f6fecb74c3af74f6df986dd6f7ce))
* **model-registry:** get/upsert/remove helpers ([9f1e9dd](https://github.com/mtopcu1/local-llm-scaffold/commit/9f1e9ddf5a589f72e54f3c01143c7b9185f53139))
* **model-resolve:** build_artifact from download directory ([30094ad](https://github.com/mtopcu1/local-llm-scaffold/commit/30094ad038a9329802f6e24fcc0d2735ca84dcca))
* **model-resolve:** derive_model_id from HF URL pieces ([f32e0db](https://github.com/mtopcu1/local-llm-scaffold/commit/f32e0db880165b27fea28a91fa40470a57bea99f))
* **model-resolve:** infer_format with strict ambiguity handling ([b2d08e5](https://github.com/mtopcu1/local-llm-scaffold/commit/b2d08e5d3652bd073d1faaab8702d8a17653e9fb))
* **model:** model_app sub-app (list/info/pull) ([d960f42](https://github.com/mtopcu1/local-llm-scaffold/commit/d960f425c6a06f2c101ca1d2d6dcd304f71f61f3))
* **params:** coerce_value for string/int/float/bool/enum ([d9b6a9d](https://github.com/mtopcu1/local-llm-scaffold/commit/d9b6a9d01f6150f6b306a0bcb41fedc905dd4b3f))
* **params:** env var name derivation with build/serve scope fallback ([48e331f](https://github.com/mtopcu1/local-llm-scaffold/commit/48e331f3fc32b128bf626ed951ea264316e2b865))
* **params:** ParamSpec dataclass and schema parsing ([b8999e0](https://github.com/mtopcu1/local-llm-scaffold/commit/b8999e0994a5fd34537dee2e69e7a88336b0a012))
* **params:** path template expansion (${data_root} etc.) ([618b9bf](https://github.com/mtopcu1/local-llm-scaffold/commit/618b9bf42632a55fd296654ebe47dcaeb9bcc5c7))
* **params:** validate_params orchestrator (unknown/missing/coerce) ([8ad999b](https://github.com/mtopcu1/local-llm-scaffold/commit/8ad999b9a9980a0703a15f73031f839dd6920abc))
* **registry:** params.yaml serve schema, ParamSpec tiers, runtime kind ([5103835](https://github.com/mtopcu1/local-llm-scaffold/commit/5103835ef2ec05ac83a12dae1b1c44bc57714af3))
* **registry:** RuntimeManifest.accepts_formats ([b658e78](https://github.com/mtopcu1/local-llm-scaffold/commit/b658e78cff6fdb76df7e284981c9e0bdc4d1c1f1))
* **registry:** typed RuntimeManifest and manifest loaders ([7ec091f](https://github.com/mtopcu1/local-llm-scaffold/commit/7ec091f49a7f1482e10a2cc0ffa0058d36e28e0e))
* **registry:** validate_config_v2 with serve.params + uninstalled warning ([581b7d3](https://github.com/mtopcu1/local-llm-scaffold/commit/581b7d3bb27f66142c10dfe6d7e155fda00399f2))
* **runtime:** add runtime install CLI ([b3270d4](https://github.com/mtopcu1/local-llm-scaffold/commit/b3270d4dc5027f918e81115c21741c68a16def94))
* **runtimes:** declare accepts_formats on llamacpp and stub-runtime ([4a5abdd](https://github.com/mtopcu1/local-llm-scaffold/commit/4a5abdd8e336c2b186e5f5e097b72bf70121cf42))
* **serve-spawn:** build_serve_inner with exec for clean signal delivery ([18e4bb8](https://github.com/mtopcu1/local-llm-scaffold/commit/18e4bb89c5c53159ad79c6ae4cf98bad274c99ab))
* **serve-spawn:** port_in_use bind probe ([aedd4b5](https://github.com/mtopcu1/local-llm-scaffold/commit/aedd4b57af5459f3abedebc7e658664a80d1dff4))
* **serve-spawn:** spawn_background uses nohup + echo $! for PID ([d72a59c](https://github.com/mtopcu1/local-llm-scaffold/commit/d72a59c3b4feefdb362a651508b95cbb3bcb9b65))
* **serve-spawn:** spawn_foreground blocks with on_started callback ([68563db](https://github.com/mtopcu1/local-llm-scaffold/commit/68563db4e400c14c07aadbca5073f5616039d216))
* **serve-spawn:** wait_for_ready poll loop with injectable probe ([d47bd7c](https://github.com/mtopcu1/local-llm-scaffold/commit/d47bd7c41ed42a72d197efdcdd63b58290b23cdd))
* **serve:** build env from validated serve.params ([6db4383](https://github.com/mtopcu1/local-llm-scaffold/commit/6db43836f135548fb1a4ff8735dd37d0da68a335))
* **settings:** add `llm settings env` (eval-friendly export lines) ([5039695](https://github.com/mtopcu1/local-llm-scaffold/commit/50396959459cf05cc0d3fc99ade995d433fa4995))
* **settings:** add `llm settings show` ([9f51a8a](https://github.com/mtopcu1/local-llm-scaffold/commit/9f51a8abc9b73b6d31169cc0f128caa6bf077d0f))
* **settings:** add ensure_data_dirs() helper ([3f5418c](https://github.com/mtopcu1/local-llm-scaffold/commit/3f5418cb116d9d0519f2be51175b401d21adfbbf))
* **settings:** add interactive `llm settings edit <key>` ([62eaef2](https://github.com/mtopcu1/local-llm-scaffold/commit/62eaef26134e707c3889520a00307e7926c7d0aa))
* **settings:** add load_settings() with key validation ([e24647c](https://github.com/mtopcu1/local-llm-scaffold/commit/e24647c7f198582040ef62b3c1c189eba6ce094d))
* **settings:** add resolve() to fill defaults and derived dirs ([0f28639](https://github.com/mtopcu1/local-llm-scaffold/commit/0f286395b01b31cc617c2857e13e4bfde6093445))
* **settings:** add save_settings() with key validation ([ec22f70](https://github.com/mtopcu1/local-llm-scaffold/commit/ec22f70c83562f4498e875a3138220886779f2f5))
* **settings:** add XDG-aware settings_path() ([3b0070d](https://github.com/mtopcu1/local-llm-scaffold/commit/3b0070d2527f624eccf065926a4fb580791f7845))
* **settings:** introduce Settings dataclass and KEY_REGISTRY ([b1b9c57](https://github.com/mtopcu1/local-llm-scaffold/commit/b1b9c5710e2d11aea69c477ba3a39b6c3dc5596b))
* **setup:** add `llm setup --default` (non-interactive) ([8c71bb3](https://github.com/mtopcu1/local-llm-scaffold/commit/8c71bb3539c86c0c459f2790f940432b378d1d14))
* **setup:** granular per-directory override prompts ([eecb6fa](https://github.com/mtopcu1/local-llm-scaffold/commit/eecb6fa99c991f22f79f0e2c44d72d89c596bc00))
* **setup:** interactive data_root prompt + default layout ([aa116ae](https://github.com/mtopcu1/local-llm-scaffold/commit/aa116ae8d1ebabde6fd6b612b19464b9bf50a148))
* **setup:** recommended next steps panel ([7d94b70](https://github.com/mtopcu1/local-llm-scaffold/commit/7d94b703a587d12c037ec8844b7f2d73bfc1a67f))
* **systemd:** render llm.service template per config ([5028b75](https://github.com/mtopcu1/local-llm-scaffold/commit/5028b75869db93c860b2057eaa0a63f32ddb8639))
* **systemd:** unit_path resolves via XDG with HOME fallback ([93ab143](https://github.com/mtopcu1/local-llm-scaffold/commit/93ab14348b378516438ad42bb1642fc361996f66))
* **systemd:** wrappers for daemon-reload, restart, stop, is-active ([79cea4a](https://github.com/mtopcu1/local-llm-scaffold/commit/79cea4a01eee1b33690604a766fcd9ea0ad18d77))
* **systemd:** write_if_different skips disk write when unchanged ([a1796c9](https://github.com/mtopcu1/local-llm-scaffold/commit/a1796c9fdbe83244cc367cb384af75a830649317))
* **tests:** add PTY TUI integration coverage for setup flows ([aa566b2](https://github.com/mtopcu1/local-llm-scaffold/commit/aa566b2c57ad7fdf6cdeff5c545cb62bff40fc93))
* **update:** add llm update with scaffold tarball swap ([bc35245](https://github.com/mtopcu1/local-llm-scaffold/commit/bc35245cf52deb7f1a757ef7b099842e0a4a006d))
* **validate,model-cmd:** registry-backed model rules + drop legacy model dir code ([f124e3a](https://github.com/mtopcu1/local-llm-scaffold/commit/f124e3af8853f761eb60ea5bf6b578f678b71a0c))


### Bug Fixes

* **ci:** stabilize Actions runs and add WSL CI mirror scripts ([2433223](https://github.com/mtopcu1/local-llm-scaffold/commit/24332233957983ea017d02ae86096a3667e08a3f))
* **cli:** unregister removed init command ([659228e](https://github.com/mtopcu1/local-llm-scaffold/commit/659228ec7a5cd73e9b9024cdcc091cb4ae5bd82e))
* **core:** validate paths.yaml mapping and non-empty string values ([7b4b106](https://github.com/mtopcu1/local-llm-scaffold/commit/7b4b106a4999ed6947928753bf20c7be1c7fda10))
* **param-grid:** separate page nav from back/save actions ([91ad93e](https://github.com/mtopcu1/local-llm-scaffold/commit/91ad93e0c7055e44e7bde2291c2d35fe58c907ed))
* **params:** restore evaluate_when and unit tests (Task A5) ([fce3b8f](https://github.com/mtopcu1/local-llm-scaffold/commit/fce3b8fa7242f8ac64bbaa948afc592b2d607ef5))
* **tests:** CI failures for logs tail and user-layer TUI paths ([3511043](https://github.com/mtopcu1/local-llm-scaffold/commit/3511043f6e07f6a722425c2c0e1889d59cfdc8fe))
* **test:** set USERPROFILE for tilde expansion on Windows ([af4b65b](https://github.com/mtopcu1/local-llm-scaffold/commit/af4b65b0eaa75284c2e8bd7b89ac82f2fc8ba697))
* **tests:** harden CLI output assertions for CI Rich/TTY capture ([d32bbf3](https://github.com/mtopcu1/local-llm-scaffold/commit/d32bbf37bf40d4774fb36d5ab55bb67271847baa))
* **tests:** patch advisor.detect_all so advisor tests pass without GPU ([e776d88](https://github.com/mtopcu1/local-llm-scaffold/commit/e776d88bf32888272fb4158e61076d19429bc35a))
* **tests:** tolerate Rich CLI output when checking required --runtime ([2e78984](https://github.com/mtopcu1/local-llm-scaffold/commit/2e78984d3ad8ce747f23105ea311a3e9de636846))
* **wizards:** treat questionary cancel as abort ([6e89666](https://github.com/mtopcu1/local-llm-scaffold/commit/6e89666eda9fcf4d2e20cea2cc0a4223efa43400))
* **wsl:** gate PureWindowsPath when faking non-Windows on Windows host ([af4b65b](https://github.com/mtopcu1/local-llm-scaffold/commit/af4b65b0eaa75284c2e8bd7b89ac82f2fc8ba697))


### Documentation

* add CONTRIBUTING with Conventional Commits guide ([89f43ee](https://github.com/mtopcu1/local-llm-scaffold/commit/89f43ee08ecab5da05b66f89ed24ecb21843cd39))
* add full project review and expand example config ([042aaea](https://github.com/mtopcu1/local-llm-scaffold/commit/042aaea3a1a89ab39d3ae401f1d0e1f9792950e1))
* add install, update, and versioning design spec ([cd1b569](https://github.com/mtopcu1/local-llm-scaffold/commit/cd1b569c9898dbdbaf5086f6de5a613e7c98dec3))
* add install, update, and versioning implementation plan ([d92b5aa](https://github.com/mtopcu1/local-llm-scaffold/commit/d92b5aa73c0d111eab6cea3fc4ce95e20f1ec39d))
* add LocalLLM scaffolding design spec ([6e4abec](https://github.com/mtopcu1/local-llm-scaffold/commit/6e4abec6fa57b6845ed6c7a5404d4c60e6365582))
* add Milestone 1 (Foundation) implementation plan ([32b6dbd](https://github.com/mtopcu1/local-llm-scaffold/commit/32b6dbd55244ecb8c00c7cdebd1eba7da1720b96))
* **add-a-model:** rewrite for registry + pull/add commands ([50d8888](https://github.com/mtopcu1/local-llm-scaffold/commit/50d8888e7bae89f49d821ae86939c715298edc13))
* **add-a-runtime:** rewrite for typed manifest, four-script contract, install flow ([58c4bcb](https://github.com/mtopcu1/local-llm-scaffold/commit/58c4bcbe7821827028ded5f948328fad01e22616))
* approve TUI pexpect integration spec ([23badd8](https://github.com/mtopcu1/local-llm-scaffold/commit/23badd80bf8c008cb8fc8ae2a051d4f67e51edb1))
* clarify lifecycle state_root in install plan ([deb32a8](https://github.com/mtopcu1/local-llm-scaffold/commit/deb32a87c1e0efb670927b2d11e85aebe4023bc6))
* **conventions:** describe settings and config namespace split ([16dc9c0](https://github.com/mtopcu1/local-llm-scaffold/commit/16dc9c01360e670636cf70a24613e394ca266d36))
* **conventions:** models live in registry.json under data root ([15380d3](https://github.com/mtopcu1/local-llm-scaffold/commit/15380d3ab89705684782e14da99b5e39e2531008))
* **howto:** replace init env flow with setup settings env ([022b02f](https://github.com/mtopcu1/local-llm-scaffold/commit/022b02f246cec148f7beb54c0d978f9b1f84e070))
* **plan:** add 0.2 wizards/advisor implementation plan ([9c5ea36](https://github.com/mtopcu1/local-llm-scaffold/commit/9c5ea36a143a46115679178403610c22a3bd1dd7))
* **plan:** add lifecycle and serve implementation plan ([7a0bdbe](https://github.com/mtopcu1/local-llm-scaffold/commit/7a0bdbe9c7c30e0ae1816c6cb5f9be1b50d6e5e3))
* **plan:** add release plumbing implementation plan (cut 1) ([9ec9ea3](https://github.com/mtopcu1/local-llm-scaffold/commit/9ec9ea3c35a8c32afa8704e479fcfebb04a76fb8))
* **plan:** add settings and setup redesign implementation plan ([27ab8da](https://github.com/mtopcu1/local-llm-scaffold/commit/27ab8da07652ac88e172104f7d75b4ad5ba4d1ec))
* **plan:** models registry redesign implementation plan ([12aa363](https://github.com/mtopcu1/local-llm-scaffold/commit/12aa3633cbc7e1d7f52c0934a86ccba8faa37f36))
* **plan:** runtime manifests and installs implementation plan ([a5cee96](https://github.com/mtopcu1/local-llm-scaffold/commit/a5cee9620d5c559fe8a815c76ee5fed00ce1824c))
* **readme:** replace init flow with setup and settings ([3393ed0](https://github.com/mtopcu1/local-llm-scaffold/commit/3393ed0fe7a18a5671347a177d6c0a7b0770e507))
* **readme:** update model CLI section for registry + pull from URL ([3a691d3](https://github.com/mtopcu1/local-llm-scaffold/commit/3a691d3c35295bb5b9a6cea9bde3bdebb6a3876a))
* **requirements:** regenerate with universal + per-runtime sections ([e3da373](https://github.com/mtopcu1/local-llm-scaffold/commit/e3da373235fd224da5df13abbf996fcb5bfbf30c))
* **runtime-lifecycle:** install/uninstall/rebuild, .installed, drift behavior ([9a8da70](https://github.com/mtopcu1/local-llm-scaffold/commit/9a8da7015870f4434a42c8d6964991b9a5f4280c))
* **spec:** add lifecycle and serve design ([a7b647b](https://github.com/mtopcu1/local-llm-scaffold/commit/a7b647b73c2726a79d0b8f310451a4b1c298a2ac))
* **spec:** add settings and setup redesign ([614f547](https://github.com/mtopcu1/local-llm-scaffold/commit/614f547a20ae44a50c9b82fd774728668370abd6))
* **spec:** add update/distribution/versioning design ([6450d73](https://github.com/mtopcu1/local-llm-scaffold/commit/6450d731664fe1a83409f0049c17bbf41f8ba598))
* **spec:** mark distribution design as approved ([be8f9c8](https://github.com/mtopcu1/local-llm-scaffold/commit/be8f9c8a021bab59bcaf5ab078efe773063f813e))
* **spec:** models registry redesign ([828d3a1](https://github.com/mtopcu1/local-llm-scaffold/commit/828d3a1370a76ea6b5a7265de35c1dc95f7397bf))
* **spec:** point original scaffolding design at redesign ([4dc0948](https://github.com/mtopcu1/local-llm-scaffold/commit/4dc09485b9fdf4e675aa398b71b433ea7a2902dc))
* **spec:** runtime manifest schemas, install lifecycle, and CLI groups ([d970835](https://github.com/mtopcu1/local-llm-scaffold/commit/d9708356433947f57f01c0b2c1f6434165d05d8c))
* **spec:** simplify repo discovery via settings.repo_root ([e7ac660](https://github.com/mtopcu1/local-llm-scaffold/commit/e7ac660bfb5c73a6fbf09e29d7c46bdb6b0b6bbd))
* **spec:** switch scaffold transport from git to release tarball ([3f6dc7a](https://github.com/mtopcu1/local-llm-scaffold/commit/3f6dc7a2d84ad08c9517c3347c95de4a064e8134))
* sweep for runtime/model sub-apps and .installed serve gate ([510bf1c](https://github.com/mtopcu1/local-llm-scaffold/commit/510bf1ce26553548c05b897d0099d9e197799f31))
