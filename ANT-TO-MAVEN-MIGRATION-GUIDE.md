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

The Maven compiler plugin reads `maven.compiler.debug` as a property, so `mvn compile` builds with the default from the POM and `mvn compile -Dmaven.compiler.debug=false` overrides it from the command line — the same convention as `-Dcompile.debug=true`, with the POM supplying the default instead of the script. User-defined properties work the same way: any `<properties>` entry can be overridden with `-D` and referenced as `${name}` in plugin configuration. Chapter 7 revisits this pattern for environment-specific settings, where it becomes the basis for profiles.

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
| everything else | `maven-antrun-plugin` | The escape hatch: embed any Ant task in the lifecycle. Covered fully in Chapter 7. |

Two rows deserve emphasis before the examples. First, `delete` and `mkdir`: in Ant these exist because the build must create and reset its own scratch directories. Maven's standard layout removes the need — `target/` is created on demand and wiped by `mvn clean` — so the correct migration for a `clean` target that deletes `build/` and `dist/` is deletion of the target itself, not a `maven-clean-plugin` configuration. If a `delete` target removes something other than build output (a scratch file, a downloaded artifact), that is a different conversation, and Chapter 7 covers how to keep it. Second, `junit`: Ant's `<junit>` block with its `<batchtest>` is replaced not just by the surefire plugin but by its conventions — test classes named `*Test`, `Test*`, or `*Tests` in `src/test/java` are discovered automatically. Chapter 6 covers the details, including `@RunWith`/`@Nested` edge cases and nonstandard names.

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

Two things to check when translating a `jar` target: whether it used `includes`/`excludes` to split classes across multiple jars (Maven strongly prefers one artifact per module — split with a multi-module build per Chapter 8 rather than per-jar filters), and whether it jars anything other than compiled classes. A jar that bundles `lib/*.jar` inside it is not a plain jar — that is a shaded jar, covered below.

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

- [ ] Every target in the Chapter 2 inventory mapped to a row in the table above (or flagged for Chapter 7's Antrun escape hatch)
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
