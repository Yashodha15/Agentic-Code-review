from pathlib import Path

from aegis_review.diff_parser import parse_unified_diff


FIXTURE = Path(__file__).parent / "fixtures" / "sample_pr.diff"


def test_parser_tracks_added_lines_for_each_destination_file() -> None:
    parsed = parse_unified_diff(FIXTURE.read_text(encoding="utf-8"))

    assert parsed.changed_files == ["src/access.py", "src/new_name.py"]
    assert parsed.by_path()["src/access.py"].publishable_lines == frozenset({10, 11, 12})
    assert parsed.by_path()["src/new_name.py"].publishable_lines == frozenset({1})


def test_parser_handles_new_and_deleted_files() -> None:
    content = """diff --git a/new.py b/new.py
new file mode 100644
--- /dev/null
+++ b/new.py
@@ -0,0 +1,2 @@
+FIRST = 1
+SECOND = 2
diff --git a/deleted.py b/deleted.py
deleted file mode 100644
--- a/deleted.py
+++ /dev/null
@@ -1 +0,0 @@
-OLD = True
"""

    parsed = parse_unified_diff(content)

    assert parsed.by_path()["new.py"].publishable_lines == frozenset({1, 2})
    assert parsed.files[1].new_path is None

