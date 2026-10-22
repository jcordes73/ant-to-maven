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

TODO: content

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
