# Changelog

All notable changes to XMI2SDC are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html):
MAJOR = SDC Reference Model generation (4), MINOR = features, PATCH = fixes.

## [4.1.2] - 2026-10-25

### Security

- CI and release workflows install pip 26.2.2 from a hash-pinned wheel right after Python is set up, before any
  other install. pip before 26.2.2 vendors a certifi that still trusts the emSign root removed after the eMudhra
  intermediate-CA key compromise (October 2026), so the release is built and published with the fixed pip.
  No change to the package's code.

## [4.1.1] - 2026-08-24

### Fixed

- A 402 from SDCStudio surfaces the server's own message, quoted in credits, instead of a stale "Insufficient wallet
  funds" prefix around the raw JSON.

## [4.1.0] - 2026-07-21

### Added

**Inheritance provenance, so the class-diagram round trip is lossless ([#11](https://github.com/SemanticDataCharter/XMI2SDC/issues/11)).**
When a UML generalization hierarchy is flattened into SDC's flat component space, the mapping
plan now records where each materialized attribute came from, so the original class diagram can
be reconstructed rather than approximated by name-matching. Two carriers, both on channels the
tool already owns (no SDCStudio Assembly change):

- **Machine (automated reconstruction) — per-component semantic links**, using ratified
  in-stack vocabularies (no invented predicates):
  - `prov:wasDerivedFrom` on each inherited component, pointing at the component the ancestor
    introduced (e.g. `DanubeHerring.head` → `Fish.head`, the true origin, not the immediate
    parent).
  - `rdfs:subClassOf` on each class cluster, pointing at its parent cluster, recording the
    generalization edges.
  - A `namespaces` block in the mapping plan documents the `prov` and `rdfs` URIs.
- **Human (HITL containment in SDCStudio) — the component `description`**, which already flows
  through the whole pipeline, now carries a fenced `[XMI2SDC provenance]` note on inherited
  components: where the attribute came from and how to contain it if reconstructing the original
  hierarchy. It guides the human decision without dictating it; any component may still be placed
  in any Cluster.
- `flatten_inheritance` stamps each attribute with its introducing class (`introduced_by_name` /
  `introduced_by_xmi_id`); the origin is recorded once, at the defining class, and propagates to
  every descendant that inherits it.

### Notes

- Backward-compatible: own (non-inherited) components are unchanged (no `semantic_links` key, no
  description note). Inheritance provenance appears only where there is inheritance.
- Scope is contained to the `convert` mapping plan. Persisting these links onto the **assembled**
  SDC4 graph (via the Assembly API mint-ref + SDCStudio) is intentionally out of scope for this
  release; the human-facing description note reaches the published component regardless, since
  `description` is already carried through assembly.
- Surfaced by Yuriy Chernyavskiy while evaluating XMI ↔ SDC round-trip fidelity.

## [4.0.0] - 2026

- Initial release: agentic XMI/UML to SDC4 converter (parser, mapper, assembler pipeline on the
  Google ADK); Sparx EA / MagicDraw / generic XMI 2.x dialects; deterministic type mapping;
  inheritance flattening; SDCStudio Assembly API integration.
