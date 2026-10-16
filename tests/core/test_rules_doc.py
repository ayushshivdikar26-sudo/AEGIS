"""
Test to ensure docs/RULES.md matches the output of scripts/gen_rules_doc.py (FR-E6).
Fails if documentation is stale.
"""

from pathlib import Path

from scripts.gen_rules_doc import generate_rules_markdown

DOCS_RULES_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "RULES.md"


def test_rules_doc_not_stale():
    assert DOCS_RULES_PATH.exists(), "docs/RULES.md does not exist"
    with open(DOCS_RULES_PATH, "r", encoding="utf-8") as f:
        committed_content = f.read()

    fresh_content = generate_rules_markdown()
    assert committed_content == fresh_content, (
        "docs/RULES.md is stale. Run 'python scripts/gen_rules_doc.py' to update it."
    )
