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
