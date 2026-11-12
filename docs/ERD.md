# Engineering reference — index

This file used to hold everything. On 2026-11-11 it was split by app. Update the file for the code you changed:

| File | Scope |
|---|---|
| [`shared/ERD.md`](shared/ERD.md) | The reader, Kindle e-ink mode, sign-in and progress, audio player, media policy and repository layout that both apps use. |
| [`plainly/ERD.md`](plainly/ERD.md) | Plainly: classics, ingestion, Plain English, summaries, illustrations, discovery, SEO |
| [`distill/ERD.md`](distill/ERD.md) | Distill: private summaries, book format, import, deploy, Listen |

Older references of the form "`docs/ERD.md` → *Section*" still work: find the section below.

## shared/ERD.md

- 2026-11-07: Native Kindle viewport stabilization
- 2026-11-03: Kindle reader chrome sizing and overflow
- 2026-11-03 — Physical PW3 image painting correction
- 2026-11-02 — Kindle startup and illustration layout repair
- Shared audio player (2026-11-09)
- Generated media lives outside Git (2026-10-27)
- Shared Kindle pairing and launcher source (2026-10-27)
- Native browser gestures and sleep lifecycle (2026-11-03)
- Verified native fullscreen architecture (2026-10-27)
- 2026-10-27: Clear native pan on fullscreen exit
- 2026-10-27: Detect measured fullscreen outer height
- 2026-10-27: Use native fullscreen browser space
- Verified native PW3 implementation (2026-10-27)
- 2026-10-27: Match measured native surface initialization
- 2026-10-27: Reconcile native scroll range after load
- 2026-10-27: Initialize native scroll surface after pagination
- 2026-10-27: Preserve native profile after font relayout
- Native PW3 viewport profile (2026-10-27)
- Kindle gesture scroll containment (2026-10-27)
- Kindle viewport sizing (2026-10-27)
- Kindle typography configuration (2026-10-27)
- Distill Kindle device authentication (2026-10-27)
- Reader section boundary navigation (2026-10-27)
- Repository layout (post repo split, 2026-10-24)
- User Authentication & Progress Tracking (Added 2025-12-20; **auth rebuilt 2026-09-06 — see note**)
- Reader platform (shared reader, 2026-10-25; updated 2026-10-26)

## plainly/ERD.md

- Table of Contents
- Brand name
- Backend Module Map
- Frontend Module Map
- Database Schema & ERD
- SEO Architecture
- Related Books System
- Chapter Parser Implementation
- TTS Engine Implementation
- LLM Call Logic & Rate Limiting
- Summary Regeneration Modes (Added 2025-12-12)
- Bulk Summary Processing
- Project Gutenberg Integration
- Backend Architecture
- Frontend Architecture (Redesigned 2025-11-25)
- Navigation UX Improvements (Added 2025-11-28)
- Reading Experience Customization (Added 2025-11-30)
- Chapter Illustration Lightbox (Added 2025-12-01)
- Summary
- Two-Level Book Structure Detection
- Gemini Image Generation System
- Image Optimization System
- Book Metadata Enrichment
- Frontend UI Components & Architecture
- API Endpoints
- Text Formatting & Rendering
- Top 10 Carousel - Responsive Layout System
- Frontend Loading State Architecture (Added 2025-12-11)
- Discover Page Architecture (Added 2025-12-11)
- Blog Header Images & Unsplash Integration
- Database Quality & Audit System
- Progressive Web App (PWA) Installability
- Pagination System (Added 2025-12-19)

## distill/ERD.md

- 2026-11-03 — GitHub and VM synchronization
- 2026-11-02 — Research grids and NVIDIA publication
- File-media migration verified live (2026-10-28)
- Distill home and Listen outside the reader (2026-11-08)
- Distill Listen: chapter audio (2026-11-07)
- Distill image files and metadata schema (2026-10-27)
- Distill book action styling (2026-10-27)
- Distill app (2026-10-25; updated 2026-10-26)
