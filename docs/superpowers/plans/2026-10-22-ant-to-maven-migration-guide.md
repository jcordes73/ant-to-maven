# Ant to Maven Migration Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write a comprehensive single-document Markdown migration guide (`ANT-TO-MAVEN-MIGRATION-GUIDE.md`) covering 9 migration phases, troubleshooting, and a task-mapping appendix, with before/after Ant/Maven code pairs throughout.

**Architecture:** One deliverable Markdown file built chapter by chapter. A small Python verifier script (created in Task 1) extracts every fenced `xml` code block from the guide and validates well-formedness, and checks that every table-of-contents link resolves to a heading anchor in the document. Each task adds one chapter (or appendix) and re-runs the verifier.

**Tech Stack:** Markdown, Python 3 (standard library only) for the snippet/anchor verifier, git.

## Global Constraints

- Deliverable file: `ANT-TO-MAVEN-MIGRATION-GUIDE.md` at repo root (exact name).
- Single Markdown document with a table of contents at the top; every TOC entry links to a chapter heading anchor in the same file.
- Style: before/after pairs — Ant `build.xml` snippet in a fenced `xml` block followed by the equivalent Maven `pom.xml` configuration in a fenced `xml` block, for each topic.
- Recurring example project: "acme-core", groupId `com.acme`, artifactId `acme-core`, Java 11, JUnit 5, plus custom Ant tasks. All examples across chapters must stay consistent with this project.
- Maven XML must use real artifactIds (e.g., `maven-compiler-plugin`, `maven-surefire-plugin`, `maven-antrun-plugin`, `build-helper-maven-plugin`, `jacoco-maven-plugin`, `maven-shade-plugin`). Do not invent plugin names. Do not pin plugin version numbers unless the section explicitly discusses version pinning (Chapter 12 does; that is the only place).
- Language: English, technical, practitioner-oriented. No emojis.
- Guide prose must not reference this plan or the spec.

## Verification Tooling

All chapter tasks run the same two commands after writing content:

```
python3 tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md
```

Expected: `OK: N xml snippets well-formed, M toc links resolve` (exit 0). If it prints a failure (malformed XML, unresolved anchor), fix the guide and re-run until OK.

The script is created in Task 1 and lives at `tools/check_snippets.py`.

---

### Task 1: Verifier script and document skeleton

**Files:**
- Create: `tools/check_snippets.py`
- Create: `ANT-TO-MAVEN-MIGRATION-GUIDE.md` (title + TOC placeholders for all chapters, empty section bodies)

**Interfaces:**
- Consumes: nothing
- Produces: `tools/check_snippets.py` — usage `python3 tools/check_snippets.py <markdown-file>`. Behavior: (1) extract all fenced code blocks tagged `xml`, parse each with `xml.etree.ElementTree.fromstring` (wrapping multi-root content in a synthetic root), report malformed ones with line numbers; (2) parse all `[text](#anchor)` links in the file, verify each anchor matches a generated GitHub-style heading slug (lowercase, spaces→hyphens, punctuation stripped); exit 1 with messages on any failure, print `OK: ...` summary on success.

- [ ] **Step 1: Write the verifier script**

```python
#!/usr/bin/env python3
"""Validate a Markdown guide: xml snippet well-formedness and TOC anchors."""
import re
import sys
import xml.etree.ElementTree as ET


def heading_slug(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s]+", "-", text)


def main(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        content = f.read()

    errors = []

    # 1. XML snippet well-formedness
    fence_re = re.compile(r"```xml\n(.*?)```", re.DOTALL)
    snippets = fence_re.findall(content)
    for i, snippet in enumerate(snippets, 1):
        try:
            ET.fromstring(f"<root>{snippet}</root>")
        except ET.ParseError as e:
            errors.append(f"xml snippet #{i} is malformed: {e}")

    # 2. TOC anchor resolution
    anchors = set()
    for line in content.splitlines():
        m = re.match(r"#{1,6}\s+(.*)", line)
        if m:
            anchors.add(heading_slug(m.group(1)))
    links = re.findall(r"\]\(#([^)]+)\)", content)
    for anchor in links:
        if anchor not in anchors:
            errors.append(f"toc link '#{anchor}' does not resolve to a heading")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print(f"OK: {len(snippets)} xml snippets well-formed, {len(links)} toc links resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
```

- [ ] **Step 2: Run the script against a scratch file to verify it works**

Run: `printf '# Title\n\nSee [intro](#missing).\n' > /tmp/bad.md && python3 tools/check_snippets.py /tmp/bad.md`
Expected: `FAIL: toc link '#missing' does not resolve to a heading`, exit 1.

Run: `printf '# Title\n\nSee [intro](#title).\n' > /tmp/good.md && python3 tools/check_snippets.py /tmp/good.md`
Expected: `OK: 0 xml snippets well-formed, 1 toc links resolve`, exit 0.

- [ ] **Step 3: Create the guide skeleton**

Create `ANT-TO-MAVEN-MIGRATION-GUIDE.md` with the document title and a table of contents with these exact entries (each a Markdown link to the anchor of the future chapter heading):

```markdown
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
```

Beneath the TOC, add each chapter heading (`## 1. Introduction` etc., matching the anchors above) with a single placeholder paragraph `TODO: content`. Placeholders are temporary and must be removed by the final task; intermediate tasks replace theirs with real content.

- [ ] **Step 4: Run the verifier**

Run: `python3 tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md`
Expected: `OK: 0 xml snippets well-formed, 13 toc links resolve`

- [ ] **Step 5: Commit**

```bash
git add tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md
git commit -m "docs: add guide skeleton and snippet/anchor verifier"
```

---

### Task 2: Chapter 1 — Introduction

**Files:**
- Modify: `ANT-TO-MAVEN-MIGRATION-GUIDE.md` (replace the `## 1. Introduction` placeholder)

**Interfaces:**
- Consumes: TOC anchor `#1-introduction` from Task 1 (heading text `## 1. Introduction` must remain exactly)
- Produces: nothing consumed by later tasks

- [ ] **Step 1: Write the chapter**

Replace the placeholder with content covering, in order:
1. Why migrate: declarative project model, built-in dependency management with transitive resolution, conventional lifecycle and standardized commands, ecosystem tooling (IDE integration, CI, artifact repositories, billions of published artifacts on Maven Central).
2. When *not* to migrate: builds dominated by procedural steps with no plugin equivalent, legacy code generators tightly coupled to Ant, projects near end-of-life — note that `maven-antrun-plugin` (Chapter 7) widens the practical window.
3. Philosophy comparison: Ant is a build *scripting* library (imperative: you write every procedure in XML; no built-in notion of a project, dependencies, or lifecycle), Maven is a build *framework* (declarative: you describe the project and its dependencies; the framework supplies the lifecycle and conventions). Contrast "target" vs "phase/goal" vocabulary in a short table.

Include no code snippets in this chapter.

- [ ] **Step 2: Run the verifier**

Run: `python3 tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md`
Expected: `OK: ...` (snippet count unchanged, no FAIL lines)

- [ ] **Step 3: Commit**

```bash
git add ANT-TO-MAVEN-MIGRATION-GUIDE.md
git commit -m "docs: write chapter 1 - introduction"
```

---

### Task 3: Chapter 2 — Phase 0: Assess the existing build

**Files:**
- Modify: `ANT-TO-MAVEN-MIGRATION-GUIDE.md` (replace the `## 2. Phase 0: Assess the Existing Build` placeholder)

**Interfaces:**
- Consumes: TOC anchor `#2-phase-0-assess-the-existing-build`
- Produces: nothing consumed by later tasks

- [ ] **Step 1: Write the chapter**

Content, in order:
1. How to inventory a `build.xml`: enumerate every target and its `depends` chain; extract every `<path>`/`<classpath>` element; list custom tasks (`<taskdef>`, `<typedef>`) and where their classes come from; find generated-source steps (`<javacc>`, `<jaxb>`, `<wsimport>`, custom generators); find copy/filter/replace steps; capture compiler options (`source`, `target`, `debug`, `encoding`, `excludes`).
2. A pre-migration checklist (Markdown checkbox list) of everything to capture before starting: compiler flags, full classpath contents, JVM version, packaging artifacts produced (jar/war/zip), signing/manifest steps, test invocation, environment-specific property files.
3. How to identify blockers: source layout far from standard, heavy code generation, procedural steps with no plugin equivalent. For each, one sentence on the escape hatch (layout override in Chapter 3, build-helper in Chapter 5, antrun in Chapter 7).

Include one example: a representative `build.xml` excerpt for the acme-core project showing `<path>` with a `lib` fileset, a `compile` target with `javac source="1.8"`, and a `clean` target. No Maven counterpart yet — this chapter is assessment only; state that explicitly in prose.

- [ ] **Step 2: Run the verifier**

Run: `python3 tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md`
Expected: `OK: 1 xml snippets well-formed, ...`

- [ ] **Step 3: Commit**

```bash
git add ANT-TO-MAVEN-MIGRATION-GUIDE.md
git commit -m "docs: write chapter 2 - assess the existing build"
```

---

### Task 4: Chapter 3 — Phase 1: Scaffold the POM

**Files:**
- Modify: `ANT-TO-MAVEN-MIGRATION-GUIDE.md` (replace the `## 3. Phase 1: Scaffold the POM` placeholder)

**Interfaces:**
- Consumes: TOC anchor `#3-phase-1-scaffold-the-pom`; the acme-core assessment from Chapter 2
- Produces: the acme-core baseline `pom.xml` (groupId `com.acme`, artifactId `acme-core`, version `1.0.0-SNAPSHOT`, packaging `jar`, Java 11 compiler config) that Chapters 4–10 extend

- [ ] **Step 1: Write the chapter**

Content, in order:
1. Coordinates: explain groupId/artifactId/version/packaging; mapping from a jar filename convention to coordinates.
2. Standard layout: explain `src/main/java`, `src/main/resources`, `src/test/java`, `src/test/resources`, `target/`; include a directory tree in a fenced `text` block.
3. Preferred path: physically move sources to the standard layout (show `git mv` commands in a fenced `bash` block for the acme-core case: `git mv src com/acme/core`-style move from an assumed legacy layout `src/com/acme/core` into `src/main/java/com/acme/core`).
4. Alternative path: keep the legacy layout with overrides — before/after pair showing an Ant layout assumption vs a `pom.xml` with `<sourceDirectory>`, `<testSourceDirectory>`, `<resources>`, `<testResources>` overrides. Warn about tooling that assumes convention.
5. The baseline POM: before/after pair — the Ant `project` element with `default="jar"` vs the complete minimal `pom.xml` for acme-core with `maven.compiler.source`/`maven.compiler.target` properties set to 11 (via `maven-compiler-plugin` properties, not explicit plugin config), `project.build.sourceEncoding` UTF-8.

- [ ] **Step 2: Run the verifier**

Run: `python3 tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md`
Expected: `OK` with snippet count increased by at least 2 (one Ant, one full pom.xml)

- [ ] **Step 3: Commit**

```bash
git add ANT-TO-MAVEN-MIGRATION-GUIDE.md
git commit -m "docs: write chapter 3 - scaffold the POM"
```

---

### Task 5: Chapter 4 — Phase 2: Dependencies

**Files:**
- Modify: `ANT-TO-MAVEN-MIGRATION-GUIDE.md` (replace the `## 4. Phase 2: Dependencies` placeholder)

**Interfaces:**
- Consumes: TOC anchor `#4-phase-2-dependencies`; baseline POM from Chapter 3
- Produces: acme-core `<dependencies>` block (commons-lang3 3.14.0, junit-jupiter 5.10.2 test-scoped, log4j-api) used implicitly by later chapters' examples

- [ ] **Step 1: Write the chapter**

Content, in order:
1. From `lib/` jars to managed dependencies: before/after pair — Ant `<path id="compile.classpath">` with a `<fileset dir="lib">` vs a `pom.xml` `<dependencies>` section listing the same jars by coordinates (show acme-core with `org.apache.commons:commons-lang3:3.14.0` compile-scoped and `org.junit.jupiter:junit-jupiter:5.10.2` test-scoped). Explain scopes (`compile`, `provided`, `runtime`, `test`, `system`) and that `system` scope is deprecated/last-resort.
2. Transitive resolution: explain that Maven fetches dependencies of dependencies; `mvn dependency:tree` to inspect; how to find coordinates on Maven Central (search by jar filename/hash).
3. Version conflicts Ant silently tolerated: `<dependencyManagement>` to pin versions; `mvn dependency:tree -Dverbose` to spot conflicts; `nearest-wins` resolution explained in two sentences.
4. Internal jars: publishing shared company artifacts to a repository manager (Nexus/Artifactory) as the end state; a temporary file-based repository in the POM (`<repositories><repository>` with `file://${project.basedir}/local-repo`) as a stepping stone, with a before/after pair showing the Ant copy-from-shared-drive pattern vs the file repo config.
5. Build flags to properties: brief before/after showing an Ant `-Dcompile.debug=true` convention vs Maven properties and `-D` usage on the command line.

- [ ] **Step 2: Run the verifier**

Run: `python3 tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md`
Expected: `OK`, snippet count increased by at least 3

- [ ] **Step 3: Commit**

```bash
git add ANT-TO-MAVEN-MIGRATION-GUIDE.md
git commit -m "docs: write chapter 4 - dependencies"
```

---

### Task 6: Chapter 5 — Phase 3: Map build steps to plugins

**Files:**
- Modify: `ANT-TO-MAVEN-MIGRATION-GUIDE.md` (replace the `## 5. Phase 3: Map Build Steps to Plugins` placeholder)

**Interfaces:**
- Consumes: TOC anchor `#5-phase-3-map-build-steps-to-plugins`; baseline POM and dependencies from Chapters 3–4
- Produces: nothing consumed by later tasks (later chapters reference this chapter's mapping table by link)

- [ ] **Step 1: Write the chapter**

Content, in order:
1. The lifecycle in two paragraphs: phases (`validate`, `compile`, `test`, `package`, `verify`, `install`, `deploy`) vs Ant targets; plugins bind goals to phases; `mvn package` runs everything up to package.
2. A core mapping table: Ant task → Maven equivalent → notes. Rows: `javac` → `maven-compiler-plugin`; `jar` → `maven-jar-plugin`; `war` → `maven-war-plugin`; `copy`/filtering → `maven-resources-plugin`; `delete`/`mkdir` → `maven-clean-plugin` (+ conventions); `junit` → `maven-surefire-plugin`; `javadoc` → `maven-javadoc-plugin`; `zip`/`tar` → `maven-assembly-plugin`; fat jar → `maven-shade-plugin`; everything else → `maven-antrun-plugin`.
3. Before/after pair per major row: (a) `javac` target vs compiler-plugin config; (b) `jar` target with `<manifest>` vs jar-plugin with `archive/manifest` config; (c) `copy`+`filterset` vs resources-plugin `filtering` enabled and a `application.properties` with `@project.version@`; (d) assembly: Ant `<zip>` of jar+docs+scripts vs a minimal `maven-assembly-plugin` `jar-with-dependencies` (or `src` descriptor) config; (e) shade: Ant one-jar-style merge vs shade plugin config with `ServicesResourceTransformer`.
4. Generated sources: before/after — Ant codegen target writing to `build/gen` vs `build-helper-maven-plugin` `add-source` goal adding a generated directory, with prose noting most generators exist as Maven plugins (e.g., JAXB, ANTLR) and should be preferred.

- [ ] **Step 2: Run the verifier**

Run: `python3 tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md`
Expected: `OK`, snippet count increased by at least 8

- [ ] **Step 3: Commit**

```bash
git add ANT-TO-MAVEN-MIGRATION-GUIDE.md
git commit -m "docs: write chapter 5 - map build steps to plugins"
```

---

### Task 7: Chapter 6 — Phase 4: Migrate tests

**Files:**
- Modify: `ANT-TO-MAVEN-MIGRATION-GUIDE.md` (replace the `## 6. Phase 4: Migrate Tests` placeholder)

**Interfaces:**
- Consumes: TOC anchor `#6-phase-4-migrate-tests`; acme-core junit-jupiter dependency from Chapter 4
- Produces: nothing consumed by later tasks

- [ ] **Step 1: Write the chapter**

Content, in order:
1. Surefire basics: `mvn test`; default naming conventions (`*Test`, `Test*`, `*Tests`, `*TestCase`) vs Ant explicit `<include name="**/*Test.java">`; before/after pair of an Ant `junit` task with explicit includes/formatter vs zero-config Surefire (only present if overriding, e.g., excludes).
2. TestNG note: same plugin, `<testNGXml>` or auto-detection; one short paragraph.
3. Test resources: `src/test/resources` replacing Ant copy steps into test classpath.
4. Coverage: before/after — Ant JaCoCo/Cobertura task wrapping junit vs `jacoco-maven-plugin` `prepare-agent` + `report` bound to `verify`, producing `target/site/jacoco`.
5. Integration tests: Ant pattern of a separate `itest` target vs Failsafe plugin with `*IT` naming, `integration-test` and `verify` goals; short before/after pair.
6. JUnit 4 vs 5 note: vintage engine for legacy JUnit 4 tests during migration; one short paragraph.

- [ ] **Step 2: Run the verifier**

Run: `python3 tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md`
Expected: `OK`, snippet count increased by at least 4

- [ ] **Step 3: Commit**

```bash
git add ANT-TO-MAVEN-MIGRATION-GUIDE.md
git commit -m "docs: write chapter 6 - migrate tests"
```

---

### Task 8: Chapter 7 — Phase 5: Custom Ant tasks and the antrun escape hatch

**Files:**
- Modify: `ANT-TO-MAVEN-MIGRATION-GUIDE.md` (replace the `## 7. Phase 5: Custom Ant Tasks and the Antrun Escape Hatch` placeholder)

**Interfaces:**
- Consumes: TOC anchor `#7-phase-5-custom-ant-tasks-and-the-antrun-escape-hatch`
- Produces: nothing consumed by later tasks

- [ ] **Step 1: Write the chapter**

Content, in order:
1. The strategy ladder, presented as an ordered decision list:
   1. Find a plugin equivalent (most "custom" tasks replicate something that exists).
   2. Wrap the task with `maven-antrun-plugin` — acceptable short-term, acceptable long-term only for genuinely odd steps.
   3. Rewrite the task logic as a Maven plugin or call it via `exec-maven-plugin`.
2. Antrun example: before/after — a `<taskdef>` + custom task invocation in acme-core's `build.xml` (invent a plausible `com.acme.build.VersionStampTask` that writes a version stamp file) vs `maven-antrun-plugin` config with `<target>` invoking the same task, including the `dependencies` block inside antrun to put the task jar on Ant's classpath.
3. When wrapping is acceptable: clearly-scoped side effects, low churn, deadline pressure; when it is not: anything touching the compile classpath, test execution, or artifact assembly — those must become native Maven before cutover.
4. `exec-maven-plugin` alternative: short before/after showing Ant `<exec>`/`<java>` vs `exec-maven-plugin` `java`/`exec` goals.

- [ ] **Step 2: Run the verifier**

Run: `python3 tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md`
Expected: `OK`, snippet count increased by at least 3

- [ ] **Step 3: Commit**

```bash
git add ANT-TO-MAVEN-MIGRATION-GUIDE.md
git commit -m "docs: write chapter 7 - custom ant tasks and antrun"
```

---

### Task 9: Chapter 8 — Phase 6: Multi-module builds

**Files:**
- Modify: `ANT-TO-MAVEN-MIGRATION-GUIDE.md` (replace the `## 8. Phase 6: Multi-Module Builds` placeholder)

**Interfaces:**
- Consumes: TOC anchor `#8-phase-6-multi-module-builds`; acme-core example (now expanded to `acme-core` + `acme-web`)
- Produces: nothing consumed by later tasks

- [ ] **Step 1: Write the chapter**

Content, in order:
1. The reactor: one command builds dependent modules in correct order; `<modules>` in the aggregator POM.
2. Before/after pair: Ant `<subant>` (or repeated `<ant antfile=...>` calls with manual ordering in a script) vs an aggregator `pom.xml` (packaging `pom`) listing `acme-core` and `acme-web` modules.
3. Parent POMs: shared properties, dependency versions, and plugin management in a parent vs Ant's shared property files and copy-pasted macrodefs; before/after pair showing a parent POM with `<properties>` + `<dependencyManagement>` and the child inheriting.
4. Inter-module dependencies: child declares `<dependency>` on sibling by coordinates; reactor resolves it from the build, no local `install` required.
5. Build ordering and partial builds: `-pl acme-web -am`; one short paragraph.

- [ ] **Step 2: Run the verifier**

Run: `python3 tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md`
Expected: `OK`, snippet count increased by at least 3

- [ ] **Step 3: Commit**

```bash
git add ANT-TO-MAVEN-MIGRATION-GUIDE.md
git commit -m "docs: write chapter 8 - multi-module builds"
```

---

### Task 10: Chapter 9 — Phase 7: Profiles, properties, environments

**Files:**
- Modify: `ANT-TO-MAVEN-MIGRATION-GUIDE.md` (replace the `## 9. Phase 7: Profiles, Properties, Environments` placeholder)

**Interfaces:**
- Consumes: TOC anchor `#9-phase-7-profiles-properties-environments`
- Produces: nothing consumed by later tasks

- [ ] **Step 1: Write the chapter**

Content, in order:
1. Properties: Ant `<property file="build.properties">` vs Maven `<properties>` and `settings.xml`; built-in properties (`${project.version}`, `${project.build.directory}`).
2. Profiles: activation (`-P`, property-based, file-based); before/after pair — Ant `dev.properties`/`prod.properties` selected by `-Denv=` vs two Maven profiles `dev` (default active) and `prod` that set properties / enable filtering.
3. Environment-specific builds via resource filtering: profile-defined `filter` values replacing Ant `<filterset>` per environment.
4. When *not* to use profiles: configuration that varies per deployment should be externalized at runtime (read from filesystem/env vars), not baked into artifacts at build time — two to three sentences of guidance; one-build-fits-all-artifact principle.

- [ ] **Step 2: Run the verifier**

Run: `python3 tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md`
Expected: `OK`, snippet count increased by at least 2

- [ ] **Step 3: Commit**

```bash
git add ANT-TO-MAVEN-MIGRATION-GUIDE.md
git commit -m "docs: write chapter 9 - profiles properties environments"
```

---

### Task 11: Chapter 10 — Phase 8: CI/CD and release

**Files:**
- Modify: `ANT-TO-MAVEN-MIGRATION-GUIDE.md` (replace the `## 10. Phase 8: CI/CD and Release` placeholder)

**Interfaces:**
- Consumes: TOC anchor `#10-phase-8-cicd-and-release`
- Produces: nothing consumed by later tasks

- [ ] **Step 1: Write the chapter**

Content, in order:
1. CI: replacing Ant-based CI scripts (e.g., `ant clean test jar` invocation lines) with Maven lifecycle invocations (`mvn verify`); caching `~/.m2/repository` in CI; `mvn -B -ntp` flags for clean logs.
2. Versioning discipline: SNAPSHOT semantics vs release; why Ant builds often lack versioning discipline and how Maven enforces it.
3. Release tooling: `versions:set` / `versions:commit-revert` from `versions-maven-plugin` for bulk version changes; `maven-release-plugin` for tagged, reproducible releases (short description, config example).
4. Deploy: `<distributionManagement>` config and `mvn deploy`; repository manager credentials in `settings.xml`.

- [ ] **Step 2: Run the verifier**

Run: `python3 tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md`
Expected: `OK`, snippet count increased by at least 2

- [ ] **Step 3: Commit**

```bash
git add ANT-TO-MAVEN-MIGRATION-GUIDE.md
git commit -m "docs: write chapter 10 - CI/CD and release"
```

---

### Task 12: Chapter 11 — Phase 9: Cutover and decommissioning

**Files:**
- Modify: `ANT-TO-MAVEN-MIGRATION-GUIDE.md` (replace the `## 11. Phase 9: Cutover and Decommissioning` placeholder)

**Interfaces:**
- Consumes: TOC anchor `#11-phase-9-cutover-and-decommissioning`
- Produces: nothing consumed by later tasks

- [ ] **Step 1: Write the chapter**

Content, in order:
1. Parallel running: keep `build.xml` working while `pom.xml` matures; document which build is authoritative and switch the flag once Maven reaches parity.
2. Verification checklist (Markdown checkbox list): same unit tests pass under both builds; test count parity; artifact contents compared (`unzip -l` / `jar tf` diff, allowing for manifest and metadata differences); startup smoke test of the built artifact; CI produces equivalent outputs.
3. Decommissioning: delete `build.xml`, `lib/`, Ant property files; update README, dev docs, CI config; one team announcement with the new commands cheat-sheet (`mvn clean verify`, `mvn package`, `mvn test`).
4. Keep `maven-antrun-plugin` or not: audit leftover antrun usages at cutover and decide per Chapter 7's ladder.

Include no code snippets.

- [ ] **Step 2: Run the verifier**

Run: `python3 tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md`
Expected: `OK` (counts unchanged from Task 11)

- [ ] **Step 3: Commit**

```bash
git add ANT-TO-MAVEN-MIGRATION-GUIDE.md
git commit -m "docs: write chapter 11 - cutover and decommissioning"
```

---

### Task 13: Chapter 12 — Troubleshooting and Appendix A

**Files:**
- Modify: `ANT-TO-MAVEN-MIGRATION-GUIDE.md` (replace the `## 12. Troubleshooting and Common Pitfalls` placeholder AND the `## Appendix A: Ant Task to Maven Plugin Mapping` placeholder)

**Interfaces:**
- Consumes: TOC anchors `#12-troubleshooting-and-common-pitfalls` and `#appendix-a-ant-task-to-maven-plugin-mapping`; consolidates the per-chapter mapping rows from Chapter 5
- Produces: final, placeholder-free document

- [ ] **Step 1: Write Chapter 12**

Content, in order, as problem/solution pairs (symptom in bold, cause and fix in prose):
1. Dependency convergence errors / `conflict` warnings — explain mediation, fix with `<dependencyManagement>` or `<exclusions>`.
2. Scope leaks (`provided` needed at runtime, `test` leaking into compile) — how to spot with `dependency:tree`.
3. Wrong plugin behavior because versions were not pinned — explain that plugin versions are NOT pinned by default and builds can change behavior over time; recommend `maven-enforcer-plugin` `requirePluginVersions` rule (this is the one place a specific version-pin discussion belongs, per Global Constraints).
4. IDE integration issues (m2e import problems from nonstandard layout) — fix by adopting standard layout or configuring m2e.
5. Slow builds — `-o` offline mode, `-T` parallel threads, `-pl -am` partial builds, repository manager caching.
6. "My jar is missing resources" — resources not under `src/main/resources` or wrong filtering config.
7. Encoding warnings — set `project.build.sourceEncoding` explicitly.

Include at most 2 short code snippets in this chapter (enforcer rule, encoding property).

- [ ] **Step 2: Write Appendix A**

A single consolidated Markdown table, columns: **Ant Task** | **Maven Equivalent** | **Notes**. Consolidate all rows from Chapter 5's table plus these additional rows: `<touch>` → no direct equivalent (use antrun); `<condition>`/`<if>` → profiles or plugin config; `<signjar>` → `maven-jarsigner-plugin`; `<native2ascii>` → `native2ascii-maven-plugin` or resource encoding; `<replace>` → resources filtering; `<ftp>`/`<scp>` → `maven-deploy-plugin`/`wagon` or CI-level scripting; `<sql>` → `sql-maven-plugin`; `<wsimport>`/`<wsdl2java>` → corresponding JAXB/CXF/Axis2 plugins; `<antlr>` → `antlr4-maven-plugin`. Add a one-line preamble noting Chapter 5 covers the top rows in depth with before/after pairs.

- [ ] **Step 3: Remove all remaining placeholders and run final verification**

Run: `grep -n "TODO: content" ANT-TO-MAVEN-MIGRATION-GUIDE.md`
Expected: no output (exit 1).

Run: `python3 tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md`
Expected: `OK: <N> xml snippets well-formed, 13 toc links resolve`

- [ ] **Step 4: Commit**

```bash
git add ANT-TO-MAVEN-MIGRATION-GUIDE.md
git commit -m "docs: write chapter 12 troubleshooting and appendix A task mapping"
```

---

## Final Verification (after Task 13)

- [ ] Run `python3 tools/check_snippets.py ANT-TO-MAVEN-MIGRATION-GUIDE.md` — expected `OK`
- [ ] Run `grep -rn "TODO" ANT-TO-MAVEN-MIGRATION-GUIDE.md tools/` — expected no output in the guide
- [ ] `git log --oneline` shows one commit per task
