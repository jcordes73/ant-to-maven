# Migrating from Apache Ant to Apache Maven

A practical, phase-by-phase guide for teams moving Ant-based Java builds to Maven.

## Table of Contents

- [1. Introduction](#1-introduction)
- [2. Phase 0: Assess the Existing Build](#2-phase-0-assess-the-existing-build)
- [3. Phase 1: Scaffold the POM](#3-phase-1-scaffold-the-pom)
- [4. Phase 2: Dependencies](#4-phase-2-dependencies)
- [5. Phase 3: Map Build Steps to Plugins](#5-phase-3-map-build-steps-to-plugins)
- [6. Phase 4: Migrate Tests](#6-phase-4-migrate-tests)
- [7. Phase 5: Custom Ant Tasks and the Antrun Escape Hatch](#7-phase-5-custom-ant-tasks-and-the-antrun-escape-hatch)
- [8. Phase 6: Multi-Module Builds](#8-phase-6-multi-module-builds)
- [9. Phase 7: Profiles, Properties, Environments](#9-phase-7-profiles-properties-environments)
- [10. Phase 8: CI/CD and Release](#10-phase-8-cicd-and-release)
- [11. Phase 9: Cutover and Decommissioning](#11-phase-9-cutover-and-decommissioning)
- [12. Troubleshooting and Common Pitfalls](#12-troubleshooting-and-common-pitfalls)
- [Appendix A: Ant Task to Maven Plugin Mapping](#appendix-a-ant-task-to-maven-plugin-mapping)

## 1. Introduction

Apache Ant served the Java community well for nearly two decades, and many production builds still depend on it. But the broader ecosystem has standardized on Maven and, increasingly, on the project model Maven established. This guide is for teams that have decided to migrate — or are deciding — and want a practical, phase-by-phase path rather than a rewrite from scratch.

### Why migrate

Migrating an Ant build to Maven is an investment, so it is worth being explicit about what you get in return:

- **A declarative project model.** In Maven you describe *what* your project is — its coordinates, modules, dependencies, and packaging — rather than *how* to produce it. A single `pom.xml` per project tells every tool that understands the model what it needs to know.
- **Built-in dependency management with transitive resolution.** Ant has no notion of dependencies; you fetch jars manually or with Ivy. Maven resolves your declared dependencies automatically, pulls in their transitive dependencies, detects version conflicts, and gives you a dependency tree you can inspect and control.
- **A conventional lifecycle and standardized commands.** Every Maven project shares the same lifecycle, so anyone can build, test, package, install, and deploy your project with the same commands — no reading a bespoke `build.xml` first. New team members and CI systems get consistent behavior across all projects.
- **Ecosystem tooling.** IDEs, CI servers, code coverage, static analysis, containerization, and release tooling all speak Maven natively. Public and private artifact repositories give you versioned, reproducible distribution of your own binaries, and Maven Central provides access to billions of published artifacts.

### When not to migrate

Migration is not always the right call. Consider staying on Ant, or deferring, when:

- **Your build is dominated by procedural steps with no plugin equivalent.** If most of your build is arbitrary shell logic, custom file manipulation, or bespoke orchestration, you will spend your time forcing non-build logic into plugins rather than benefiting from conventions.
- **Legacy code generators are tightly coupled to Ant.** Some older code-generation tools can only be invoked as Ant tasks or depend on Ant's internal APIs and project model. Replacing that coupling can be a project in itself.
- **The project is near end-of-life.** If a build will be retired soon, the migration cost may never pay for itself.

That said, the window for migration is wider than it first appears. The `maven-antrun-plugin`, covered in Chapter 7, lets you run Ant targets and scripts from within a Maven build, so procedural islands can be carried over incrementally instead of being eliminated up front.

### Two philosophies: scripting vs. framework

The deepest difference between Ant and Maven is philosophical, and understanding it makes every later chapter easier.

Ant is a build *scripting* library. It is imperative: you write every procedure yourself as XML targets, and the tool executes what you wrote and nothing more. Ant has no built-in notion of a project, no dependency management, and no lifecycle — those exist only to the extent you build them in your script. This makes Ant extremely flexible and makes every Ant build unique.

Maven is a build *framework*. It is declarative: you describe your project and its dependencies, and the framework supplies the lifecycle, the standard directory layout, and the conventions. You only deviate when your project does not fit the default conventions. This makes Maven projects uniform, and it is exactly what enables the standardized commands and ecosystem tooling described above.

The vocabulary differs accordingly. An Ant "target" is a named unit of work you invoke directly; in Maven, work happens in lifecycle *phases*, which are executed by *goals* bound to those phases. Roughly:

| Ant concept | Maven counterpart |
| --- | --- |
| target | phase (lifecycle step) or goal (plugin unit of work) |
| depends on | lifecycle ordering / plugin execution binding |
| build.xml | pom.xml |
| task | plugin goal |
| property | property (with the POM's built-in properties) |

Keep this mapping in mind as we go; the rest of the guide builds on it.

## 2. Phase 0: Assess the Existing Build

Before you write a single line of `pom.xml`, you need a complete picture of what your Ant build actually does. Maven will supply a lifecycle, a dependency tree, and a standard layout — but only if you know exactly which behaviors you are replacing and which you must reproduce. Phase 0 is an assessment phase only: nothing in this chapter produces Maven configuration, and no Maven counterpart is shown. Its deliverable is a written inventory you can check against in every later chapter.

### Inventory the build.xml

Work through your `build.xml` (and any files it imports or includes) systematically and record four things:

1. **Every target and its `depends` chain.** List each `<target>` with its `depends` attribute so you can see the true execution order. Ant targets with long dependency chains often hide implicit lifecycle phases — a `dist` target that depends on `compile`, `test`, and `javadoc` is really a package-plus-verify pipeline, and that ordering will map onto Maven's lifecycle later.
2. **Every `<path>` and `<classpath>` element.** These are your dependency declarations in disguise. For each one, record the jars it pulls in (via `<fileset>`, `<pathelement>`, or a referenced path), because each jar must become a Maven dependency in Chapter 4. Watch for jars that are duplicated across paths, versioned filenames like `commons-lang-2.6.jar`, and jars that exist only locally — those are your dependency-management risks.
3. **Custom tasks and where their classes come from.** Find every `<taskdef>` and `<typedef>`, and note whether the implementing classes come from a jar on the classpath, from the project's own compiled code, or from a bundled tool. Custom tasks are the single most common migration blocker, so you want the full list early. Chapter 7 covers what to do with them.
4. **Everything else the build does that is not compilation.** Specifically look for:
   - **Generated-source steps**: `<javacc>`, `<jaxb>`, `<wsimport>`, XDoclet-style generators, or custom code generators invoked via `<java>` or `<exec>`. Maven handles the common ones with plugins, but each needs a dedicated mapping decision.
   - **Copy, filter, and replace steps**: `<copy>` with filtering, `<replace>`, `<replaceregexp>`, and resource staging. These usually map to the resources plugin or build-helper, but only if you know exactly which files move where.
   - **Compiler options**: every `javac` invocation's `source`, `target`, `debug`, `encoding`, and `excludes` settings. These translate directly into `maven-compiler-plugin` configuration, and inconsistencies between targets (one compiles at 1.8, another at 11) must be resolved before they can become a single POM-level setting.

### A representative example

Throughout this guide we use a fictional project, **acme-core**, as the running example: groupId `com.acme`, currently compiling with Java 8 settings, using JUnit 5 for tests, and carrying a couple of custom Ant tasks. Here is a representative excerpt of its `build.xml` — the classpath definition, the compile target, and the clean target:

```xml
<project name="acme-core" default="dist" basedir=".">
  <property name="lib.dir" value="lib"/>
  <property name="build.dir" value="build"/>
  <property name="src.dir" value="src"/>

  <path id="compile.classpath">
    <fileset dir="${lib.dir}">
      <include name="*.jar"/>
    </fileset>
  </path>

  <target name="clean" description="Remove build artifacts">
    <delete dir="${build.dir}"/>
  </target>

  <target name="compile" depends="init" description="Compile sources">
    <javac srcdir="${src.dir}" destdir="${build.dir}/classes"
           source="1.8" target="1.8" debug="on" encoding="UTF-8">
      <classpath refid="compile.classpath"/>
      <exclude name="com/acme/legacy/**"/>
    </javac>
  </target>

  <target name="dist" depends="compile, test" description="Build distribution jar"/>
</project>
```

Applying the inventory to this excerpt: the `compile.classpath` path sweeps every jar in `lib/` into the compile classpath (each one is a future `<dependency>`); the `compile` target fixes `source`/`target` at 1.8 with debug on, UTF-8 encoding, and an exclude pattern for a legacy package; `clean` is a plain directory delete; and the `dist` target's `depends` chain (`compile, test`) reveals an implicit package-and-verify ordering. Note that this chapter produces no Maven configuration — the POM that replaces this file is built up starting in Chapter 3.

### Pre-migration checklist

Capture all of the following before you start. Each item maps to a decision in a later chapter, and discovering a gap mid-migration is far more expensive than discovering it now:

- [ ] Compiler flags: `source`, `target`, `debug`, `encoding`, and any `excludes`/`includes` on every `javac` invocation
- [ ] Full classpath contents: every jar on every `<path>`/`<classpath>`, with versions where filenames reveal them
- [ ] JVM version actually used to run the build (not just the compile target)
- [ ] Packaging artifacts produced: jar, war, zip, tar, or anything else, and their final names
- [ ] Signing and manifest steps: `<signjar>`, manifest attributes, classpath entries written into the manifest
- [ ] Test invocation: which runner executes tests, which directories they live in, and any test-specific classpath or system properties
- [ ] Environment-specific property files and how they are selected (property files passed on the command line, per-environment targets, filtered resources)

### Identify the blockers

With the inventory in hand, classify your build against three common blockers:

- **Source layout far from the standard Maven layout** (for example, `src/` containing both main and test code, or sources split across `java/` and `src-java/`). The escape hatch is a build layout override, covered in Chapter 3.
- **Heavy code generation** — multiple generators, generators tied to Ant's internal APIs, or generated sources feeding further generation. The escape hatch is the build-helper plugin for attaching extra source roots, covered in Chapter 5.
- **Procedural steps with no plugin equivalent** — arbitrary file surgery, orchestration, or shell logic embedded in targets. The escape hatch is the `maven-antrun-plugin`, which lets you keep those targets as-is while everything else moves to Maven, covered in Chapter 7.

If a blocker dominates the build rather than decorating it, revisit the "When not to migrate" discussion in Chapter 1 before investing further.

### Where the inventory goes

Keep the inventory in a short document next to the project (a `MIGRATION-NOTES.md` is fine). Every later chapter of this guide starts from it: the POM scaffold in Chapter 3 consumes the packaging and compiler settings, Chapter 4 consumes the classpath inventory, and Chapter 5 consumes the generated-source and copy/filter steps. When a chapter says "check your inventory," this is the document it means.

## 3. Phase 1: Scaffold the POM

Phase 1 produces the first real Maven artifact: a minimal, buildable `pom.xml` that compiles your sources with the correct Java version and produces the same packaging your Ant build did. It does not yet carry dependencies, tests, or plugin mappings — those arrive in Chapters 4 through 7. The goal here is a baseline so clean that every later chapter is a small, reviewable increment on top of it.

This chapter uses the acme-core example from Chapter 2: currently an Ant build compiling with `javac source="1.8" target="1.8"` from a `src/` directory. By the end of the chapter, acme-core is a Maven project on Java 11 with a standard layout.

### Coordinates: naming your project

Maven identifies every artifact with three required coordinates plus a packaging type:

- **groupId** — the organization or team that owns the artifact, written as a reversed domain name. It exists to keep artifacts from different organizations from colliding, and it typically mirrors your Java package root. For acme-core: `com.acme`.
- **artifactId** — the name of the artifact within that group. It should match the jar your build already produces and, usually, the project's directory name. For acme-core: `acme-core`.
- **version** — the version string. Maven has a strong convention that in-development versions end in `-SNAPSHOT` (mutable, rebuilt freely) while release versions do not (immutable, published once). For acme-core: `1.0.0-SNAPSHOT`.
- **packaging** — the type of artifact the build produces: `jar` (the default), `war`, `pom` (for aggregator parents, covered in Chapter 8), and others. For acme-core: `jar`.

Together, `groupId:artifactId:version` is often abbreviated as GAV. If your Ant build names its output jars by a convention like `<artifactId>-<version>.jar`, the mapping to coordinates is direct: `acme-core-1.0.0.jar` produced by an Ant `dist` target means artifactId `acme-core`, version `1.0.0`, and — if the jar was a development build that was continually rebuilt — `1.0.0-SNAPSHOT` once it is under Maven. If your convention embeds the group, as in a directory tree like `com/acme/acme-core/1.0.0/acme-core-1.0.0.jar`, the groupId falls out of the path: `com.acme`. Pick coordinates that match what the jars are already called wherever possible; renaming artifacts mid-migration is churn you do not need.

### The standard layout

Maven's most visible convention is the standard directory layout. The compiler, resources plugin, jar plugin, and every other lifecycle plugin look in fixed, well-known directories, which is why a Maven project needs no per-plugin path configuration:

- **`src/main/java`** — the project's own Java sources (what Ant compiled into the jar).
- **`src/main/resources`** — resources bundled into the jar alongside the classes: property files, XML descriptors, and so on.
- **`src/test/java`** — test sources, compiled separately so they never land in the main artifact.
- **`src/test/resources`** — resources used only by tests.
- **`target/`** — the build output directory: compiled classes, the packaged jar, test reports, and everything else generated by the build. It is fully regenerable and should never be committed to version control. This is the counterpart of Ant's `build/` (and `dist/`) directories.

For a project whose Java package root is `com.acme`, the populated layout looks like this:

```text
acme-core/
├── pom.xml
├── src/
│   ├── main/
│   │   ├── java/
│   │   │   └── com/
│   │   │       └── acme/
│   │   │           ├── Core.java
│   │   │           └── util/
│   │   │               └── Strings.java
│   │   └── resources/
│   │       └── acme-core.properties
│   └── test/
│       ├── java/
│       │   └── com/
│       │       └── acme/
│       │           └── util/
│       │               └── StringsTest.java
│       └── resources/
│           └── test-fixtures.xml
└── target/                (generated; never committed)
    ├── classes/
    └── acme-core-1.0.0-SNAPSHOT.jar
```

### Preferred path: move sources to the standard layout

The strongly preferred migration is to physically move your sources into the standard layout. A one-time directory move is cheap — a handful of `git mv` commands and a commit — whereas keeping a nonstandard layout means every Maven configuration you write in later chapters carries the override with it, and every tool that assumes the convention (IDE import, code coverage, formatting plugins, container builds) needs the same exception repeated.

Assume acme-core's legacy Ant layout puts its Java sources under `src/com/acme/core` (a common pattern: a `src/` root holding the package tree directly), with no separated resources or test tree yet. The move is:

```bash
mkdir -p src/main/java src/main/resources src/test/java src/test/resources
git mv src/com/acme/core src/main/java/com/acme/core
rmdir src/com src/com/acme 2>/dev/null || true
# if any non-Java files sat alongside the sources, move them into resources:
# git mv src/some.properties src/main/resources/some.properties
git commit -m "Move sources to standard Maven layout"
```

After this, `src/` contains only `main/` and `test/`, and the POM needs no layout configuration at all — the single most valuable outcome of this chapter.

If your legacy layout is more tangled (for example, main and test sources interleaved under one tree, per Chapter 2's blocker list), untangle them into `src/main/java` and `src/test/java` in separate commits so each move is easy to review and revert. Chapter 6, which migrates tests, depends on the test tree existing by then.

### Alternative path: keep the legacy layout with overrides

If a physical move is not feasible right now — perhaps other tools, scripts, or release processes hard-code the current paths — Maven will accept an overridden layout. But treat this as a bridge, not a destination. Before the move, acme-core's Ant build assumes its layout via properties:

```xml
<project name="acme-core" default="compile" basedir=".">
  <property name="src.dir" value="src/com/acme/core"/>
  <target name="compile" description="Compile sources from legacy layout">
    <javac srcdir="${src.dir}" destdir="${build.dir}/classes"
           source="1.8" target="1.8"/>
  </target>
</project>
```

The equivalent Maven POM points the compiler and resources plugins at the legacy locations:

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
                             http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.acme</groupId>
  <artifactId>acme-core</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <packaging>jar</packaging>

  <build>
    <sourceDirectory>src/com/acme/core</sourceDirectory>
    <testSourceDirectory>test/com/acme/core</testSourceDirectory>
    <resources>
      <resource>
        <directory>config</directory>
      </resource>
    </resources>
    <testResources>
      <testResource>
        <directory>test/config</directory>
      </testResource>
    </testResources>
  </build>
</project>
```

The warnings that come with this approach:

- **Every tool that assumes the convention needs the same exception.** IDEs usually pick the override up from the POM, but code coverage agents, formatter plugins, security scanners, and hand-written scripts that walk the tree will not.
- **Snippets and documentation you copy from the Maven ecosystem assume `src/main/java`.** Every path you read in a plugin example is a path you must mentally translate.
- **Later chapters inherit the override.** Each plugin introduced in Chapters 5 through 7 gets a little more configuration that exists only to compensate for the layout.

If you take this path, schedule the physical move as an explicit follow-up. The override block is deletable the day the move completes, and deleting it should be its own commit.

### The baseline POM

With the layout settled, the chapter's main deliverable: the POM itself. The Ant side of the before/after is the `project` element and the compiler settings it drives — here reduced to the pieces the baseline POM replaces (the `jar` packaging via the `default` target, and the `javac` flags):

```xml
<project name="acme-core" default="jar" basedir=".">
  <property name="src.dir" value="src"/>
  <property name="build.dir" value="build"/>

  <target name="compile">
    <javac srcdir="${src.dir}" destdir="${build.dir}/classes"
           source="1.8" target="1.8" encoding="UTF-8"/>
  </target>

  <target name="jar" depends="compile">
    <jar destfile="dist/acme-core-1.0.0.jar" basedir="${build.dir}/classes"/>
  </target>
</project>
```

And the after — the complete minimal `pom.xml` for acme-core. Note how the Ant build's compiler settings translate into properties rather than plugin configuration: `maven-compiler-plugin` reads `maven.compiler.source` and `maven.compiler.target`, and the resources and compiler plugins read `project.build.sourceEncoding`, so three properties configure the whole compile-and-package pipeline. This is the acme-core version bump from Chapter 2's Java 8 to Java 11:

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
                             http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.acme</groupId>
  <artifactId>acme-core</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <packaging>jar</packaging>

  <properties>
    <maven.compiler.source>11</maven.compiler.source>
    <maven.compiler.target>11</maven.compiler.target>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
  </properties>
</project>
```

The mapping from the Ant build, item by item:

| Ant construct | Baseline POM equivalent |
| --- | --- |
| `<project name="acme-core">` | `groupId`/`artifactId`/`version` coordinates |
| `default="jar"` | `<packaging>jar</packaging>` (also the default) |
| `javac source="1.8" target="1.8"` | `maven.compiler.source`/`maven.compiler.target` = 11 |
| `javac encoding="UTF-8"` | `project.build.sourceEncoding` = UTF-8 |
| `dist/acme-core-1.0.0.jar` | `target/acme-core-1.0.0-SNAPSHOT.jar`, named from coordinates |
| `clean` target | `mvn clean` (the clean lifecycle, built in) |

Three things the POM does not contain yet, deliberately: dependencies (Chapter 2's classpath inventory becomes `<dependency>` entries in Chapter 4), test configuration (Chapter 6), and any plugin beyond the built-in defaults (Chapter 5). The `javac debug="on"` and the `com/acme/legacy/**` exclude from Chapter 2's excerpt are also deferred — debug is on by default in the compiler plugin, and the exclude moves into compiler configuration in Chapter 5.

### Verify the baseline

From the project root:

```bash
mvn clean package
```

On the baseline POM this compiles `src/main/java` with Java 11 and produces `target/acme-core-1.0.0-SNAPSHOT.jar`. If compilation fails on Java-8-era APIs or language constructs removed since, fix those compile errors now — they are exactly the kind of issue you want surfaced while the build is still trivial, not after dependencies and plugins have piled on.

The checklist for this phase:

- [ ] Coordinates chosen to match existing jar names and package root
- [ ] Sources physically moved to the standard layout (or a dated follow-up scheduled if overrides were used)
- [ ] `mvn clean package` succeeds and produces the expected jar under `target/`
- [ ] Compiler level set to the agreed target (Java 11 for acme-core) via properties
- [ ] `project.build.sourceEncoding` matches what the Ant `javac` used

## 4. Phase 2: Dependencies

TODO: content

## 5. Phase 3: Map Build Steps to Plugins

TODO: content

## 6. Phase 4: Migrate Tests

TODO: content

## 7. Phase 5: Custom Ant Tasks and the Antrun Escape Hatch

TODO: content

## 8. Phase 6: Multi-Module Builds

TODO: content

## 9. Phase 7: Profiles, Properties, Environments

TODO: content

## 10. Phase 8: CI/CD and Release

TODO: content

## 11. Phase 9: Cutover and Decommissioning

TODO: content

## 12. Troubleshooting and Common Pitfalls

TODO: content

## Appendix A: Ant Task to Maven Plugin Mapping

TODO: content
