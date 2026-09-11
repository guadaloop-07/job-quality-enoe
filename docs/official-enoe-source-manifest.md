# Official ENOE source manifest

The independent ingestion uses INEGI's ENOE 15-and-over CSV archive URL pattern:

    https://www.inegi.org.mx/contenidos/programas/enoe/15ymas/microdatos/enoe_<year>_trim<quarter>_csv.zip

The following archives were downloaded and SHA-256 verified on 2026-09-11.
Archives remain in ignored local storage; this document contains provenance only.

| Period | Bytes | SHA-256 |
|---|---:|---|
| 2023 Q1 | 37,487,716 | `ae627ebd3b749f15b5faf27fdc59dadb69a696a5f359d1faa7aae5eae856041c` |
| 2023 Q2 | 39,500,761 | `e2035d3a3e3d0789ee10fac875c792c5833fc90f7e1ccb9345e0690dd8c40eb5` |
| 2023 Q3 | 40,893,331 | `cb91900ad406e1d7435cc51ed418866cbdd08808892d2dd60644516e82be9752` |
| 2023 Q4 | 40,681,812 | `24f15e1ab8ad942b479b32f491b9e2d8b640ac3c8e79dbea02e74baa78ae9d2e` |
| 2024 Q1 | 37,004,177 | `5ef594c06487cd277de1ae9f9b0846f9ba64dbd8d743c983002dcf431974d02b` |
| 2024 Q2 | 31,773,308 | `13922f8902f587939145e0302ec8e6e5fa9fb0df4207229f7447deaaab96e285` |
| 2024 Q3 | 43,272,328 | `6594158c1a3f9732d9844061e46f95c0abe7ef9f8fe4f7605b72be31c3628ef3` |
| 2024 Q4 | 43,410,469 | `817f28d20a43fa4fed08195e62df58bf320b31c323a3049fe09b5194a1677305` |
| 2025 Q1 | 40,919,680 | `dddbb698e7f18f63bc256ece61ac0038a5ad062d42aca13390d88828fb27796e` |
| 2025 Q2 | 38,752,236 | `291db61afcc472a0933d2bebf46720cfd024df8912dc899d541d8109bd406722` |
| 2025 Q3 | 40,062,680 | `d2817a14201694e119a3fd6fcb8b8ed7619ea7e26cf8b353761a1ac1f23d6022` |
| 2025 Q4 | 43,383,478 | `e675b41bde4fb3c183a0abd067738109c6aaf30ed314bc9fc548669fb8a1565d` |

The loader records the concrete URL, archive name, byte size, SHA-256, local
retrieval time, and code revision in the repository-owned PostgreSQL metadata
schema for every loaded period.
