"""
Test: Skill Metadata Parsing

Verifies that all SKILL.md files:
1. Exist in their skill directories
2. Have valid YAML frontmatter
3. Contain required fields (name, description, triggers, keywords)

Run: python tests/test_skill_metadata.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml


def test_skill_metadata():
    """Test that all skill metadata parses correctly."""

    skills_dir = Path(__file__).parent.parent / "skills"

    print("=" * 60)
    print("TEST: Skill Metadata Parsing")
    print("=" * 60)
    print(f"\nSkills directory: {skills_dir}")
    print()

    results = {"passed": 0, "failed": 0, "skills": []}

    # Expected skills
    expected_skills = [
        "understand_image",
        "generate_character",
        "generate_video",
        "generate_music",
        "compose_final",
    ]

    for skill_name in expected_skills:
        skill_dir = skills_dir / skill_name
        skill_md = skill_dir / "SKILL.md"

        print(f"Testing: {skill_name}")
        print("-" * 40)

        # Check directory exists
        if not skill_dir.exists():
            print(f"  ✗ Directory not found: {skill_dir}")
            results["failed"] += 1
            continue
        print(f"  ✓ Directory exists")

        # Check SKILL.md exists
        if not skill_md.exists():
            print(f"  ✗ SKILL.md not found")
            results["failed"] += 1
            continue
        print(f"  ✓ SKILL.md exists")

        # Check YAML frontmatter
        content = skill_md.read_text()
        if not content.startswith("---"):
            print(f"  ✗ Missing YAML frontmatter (should start with ---)")
            results["failed"] += 1
            continue
        print(f"  ✓ Has YAML frontmatter")

        # Parse frontmatter
        end = content.find("---", 3)
        if end < 0:
            print(f"  ✗ Invalid frontmatter (missing closing ---)")
            results["failed"] += 1
            continue

        frontmatter = content[3:end].strip()
        try:
            metadata = yaml.safe_load(frontmatter)
        except yaml.YAMLError as e:
            print(f"  ✗ YAML parse error: {e}")
            results["failed"] += 1
            continue
        print(f"  ✓ YAML parses correctly")

        # Check required fields
        required_fields = ["name", "description", "triggers", "keywords"]
        missing = [f for f in required_fields if f not in metadata]
        if missing:
            print(f"  ✗ Missing required fields: {missing}")
            results["failed"] += 1
            continue
        print(f"  ✓ All required fields present")

        # Validate field types
        if not isinstance(metadata["triggers"], list):
            print(f"  ✗ 'triggers' should be a list")
            results["failed"] += 1
            continue
        if not isinstance(metadata["keywords"], list):
            print(f"  ✗ 'keywords' should be a list")
            results["failed"] += 1
            continue
        print(f"  ✓ Field types correct")

        # Print metadata
        print(f"  → name: {metadata['name']}")
        print(f"  → description: {metadata['description'][:50]}...")
        print(f"  → triggers: {len(metadata['triggers'])} items")
        print(f"  → keywords: {metadata['keywords']}")

        results["passed"] += 1
        results["skills"].append(metadata)
        print()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Passed: {results['passed']}/{len(expected_skills)}")
    print(f"Failed: {results['failed']}/{len(expected_skills)}")

    if results["failed"] == 0:
        print("\n✅ All tests passed!")
        return True
    else:
        print("\n❌ Some tests failed!")
        return False


def test_skill_module_imports():
    """Test that the skills module can be imported."""

    print()
    print("=" * 60)
    print("TEST: Skill Module Imports")
    print("=" * 60)
    print()

    try:
        from skills import list_skills, get_skill_context, SKILLS_DIR
        print("✓ Imported list_skills")
        print("✓ Imported get_skill_context")
        print(f"✓ SKILLS_DIR: {SKILLS_DIR}")
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

    # Test list_skills
    print()
    print("Testing list_skills():")
    skills = list_skills()
    print(f"  → Found {len(skills)} skills")
    for s in skills:
        print(f"    • {s['name']}")

    if len(skills) < 5:
        print(f"✗ Expected 5 skills, found {len(skills)}")
        return False
    print("✓ All 5 skills found")

    # Test get_skill_context
    print()
    print("Testing get_skill_context():")
    context = get_skill_context()
    print(f"  → Generated {len(context)} characters")
    print(f"  → Preview:\n{context[:200]}...")
    print("✓ Context generated successfully")

    print("\n✅ All import tests passed!")
    return True


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print(" SKILL METADATA TESTS")
    print("=" * 60 + "\n")

    # Change to project root for imports
    import os
    os.chdir(Path(__file__).parent.parent)

    test1 = test_skill_metadata()
    test2 = test_skill_module_imports()

    print("\n" + "=" * 60)
    print(" FINAL RESULT")
    print("=" * 60)

    if test1 and test2:
        print("\n✅ ALL TESTS PASSED\n")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED\n")
        sys.exit(1)
