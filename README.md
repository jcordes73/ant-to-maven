# Migrating from Apache Ant to Apache Maven

A practical, phase-by-phase guide for teams moving Ant-based Java builds to Maven.

## Table of Contents

- [1. Introduction](#1-introduction)
- [2. Phase 0: Assess the Existing Build](#2-phase-0-assess-the-existing-build)
- [3. Phase 1: Scaffold the POM](#3-phase-1-scaffold-the-pom)
- [4. Phase 2: Dependencies](#4-phase-2-dependencies)
- [5. Phase 3: Map Build Steps to Plugins](#5-phase-3-map-build-steps-to-plugins)
- [6. Phase 4: Migrate Tests](#6-phase-4-migrate-tests)
- [7. Packaging Web Applications (WAR)](#7-packaging-web-applications-war)
- [8. Phase 5: Custom Ant Tasks and the Antrun Escape Hatch](#8-phase-5-custom-ant-tasks-and-the-antrun-escape-hatch)
- [9. Phase 6: Multi-Module Builds](#9-phase-6-multi-module-builds)
- [10. Phase 7: Profiles, Properties, Environments](#10-phase-7-profiles-properties-environments)
- [11. Phase 8: CI/CD and Release](#11-phase-8-cicd-and-release)
- [12. Phase 9: Cutover and Decommissioning](#12-phase-9-cutover-and-decommissioning)
- [13. Troubleshooting and Common Pitfalls](#13-troubleshooting-and-common-pitfalls)
- [Appendix A: Ant Task to Maven Plugin Mapping](#appendix-a-ant-task-to-maven-plugin-mapping)

## 1. Introduction

Apache Ant served the Java community well for over two decades, and many production builds still depend on it. But the broader ecosystem has standardized on Maven and, increasingly, on the project model Maven established. This guide is for teams that have decided to migrate — or are deciding — and want a practical, phase-by-phase path rather than a rewrite from scratch.

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

That said, the window for migration is wider than it first appears. The `maven-antrun-plugin`, covered in Chapter 8, lets you run Ant targets and scripts from within a Maven build, so procedural islands can be carried over incrementally instead of being eliminated up front.

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
3. **Custom tasks and where their classes come from.** Find every `<taskdef>` and `<typedef>`, and note whether the implementing classes come from a jar on the classpath, from the project's own compiled code, or from a bundled tool. Custom tasks are the single most common migration blocker, so you want the full list early. Chapter 8 covers what to do with them.
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
- **Procedural steps with no plugin equivalent** — arbitrary file surgery, orchestration, or shell logic embedded in targets. The escape hatch is the `maven-antrun-plugin`, which lets you keep those targets as-is while everything else moves to Maven, covered in Chapter 8.

If a blocker dominates the build rather than decorating it, revisit the "When not to migrate" discussion in Chapter 1 before investing further.

### Where the inventory goes

Keep the inventory in a short document next to the project (a `MIGRATION-NOTES.md` is fine). Every later chapter of this guide starts from it: the POM scaffold in Chapter 3 consumes the packaging and compiler settings, Chapter 4 consumes the classpath inventory, and Chapter 5 consumes the generated-source and copy/filter steps. When a chapter says "check your inventory," this is the document it means.

## 3. Phase 1: Scaffold the POM

Phase 1 produces the first real Maven artifact: a minimal, buildable `pom.xml` that compiles your sources with the correct Java version and produces the same packaging your Ant build did. It does not yet carry dependencies, tests, or plugin mappings — those arrive in Chapters 4 through 8. The goal here is a baseline so clean that every later chapter is a small, reviewable increment on top of it.

This chapter uses the acme-core example from Chapter 2: currently an Ant build compiling with `javac source="1.8" target="1.8"` from a `src/` directory. By the end of the chapter, acme-core is a Maven project on Java 11 with a standard layout.

### Coordinates: naming your project

Maven identifies every artifact with three required coordinates plus a packaging type:

- **groupId** — the organization or team that owns the artifact, written as a reversed domain name. It exists to keep artifacts from different organizations from colliding, and it typically mirrors your Java package root. For acme-core: `com.acme`.
- **artifactId** — the name of the artifact within that group. It should match the jar your build already produces and, usually, the project's directory name. For acme-core: `acme-core`.
- **version** — the version string. Maven has a strong convention that in-development versions end in `-SNAPSHOT` (mutable, rebuilt freely) while release versions do not (immutable, published once). For acme-core: `1.0.0-SNAPSHOT`.
- **packaging** — the type of artifact the build produces: `jar` (the default), `war`, `pom` (for aggregator parents, covered in Chapter 9), and others. For acme-core: `jar`.

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
- **Later chapters inherit the override.** Each plugin introduced in Chapters 5 through 8 gets a little more configuration that exists only to compensate for the layout.

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

Phase 2 replaces the Ant classpath — the `lib/` directory of hand-collected jars — with Maven's dependency model. This is the phase where the migration starts paying for itself: jars are named by coordinates instead of filenames, transitive dependencies arrive automatically, and version conflicts become visible instead of silently tolerated. The deliverable is a `<dependencies>` section on the acme-core POM from Chapter 3, plus a strategy for the jars Maven cannot fetch on its own.

This chapter consumes the classpath inventory from Chapter 2: every jar on every `<path>` and `<classpath>` element becomes a `<dependency>` entry here.

### From `lib/` jars to managed dependencies

In the Ant build, dependencies are files. The `compile.classpath` path from Chapter 2's excerpt sweeps every jar in `lib/` into the classpath, and the only thing distinguishing a compile-time jar from a test-only one is which paths reference it:

```xml
<project name="acme-core" default="compile" basedir=".">
  <property name="lib.dir" value="lib"/>

  <path id="compile.classpath">
    <fileset dir="${lib.dir}">
      <include name="*.jar"/>
    </fileset>
  </path>

  <path id="test.classpath">
    <path refid="compile.classpath"/>
    <fileset dir="${lib.dir}/test">
      <include name="*.jar"/>
    </fileset>
  </path>
</project>
```

In Maven, dependencies are coordinates. Each jar becomes a `groupId:artifactId:version` triple plus a scope, and Maven fetches the jar itself from a repository. Translating the classpath inventory, acme-core's `<dependencies>` section lists the same jars by name instead of by filename:

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

  <dependencies>
    <dependency>
      <groupId>org.apache.commons</groupId>
      <artifactId>commons-lang3</artifactId>
      <version>3.14.0</version>
    </dependency>
    <dependency>
      <groupId>org.apache.logging.log4j</groupId>
      <artifactId>log4j-api</artifactId>
      <version>2.23.1</version>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <version>5.10.2</version>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

Notice what disappeared: the split between `compile.classpath` and `test.classpath` is now expressed by scope rather than by separate path definitions, and nothing in the build refers to a `lib/` directory at all. Delete the `lib/` directory only after the build compiles and tests pass without it — but delete it in the same migration, or it will keep growing.

The scope decides which classpaths a dependency lands on, and it is the direct replacement for the Ant pattern of maintaining separate `<path>` elements per target:

| Scope | Available at compile time | Available at runtime | Typical use |
| --- | --- | --- | --- |
| `compile` (default) | yes | yes | libraries the code itself uses, like `commons-lang3` |
| `provided` | yes | no (expected from the container/JVM) | servlet API in a war, annotation processors, Lombok |
| `runtime` | no | yes | JDBC drivers, service-loader implementations |
| `test` | test compile and test runtime only | test runtime only | JUnit, test fixtures, assertion libraries |
| `system` | yes | no | a jar on the local disk, referenced by absolute path |

When in doubt, omit `<scope>` — the default is `compile`, which is what most jar-in-`lib/` relationships were in the Ant build anyway. Two cautions:

- **`system` scope is deprecated and a last resort.** It points at a jar via an absolute path (`<systemPath>`), which defeats everything the migration is buying you: no transitive resolution, no repository, no reproducibility on other machines. If you reach for it, treat that as a marker that the jar needs a real home (see "Internal jars" below) and fix the underlying problem instead.
- **A jar used by both main code and tests is `compile`, not `test`.** Scope `test` means the main sources cannot see it, so the compiler will reject imports that the Ant build allowed. This is a common and healthy breakage: it surfaces an accidental test-to-main dependency.

### Transitive resolution

In the Ant build, if `commons-lang3` needed another jar, someone had to know that and drop that jar into `lib/` too. Maven does this for you: when you declare a dependency, Maven also fetches *its* dependencies, recursively, along with the versions those projects declare. This is transitive resolution, and it is the single largest deletion from your dependency inventory — the jars in `lib/` that existed only because some other jar needed them do not get `<dependency>` entries at all.

The command for seeing what actually ended up on your classpath is:

```bash
mvn dependency:tree
```

This prints the full resolved graph, your direct dependencies at the top level and everything they pulled in beneath them, with the scope of each node. Two things to do with it during the migration:

- **Compare it against the `lib/` inventory.** Every jar in `lib/` should either appear in the tree or be accounted for (not needed, or replaced by an API that moved into the JDK). A jar in `lib/` that does not appear in the tree was probably dead weight; a jar the code imports that is missing from the tree is a missing `<dependency>`.
- **Use it to find coordinates.** For a jar whose filename you know but whose coordinates you do not, search Maven Central (https://central.sonatype.com/) by filename — its search indexes artifacts by name, and a SHA-1 hash of the jar file also works if the filename is opaque. The search result gives you the `groupId`, `artifactId`, and available versions to paste into the `<dependency>` entry.

### Version conflicts: what Ant silently tolerated

The `lib/` directory accumulates versions: `commons-lang-2.6.jar` and `commons-lang3-3.14.0.jar` can sit side by side for years, with different code paths picking up whichever one the classloader finds first. Worse, two jars can both bundle (not just depend on) different versions of a third library, and the Ant build never complains — it just behaves differently depending on classpath order, which is exactly the kind of bug that surfaces in production and not in development.

Maven refuses to put two versions of the same artifact on one classpath. When the dependency graph contains two versions of the same `groupId:artifactId`, Maven resolves the conflict with a *nearest-wins* rule: the version closest to the root of the dependency tree (that is, declared directly by your project, or reached through the fewest intermediate dependencies) wins, and the other version is silently omitted. Nearest-wins is deterministic, which makes the build reproducible — but the winner may not be the version you wanted, so verify rather than assume.

To see conflicts as they are resolved, run the tree with the verbose flag:

```bash
mvn dependency:tree -Dverbose
```

Omitted versions are marked `omitted for conflict` (nearest-wins picked another version) or `omitted for duplicate` (the same version was reached twice). Any `omitted for conflict` line is a version decision Maven made on your behalf; check each one.

When you want the decision made by you instead of by tree distance, pin the version with `<dependencyManagement>`. This section declares versions without adding dependencies: every module and transitive path that references the artifact is forced to the version you name, and the artifact still has to be declared in `<dependencies>` (usually without a version) to land on the classpath:

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

  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>org.apache.logging.log4j</groupId>
        <artifactId>log4j-api</artifactId>
        <version>2.23.1</version>
      </dependency>
    </dependencies>
  </dependencyManagement>
</project>
```

For acme-core, where transitive dependencies first appear is when log4j or JUnit pull in their own modules; those arrive at the versions their publishers tested together, which is usually what you want, so start with no `<dependencyManagement>` at all and add pins only where the verbose tree shows a conflict you disagree with.

### Internal jars: the file repository stepping stone

Every migration has jars Maven Central cannot supply: shared company libraries, a vendor jar with no public repository, the custom Ant task jar itself. The Ant build's answer was a shared drive, and a `<copy>` (or `<available>`/`<fail>` check) to fetch from it:

```xml
<project name="acme-core" default="fetch-libs" basedir=".">
  <property name="shared.drive" value="//fileserver/acme/libs"/>
  <property name="lib.dir" value="lib"/>

  <target name="fetch-libs" description="Copy shared jars from the company drive">
    <mkdir dir="${lib.dir}"/>
    <copy todir="${lib.dir}" failonerror="true">
      <fileset dir="${shared.drive}">
        <include name="acme-shared-2.3.0.jar"/>
        <include name="acme-ant-tasks-1.1.0.jar"/>
      </fileset>
    </copy>
  </target>
</project>
```

The end state is a repository manager — Nexus or Artifactory are the common choices — hosting `com.acme` artifacts, with the POM pointing at it via `<repositories>` in `settings.xml` or the POM, and developers deploying shared jars there with `mvn deploy`. That is infrastructure work, though, and it does not need to block the migration. The stepping stone is a file-based repository checked into the project: a `local-repo/` directory laid out in Maven's repository format (`com/acme/acme-shared/2.3.0/acme-shared-2.3.0.jar` and so on), declared in the POM:

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

  <repositories>
    <repository>
      <id>acme-local</id>
      <url>file://${project.basedir}/local-repo</url>
    </repository>
  </repositories>
</project>
```

With this in place, each internal jar is an ordinary `<dependency>` (`com.acme:acme-shared:2.3.0`) resolved from the checked-in directory, and the `copy`-from-shared-drive target is gone. The layout inside `local-repo/` is just the GAV path convention: `local-repo/com/acme/acme-shared/2.3.0/acme-shared-2.3.0.jar`. Treat the file repo as explicitly temporary: it exists so the POM can be finished before the repository manager is, and migrating `local-repo/` contents into Nexus or Artifactory (which then serves the same `com.acme` group) is the follow-up that closes it out.

### Build flags to properties

A smaller but related conversion: Ant builds pass build behavior in flags (`ant -Dcompile.debug=true`) and read them as properties inside `build.xml`. Maven uses the same mechanism — POM properties, overridable with `-D` on the command line:

```xml
<project name="acme-core" default="compile" basedir=".">
  <property name="compile.debug" value="false"/>

  <target name="compile">
    <javac srcdir="src" destdir="build/classes"
           source="11" target="11" debug="${compile.debug}"/>
  </target>
</project>
```

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
    <maven.compiler.debug>true</maven.compiler.debug>
  </properties>
</project>
```

The Maven compiler plugin reads `maven.compiler.debug` as a property, so `mvn compile` builds with the default from the POM and `mvn compile -Dmaven.compiler.debug=false` overrides it from the command line — the same convention as `-Dcompile.debug=true`, with the POM supplying the default instead of the script. User-defined properties work the same way: any `<properties>` entry can be overridden with `-D` and referenced as `${name}` in plugin configuration. Chapter 10 revisits this pattern for environment-specific settings, where it becomes the basis for profiles.

### Phase 2 checklist

- [ ] Every jar from the classpath inventory is either a `<dependency>`, resolved transitively, or accounted for as unneeded
- [ ] Scopes assigned deliberately: `test` for test-only jars, `provided` for container-supplied ones, `compile` for everything in main code
- [ ] No `system`-scoped dependencies
- [ ] `mvn dependency:tree` reviewed against the `lib/` inventory; conflicts checked with `-Dverbose`
- [ ] Internal jars available via a repository (file-based `local-repo/` as the stepping stone, repository manager as the end state)
- [ ] `lib/` directory deleted and the copy-from-shared-drive target removed

## 5. Phase 3: Map Build Steps to Plugins

Phase 3 replaces the body of your Ant `build.xml` — the targets that compile, jar, copy, and package — with Maven plugins. The good news is that most Ant builds are a small set of common tasks, and each of those tasks has a direct, well-documented Maven equivalent. The work is not inventing configuration; it is reading each target in your inventory from Chapter 2 and translating it, one row at a time.

### The lifecycle: where Ant targets go

In Ant, you wire the build yourself: a `jar` target `depends` on `compile`, which `depends` on `init`, and the caller invokes the entry point. In Maven, the wiring already exists. The build is a fixed sequence of lifecycle phases — `validate`, `compile`, `test`, `package`, `verify`, `install`, `deploy` — and each phase runs in order. When you run `mvn package`, Maven runs everything up to and including `package`: resources are copied, sources compiled, tests run, and the jar assembled. You never declare that `jar` depends on `compile`, because that relationship is built into the lifecycle.

Plugins are what do the work at each phase. A plugin contributes *goals* (individual executable units, written `plugin-artifact:goal` — for example `maven-compiler-plugin:compile`), and goals bind to phases. The built-in lifecycle bindings mean a POM with no plugin configuration at all already compiles and jars: `maven-compiler-plugin`'s `compile` goal is bound to the `compile` phase, `maven-surefire-plugin`'s `test` goal to the `test` phase, and `maven-jar-plugin`'s `jar` goal to the `package` phase. Your Phase 3 work is therefore mostly of two kinds: configuring the plugins that are already bound (compiler options, manifest entries, resource filtering) and, where an Ant target did something the lifecycle does not cover, adding a plugin and binding one of its goals to a phase yourself. Appendix A has the full task-by-task mapping; the table below covers the tasks that account for nearly all of a typical build file.

### The core mapping

| Ant task | Maven plugin | Notes |
| --- | --- | --- |
| `javac` | `maven-compiler-plugin` | Bound to `compile` by default. Java version via `maven.compiler.*` properties (already set in the baseline POM). |
| `jar` | `maven-jar-plugin` | Bound to `package` by default. Manifest, includes/excludes via its `archive` configuration. |
| `war` | `maven-war-plugin` | Bound to `package` when `<packaging>war</packaging>`. Replaces the `war` target and its `lib/` assembly. |
| `copy` (with `filterset`) | `maven-resources-plugin` | Bound to `process-resources` and `process-test-resources`. Filtering enabled per resource directory. |
| `delete`, `mkdir` | `maven-clean-plugin` | Usually deleted, not converted: `target/` is created and wiped by the lifecycle's conventions, not by explicit tasks. |
| `junit` | `maven-surefire-plugin` | Bound to `test`. Runs everything matching `*Test` naming conventions; reports under `target/surefire-reports/`. |
| `javadoc` | `maven-javadoc-plugin` | Run on demand (`mvn javadoc:javadoc`) or bound to the `verify`/`package` phase for release builds. |
| `zip`, `tar` | `maven-assembly-plugin` | Bound to `package` with a descriptor. Replaces distribution-archive targets. |
| fat jar (one-jar style merges) | `maven-shade-plugin` | Bound to `package`. Replaces the unpack-everything-into-one-jar target. |
| everything else | `maven-antrun-plugin` | The escape hatch: embed any Ant task in the lifecycle. Covered fully in Chapter 8. |

Two rows deserve emphasis before the examples. First, `delete` and `mkdir`: in Ant these exist because the build must create and reset its own scratch directories. Maven's standard layout removes the need — `target/` is created on demand and wiped by `mvn clean` — so the correct migration for a `clean` target that deletes `build/` and `dist/` is deletion of the target itself, not a `maven-clean-plugin` configuration. If a `delete` target removes something other than build output (a scratch file, a downloaded artifact), that is a different conversation, and Chapter 8 covers how to keep it. Second, `junit`: Ant's `<junit>` block with its `<batchtest>` is replaced not just by the surefire plugin but by its conventions — test classes named `*Test`, `Test*`, or `*Tests` in `src/test/java` are discovered automatically. Chapter 6 covers the details, including `@RunWith`/`@Nested` edge cases and nonstandard names.

### Compiling: `javac` vs `maven-compiler-plugin`

The Ant side, from the baseline POM chapter:

```xml
<target name="compile">
  <javac srcdir="${src.dir}" destdir="${build.dir}/classes"
         source="1.8" target="1.8" encoding="UTF-8" debug="on"/>
</target>
```

The Maven side. Note that acme-core's baseline POM already covers this target: the `maven.compiler.source`/`maven.compiler.target` and `project.build.sourceEncoding` properties configure the compiler plugin, and `debug` is on by default. Configuration in the POM is only needed for what the properties cannot express — here, the `com/acme/legacy/**` exclude deferred from Chapter 2:

```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-compiler-plugin</artifactId>
      <configuration>
        <excludes>
          <exclude>com/acme/legacy/**</exclude>
        </excludes>
      </configuration>
    </plugin>
  </plugins>
</build>
```

Keep compiler settings in properties wherever possible. Plugin configuration for source/target/encoding is redundant with the properties and tends to drift from them; a future reader cannot tell which one wins without knowing Maven's precedence rules. Reserve compiler-plugin configuration for includes, excludes, annotation processor settings, and things properties genuinely cannot do.

### Packaging the jar: `jar` vs `maven-jar-plugin`

A typical Ant `jar` target with a manifest:

```xml
<target name="jar" depends="compile">
  <mkdir dir="dist"/>
  <jar destfile="dist/acme-core-1.0.0.jar" basedir="${build.dir}/classes">
    <manifest>
      <attribute name="Main-Class" value="com.acme.Core"/>
      <attribute name="Implementation-Version" value="1.0.0"/>
    </manifest>
  </jar>
</target>
```

The equivalent `maven-jar-plugin` configuration. The `archive` element replaces the nested `<manifest>`, and `addDefaultImplementationEntries` pulls `Implementation-Version` from the POM coordinates rather than a hard-coded value. Note there is no `destfile` and no `basedir`: the jar is always `target/<finalName>.jar`, built from `target/classes/`, because those locations are lifecycle conventions:

```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-jar-plugin</artifactId>
      <configuration>
        <archive>
          <manifest>
            <mainClass>com.acme.Core</mainClass>
            <addDefaultImplementationEntries>true</addDefaultImplementationEntries>
          </manifest>
        </archive>
      </configuration>
    </plugin>
  </plugins>
</build>
```

Two things to check when translating a `jar` target: whether it used `includes`/`excludes` to split classes across multiple jars (Maven strongly prefers one artifact per module — split with a multi-module build per Chapter 9 rather than per-jar filters), and whether it jars anything other than compiled classes. A jar that bundles `lib/*.jar` inside it is not a plain jar — that is a shaded jar, covered below.

### Resources: `copy` with `filterset` vs `maven-resources-plugin` filtering

The Ant pattern — copy a properties file and substitute tokens while copying:

```xml
<target name="resources" depends="init">
  <copy todir="${build.dir}/classes" filtering="true">
    <fileset dir="config"/>
    <filterset>
      <filter token="project.version" value="1.0.0"/>
      <filter token="build.timestamp" value="${TODAY}"/>
    </filterset>
  </copy>
</target>
```

The Maven equivalent: resources in `src/main/resources` are copied and (with filtering on) token-substituted by `maven-resources-plugin` automatically — no configuration beyond switching filtering on. Note that Ant's `<filterset>` already defaults to `@token@` delimiters, and Maven's resources plugin substitutes both `${token}` and `@token@` by default, so writing tokens as `@token@` does not by itself protect `${}` placeholders that Spring or another framework needs at runtime — that requires restricting Maven to `@`-only delimiters (shown below):

```xml
<build>
  <resources>
    <resource>
      <directory>src/main/resources</directory>
      <filtering>true</filtering>
    </resource>
  </resources>
</build>
```

With filtering enabled, a resource like `application.properties` that contained Ant-style tokens is rewritten to use the `@token@` form, and the tokens resolve from the POM's project properties:

```properties
app.name=@project.artifactId@
app.version=@project.version@
build.jdk=@java.version@
```

After the migration, `app.version` resolves to `1.0.0-SNAPSHOT` from the POM, with no per-release filter file to update. (`@java.version@` is the exception — it resolves from the JVM system properties of the JDK running the build, which is not necessarily the target Java version.)

If your filtered resources contain `${...}` placeholders that must survive to runtime — Spring's `@Value("${some.key}")` injection is the common case — restrict the plugin to `@`-only delimiters so Maven leaves `${...}` alone:

```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-resources-plugin</artifactId>
      <configuration>
        <useDefaultDelimiters>false</useDefaultDelimiters>
        <delimiters>
          <delimiter>@</delimiter>
        </delimiters>
      </configuration>
    </plugin>
  </plugins>
</build>
```

With this configuration, only `@token@` references are substituted and any unfiltered `${...}` placeholders pass through the copied resources verbatim. A caution that applies to the whole row: filtering is a per-resource-directory switch, and enabling it on a directory holding binary files (images, keystores) corrupts them. If `src/main/resources` mixes both, split binaries into a second `<resource>` entry with `filtering` left off. Also prefer `@project.version@` over Ant-style timestamp filters — a timestamp in a resource makes every build's output differ byte-for-byte, which breaks reproducible builds and bloats artifact repositories. If a filter value genuinely has no POM equivalent, define it as a `<property>` and reference it the same way.

### Distribution archives: `zip` vs `maven-assembly-plugin`

The Ant distribution target — jar, docs, and scripts zipped together:

```xml
<target name="dist" depends="jar">
  <mkdir dir="dist"/>
  <zip destfile="dist/acme-core-1.0.0-distribution.zip">
    <zipfileset dir="dist" includes="acme-core-1.0.0.jar"/>
    <zipfileset dir="docs" prefix="docs"/>
    <zipfileset dir="scripts" prefix="bin" filemode="755"/>
  </zip>
</target>
```

The Maven equivalent is `maven-assembly-plugin` with a descriptor, bound to the `package` phase. For the common case of "the jar plus its dependencies, runnable," the built-in `jar-with-dependencies` descriptor needs no descriptor file at all:

```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-assembly-plugin</artifactId>
      <configuration>
        <descriptorRefs>
          <descriptorRef>jar-with-dependencies</descriptorRef>
        </descriptorRefs>
        <archive>
          <manifest>
            <mainClass>com.acme.Core</mainClass>
          </manifest>
        </archive>
      </configuration>
      <executions>
        <execution>
          <id>make-assembly</id>
          <phase>package</phase>
          <goals>
            <goal>single</goal>
          </goals>
        </execution>
      </executions>
    </plugin>
  </plugins>
</build>
```

This produces `target/acme-core-1.0.0-SNAPSHOT-jar-with-dependencies.jar` during `mvn package`, with no separate target to remember to run. If the archive genuinely bundles non-jar content like `docs/` and executable scripts (with their permissions), write a custom assembly descriptor (`src/assembly/distribution.xml`) that mirrors the `zipfileset` layout — the `<fileSets>` element with `<directoryMode>` and `<fileMode>` is the direct translation. The full descriptor format is in the plugin's documentation; the principle for this guide is that assembly descriptors live in the project under `src/assembly/`, are versioned with the code, and are reproducible on every machine — which a `zip` target that walks whatever happens to be in `dist/` at the time is not.

### Fat jars: one-jar-style merges vs `maven-shade-plugin`

Some Ant builds do not zip the dependencies alongside the jar; they merge them *into* it — unpacking every jar in `lib/` into one directory and jarring the result, so the application is a single classpath-free file:

```xml
<target name="onejar" depends="jar,resolve-libs">
  <mkdir dir="${build.dir}/onejar"/>
  <unzip dest="${build.dir}/onejar">
    <fileset dir="lib" includes="*.jar"/>
  </unzip>
  <copy todir="${build.dir}/onejar" overwrite="true">
    <fileset dir="${build.dir}/classes"/>
  </copy>
  <jar destfile="dist/acme-core-1.0.0-onejar.jar" basedir="${build.dir}/onejar"/>
</target>
```

This target has a subtle, well-known bug: when two dependency jars both contain, say, `META-INF/services/org.slf4j.spi.SLF4JServiceProvider` (service loader files) or overlapping `META-INF/LICENSE` entries, the last-unpacked jar wins and the others are silently dropped — a build-order-dependent failure that works on one machine and breaks on another. The `maven-shade-plugin` exists precisely to do this merge correctly, and its transformers handle the conflicts explicitly:

```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-shade-plugin</artifactId>
      <executions>
        <execution>
          <phase>package</phase>
          <goals>
            <goal>shade</goal>
          </goals>
          <configuration>
            <transformers>
              <transformer implementation="org.apache.maven.plugins.shade.resource.ServicesResourceTransformer"/>
              <transformer implementation="org.apache.maven.plugins.shade.resource.ManifestResourceTransformer">
                <mainClass>com.acme.Core</mainClass>
              </transformer>
            </transformers>
          </configuration>
        </execution>
      </executions>
    </plugin>
  </plugins>
</build>
```

`ServicesResourceTransformer` merges `META-INF/services/` files by concatenating their contents instead of overwriting, which fixes the bug the Ant build carried. Migrating to shade also replaces the `lib/`-driven `resolve-libs` dependency: shade works from the POM's `<dependency>` graph (Chapter 4's work), not from whatever jars are present in a directory. Expect the shaded jar to surface dependency problems the Ant build hid — duplicate classes from conflicting versions in the dependency tree become visible with the shade plugin's warnings, and `mvn dependency:tree -Dverbose` from Chapter 4 is the tool for resolving them.

### Generated sources: codegen targets vs `build-helper-maven-plugin`

Many Ant builds generate source code into a scratch directory before compiling — JAXB classes from schemas, parsers from grammars, or in-house code generators. The Ant pattern:

```xml
<target name="codegen" depends="init">
  <mkdir dir="build/gen"/>
  <java classname="com.acme.tools.CodeGen" fork="true">
    <arg value="-o"/>
    <arg value="build/gen"/>
    <arg value="src/main/schema/model.json"/>
  </java>
  <!-- the compile target then adds build/gen to its srcdir -->
</target>
```

In Maven, generated sources are just another source directory added before the `compile` phase runs. The `build-helper-maven-plugin`'s `add-source` goal registers the directory, and the generator itself runs earlier in the build:

```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.codehaus.mojo</groupId>
      <artifactId>build-helper-maven-plugin</artifactId>
      <executions>
        <execution>
          <id>add-generated-sources</id>
          <phase>generate-sources</phase>
          <goals>
            <goal>add-source</goal>
          </goals>
          <configuration>
            <sources>
              <source>target/generated-sources/acme</source>
            </sources>
          </configuration>
        </execution>
      </executions>
    </plugin>
  </plugins>
</build>
```

The directory you register should live under `target/generated-sources/` — IDEs recognize that path as generated and exclude it from refactoring and formatting. Before reaching for a hand-run generator, though, check whether a Maven plugin exists for it: most generators do, and they are the better answer. JAXB has `jaxb2-maven-plugin` and the `maven-jaxb2-plugin`, ANTLR has `antlr4-maven-plugin`, and both bind their generation goal to the `generate-sources` phase and register their output directory automatically — no `build-helper-maven-plugin` needed. The `add-source` approach above is the tool for in-house generators, invoked via `maven-antrun-plugin` or `exec-maven-plugin` bound to `generate-sources` before the `add-source` execution. The order matters: the generation must run before the sources are registered and compiled, which the `generate-sources` phase guarantees.

### Phase 3 checklist

- [ ] Every target in the Chapter 2 inventory mapped to a row in the table above (or flagged for Chapter 8's Antrun escape hatch)
- [ ] Compiler settings left in properties; compiler-plugin configuration only for includes/excludes and processors
- [ ] `maven-jar-plugin` manifest (if any) translated, with versions pulled from coordinates rather than hard-coded
- [ ] Filtered resources switched to `@token@` form; binaries excluded from filtering
- [ ] Distribution `zip`/`tar` targets replaced with assembly descriptors (or removed if the jar suffices)
- [ ] Fat-jar merges replaced with `maven-shade-plugin` including `ServicesResourceTransformer`
- [ ] Generated-source directories registered via `build-helper-maven-plugin` (or a dedicated generator plugin) under `target/generated-sources/`
- [ ] `mvn clean package` produces the same artifact(s) the Ant build did, byte-comparable in content if not in name

## 6. Phase 4: Migrate Tests

Phase 4 replaces the test targets in your `build.xml` — the `<junit>` blocks, the hand-assembled test classpath, the report formatters, and any separate integration-test targets — with Maven's testing conventions. As in Phase 3, most of the work is deletion: the standard layout plus the Surefire plugin's defaults cover what a typical Ant test target does by hand.

### Unit tests: `junit` vs `maven-surefire-plugin`

The Ant side, typical of a build that grew organically. Note everything the target does manually: assembling the classpath from `lib/` and two build directories, selecting tests with an explicit include pattern, and configuring a report formatter:

```xml
<target name="test" depends="compile-tests">
  <mkdir dir="${build.dir}/test-reports"/>
  <junit printsummary="yes" haltonfailure="yes">
    <classpath>
      <pathelement path="${build.dir}/classes"/>
      <pathelement path="${build.dir}/test-classes"/>
      <fileset dir="lib" includes="*.jar"/>
    </classpath>
    <batchtest todir="${build.dir}/test-reports">
      <fileset dir="${test.dir}">
        <include name="**/*Test.java"/>
      </fileset>
    </batchtest>
    <formatter type="xml"/>
  </junit>
</target>
```

The Maven side is a command, not a target: `mvn test`. The `maven-surefire-plugin` is already bound to the `test` phase (as noted in Chapter 5), so the baseline POM from Chapter 3 already runs your tests. Surefire discovers every class in `src/test/java` whose name matches its conventions — `*Test`, `Test*`, `*Tests`, and `*TestCase` — so the explicit `<include name="**/*Test.java">` disappears. The classpath assembly disappears too: main classes plus test-scoped dependencies (acme-core's `junit-jupiter`, for example) are on the test classpath automatically. Reports in XML and plain-text form are written to `target/surefire-reports/` without a `<formatter>` element, and a failing test fails the build the way `haltonfailure="yes"` did.

You configure Surefire only when you are overriding a default. A common case is excluding slow or environment-dependent tests from every run:

```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-surefire-plugin</artifactId>
      <configuration>
        <excludes>
          <exclude>**/*SlowTest.java</exclude>
        </excludes>
      </configuration>
    </plugin>
  </plugins>
</build>
```

The one adjustment that may be needed is renaming. Test classes whose names do not match the conventions — `LegacyChecks`, `AllTheTestsRunner` — are silently not run by Surefire, which is worse than an Ant build that missed them, because in Ant the include list at least made the selection visible. Rename nonconforming classes as part of the migration, or add an explicit `<includes>` configuration for the stragglers and delete it as they are renamed.

### TestNG

If your tests use TestNG rather than JUnit, nothing above changes structurally: Surefire runs TestNG tests too, auto-detecting them from the classpath, and the same naming conventions apply. Where your Ant build drove TestNG through `testng` XML suite files, point Surefire at them with a `<suiteXmlFiles>` configuration; otherwise no configuration is needed at all.

### Test resources

In the Ant build, test fixtures — property files, sample XML, certificates — were usually another `<copy>` step into the test classpath directory, wired into the `test` target's `depends` chain. In Maven, test resources have a home: `src/test/resources`. Everything in that directory is copied onto the test classpath by the `process-test-resources` phase, before tests compile and run, with no configuration and no copy step. The same filtering described for main resources in Chapter 5 applies here: add `<filtering>true</filtering>` to the `src/test/resources` resource declaration if a fixture file contains tokens to substitute. Move the files, delete the copy step, and the test classpath looks after itself.

### Coverage: JaCoCo

Coverage in Ant means wrapping the `junit` task in a coverage tool's instrumentation and then generating a report from the execution data. With the JaCoCo Ant library:

```xml
<target name="coverage" depends="compile-tests" xmlns:jacoco="antlib:org.jacoco.ant">
  <jacoco:coverage destfile="${build.dir}/jacoco.exec">
    <junit printsummary="yes" haltonfailure="yes">
      <classpath path="${build.dir}/classes"/>
      <batchtest>
        <fileset dir="${test.dir}">
          <include name="**/*Test.java"/>
        </fileset>
      </batchtest>
    </junit>
  </jacoco:coverage>
</target>
```

followed, in most builds, by a second `jacoco:report` invocation to turn the `.exec` file into HTML — two more targets' worth of wiring to maintain. If your build used Cobertura instead, the pattern was similar but with its own instrumentation and report tasks, and Cobertura itself has been effectively unmaintained for years.

The Maven side is the `jacoco-maven-plugin` with two executions. The `prepare-agent` goal instruments the JVM before tests run (its default binding, `initialize`, is early enough), and the `report` goal turns the execution data into an HTML report under `target/site/jacoco`:

```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.jacoco</groupId>
      <artifactId>jacoco-maven-plugin</artifactId>
      <executions>
        <execution>
          <id>prepare-agent</id>
          <goals>
            <goal>prepare-agent</goal>
          </goals>
        </execution>
        <execution>
          <id>report</id>
          <phase>verify</phase>
          <goals>
            <goal>report</goal>
          </goals>
        </execution>
      </executions>
    </plugin>
  </plugins>
</build>
```

Binding `report` to the `verify` phase means `mvn verify` runs tests and then produces the coverage report — one command, no separate `coverage` target, and CI can collect the report from a known location. The explicit `<phase>verify</phase>` is technically redundant (it is the `report` goal's default binding) but is worth declaring so the intent is visible in the POM.

### Integration tests: Failsafe

Many Ant builds separate long-running or environment-dependent tests into a second target, run on demand or from a different CI job, so that `ant test` stays fast:

```xml
<target name="itest" depends="jar">
  <mkdir dir="${build.dir}/itest-reports"/>
  <junit printsummary="yes" haltonfailure="yes">
    <classpath>
      <pathelement path="${build.dir}/classes"/>
      <pathelement path="${build.dir}/test-classes"/>
      <fileset dir="lib" includes="*.jar"/>
    </classpath>
    <batchtest todir="${build.dir}/itest-reports">
      <fileset dir="${test.dir}">
        <include name="**/*IT.java"/>
      </fileset>
    </batchtest>
    <formatter type="xml"/>
  </junit>
</target>
```

Maven's equivalent is the `maven-failsafe-plugin`, which is Surefire's sibling for integration tests. It uses the same discovery machinery but with `*IT` naming conventions, so integration tests live alongside unit tests in `src/test/java` and are distinguished by name. Its two goals split the work: `integration-test` runs the tests (bound to the `integration-test` phase), and `verify` fails the build if any of them failed (bound to the `verify` phase). The split exists so that cleanup code can run between the two — a failing integration test does not prevent `post-integration-test` cleanup from executing:

```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-failsafe-plugin</artifactId>
      <executions>
        <execution>
          <goals>
            <goal>integration-test</goal>
            <goal>verify</goal>
          </goals>
        </execution>
      </executions>
    </plugin>
  </plugins>
</build>
```

With this in place, `mvn install` or `mvn verify` runs unit tests via Surefire and then integration tests via Failsafe, with reports under `target/failsafe-reports/`. Rename the classes picked up by the old `<include name="**/*IT.java">` to end in `IT` if they do not already (the include pattern and the convention usually agree), and delete the `itest` target.

### JUnit 4 vs JUnit 5

Acme-core's dependency from Chapter 4 is `junit-jupiter`, which brings the JUnit Platform that Surefire uses to discover and run tests. Running JUnit 5 tests requires Surefire 2.22.0 or newer; every current Maven version ships a compatible Surefire by default, so this is only worth checking if your POM or parent pins an older one. The migration trap is the reverse case: a codebase mid-migration that still has JUnit 4 tests. The JUnit Platform does not run them by default — add the `junit-vintage-engine` as a test-scoped dependency alongside `junit-jupiter`, and the platform runs both generations in the same `mvn test`. Plan to remove the vintage engine once the last JUnit 4 test is rewritten; its presence is a migration marker, not an end state.

### Phase 4 checklist

- [ ] Every `<junit>` block in the build.xml replaced by Surefire's defaults (or a deliberate `<includes>`/`<excludes>` override)
- [ ] Test classes renamed to match the conventions, or stragglers covered by explicit configuration
- [ ] Test fixtures moved to `src/test/resources`; Ant copy steps deleted
- [ ] Coverage via `jacoco-maven-plugin` `prepare-agent` + `report`, with the report produced by `mvn verify` under `target/site/jacoco`
- [ ] Integration tests migrated to Failsafe with `*IT` naming; the separate `itest` target deleted
- [ ] JUnit 4 legacy tests (if any) running under the vintage engine, with removal tracked
- [ ] `mvn verify` runs unit tests, integration tests, and produces both Surefire and JaCoCo reports

## 7. Packaging Web Applications (WAR)

If your Ant build produces a web application rather than a library jar, packaging is where the migration pays off most visibly: Maven has first-class WAR support built into the lifecycle, and the hand-assembled `WEB-INF/lib` staging that dominates most Ant web builds disappears entirely. This chapter covers the packaging switch, the war plugin that replaces the Ant `war` task, the container APIs that belong in `provided` scope, and the container and integration-test tooling that replaces Ant's deploy and smoke-test targets. It assumes the single-module story from Chapters 3 through 6; a web tier that depends on a core library becomes a multi-module build, covered in Chapter 9.

### The packaging switch: from `war` target to `war` packaging

In Ant, a WAR is something your build assembles: a `war` target (or a `zip`/`jar` target with a `WEB-INF` layout) that copies compiled classes, dependency jars, and web resources into a staging directory and zips the result. In Maven, a WAR is something your project *is*: the `<packaging>` element switches the lifecycle's default bindings from the jar plugin to the war plugin, and `mvn package` produces a `.war` with no per-target wiring.

A Maven webapp follows the standard layout from Chapter 3 plus one extra directory:

- **`src/main/java`** and **`src/main/resources`** — unchanged. Servlet classes, filters, listeners, and their classpath resources come from exactly the same places they did for acme-core's jar, and land in `WEB-INF/classes` in the archive.
- **`src/main/webapp`** — the web resources: JSPs, static assets, and `WEB-INF/web.xml`. Everything in this directory is copied into the root of the WAR as-is; it is the counterpart of the `docroot/`, `web/`, or `WebContent/` directory the Ant build staged from.
- **`target/`** — where `mvn package` produces `target/<finalName>.war`, named from the coordinates the same way a jar is.

The populated layout for a web module:

```text
acme-web/
├── pom.xml
└── src/
    ├── main/
    │   ├── java/
    │   │   └── com/
    │   │       └── acme/
    │   │           └── web/
    │   │               └── AcmeServlet.java
    │   ├── resources/
    │   │   └── messages.properties
    │   └── webapp/
    │       ├── WEB-INF/
    │       │   └── web.xml
    │       ├── index.jsp
    │       └── css/
    │           └── acme.css
    └── test/
        └── java/
            └── com/
                └── acme/
                    └── web/
                        └── AcmeServletTest.java
```

The packaging declaration is one element on the acme-web POM (acme-core from the previous chapters stays a jar; this is the web-tier module that depends on it):

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
                             http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.acme</groupId>
  <artifactId>acme-web</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <packaging>war</packaging>
</project>
```

With `<packaging>war</packaging>`, `mvn package` compiles `src/main/java`, copies `src/main/resources` into `WEB-INF/classes`, copies `src/main/webapp` into the archive root, and produces `target/acme-web-1.0.0-SNAPSHOT.war`. No staging directory, no copy targets, and no `war` task.

### The `war` task vs `maven-war-plugin`

A typical Ant `war` task assembles the archive piece by piece — compiled classes here, dependency jars there, web resources somewhere else:

```xml
<target name="war" depends="compile, resolve-libs">
  <mkdir dir="${build.dir}/webapp/WEB-INF"/>
  <war destfile="dist/acme-web-1.0.0.war"
       webxml="config/web.xml">
    <fileset dir="${build.dir}/webapp"/>
    <lib dir="${lib.dir}">
      <include name="*.jar"/>
      <exclude name="servlet-api*.jar"/>
    </lib>
    <classes dir="${build.dir}/classes"/>
    <webres dir="src/webres"/>
  </war>
</target>
```

Note what this target does by hand: assemble `WEB-INF/lib` from a `lib/` sweep (explicitly excluding the servlet API jar so it does not leak into the archive), copy compiled classes into `WEB-INF/classes`, and stage web resources from a nonstandard source directory. The Maven equivalent — with the standard layout — is the `maven-war-plugin`, which is bound to the `package` phase by the `war` packaging itself and needs no declaration at all for a conventional layout:

```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-war-plugin</artifactId>
      <configuration>
        <warSourceDirectory>src/main/webapp</warSourceDirectory>
        <webXml>src/main/webapp/WEB-INF/web.xml</webXml>
      </configuration>
    </plugin>
  </plugins>
</build>
```

The mapping from the Ant task, item by item:

| Ant `war` construct | `maven-war-plugin` equivalent |
| --- | --- |
| `<classes dir="${build.dir}/classes"/>` | `src/main/java` compiled and placed in `WEB-INF/classes` automatically |
| `<lib dir="${lib.dir}">` | the POM's `<dependencies>`, copied into `WEB-INF/lib` by scope (`compile` and `runtime`) |
| `<exclude name="servlet-api*.jar"/>` in `<lib>` | unnecessary — `provided`-scoped dependencies never enter the archive |
| `<fileset dir="${build.dir}/webapp"/>` | `warSourceDirectory`, defaulting to `src/main/webapp` |
| `webxml="config/web.xml"` | `<webXml>`, defaulting to `src/main/webapp/WEB-INF/web.xml` |
| `<webres dir="src/webres"/>` | files in `src/main/webapp` land at the archive root, no separate source |

The `warSourceDirectory` and `webXml` overrides are the escape hatch for legacy layouts, following the same pattern as the compiler and resources overrides in Chapter 3: point the plugin at where the old build kept its web sources, schedule the physical move into `src/main/webapp` as a follow-up, and delete the overrides when the move completes. For a project already on the standard layout, the entire `<plugin>` block above is redundant and should be removed — the defaults are the configuration.

One feature with no Ant counterpart is the overlay. An `<overlay>` merges another WAR — typically a dependency, such as a framework's prebuilt web fragment or your own base WAR — into the archive as it is assembled, with the current project's files taking precedence over the overlaid ones:

```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-war-plugin</artifactId>
      <configuration>
        <overlays>
          <overlay>
            <groupId>com.acme</groupId>
            <artifactId>acme-web-base</artifactId>
          </overlay>
        </overlays>
      </configuration>
    </plugin>
  </plugins>
</build>
```

Ant builds that needed this did it with manual `unzip`-and-recopy sequences that lost files on collisions; the plugin merges deterministically and reports conflicts. It is an advanced feature — skip it unless your build actually merges WARs — but it is the answer when you find that pattern in an old build file.

### JEE APIs: bundling vs `provided` scope

The most common and most damaging pattern in Ant web builds is bundling the container's own jars into the WAR. The Ant path looked like this:

```xml
<path id="web.classpath">
  <pathelement path="${build.dir}/classes"/>
  <fileset dir="${lib.dir}">
    <include name="*.jar"/>
  </fileset>
  <fileset dir="${j2ee.jar.dir}">
    <include name="servlet-api.jar"/>
    <include name="jsp-api.jar"/>
  </fileset>
</path>

<target name="war" depends="compile">
  <war destfile="dist/acme-web-1.0.0.war" webxml="config/web.xml">
    <classes dir="${build.dir}/classes"/>
    <lib dir="${lib.dir}"/>
  </war>
</target>
```

The servlet API jars are on the compile classpath (necessary — the code imports `javax.servlet.http.HttpServlet`), but nothing keeps them out of the archive, so `WEB-INF/lib` ships with a second copy of the servlet API. The servlet container supplies its own implementation of those APIs through the web application classloader hierarchy, and a bundled copy produces exactly the classloader conflicts the container spec exists to prevent: `ClassCastException`s on `HttpServletRequest`, `ClassCastException`-adjacent `LinkageError`s, or an application that works on one container version and fails on the next, depending on which copy of the class the classloader finds first.

Maven's answer is `provided` scope, from the scope table in Chapter 4: the dependency is on the compile and test classpaths but is *not* packaged into the archive, because the runtime environment — here, the servlet container — supplies it:

```xml
<dependencies>
  <dependency>
    <groupId>jakarta.servlet</groupId>
    <artifactId>jakarta.servlet-api</artifactId>
    <version>6.1.0</version>
    <scope>provided</scope>
  </dependency>
  <dependency>
    <groupId>jakarta.enterprise</groupId>
    <artifactId>jakarta.enterprise.cdi-api</artifactId>
    <version>4.1.0</version>
    <scope>provided</scope>
  </dependency>
</dependencies>
```

The example above is framed for Jakarta EE 11, where the APIs use the `jakarta.*` namespace; if your target container is a Java EE 8 server, the equivalent coordinates are `javax.servlet:javax.servlet-api:4.0.1` with the `javax.*` namespace. The namespace distinction is not cosmetic: the two are different artifacts with incompatible package names, and you must match whichever one your container implements — migrating `javax`-namespace code to a Jakarta container is a code change (import rewrites), not a dependency swap.

The principle is the one the Ant build violated by accident: the container supplies the JEE APIs, so your build compiles against them but ships without them. Declare the API with `<scope>provided</scope>`, and `mvn package` produces a `WEB-INF/lib` containing only what your application actually brings — with no exclusion lists to maintain and no way for the servlet jar to sneak back into the archive when someone adds it to `lib/`. This is also the honest correction of the `servlet-api*.jar` exclude in the previous section's Ant task: in Ant, keeping the container jar out of the WAR was a manual, per-target chore; in Maven it is a property of the scope.

### Container deployment: the Cargo plugin

In the Ant build, "deploy" usually meant a target that copied the WAR into a running container's deployment directory, plus another target to start and stop that container — often shell-scripted around `<exec>`. In Maven, that work belongs to the Cargo plugin, `org.codehaus.cargo:cargo-maven3-plugin`, which downloads, starts, stops, and deploys to containers (Tomcat, Jetty, WildFly, and others) from the build:

```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.codehaus.cargo</groupId>
      <artifactId>cargo-maven3-plugin</artifactId>
      <configuration>
        <container>
          <containerId>tomcat10x</containerId>
        </container>
        <configuration>
          <type>standalone</type>
          <properties>
            <cargo.servlet.port>8080</cargo.servlet.port>
          </properties>
        </configuration>
        <deployables>
          <deployable>
            <groupId>com.acme</groupId>
            <artifactId>acme-web</artifactId>
          </deployable>
        </deployables>
      </configuration>
    </plugin>
  </plugins>
</build>
```

Cargo's goals run on demand — `mvn cargo:start` to start a container with the WAR deployed, `mvn cargo:run` to keep it running, `mvn cargo:stop` to stop it — or bind to the pre-integration-test and post-integration-test phases so a container lifecycle wraps the integration tests. A word of disambiguation that matters in this guide: `mvn deploy` (Chapter 11) publishes an artifact to a repository manager, which is distribution, not deployment; the Cargo plugin's deploy puts a WAR into a running servlet container, which is what the Ant deploy target actually did. The two are unrelated despite sharing a verb — this chapter's deploy is the container one.

Cargo is generic and container-agnostic, which makes it the right default for CI smoke tests. Container-native plugins exist when your target server has its own tooling: `org.wildfly.plugins:wildfly-maven-plugin` for WildFly and JBoss EAP (goals like `wildfly:deploy` against a running or managed server) and `org.glassfish.embedded:maven-embedded-glassfish-plugin` for an embedded GlassFish instance. They configure faster and speak the server's own deployment semantics, at the cost of tying the build to one container; prefer Cargo when the build should stay portable, and a native plugin when you specifically need the target server's behavior.

### Integration tests with Arquillian

The final piece: tests that exercise code inside a real container. The Ant pattern was a hand-wired test target — start the container, deploy the WAR, run the JUnit suite against it, tear it down:

```xml
<target name="container-test" depends="war">
  <exec executable="${catalina.home}/bin/startup.sh"/>
  <waitfor maxwait="30" maxwaitunit="second">
    <http url="http://localhost:8080/acme-web/health"/>
  </waitfor>
  <junit printsummary="yes" haltonfailure="yes">
    <classpath>
      <pathelement path="${build.dir}/test-classes"/>
      <fileset dir="${lib.dir}/test" includes="*.jar"/>
    </classpath>
    <batchtest todir="${build.dir}/itest-reports">
      <fileset dir="${test.dir}" includes="**/*IT.java"/>
    </batchtest>
  </junit>
  <exec executable="${catalina.home}/bin/shutdown.sh"/>
</target>
```

Every part of this — the lifecycle scripting, the readiness poll, the classpath assembly, the report wiring — is what Arquillian automates. Arquillian takes over the container lifecycle around each test *deployment*: the test class declares what to deploy (`@Deployment` returning a shrinkwrap archive), Arquillian packages and deploys it into the container, runs the test cases inside that deployment, and reports results through JUnit. The dependencies are test-scoped — the Arquillian JUnit 5 integration plus a container adapter matching your target server:

```xml
<dependencies>
  <dependency>
    <groupId>org.jboss.arquillian.junit5</groupId>
    <artifactId>arquillian-junit5-container</artifactId>
    <version>1.9.3.Final</version>
    <scope>test</scope>
  </dependency>
  <dependency>
    <groupId>org.jboss.arquillian.container</groupId>
    <artifactId>arquillian-tomcat-managed-10</artifactId>
    <version>1.2.0.Alpha1</version>
    <scope>test</scope>
  </dependency>
</dependencies>
```

Arquillian tests are named and discovered like any other integration test, so they run under the Failsafe plugin from Chapter 6 — the same `integration-test`/`verify` goal pair, the same `*IT` naming conventions, the same `target/failsafe-reports/` output. If the chapter's Cargo configuration is bound to the pre-integration-test and post-integration-test phases, Failsafe runs the Arquillian tests against that container; if the container adapter manages its own (as the managed Tomcat adapter does), no Cargo configuration is needed for the test run at all. Either way, the `container-test` target and its shell-scripted container choreography are deleted, and `mvn verify` runs the whole pipeline: unit tests, integration tests, container tests, and the coverage report from Chapter 6.

The checklist for this chapter:

- [ ] `<packaging>war</packaging>` set on the web module, and `mvn package` produces `target/<finalName>.war`
- [ ] Web resources moved to `src/main/webapp` (with `WEB-INF/web.xml`), or `warSourceDirectory`/`webXml` overrides in place with a dated follow-up to move them
- [ ] Ant `war` task's `lib`/`classes`/`webres` assembly replaced by the POM's dependencies and the standard layout; the plugin declared only where defaults are overridden
- [ ] All container-supplied APIs (servlet, CDI, JSF, JSP) declared with `<scope>provided</scope>`; no JEE jar in `WEB-INF/lib` of the built WAR
- [ ] Ant deploy/start/stop targets replaced by the Cargo plugin (or a container-native plugin), with the repository `mvn deploy` from Chapter 11 kept distinct
- [ ] Container tests running as Arquillian deployments under the Failsafe plugin, and the shell-scripted `container-test` target deleted

## 8. Phase 5: Custom Ant Tasks and the Antrun Escape Hatch

Chapter 5 covered the tasks that account for nearly every line of a typical `build.xml` — compile, jar, resources, tests — and each of those had a direct plugin equivalent. This chapter covers the remainder: the custom `<taskdef>` classes your team wrote, the oddball steps that do not map to any plugin, and the two tools that keep them working inside a Maven build. It replaces the "everything else" row of the core mapping with a concrete decision process.

### The strategy ladder

When your Phase 0 inventory turns up a step with no obvious plugin, work down this list in order. Do not start at the bottom.

1. **Find a plugin equivalent.** Most "custom" tasks replicate something that exists. A task that copies files with a twist is usually `maven-resources-plugin` configuration; a task that generates sources usually has a dedicated Maven plugin (such as `jaxb2-maven-plugin` for JAXB code generation, or `build-helper-maven-plugin` to wire generated sources in); a task that checks file sizes or timestamps is often a combination of `maven-enforcer-plugin` rules. Search Central and the Appendix A mapping before assuming a task is unique — writing a wrapper for something a plugin already does is the most common migration mistake.
2. **Wrap the task with `maven-antrun-plugin`.** If no plugin exists, run the original Ant task from within the lifecycle using antrun. This is acceptable short-term for anything, and acceptable long-term only for genuinely odd steps — the criteria are below.
3. **Rewrite the task logic as a Maven plugin, or call it via `exec-maven-plugin`.** If the step is going to live in the build permanently, it should eventually stop depending on Ant. That means either a small in-house Maven plugin (a `maven-archiver`-style mojo is a day of work for a simple task) or, for steps that are really just a process invocation, `exec-maven-plugin` with no Ant involved at all.

The ladder is a sequencing tool, not a taxonomy: step 2 buys you a working Maven build now, and steps 1 and 3 are how you pay the wrapper down later.

### Wrapping a custom task: `taskdef` vs `maven-antrun-plugin`

Suppose acme-core's `build.xml` stamps the build with a version file using a custom task:

```xml
<target name="version-stamp" depends="compile">
  <taskdef name="version-stamp"
           classname="com.acme.build.VersionStampTask"
           classpath="${build.dir}/classes"/>
  <version-stamp version="1.0.0"
                 outfile="${build.dir}/classes/version-stamp.properties"/>
</target>
```

The task itself is ordinary Ant code — a class extending `org.apache.tools.ant.Task` that writes a properties file — and it lives in the project's sources or a build-tools jar. The `taskdef` puts it on Ant's classpath, and the target invokes it.

The antrun equivalent binds the same invocation to a lifecycle phase. The `maven-antrun-plugin` runs an embedded Ant `target`, and because the custom task's jar is not on Ant's classpath by default, it must be declared in the plugin's own `<dependencies>` block — this is the part most teams miss; without it, the `<taskdef classname="...">` fails with `taskdef class com.acme.build.VersionStampTask cannot be found`:

```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-antrun-plugin</artifactId>
      <dependencies>
        <dependency>
          <groupId>com.acme</groupId>
          <artifactId>acme-build-tools</artifactId>
          <version>1.0.0</version>
        </dependency>
      </dependencies>
      <executions>
        <execution>
          <id>version-stamp</id>
          <phase>process-classes</phase>
          <goals>
            <goal>run</goal>
          </goals>
          <configuration>
            <target>
              <taskdef name="version-stamp"
                       classname="com.acme.build.VersionStampTask"/>
              <version-stamp version="${project.version}"
                             outfile="${project.build.outputDirectory}/version-stamp.properties"/>
            </target>
          </configuration>
        </execution>
      </executions>
    </plugin>
  </plugins>
</build>
```

Three things changed in the translation, and all three are improvements the wrapper gives you for free. The hard-coded `1.0.0` became `${project.version}`, so the stamp tracks the POM coordinates instead of drifting from them. `${build.dir}/classes` became `${project.build.outputDirectory}`, tying the output to the lifecycle's convention rather than an Ant property. And the `classpath` on the `taskdef` disappeared — the dependency block resolved `acme-build-tools` through Maven's dependency management, the same mechanism that resolves the project's own dependencies, instead of a hand-built Ant path. Note also the phase choice: `process-classes` runs after compilation, so the stamp lands in `target/classes` and is packaged into the jar by the `package` phase automatically.

### When wrapping is acceptable — and when it is not

Antrun is an escape hatch, not a destination. Whether a given wrapper can stay depends entirely on what the task touches:

**Acceptable to wrap, possibly indefinitely:**

- Clearly-scoped side effects that the lifecycle has no opinion about: writing a build-info file, publishing a notification, updating a changelog, calling an internal deployment script.
- Steps with low churn: a task that has not changed in three years and is unlikely to need one.
- Steps under deadline pressure. A working `mvn package` with one antrun block beats a half-finished pure-Maven build; track the wrapper as debt and move on.

**Not acceptable to wrap — these must become native Maven before cutover:**

- Anything touching the **compile classpath**. If the custom task generates sources, weaves aspects, or annotates classes, wrapping it means the antrun block must run in the right phase with the right classpath and ordering relative to `maven-compiler-plugin` — fragile, and invisible to IDEs, which will not see the generated or modified sources. Use an existing generator plugin or write a mojo.
- Anything touching **test execution**. A custom task that runs tests replaces work surefire and failsafe already do, and wrapping it forfeits surefire's reporting, IDE integration, and parallelism. Chapter 6's migration applies; do not preserve the task.
- Anything touching **artifact assembly**. A task that builds the jar, war, or distribution archive in a custom way must map to `maven-jar-plugin`, `maven-war-plugin`, `maven-assembly-plugin`, or `maven-shade-plugin` configuration. A wrapped assembly step means `target/` contains artifacts Maven's own plugins did not produce, and every downstream tool — install, deploy, site, CI — is working against the grain.

The dividing line is simple: if the step's output ends up inside `target/classes`, the test run, or the packaged artifact, it is part of the build proper and needs a native Maven answer. If it is an external side effect that happens to run during the build, antrun is a fine permanent home.

### When there is no Ant task at all: `exec-maven-plugin`

Some steps in a legacy `build.xml` are not Ant tasks but raw process invocations. The Ant side, using `<exec>` for a native command or `<java>` for a forked JVM process:

```xml
<target name="generate-schema">
  <java classname="com.acme.tools.SchemaGenerator" fork="true">
    <classpath>
      <pathelement path="${build.dir}/classes"/>
      <fileset dir="lib" includes="schema-tools.jar"/>
    </classpath>
    <arg value="-out"/>
    <arg value="${build.dir}/schema"/>
  </java>
  <exec executable="gzip">
    <arg value="${build.dir}/schema/catalog.sql"/>
  </exec>
</target>
```

The `exec-maven-plugin` replaces both patterns, with one goal per kind of invocation: the `exec` goal runs a native executable, while the `java` goal executes the main class in the Maven JVM — it does not fork. This matters because the Ant `<java fork="true">` above ran in a separate process: if the step relies on forking for isolation (calling `System.exit()`, mutating static state, or needing classloader separation from Maven's own classes), `exec:java` will behave differently. In that case, use the `exec` goal with a `java` executable and the full classpath spelled out via the `<executable>` and `<arguments>` elements, which forks a real JVM. Configuration maps to the Ant attributes closely, but not one-for-one — the forked-JVM option in particular requires re-expressing the classpath and arguments explicitly:

```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.codehaus.mojo</groupId>
      <artifactId>exec-maven-plugin</artifactId>
      <executions>
        <execution>
          <id>generate-schema</id>
          <phase>generate-resources</phase>
          <goals>
            <goal>java</goal>
          </goals>
          <configuration>
            <mainClass>com.acme.tools.SchemaGenerator</mainClass>
            <arguments>
              <argument>-out</argument>
              <argument>${project.build.directory}/schema</argument>
            </arguments>
            <classpathScope>compile</classpathScope>
          </configuration>
        </execution>
        <execution>
          <id>gzip-schema</id>
          <phase>generate-resources</phase>
          <goals>
            <goal>exec</goal>
          </goals>
          <configuration>
            <executable>gzip</executable>
            <arguments>
              <argument>${project.build.directory}/schema/catalog.sql</argument>
            </arguments>
          </configuration>
        </execution>
      </executions>
    </plugin>
  </plugins>
</build>
```

Prefer `exec-maven-plugin` over an antrun block containing `<java>`/`<exec>` whenever the step is a plain process invocation — it expresses the intent directly, avoids dragging the Ant object model into the build, and reads the same way to anyone who has never seen a `build.xml`. Its `classpathScope` attribute uses the project's own resolved dependencies rather than a hand-built path, so `schema-tools.jar` should be a declared dependency of acme-core (or of a `acme-build-tools` artifact) instead of a file in `lib/`. Note the phase choice: `generate-resources` runs before compilation, which is right for a generator; a step that must run after packaging binds to `package` or `verify` instead.

### Phase 5 checklist

- [ ] Every custom-task step checked against Appendix A and Central for an existing plugin equivalent
- [ ] Remaining custom tasks wrapped in `maven-antrun-plugin`, with the task jar declared in the plugin's `<dependencies>` block
- [ ] Wrapper outputs tracked: file stamps and notifications may stay; compile-classpath, test, and assembly steps have a ticket to become native Maven
- [ ] Plain process invocations moved to `exec-maven-plugin` `java`/`exec` goals rather than antrun `<exec>`/`<java>`
- [ ] `mvn package` produces the same artifacts with the same side effects as the old `build.xml` targets

## 9. Phase 6: Multi-Module Builds

Chapters 3 through 8 migrated a single project: acme-core, one `build.xml`, one `pom.xml`. Real codebases are rarely that flat — a web tier depends on a core library, shared utilities sit in their own module, and the Ant build glues them together with a driver script that invokes each `build.xml` in a hand-maintained order. This chapter replaces that driver script with Maven's reactor and replaces the copy-pasted common configuration with a parent POM. The running example expands to two modules: `acme-core` (the library built in the previous chapters) and `acme-web`, a new module that depends on it.

### The reactor

In Ant, multi-module builds are orchestrated by hand. A driver `build.xml` (or a shell script) invokes each module's `build.xml` in an order someone worked out, and nothing enforces that order except the person who wrote the script. If acme-core's public API changes, the script's author is responsible for knowing that acme-web must be rebuilt afterward.

Maven inverts this. A single POM — the *aggregator* — declares which directories are modules, and the *reactor* (Maven's build coordinator) works out the rest: it reads every module's POM, builds the dependency graph between them, and executes the lifecycle for each module in dependency order. One command, `mvn package`, from the root directory builds acme-core and then acme-web, no matter how many modules there are or how they depend on each other. The ordering that was a script's job is now the reactor's, and it is derived from the same `<dependency>` declarations that Chapter 4 introduced — there is no separate ordering configuration to maintain.

The `<modules>` list lives in the aggregator POM. Each entry is a directory name relative to the aggregator's own directory, and each of those directories contains a `pom.xml` of its own.

### From `subant` to an aggregator POM

Suppose the acme build drives its two modules with a top-level `build.xml` using `<subant>` (or, equivalently, repeated `<ant antfile="..."/>` calls). The Ant side, with the ordering spelled out by hand — core before web, because web needs core's jar:

```xml
<project name="acme-build" default="dist" basedir=".">
  <target name="clean">
    <subant target="clean">
      <fileset dir="." includes="acme-core/build.xml"/>
      <fileset dir="." includes="acme-web/build.xml"/>
    </subant>
  </target>

  <target name="dist">
    <subant target="dist" verbose="true">
      <fileset dir="." includes="acme-core/build.xml"/>
    </subant>
    <subant target="dist" verbose="true">
      <fileset dir="." includes="acme-web/build.xml"/>
    </subant>
  </target>
</project>
```

Everything about this is manual. The module list is duplicated between the `clean` and `dist` targets (and any other targets the driver has); the ordering — core's `dist` before web's — exists only as the sequence of the two `<subant>` blocks; and a third module means editing the driver in every place the list appears. Add the usual Ant fragility: nothing checks that `acme-web/build.xml` actually exists before the `fileset` silently matches nothing, and each module re-derives its own classpath to the sibling's freshly built jar.

The Maven equivalent is an aggregator POM at the root of the tree — packaging `pom`, meaning it produces no artifact of its own, only a module list:

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
                             http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.acme</groupId>
  <artifactId>acme-parent</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <packaging>pom</packaging>

  <modules>
    <module>acme-core</module>
    <module>acme-web</module>
  </modules>
</project>
```

The resulting directory tree:

```text
acme/
├── pom.xml          (the aggregator above)
├── acme-core/
│   └── pom.xml      (the acme-core POM from Chapters 3-8)
└── acme-web/
    └── pom.xml
```

What changed in the translation: the module list appears exactly once, in `<modules>`; the ordering is gone entirely — the reactor derives it from the modules' dependency declarations (shown below); and the driver's targets are gone, because `mvn clean`, `mvn package`, and every other lifecycle goal work across all modules from the root. Adding a third module is one `<module>` entry plus the new directory, not an edit to a script in several places. Note that the `dist` target's job — build each module's distributable — is simply `mvn package`, the same command as the single-module case from Chapter 3.

### Parent POMs: shared configuration

The Ant build shared configuration between modules the same way it shared everything else: property files and copy-paste. A `common.properties` at the root, imported by each module's `build.xml`:

```xml
<project name="acme-core" default="compile" basedir=".">
  <property file="../common.properties"/>

  <target name="compile">
    <javac srcdir="src" destdir="${build.dir}/classes"
           source="${javac.source}" target="${javac.target}" encoding="UTF-8"/>
  </target>
</project>
```

and the identical block copy-pasted into `acme-web/build.xml`. This covers the simple cases — compiler flags, common paths — but not the harder ones. Each module's `build.xml` still repeats the `<path>` definitions for the shared third-party jars, and when two modules copy the same `<macrodef>` or the same `dist` target, the copies drift: one module gets the encoding fix, the other does not, and nothing detects the divergence.

Maven's answer is the *parent POM*: an aggregator whose `pom` packaging also carries configuration that every child inherits. The aggregator from the previous section extended with the properties from the baseline POM and a `<dependencyManagement>` block pinning the shared third-party versions:

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
                             http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.acme</groupId>
  <artifactId>acme-parent</artifactId>
  <version>1.0.0-SNAPSHOT</version>
  <packaging>pom</packaging>

  <modules>
    <module>acme-core</module>
    <module>acme-web</module>
  </modules>

  <properties>
    <maven.compiler.source>11</maven.compiler.source>
    <maven.compiler.target>11</maven.compiler.target>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
  </properties>

  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>org.apache.commons</groupId>
        <artifactId>commons-lang3</artifactId>
        <version>3.14.0</version>
      </dependency>
      <dependency>
        <groupId>org.apache.logging.log4j</groupId>
        <artifactId>log4j-api</artifactId>
        <version>2.23.1</version>
      </dependency>
      <dependency>
        <groupId>org.junit.jupiter</groupId>
        <artifactId>junit-jupiter</artifactId>
        <version>5.10.2</version>
        <scope>test</scope>
      </dependency>
    </dependencies>
  </dependencyManagement>
</project>
```

Two mechanisms are at work here, and they behave differently. The `<properties>` block is inherited outright: every child compiles with Java 11 and UTF-8 with no configuration of its own — the direct replacement for `common.properties`. `<dependencyManagement>` is different: it does *not* add dependencies to the children. It declares the versions (and scopes) that a dependency will have *if* a child declares it, so each child lists only the groupId and artifactId of what it actually uses, and the version comes from one place. This is the counterpart of the per-module `<path>` definitions: the jar inventory is written once in the parent, and no child can quietly compile against a different `commons-lang3` than its sibling.

A child POM opts in with a `<parent>` element. Here is acme-web, inheriting from acme-parent and depending on its sibling:

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
                             http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>com.acme</groupId>
    <artifactId>acme-parent</artifactId>
    <version>1.0.0-SNAPSHOT</version>
  </parent>
  <artifactId>acme-web</artifactId>
  <packaging>jar</packaging>

  <dependencies>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

Three things the child POM does not contain, deliberately: no groupId or version (both are inherited from the parent, and can be overridden if a module ever needs to diverge), no compiler or encoding properties (inherited), and no version on `junit-jupiter` (supplied by `<dependencyManagement>`). The acme-core POM from the previous chapters converts the same way: it drops its own `<properties>` block and third-party versions, adds the `<parent>` element, and keeps only its `<dependencies>` entries minus their `<version>` tags. The result is the end of the copy-pasted-macrodef problem — the shared configuration exists in exactly one file, and a change to the parent applies to every module on the next build.

### Inter-module dependencies

Inside `acme-web`'s sources, a class that imports `com.acme.Core` needs acme-core's jar on the classpath. In the Ant build, that jar was a filesystem fact: acme-web's `build.xml` pointed a `<path>` at `../acme-core/dist/acme-core-1.0.0.jar` (or at a copy of it), which only existed if the driver script had built core first with the right target.

In Maven, a sibling is just another set of coordinates. acme-web declares the dependency the same way it declared `commons-lang3` in Chapter 4 — by GAV, with the version inherited from the parent via `${project.version}`:

```xml
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
                             http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>com.acme</groupId>
    <artifactId>acme-parent</artifactId>
    <version>1.0.0-SNAPSHOT</version>
  </parent>
  <artifactId>acme-web</artifactId>
  <packaging>jar</packaging>

  <dependencies>
    <dependency>
      <groupId>com.acme</groupId>
      <artifactId>acme-core</artifactId>
      <version>${project.version}</version>
    </dependency>
  </dependencies>
</project>
```

The important property of this declaration is what the reactor does with it. When the build runs from the aggregator, Maven sees that acme-web depends on acme-core and resolves acme-core *from the current build* — the classes and jar the reactor just produced — without acme-core ever being installed to the local repository. The `<path>` pointing at `../acme-core/dist/...` is gone, and with it the requirement that someone built core's `dist` target first. (Running `mvn` from *inside* `acme-web/` alone is the exception: with only acme-web's POM in play, the reactor has no acme-core to resolve, so Maven falls back to the local repository and fails if it is not there — which is what the partial builds below are for.)

This also cleans up the dependency's downstream effects. acme-web's war or fat jar picks up acme-core transitively, the same way `commons-lang3` arrives, and a change to acme-core's API surfaces as a compile error in acme-web on the very next `mvn package` — not as a stale-jar mystery at deploy time.

### Build ordering and partial builds

Two commands cover the day-to-day. From the root, `mvn package` builds everything in reactor order — here, acme-core then acme-web, because that is what the dependency graph says. When you are working in one module and do not want to pay for the rest, the `-pl` flag restricts the build to selected modules, and `-am` (also-make) tells the reactor to include everything those modules depend on:

```bash
mvn -pl acme-web -am package
```

This builds acme-core and acme-web, in that order, and nothing else — acme-core because acme-web needs it, and only because of that. Without `-am`, `-pl acme-web` builds acme-web alone, which succeeds only if acme-core is already in the local repository. The companion flag `-amd` (also-make-dependents) inverts the selection: `mvn -pl acme-core -amd package` builds acme-core and every module that depends on it. For a two-module tree these distinctions are small; for the fifteen-module build they become, they are the difference between a ninety-second feedback loop and a ten-minute one.

The checklist for this phase:

- [ ] Root aggregator POM with packaging `pom` and one `<module>` entry per directory
- [ ] The Ant driver script (or shell wrapper with the `<subant>`/`<ant>` calls) deleted
- [ ] Shared compiler, encoding, and build properties moved to the parent POM's `<properties>`
- [ ] Shared third-party versions moved to the parent's `<dependencyManagement>`; children declare dependencies without versions
- [ ] Sibling dependencies declared by coordinates (`com.acme:acme-core`), with no `<path>` pointing at a sibling's `dist/` output
- [ ] `mvn package` from the root builds all modules in dependency order, and `mvn -pl acme-web -am package` builds the selected module with its dependencies

## 10. Phase 7: Profiles, Properties, Environments

Phase 6 moved the shared build properties into the parent POM's `<properties>`. This chapter covers the rest of Ant's property machinery — property files, command-line overrides, and the built-in values you were defining by hand — and the pattern they most often feed: environment-specific builds, selected in Ant by passing `-Denv=dev` or `-Denv=prod` and in Maven by profiles.

### Properties: from Ant property files to the POM

The Ant pattern — properties loaded from an external file:

```xml
<project name="acme-core" default="dist" basedir=".">
  <property file="build.properties"/>
</project>
```

The Maven equivalent is the `<properties>` section of the POM, which you have already been using since Chapter 9's parent POM for shared compiler and encoding settings:

```xml
<project>
  <properties>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <maven.compiler.release>11</maven.compiler.release>
  </properties>
</project>
```

For values that are genuinely machine-local — repository credentials, mirror configuration — Maven has `settings.xml` (in `${user.home}/.m2/settings.xml` or the installation directory), which plays the role of the properties file a developer kept out of version control. Prefer the POM for anything the build itself needs, though: `settings.xml` is per-machine and not versioned with the project, so a build that depends on it is not reproducible from a fresh checkout. Command-line overrides work the same way in both tools: `ant -Dsome.property=value` and `mvn -Dsome.property=value` both define a property for that invocation.

Ant also made you define and wire up properties that Maven provides built in. The `build.dir` and `version` properties in acme-core's `build.xml` are examples — in Maven they already exist:

- `${project.version}` — the project's version (`1.0.0-SNAPSHOT` for acme-core); replaces a hand-maintained `version` property
- `${project.artifactId}`, `${project.groupId}` — the coordinates
- `${project.build.directory}` — the build output directory (`target/`); replaces `${build.dir}`
- `${project.build.outputDirectory}` — compiled classes (`target/classes`); replaces `${build.dir}/classes`

These built-ins are always available in plugin configuration and in filtered resources — Chapter 5 used `@project.version@` in exactly this way. There is nothing to declare and nothing to get out of sync between environments.

### Profiles

A profile is a named slice of the POM — properties, dependencies, plugin configuration, resource filters — that is included in the effective build only when activated. Three activation mechanisms cover what Ant builds typically did with property files and per-environment targets:

- **Explicitly, from the command line:** `mvn -P prod package` activates the profile named `prod`.
- **By property:** the profile activates automatically when a system property (or an `env`-prefixed environment variable) has a given value.
- **By file presence:** the profile activates when a named file exists (or is missing) — useful for "developer machine only" configuration.

The Ant pattern — two property files, selected on the command line:

```xml
<project name="acme-core" default="dist" basedir=".">
  <property file="${env}.properties"/>
</project>
```

with `dev.properties` and `prod.properties` sitting next to `build.xml`, and `ant -Denv=prod` picking which one loads. Forget the `-D` and Ant loads nothing (or, with a default set in the file, quietly builds the wrong environment).

The Maven equivalent — two profiles, with `dev` active by default:

```xml
<project>
  <profiles>
    <profile>
      <id>dev</id>
      <activation>
        <activeByDefault>true</activeByDefault>
      </activation>
      <properties>
        <env>dev</env>
        <db.url>jdbc:h2:mem:acme</db.url>
      </properties>
    </profile>
    <profile>
      <id>prod</id>
      <properties>
        <env>prod</env>
        <db.url>jdbc:postgresql://db.acme.example.com:5432/acme</db.url>
      </properties>
    </profile>
  </profiles>
</project>
```

Now `mvn package` builds the dev configuration — no forgotten `-Denv=` — and `mvn -P prod package` builds the production one. `mvn help:active-profiles` shows which profiles are active in a given invocation, which is the closest thing to Ant's "print all the properties" debugging target. One caveat on `activeByDefault`: it only holds while no other profile in the same POM is activated in any way — activating `prod` (via `-P`, a property, or a file trigger) silently deactivates `dev`, which is usually what you want, but it means `activeByDefault` is not a guarantee, only a default.

### Environment-specific builds via resource filtering

Where Ant builds most often pointed their property files was at a `<filterset>`: the same resources copied for every environment, with different token values per environment. Chapter 5 showed the single-filterset case; with profiles, each environment contributes its own filter file. The Ant pattern, generalized per environment:

```xml
<target name="resources" depends="init">
  <copy todir="${build.dir}/classes" filtering="true">
    <fileset dir="config"/>
    <filterset>
      <filter token="db.url" value="${db.url}"/>
      <filter token="project.version" value="${version}"/>
    </filterset>
  </copy>
</target>
```

The Maven equivalent — filtering on the resource directory, and the filter file chosen by the profile through the `${env}` property each profile sets:

```xml
<project>
  <build>
    <filters>
      <filter>src/main/filters/${env}.properties</filter>
    </filters>
    <resources>
      <resource>
        <directory>src/main/resources</directory>
        <filtering>true</filtering>
      </resource>
    </resources>
  </build>
</project>
```

The profile properties shown above set `<env>dev</env>` or `<env>prod</env>`, so `mvn package` filters with `src/main/filters/dev.properties` and `mvn -P prod package` with `src/main/filters/prod.properties`. A resource like `application.properties` containing:

```properties
app.version=@project.version@
db.url=@db.url@
```

resolves `app.version` from the POM (no filter file needed for it — that token is a built-in) and `db.url` from the environment's filter file, whose values take precedence for token substitution. That is the distinction between the two mechanisms: profile properties like `<db.url>` are fixed in the POM and visible at build time, while the filter file externalizes the token values so they can change per environment without touching the POM. All the cautions from Chapter 5 apply unchanged: write tokens as `@token@`, and restrict the resources plugin to `@`-only delimiters as shown in Chapter 5 so `${...}` placeholders that a framework needs at runtime survive filtering, keep binary files out of filtered directories, and avoid timestamp tokens that make every build's output differ.

Note what disappeared: the per-environment Ant targets (`dist-dev`, `dist-prod`, or whichever spelling the build used) have no Maven equivalent and need none — the artifact is the same, only the filter values differ, and the profile selects those.

### When not to use profiles

Profiles solve build-time variation, and environment configuration is usually not that. The one-build-fits-all-artifact principle says you should build each artifact exactly once and promote that same binary through every environment — which means database URLs, service endpoints, and credentials must not be baked in by a profile at build time. Configuration that varies per deployment belongs outside the artifact entirely: read from the filesystem or environment variables at startup, or injected by the deployment platform. Use profiles for things that genuinely change the build itself — a JDK-restricted build, extra debug output, or the filter-file selection above where the filtered values are only defaults — and keep the deploy-time knobs out of the POM.

### Phase 7 checklist

- [ ] Ant `<property file="...">` values moved to the POM's `<properties>` (or to per-profile properties where they vary)
- [ ] Hand-defined `version`, `build.dir`, and similar properties replaced by `${project.version}`, `${project.build.directory}`, and the other built-ins
- [ ] Per-environment property files replaced by profiles, with the everyday environment as `activeByDefault`
- [ ] Per-environment `<filterset>` values replaced by profile-selected `<filter>` files and resource filtering
- [ ] `mvn package` and `mvn -P prod package` produce the dev and prod configurations respectively, verified with `mvn help:active-profiles`
- [ ] Nothing deploy-specific (URLs, credentials, endpoints) is baked into artifacts by a profile; runtime configuration is externalized

## 11. Phase 8: CI/CD and Release

The previous phases moved the build itself to Maven. This chapter moves what surrounds it: the CI pipeline, the versioning discipline the build enforces, the release process, and the deploy step that publishes artifacts to a repository. The pattern is the same as every earlier phase — replace the bespoke Ant invocation with the standard Maven one, and let the framework supply what the script used to define by hand.

### Continuous integration

The Ant CI job was a shell script. It looked something like this:

```bash
ant clean test jar
```

possibly preceded by a checkout, a dependency-download step (or a committed `lib/` directory), and followed by archiving `dist/` somewhere. The job had to know the Ant targets by name, and every project's job was slightly different.

The Maven replacement is a lifecycle invocation, which is identical for every project:

```bash
mvn verify
```

`verify` runs everything up to and including the integration-test and verify phases — compile, test, package, and any integration checks bound by plugins (coverage thresholds, static analysis, integration tests from the earlier chapters). It is the right default for CI because it exercises everything `package` does plus the gates, and it leaves the artifact in `target/` ready to be archived or deployed. If your CI also produces coverage reports or site documentation, those are additional goals on the same invocation (`mvn verify site`), not a separate script.

Two flags belong on every CI invocation:

- `-B` (batch mode) disables ANSI color codes and progress spinners in the output, which matters the moment the log is rendered in a web UI or written to a file.
- `-ntp` (`--no-transfer-progress`) suppresses the per-jar download progress lines. Without it, a build that resolves several hundred dependencies floods the log with transfer noise; with it, the log contains only what happened, not every byte that moved.

So the canonical CI command is:

```bash
mvn -B -ntp verify
```

Caching is the other CI concern. The Ant build resolved nothing — dependencies sat in `lib/` or a shared directory, so a clean CI machine was free. Maven resolves everything into the local repository, `~/.m2/repository`, on every fresh machine, which means the first CI build after a cache miss downloads the dependency tree. Cache that directory between builds: your CI system's standard dependency caching (the cache action in GitHub Actions, the `caches` section in GitLab CI, or the workspace retention in Jenkins) should point at `~/.m2/repository`. Two cautions: cache the repository directory, not the whole `~/.m2` (the local repository is content-addressed and safe to share; `settings.xml` and other state are not worth caching), and treat the cache as disposable — a build must always succeed on a cold cache, or you have an undeclared dependency on something outside the POM. Test that occasionally by running the job with the cache cleared.

### Versioning discipline: SNAPSHOT vs. release

Ant builds typically had no enforced version discipline. The version string lived in a property, `dist` produced `acme-core-1.0.0.jar` every time regardless of what had changed, and the same filename could mean three different binaries depending on when it was built — or, if someone bumped the property manually, the jar name changed while nothing else did.

Maven enforces the distinction the Ant build left implicit. A version is either a **SNAPSHOT** (`1.0.0-SNAPSHOT`, what acme-core carries through development) or a **release** (`1.0.0`), and the two behave differently everywhere:

- A SNAPSHOT is a mutable version. Maven stores it in the local repository under the base version, and a repository manager stores the dated snapshots behind it. When acme-web declares a dependency on `acme-core:1.0.0-SNAPSHOT`, Maven checks the remote repository for a newer snapshot (subject to update policies) and re-resolves when one appears. A SNAPSHOT says: this is in flux, re-download me.
- A release is immutable, by convention and by configuration. Once `acme-core:1.0.0` is published to a repository, that repository will refuse a second deploy of the same coordinates — the repository manager's non-redeploy policy, which exists precisely to make `1.0.0` mean one binary forever. A release says: this is frozen; if anything changes, the version changes.

That immutability is what turns artifacts into something you can promote. Chapter 10's one-build-fits-all-artifact principle — build once, promote the same binary through every environment — only works if a version identifies exactly one artifact, and only the SNAPSHOT/release split plus non-redeploy gives you that. Ant could be disciplined about this, but nothing in Ant enforced it; in Maven, a redeploy of a release fails, and `1.0.0-SNAPSHOT` failing to update is a signal that something upstream did not deploy.

The working rules that fall out of this:

- Development happens on `...-SNAPSHOT` versions, and SNAPSHOT versions are only ever deployed to the snapshot repository.
- A release is a SNAPSHOT with the suffix removed, deployed once to the release repository, and tagged in version control.
- Nothing in the POM's `<version>` is hand-edited during a release — the tooling in the next section owns that change.

### Release tooling

Two Maven plugins cover what the Ant release script did with `sed`, a properties file, and a tagging target.

**Bulk version changes with versions-maven-plugin.** Bumping acme-core from `1.0.0-SNAPSHOT` to `1.0.0` — in a multi-module tree, every module's version and every inter-module dependency reference at once — is one goal:

```bash
mvn versions:set -DnewVersion=1.0.0
```

The plugin rewrites every `<version>` in the reactor's POMs, including the inherited versions and the `${project.version}`-based dependency references, and writes a backup of each file it touched. If the result looks wrong, undo it in one step:

```bash
mvn versions:revert
```

and when it looks right, remove the backups and commit:

```bash
mvn versions:commit
```

(There is no separate `versions:commit-revert` goal pair to configure — `revert` and `commit` are two goals over the same backups: `revert` restores from them, `commit` deletes them.) The plugin also covers the adjacent chores: `versions:set -DnextSnapshot=true` moves back to `1.0.1-SNAPSHOT` after a release (give the new version with `-DnewVersion=1.0.1`; `nextSnapshot` only appends the `-SNAPSHOT` suffix), `versions:display-dependency-updates` and `versions:use-latest-releases` report and apply third-party version bumps, and `versions:display-plugin-updates` does the same for build plugins.

**Tagged, reproducible releases with maven-release-plugin.** The `maven-release-plugin` automates the whole cut: flip the POMs to the release version, build and test from a clean checkout of that exact source state, deploy the release artifacts, commit the POMs back with the next development SNAPSHOT, and create a tag at the release commit. It is configured in the parent POM:

```xml
<project>
  <scm>
    <connection>scm:git:https://github.com/acme/acme-core.git</connection>
    <url>https://github.com/acme/acme-core</url>
  </scm>
  <build>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-release-plugin</artifactId>
        <configuration>
          <tagNameFormat>v@{project.version}</tagNameFormat>
          <releaseProfiles>release</releaseProfiles>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
```

Two settings matter most. `tagNameFormat` controls the tag name — `@{project.version}` is substituted with the release version, giving tags like `v1.0.0` that match whatever scheme your team used in Ant. `releaseProfiles` names profiles (from Chapter 10) activated only during the release build — the usual home for javadoc and source-jar generation that you do not want on every developer build. Running the release is then two commands:

```bash
mvn release:prepare
mvn release:perform
```

`prepare` prompts for the release and next-development versions, rewrites the POMs, runs the full build at the release version, and commits the tag; `perform` re-checks out the tag and runs `deploy` from it, which is what makes the published artifact correspond exactly to a commit you can check out later. The plugin requires a clean working tree and push access to the SCM — the same preconditions the Ant release script enforced by convention, now enforced by the tool. It also requires the POM to declare an `<scm>` element (with `connection` and `url`) pointing at the project's version control repository; without one, `release:prepare` fails before doing anything. The URLs below are illustrative — point them at your actual repository:

```xml
<project>
  <scm>
    <connection>scm:git:https://github.com/acme/acme-core.git</connection>
    <url>https://github.com/acme/acme-core</url>
  </scm>
</project>
```

### Deploy

Deploying is publishing to a remote repository, and it is the one Maven step with no Ant counterpart at all — Ant's "deploy" was a `<copy>` to a shared directory, which is exactly the practice Maven's repository model replaces.

The destination is declared in the POM's `<distributionManagement>` section, with a repository id (not a URL) that `settings.xml` keys off. For a project that publishes both releases and snapshots:

```xml
<project>
  <distributionManagement>
    <repository>
      <id>acme-releases</id>
      <url>https://repo.example.com/releases</url>
    </repository>
    <snapshotRepository>
      <id>acme-snapshots</id>
      <url>https://repo.example.com/snapshots</url>
    </snapshotRepository>
  </distributionManagement>
</project>
```

Maven picks the destination by version: `1.0.0` goes to `<repository>`, `1.0.0-SNAPSHOT` goes to `<snapshotRepository>`, which is how the SNAPSHOT/release discipline from the previous section is wired into the deploy step with no extra logic.

The credentials are not in the POM. They live in `settings.xml`, matched by the repository's `<id>`:

```xml
<settings>
  <servers>
    <server>
      <id>acme-releases</id>
      <username>ci-user</username>
      <password>${env.REPO_PASSWORD}</password>
    </server>
    <server>
      <id>acme-snapshots</id>
      <username>ci-user</username>
      <password>${env.REPO_PASSWORD}</password>
    </server>
  </servers>
</settings>
```

This is the `settings.xml` usage from Chapter 10 in its most important role: per-machine secrets stay out of the versioned POM, and the CI machine's `settings.xml` (or its equivalent, injected by the CI system) carries the deploy credentials. The `<id>` is the join key — it must match `<distributionManagement>` exactly, and a mismatch surfaces as a 401 on deploy, not a configuration error at parse time.

Publishing acme-core is then:

```bash
mvn -B -ntp deploy
```

which runs the lifecycle through `deploy`, and for each artifact built, uploads it to the repository the version selects. In CI, deploy is typically gated: `mvn -B -ntp verify` on every commit, `mvn -B -ntp deploy` only on the main branch (deploying snapshots) or on a release trigger (via `maven-release-plugin`, whose `release:perform` runs deploy for you).

### Phase 8 checklist

- [ ] CI invokes `mvn -B -ntp verify` instead of `ant clean test jar`, and the build succeeds on a machine with no `~/.m2/repository` cache
- [ ] `~/.m2/repository` cached between CI builds, with a periodic cold-cache run to catch undeclared dependencies
- [ ] All modules on `...-SNAPSHOT` during development; no hand-edited version bumps during release
- [ ] `versions-maven-plugin` used for bulk version changes (`versions:set`, with `versions:commit`/`versions:revert` over the backups)
- [ ] `maven-release-plugin` configured in the parent POM with `tagNameFormat` and `releaseProfiles`; releases produced by `release:prepare`/`release:perform` and tagged
- [ ] `<distributionManagement>` in the parent POM with separate release and snapshot repositories, ids matching `<server>` entries in `settings.xml`
- [ ] Deploy credentials in `settings.xml` only (injected into CI, never in the POM or version control); `mvn -B -ntp deploy` publishes snapshots on the main branch and releases via the release plugin

## 12. Phase 9: Cutover and Decommissioning

Every phase so far left the Ant build in place while the Maven build grew next to it. This chapter is where the old build is retired. Cutover is a decision with a checklist behind it, not a date on a calendar: the switch happens when the Maven build has demonstrably reached parity with the Ant build, and the decommissioning itself is mostly documentation and deletion work. Done carelessly, a cutover leaves teams with a stale `build.xml` that half the developers still trust; done deliberately, it removes the ambiguity for good.

### Parallel running

Up through the previous chapters, the rule has been to keep `build.xml` working while `pom.xml` matures. The Ant build remains the authoritative one — the build CI runs, the build the README documents, the build developers invoke — while the Maven build is developed and verified alongside it. The migration lives in a branch or in the same tree with the two builds coexisting; either way, nothing in the team's daily workflow depends on Maven until parity is reached.

Define the switch explicitly rather than by drift:

- Pick one artifact — `acme-core-1.0.0-SNAPSHOT.jar` is the natural candidate — and treat "Maven produces the same artifact with the same tests passing" as the definition of parity, verified by the checklist below.
- Document which build is authoritative, and where: in the README, in the CI job description, and in the team channel. "Ant is authoritative until cutover" should be written down, because the parallel-running period is exactly when a developer hits a Maven-only bug and is tempted to fall back silently.
- When the checklist passes, flip the flag in one coordinated change: CI switches from `ant clean test jar` to `mvn -B -ntp verify` (the canonical CI command from Chapter 11), the README's build instructions switch to Maven, and the announcement goes out. After the flag flips, the Ant build becomes the fallback — it should keep working for a short grace period, but fixes go to Maven, not to it.
- Set a sunset date for the fallback. A fallback with no expiration date is just two builds forever, and two builds is the situation the migration exists to end.

The parallel-running period is not the place to be cautious forever. The longer both builds are maintained, the more effort goes into keeping them in sync and the more a divergence between them goes unnoticed — a test that Ant runs but Maven skips, a resource that one build filters and the other does not. The checklist is how you catch those divergences before the flag flips, which is why it should run continuously in CI during the parallel period, not once by hand.

### Verification checklist

Cutover is justified by evidence, and the evidence is this list. Every item should pass before the authoritative flag flips:

- [ ] The same unit tests pass under both builds: `ant test` and `mvn test` both green on the same source revision
- [ ] Test count parity: surefire reports the same number of tests run as the Ant JUnit run — a missing test is usually a naming-convention mismatch (`*Test` vs `Test*`) or a test source directory the POM does not pick up
- [ ] Artifact contents compared: a diff of `unzip -l acme-core-1.0.0-SNAPSHOT.jar` (or `jar tf`) between the Ant-built and Maven-built jars is empty, allowing for differences in the manifest, `META-INF/maven/` metadata, and other Maven-injected packaging metadata
- [ ] Startup smoke test of the built artifact: the Maven-built jar runs — for a library, at least one consumer resolves it from the local repository and links against it; for an application, it starts and answers a trivial request
- [ ] CI produces equivalent outputs: the Maven CI job yields the same artifacts, reports, and coverage data the Ant job did, using the CI wiring from Chapter 11

The artifact-content diff deserves emphasis, because it is the item teams skip and later regret. Ant's `jar` task and Maven's `maven-jar-plugin` package the same classes, but the manifests differ (Maven adds `Created-By`, `Built-By`, and the POM coordinates by default) and Maven injects `META-INF/maven/com.acme/acme-core/pom.xml` and `pom.properties` into the archive. Those differences are expected and fine; what is not fine is a missing class, a stale resource, a file the Ant build filtered and Maven does not, or an extra file left behind by an Ant-only step. Read the diff line by line rather than just checking exit codes — every unexpected entry is a migration gap, and it is far cheaper to find it here than in production.

The smoke test is deliberately minimal. Its purpose is not to prove the artifact works — the test suite covers that — but to prove the artifact is *loadable*: the manifest's classpath and main class are correct, the jar is not corrupted, and nothing that lived outside the jar in the Ant build's classpath layout is now missing at runtime. Classpath-related failures are the classic cutover regression, because Ant's flat `lib/` classpath and Maven's resolved dependency graph differ in what they put on the runtime classpath, and only a real launch surfaces the difference.

### Decommissioning

Once the flag has flipped and the fallback's grace period is ending, remove the old build. Decommissioning is four deletions, a documentation sweep, and one announcement:

**Delete the Ant build.** This means `build.xml` itself, the `lib/` directory (its jars now live in the repository manager or the project's file repository, per Chapter 4), and the Ant property files — `build.properties` and any per-environment property files that Chapter 10 migrated to POM properties and profiles. Do not keep "just in case": version control keeps the history, and a copy of the old build in the tree is an invitation for someone to run it and get a different answer than Maven.

**Update the documentation.** The README's build instructions become the Maven commands; developer onboarding docs, wikis, and any build scripts that shell out to `ant` are found and updated. Search the repository for `ant ` invocations and `build.xml` references before declaring the sweep done — IDE configuration files and contribution guides are the usual hiding places. If the docs reference the file-repository stepping stone from Chapter 4 (internal jars consumed via a repository URL), update those notes too, since the stepping stone's purpose ends when `lib/` is gone.

**Update the CI config.** The pipeline should now contain only the Maven invocation — `mvn -B -ntp verify` on every commit, deploy on the main branch, per Chapter 11. Remove any leftover Ant-related steps: `lib/` checkout logic, Ant home setup, archiving of Ant-era output directories, and any job that runs the old build as a canary.

**Announce the cutover once, with the cheat-sheet.** A single team message that the Ant build is gone, the Maven build is authoritative, and the commands developers need day to day are:

- `mvn clean verify` — full build with tests and gates, the "does it work" command
- `mvn package` — build the jar without the verify gates, for quick local iteration
- `mvn test` — tests only, the fastest feedback loop

Include in the same message the handful of project-specific equivalents of the old Ant targets (which goal replaced `ant dist`, which replaced the codegen target, and so on), because those one-line mappings are what people will otherwise ask about individually for weeks. The announcement is also the natural place to state where the old build can be found if anyone truly needs it: the last commit before `build.xml` was deleted.

### Keeping `maven-antrun-plugin` or not

Cutover is the deadline for the antrun question. Every `maven-antrun-plugin` execution added during the migration, as the escape hatch from Chapter 8, should be audited before the flag flips: list the executions, and for each one, re-run the strategy ladder from Chapter 8 — is there now a plugin equivalent, or does the task belong in a mojo or behind `exec-maven-plugin`?

The decision per Chapter 8's criteria:

- Wrappers around **side effects the lifecycle has no opinion about** — writing a build-info file, publishing a notification, calling an internal script — can stay. Antrun is a fine permanent home for these, and converting them is optional polish.
- Wrappers around anything touching the **compile classpath, test execution, or artifact assembly** must not stay: they were marked as pre-cutover debt when they were added, and cutover is when the debt comes due. A wrapped assembly step means the artifact being certified by the checklist above is not the artifact Maven's own plugins produce, and a wrapped test step forfeits surefire's reporting. These convert before cutover or the cutover waits.
- Wrappers that ran under **deadline pressure** get judged honestly: if the task is low-churn and clearly scoped, keeping the wrapper and tracking it as debt is legitimate; if it is load-bearing in the build proper, it converts.

A useful heuristic for the audit: if deleting an antrun execution would change what lands in `target/classes` or in the packaged artifact, it is build-proper work and needs a native Maven answer before cutover. If deleting it would only remove an external side effect, it can stay indefinitely. Record the outcome of the audit — which wrappers stay, which convert, and why — in the same commit or pull request that flips the authoritative flag, so the state of the escape hatches at cutover is part of the project's history rather than tribal knowledge.

## 13. Troubleshooting and Common Pitfalls

The chapters above covered the happy path. This chapter collects the problems that surface most often during and after an Ant-to-Maven migration, each as a symptom you will recognize, the cause, and the fix. Almost every entry traces back to the same root: Maven enforces rules Ant silently tolerated, so an old build's hidden assumptions become visible errors.

**Symptom: the build fails with a dependency convergence or `omitted for conflict` error, or `mvn dependency:tree -Dverbose` shows two versions of the same artifact.** In the Ant build, two jars could sit side by side in `lib/` for years; in Maven, when the dependency graph contains two versions of one `groupId:artifactId` — for example, `com.google.guava:guava` 25.1-jre pulled in transitively by one dependency and 33.0.0-jre by another — Maven refuses to put both on the classpath and resolves the conflict with the nearest-wins rule described in Chapter 4: it keeps the version closest to the root of the tree and silently drops the other. `mvn dependency:tree -Dverbose` makes the dropped version visible as an `omitted for conflict` line. Nearest-wins is deterministic but the winner is chosen by tree distance, not by judgment — and if an enforcer rule or a strict resolution strategy is in play, the convergence failure is a hard error. The fix is to make the decision yourself: pin the version you want with `<dependencyManagement>` (Chapter 4's example pins `log4j-api`), or remove the unwanted version where it comes from with an `<exclusions>` block on the dependency that pulls it in. Prefer `<dependencyManagement>` for versions your project controls and `<exclusions>` for a transitive dependency that genuinely should not be there; run `mvn dependency:tree -Dverbose` after each change to confirm the resolution.

**Symptom: a `ClassNotFoundException` at runtime for a class that compiled fine, or a test that cannot see a class the main code imports.** These are scope leaks, the flip side of Chapter 4's scope table. The first case is usually a dependency marked `provided` (servlet API, annotation processor, Lombok) that is actually needed at runtime — `provided` is on the compile and test classpaths, so the code compiles and then fails when the jar runs outside the container that was supposed to supply it. The second case is the reverse: a jar marked `test` that the main sources import, which the compiler rejects, or — the sneakier variant — a `test`-scoped dependency that silently changed what a transitive consumer sees. `mvn dependency:tree` prints the scope of every node; scan it for any scope you did not assign deliberately. The fix is to re-scope honestly: `compile` for anything main code uses, `provided` only for what the container or JVM supplies, `runtime` for JDBC drivers and service-loader implementations, `test` for test-only jars.

**Symptom: the build's behavior changed over time, or two machines with the same POM build differently, with no POM change in between.** Maven does not pin plugin versions by default. When a plugin is not declared in the POM, Maven resolves the version from the lifecycle bindings of the Maven version installed on that machine — which means a Maven upgrade, or a difference between developer and CI Maven versions, can change compiler, surefire, or resources plugin behavior without anything in the repository changing. The fix is to require every plugin's version to be declared, and the tool for enforcing that is `maven-enforcer-plugin` with the `requirePluginVersions` rule:

```xml
<build>
  <plugins>
    <plugin>
      <groupId>org.apache.maven.plugins</groupId>
      <artifactId>maven-enforcer-plugin</artifactId>
      <executions>
        <execution>
          <id>enforce-plugin-versions</id>
          <goals>
            <goal>enforce</goal>
          </goals>
          <configuration>
            <rules>
              <requirePluginVersions>
                <message>Every plugin must declare its version in the POM.</message>
              </requirePluginVersions>
            </rules>
          </configuration>
        </execution>
      </executions>
    </plugin>
  </plugins>
</build>
```

With this rule bound (the `enforce` goal's default phase, `validate`, runs it before anything else), a build using an undeclared plugin version fails immediately with the plugin named, instead of quietly behaving differently between machines. Declare an explicit `<version>` for each plugin your build uses — pick current, stable releases and bump them deliberately with `versions:display-plugin-updates` from Chapter 11 — so the same POM produces the same build everywhere. Note that the rule requires versions to be *declared*; it does not choose them for you. The rule also flags the enforcer plugin itself like any other plugin — its failure output names `maven-enforcer-plugin` too if no version is declared for it — so its version should be declared as well, typically in `<pluginManagement>` rather than with a pin in the POM.

**Symptom: after importing the project, the IDE shows red everywhere, sources are marked as plain folders instead of source roots, or m2e reports lifecycle-mapping errors for a plugin execution.** Eclipse's m2e connector and other IDE integrations assume the standard layout from Chapter 3 and a set of well-known plugin executions. A project that kept the legacy layout overrides (Chapter 3's alternative path) or that binds unusual goals to lifecycle phases confuses the importer: it either marks the wrong directories as source roots or refuses to manage the plugin execution at all. The fix is two-sided. First, adopt the standard layout — this is the strongest argument for Chapter 3's preferred path, because every IDE picks up `src/main/java` and `src/test/java` with zero configuration. Second, for plugin executions the IDE cannot handle, either bind them to phases the toolchain recognizes (`generate-sources`, `process-classes`) rather than running them ad hoc, or add the m2e lifecycle-mapping metadata the plugin's documentation describes for executions that should be ignored by the workspace build. IntelliJ's Maven importer is more tolerant of overrides but still reads them from the POM, so the same advice applies: fix the POM, not the IDE settings, or every developer repeats the configuration.

**Symptom: builds that took seconds under Ant now take minutes.** Ant built only what its targets named; Maven runs the full lifecycle, resolves dependencies, and builds every module in the reactor, so an unconditional `mvn install` in a fifteen-module tree rebuilds everything every time. The fixes, in the order they usually matter: use partial builds while iterating — `mvn -pl acme-web -am package` builds one module and its dependencies only (Chapter 9); skip work you do not need with `-o` (offline mode, which skips remote checks when the local repository is warm) and `-DskipTests` or `-Dmaven.javadoc.skip=true` for runs where tests or javadoc are not the point; use `-T` (for example `mvn -T 1C package`) to run the reactor with parallel threads — safe when modules do not share output, which the reactor's dependency ordering mostly guarantees; and put a repository manager (Nexus or Artifactory) in front of your remote dependencies so repeated downloads hit the local network instead of Central, and cache `~/.m2/repository` in CI as Chapter 11 describes. If a build is still slow after all of these, profile it — `mvn -X` and the build-time summary at the end of the log show which plugin executions dominate, and an unexpectedly slow execution is often a misconfigured one (for example, an assembly descriptor scanning a huge directory).

**Symptom: the jar builds fine, but a properties file or XML descriptor that was in the Ant-built artifact is missing from the Maven-built one.** Two causes cover almost every case. First, the resource is not where Maven looks: files that sat next to the sources in the legacy layout (Chapter 2's inventory flags exactly this) must move to `src/main/resources` (or `src/test/resources` for test fixtures), because the resources plugin copies only those directories. Second, the file was produced by an Ant step that filtered, renamed, or generated it — a `<copy>` with a `<filterset>`, a `<replace>`, or a codegen step — and no Maven equivalent was configured, so the lifecycle packages whatever happens to be in `src/main/resources` and skips the transform. Check the built jar with `jar tf target/acme-core-1.0.0-SNAPSHOT.jar` and diff it against the Ant-built artifact (Chapter 12's verification checklist makes this a cutover gate). The fix is to move the files into the resources directories, and for generated or transformed files, add the plugin configuration from Chapter 5 (resources filtering, build-helper source roots) or Chapter 8's Antrun/exec escape hatch — not to copy the file into `target/` by hand.

**Symptom: the build warns `Using platform encoding (UTF-8 actually) to copy filtered resources, i.e. build is platform dependent!` — or compiles fine on one machine and produces mojibake on another.** Ant's `javac encoding="UTF-8"` was explicit; a POM with no encoding property leaves Maven to fall back on the platform's default charset, which differs between machines and operating systems. The fix is one property, which the baseline POM from Chapter 3 already sets — but it is worth restating because dropping it during a refactor is a common regression:

```xml
<project>
  <properties>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <project.reporting.outputEncoding>UTF-8</project.reporting.outputEncoding>
  </properties>
</project>
```

With `project.build.sourceEncoding` set, the compiler and resources plugins read and write sources and filtered resources as UTF-8 on every machine, and the warning disappears. Set it in the parent POM for multi-module builds (Chapter 9) so every module inherits it, and match it to the encoding the Ant `javac` actually used — a migration that changes the encoding at the same time as the build tool makes encoding bugs indistinguishable from migration bugs.

## Appendix A: Ant Task to Maven Plugin Mapping

The table below consolidates the task-by-task mapping in one place. The rows covered in depth in Chapter 5 — with before/after pairs for the core build steps — are marked there; the remaining rows are brief pointers, and Chapter 8's Antrun escape hatch is the fallback for anything not listed.

| Ant task | Maven equivalent | Notes |
| --- | --- | --- |
| `javac` | `maven-compiler-plugin` | Covered in Chapter 5. Bound to `compile` by default; Java version via `maven.compiler.*` properties. |
| `jar` | `maven-jar-plugin` | Covered in Chapter 5. Bound to `package` by default; manifest via the `archive` configuration. |
| `war` | `maven-war-plugin` | Covered in Chapter 5. Bound to `package` when `<packaging>war</packaging>`. |
| `copy` (with `filterset`) | `maven-resources-plugin` | Covered in Chapter 5. Filtering enabled per resource directory; prefer `@token@` delimiters. |
| `delete`, `mkdir` | `maven-clean-plugin` | Covered in Chapter 5. Usually deleted, not converted: `target/` is managed by the lifecycle. |
| `junit` | `maven-surefire-plugin` | Covered in Chapters 5 and 6. Test discovery by naming conventions (`*Test`, `Test*`, `*Tests`). |
| `javadoc` | `maven-javadoc-plugin` | Covered in Chapter 5. Run on demand or bound to `package`/`verify` for release builds. |
| `zip`, `tar` | `maven-assembly-plugin` | Covered in Chapter 5. Bound to `package` with a descriptor; descriptors live under `src/assembly/`. |
| fat jar (one-jar style merges) | `maven-shade-plugin` | Covered in Chapter 5. Include `ServicesResourceTransformer` to merge `META-INF/services/` correctly. |
| `touch` | no direct equivalent (use `maven-antrun-plugin`) | Timestamp-touching files makes builds non-reproducible; usually a sign the step should be redesigned rather than converted. |
| `<condition>` / `<if>` | profiles or plugin configuration | Conditional build logic maps to profile activation (Chapter 10) or to `<profiles>` with `activation` by property or file presence; per-execution conditions belong in plugin configuration. |
| `signjar` | `maven-jarsigner-plugin` | Bind its `sign` goal (default phase `package`; often moved to `verify`); reads the keystore configuration from the plugin's `<configuration>`. |
| `native2ascii` | `native2ascii-maven-plugin` (or resource encoding) | With `project.build.sourceEncoding` set and properties files written as UTF-8, modern JDKs often make the conversion unnecessary; otherwise bind the plugin's goal before `process-resources`. |
| `replace` | `maven-resources-plugin` filtering | Token replacement during resource copy; use `@token@` delimiters and keep binaries out of filtered directories (Chapter 5). |
| `ftp`, `scp` | `maven-deploy-plugin` with a `wagon` provider (or CI-level scripting) | Artifact publishing to a repository is `mvn deploy` (Chapter 11); arbitrary file transfer to servers belongs in the CI pipeline, not the build. |
| `sql` | `sql-maven-plugin` (Codehaus Mojo) | Executes SQL against a JDBC datasource; bind to a phase such as `generate-test-resources` for schema setup, with the driver as a plugin dependency. |
| `wsimport` / `wsdl2java` | corresponding JAXB/CXF/Axis2 plugins | `jaxb2-maven-plugin`, `cxf-codegen-plugin`, or `axis2-wsdl2code-maven-plugin`, bound to `generate-sources`; generated sources are registered automatically (Chapter 5). |
| `antlr` | `antlr4-maven-plugin` | Bound to `generate-sources` by default; registers its output under `target/generated-sources/` automatically. |
| everything else | `maven-antrun-plugin` | Covered in Chapter 8. The escape hatch: embed any Ant task in the lifecycle, with the task jar declared in the plugin's `<dependencies>`. |
