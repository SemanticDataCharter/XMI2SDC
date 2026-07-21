# Inheritance provenance and the lossless round trip

XMI2SDC dissolves a UML generalization hierarchy into SDC's flat component space:
each class materializes the full set of attributes it needs, including the ones it
inherits. This is deliberate, SDC composes by component reuse, not by class
inheritance. But flattening on its own loses the record of *which ancestor
introduced each attribute*, which would make the reverse direction (flat model back
to class diagram) an approximation by name-matching rather than a reconstruction.

Since 4.1.0 the `convert` mapping plan records that provenance, so the round trip
`class diagram -> flat model -> class diagram` is lossless. There are two carriers,
one for machines and one for the human doing containment.

## For machines: semantic links

Every inherited component carries a `prov:wasDerivedFrom` link pointing at the
component the ancestor introduced, and every class cluster carries `rdfs:subClassOf`
links recording the generalization edges. Both vocabularies are ratified and already
part of the SDC stack; the mapping plan includes a `namespaces` block with their URIs.

```json
{
  "namespaces": {
    "prov": "http://www.w3.org/ns/prov#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#"
  },
  "components": [
    {
      "label": "DanubeHerring.head",
      "source_class": "DanubeHerring",
      "semantic_links": [
        { "predicate": "prov:wasDerivedFrom", "object": "Fish.head" }
      ]
    }
  ],
  "clusters": [
    {
      "cluster_name": "DanubeHerring",
      "semantic_links": [
        { "predicate": "rdfs:subClassOf", "object": "Herring" }
      ]
    }
  ]
}
```

Note that `wasDerivedFrom` points at the **origin** class, not the immediate parent:
`DanubeHerring.head` derives from `Fish.head`, because Fish is where `head` was
introduced.

### Reconstructing the class diagram

No name-guessing is required:

- A class's **own** attributes are its components with **no** `prov:wasDerivedFrom`
  link.
- The **generalization edges** are the cluster `rdfs:subClassOf` links.

```python
own, parents = {}, {}
for c in plan["components"]:
    cls = c["label"].split(".", 1)[0]
    inherited = any(l["predicate"] == "prov:wasDerivedFrom"
                    for l in c.get("semantic_links", []))
    if not inherited:
        own.setdefault(cls, []).append(c["source_attribute"])
for cl in plan["clusters"]:
    for l in cl.get("semantic_links", []):
        if l["predicate"] == "rdfs:subClassOf":
            parents.setdefault(cl["cluster_name"], []).append(l["object"])
```

For the Fish -> Herring -> DanubeHerring model this yields exactly the original
diagram: Fish owns `head, scales, fins, tail`; Herring subClassOf Fish owns
`herringSmell`; DanubeHerring subClassOf Herring owns `iodineSmell`.

## For the human: the description note

The person doing containment in SDCStudio reads the component description, so an
inherited component's description carries a fenced note:

```
[XMI2SDC provenance] Inherited from UML class Fish. In the source model this
attribute belonged to Fish; if reconstructing the original hierarchy, contain it
accordingly.
```

This **guides** the containment decision, it does not dictate it. In SDC any
component may be placed in any Cluster, and that call belongs to the human. The
`[XMI2SDC provenance]` marker is stable, so the note can be found or stripped
programmatically.

## Backward compatibility and scope

- Own (non-inherited) components are unchanged: no `semantic_links` key and no
  description note. Provenance appears only where there is inheritance.
- The links live in the `convert` **mapping plan**. Carrying them onto the
  **assembled** SDC4 graph (via the SDCStudio Assembly API) is a separate step and is
  not part of this release. The human-facing description note reaches the published
  component regardless, because `description` is carried through assembly.
