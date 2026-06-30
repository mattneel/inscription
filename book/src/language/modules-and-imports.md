# Modules and Imports

Modules are optional. A module declaration must be the first declaration in its file:

```inscription,no-check
Module Protocol.
```

Imports follow the module declaration and precede other declarations:

```inscription,no-check
Import Protocol.
Import geometry.points.
```

Imported declarations remain qualified. `Import Protocol.` lets you write `Protocol.parse header bytes`, `Protocol.Mode.active`, or `Protocol.MaybeI32.some with value be 7` depending on what the module exports at source level. Import aliases exist for migration support in the parser, but canonical source should use module qualification directly.
