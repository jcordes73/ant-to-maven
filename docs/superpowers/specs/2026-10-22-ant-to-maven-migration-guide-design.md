# Ant to Maven Migration Guide — Design

Date: 2026-10-22

## Overview

A comprehensive, single-document Markdown guide for migrating Apache Ant builds to Apache Maven. The guide is generic (not tied to a specific project or organization) and is organized around the lifecycle of a real migration: each chapter covers one phase, with before/after code pairs showing an Ant `build.xml` snippet and its Maven `pom.xml` equivalent.

## Deliverable

- **File:** `ANT-TO-MAVEN-MIGRATION-GUIDE.md` in the repository root
- **Format:** Markdown, single document, with a table of contents
- **Style:** Before/after pairs — Ant snippet alongside equivalent Maven XML for each topic
- **Recurring example:** A fictional project "acme-core" (Java 11, JUnit, some custom Ant tasks) used consistently throughout

## Audience

Developers and build engineers on any team migrating Ant-based Java builds to Maven. Assumes familiarity with Ant concepts (targets, tasks, classpaths, properties) but not with Maven.

## Guide Structure

### 1. Introduction
- Why migrate: declarative builds, dependency management, transitive resolution, ecosystem tooling
- When *not* to migrate
- Ant vs Maven philosophy: imperative procedures vs declarative project model

### 2. Phase 0: Assess the existing build
- How to inventory a `build.xml`: classpaths, targets, custom tasks, generated sources, copy/filtering steps, compiler settings
- Pre-migration checklist of things to capture
- How to identify blockers (nonstandard layout, heavy code generation, procedural steps with no plugin equivalent)

### 3. Phase 1: Scaffold the POM
- Standard directory layout (`src/main/java`, `src/test/java`) vs keeping the Ant layout via `<sourceDirectory>` overrides
- Coordinates (groupId/artifactId/version), packaging
- Java compiler settings; `maven-compiler-plugin` replacing `javac` tasks

### 4. Phase 2: Dependencies
- Replace manual `lib/` jars and `<path>` classpaths with managed dependencies
- Translating build flags to properties
- Finding transitive deps; `<dependencyManagement>`
- Internal jars → repository publishing; temporary file-based repo as a stepping stone
- Handling version conflicts Ant silently tolerated

### 5. Phase 3: Map build steps to plugins
- Task-to-plugin mapping table with before/after pairs: javac → compiler, jar → jar, war → war, copy/resources → resources, junit → surefire, mkdir/clean → clean, javadoc → javadoc
- Resource filtering
- Generated sources via `build-helper-maven-plugin`
- Manifest generation
- Assembly/shade for fat jars

### 6. Phase 4: Migrate tests
- JUnit/TestNG via Surefire
- Test naming conventions vs explicit `<include>`
- Test resources
- Code coverage (JaCoCo replacing Ant coverage tasks)
- Integration tests with Failsafe

### 7. Phase 5: Custom Ant tasks and the antrun escape hatch
- Strategy ladder: plugin equivalent → wrap in `maven-antrun-plugin` → migrate task code into a plugin or `exec-maven-plugin`
- When wrapping is acceptable short-term vs permanent

### 8. Phase 6: Multi-module builds
- `<subant>`/`<ant>` cross-project calls → Maven reactor and aggregator POMs
- Parent POMs replacing shared Ant properties/macros
- Inter-module dependency management and build ordering

### 9. Phase 7: Profiles, properties, environments
- Ant properties files → Maven properties/profiles
- Environment-specific builds (dev/test/prod) via profiles and resource filtering
- When to prefer externalized config over profiles

### 10. Phase 8: CI/CD and release
- Replacing Ant-based CI scripts
- `mvn deploy`, `versions` plugin, `maven-release-plugin`
- Artifact versioning discipline (SNAPSHOT vs release)

### 11. Phase 9: Cutover and decommissioning
- Running Ant and Maven in parallel during transition
- Verification checklist (artifact comparison where feasible, test parity)
- Deleting `build.xml`, updating docs, team communication

### 12. Troubleshooting and common pitfalls
- Dependency convergence errors, scope leaks, plugin version pinning, IDE integration, performance (offline mode, parallel builds)

### Appendix A
- Consolidated Ant task → Maven plugin mapping table (quick reference)

## Testing / Verification

The deliverable is documentation. Verification:
- All chapters in the outline are present in the final document
- Every before/after pair's Maven XML is well-formed and uses real, current plugin artifactIds
- Table of contents links resolve to all chapter anchors
- Examples are internally consistent with the acme-core example project

## Out of Scope

- Gradle or other build-tool alternatives
- Framework-specific migration tooling walkthroughs (e.g., a mention is fine, but no deep dive)
- Multi-page docs site generation
