# Platform-Specific Commands

## Android/Kotlin/Java/Spring

Java parser indexes: classes, interfaces, enums, methods, constructors, fields, and annotations (@RestController, @Service, @Repository, @Component, @Entity, @GetMapping, @PostMapping, @Autowired, @Override, @Transactional, @SpringBootApplication, @Test, @Inject, @Data, @Builder).

Maven modules (pom.xml) are fully supported alongside Gradle modules.

### DI & Annotations

```bash
ya tool ast-index provides "UserRepository"     # Find DI providers
ya tool ast-index inject "NetworkModule"         # Find @Inject + @Autowired usages
ya tool ast-index annotations "@Service"         # Find annotated symbols
ya tool ast-index annotations "@RestController"  # Find REST controllers
```

### Compose

```bash
ya tool ast-index composables                    # Find @Composable functions
ya tool ast-index previews                       # Find @Preview functions
```

### Coroutines

```bash
ya tool ast-index suspend                        # Find suspend functions
ya tool ast-index flows                          # Find Flow-related code
```

### XML & Resources

```bash
ya tool ast-index xml-usages "ClassName"         # Find class usages in XML layouts
ya tool ast-index resource-usages "ic_launcher"  # Find resource usages
```

### Other

```bash
ya tool ast-index extensions                     # Find Kotlin extension functions
ya tool ast-index deeplinks                      # Find deeplink declarations
ya tool ast-index suppress                       # Find @Suppress annotations
```

## iOS/Swift/ObjC

Swift parser indexes: classes, structs, enums, protocols, actors, extensions, functions, properties, typealiases, imports. Supports async/await, Combine, SwiftUI.

```bash
ya tool ast-index storyboard-usages "ClassName"  # Find class in storyboards/XIBs
ya tool ast-index asset-usages "iconName"        # Find asset catalog usages
ya tool ast-index swiftui                        # Find SwiftUI views
ya tool ast-index async-funcs                    # Find async functions
ya tool ast-index main-actor                     # Find @MainActor symbols
ya tool ast-index publishers                     # Find Combine publishers
```

## TypeScript/JavaScript

Indexes: class, interface, type, function, const, decorators. Supports React (hooks, components), Vue SFC, Svelte, NestJS, Angular.

Vue Composition API: `ref()`, `computed()`, `reactive()`, `defineProps()`, `defineStore()` variables appear in outline.

```bash
ya tool ast-index outline "App.tsx"              # React component structure
ya tool ast-index outline "store.ts"             # Pinia store with reactive vars
ya tool ast-index callers "fetchData"            # Finds await func(), return func()
```

## Rust

Indexes: struct, enum, trait, impl, fn, macro_rules!, mod. Supports derives and attributes (#[test], #[derive]).

```bash
ya tool ast-index outline "handler.rs"           # Show structs, impls, functions
ya tool ast-index implementations "Display"      # Find Display trait implementors
```

## Ruby

Indexes: class, module, def, Rails DSL (has_many, belongs_to, validates, scope, before_action, etc.), Alba serializer, Dry::Initializer.

Supports bang/question methods (`save!`, `valid?`) in usages.

```bash
ya tool ast-index outline "user.rb"              # Rails model structure
ya tool ast-index usages "authenticate_user!"    # Find bang method usages
```

## C#/.NET

Indexes: class, interface, struct, record, enum, methods, properties. Supports ASP.NET attributes, Unity (MonoBehaviour, SerializeField).

## Dart/Flutter

Indexes: class, mixin, extension, extension type, enum, typedef, functions, constructors. Supports Dart 3 modifiers (sealed, final, base, interface, mixin class).

## Python

Indexes: class, def, async def, decorators.

## Go

Indexes: package, type struct, type interface, func.

## Scala

Indexes: class, case class, object, trait, enum (Scala 3), def, val, var, type, given. Supports inheritance (extends/with), companion objects.

## PHP

Indexes: namespace, class, interface, trait, enum, function, method, const, property, use. Supports Laravel (models, traits, facades).

## Perl

```bash
ya tool ast-index perl-exports "ModuleName"      # Find exported symbols
ya tool ast-index perl-subs "ModuleName"         # Find subroutines
ya tool ast-index perl-pod "ModuleName"          # Find POD documentation
ya tool ast-index perl-imports "file.pm"         # Find use/require statements
ya tool ast-index perl-tests                     # Find test files
```

## Module Analysis

```bash
ya tool ast-index module "payments"              # Find modules by name
ya tool ast-index deps "module-name"             # Show dependencies
ya tool ast-index dependents "module-name"       # Show reverse dependencies
ya tool ast-index unused-deps "module-name"      # Find unused dependencies
ya tool ast-index unused-symbols --module path/  # Find unused symbols in module
ya tool ast-index api "path/to/module"           # Public API of module
```
