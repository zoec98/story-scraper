from __future__ import annotations

from pathlib import Path

from storyscraper.options import StoryScraperOptions
from storyscraper.transformers.bdsmlibrary_transformer import Transformer


def test_bdsmlibrary_transformer_converts_pre_to_markdown(tmp_path: Path) -> None:
    html = """
    <html><body>
    <h3 align="center">Chapter 2</h3>
    <pre>
    First paragraph.

    Second paragraph with a dash – and some spacing.
    </pre>
    </body></html>
    """
    transformer = Transformer()
    markdown = transformer._convert_html_to_markdown(html)  # type: ignore[attr-defined]

    assert markdown.lstrip().startswith("# Chapter 2")
    assert "First paragraph." in markdown
    assert "Second paragraph" in markdown
    assert "\n\n" in markdown


def test_bdsmlibrary_transformer_decodes_cp1252_files(tmp_path: Path) -> None:
    story_dir = tmp_path / "story"
    html_dir = story_dir / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    html_path = html_dir / "story-001.html"
    content = """
    <html><body>
    <h3 align="center">Chapter 1</h3>
    <pre>Quoted text: \u201cHello\u201d</pre>
    </body></html>
    """
    html_path.write_bytes(content.encode("cp1252"))

    options = StoryScraperOptions(
        name="Story",
        slug="story",
        fetch_agent="bdsmlibrary_fetcher",
        transform_agent="bdsmlibrary_transformer",
        packaging_agent="auto",
        download_url="https://www.bdsmlibrary.com/stories/story.php?storyid=1",
        author=None,
        chosen_author=None,
        chosen_name="Story",
        chosen_slug="story",
    )

    transformer = Transformer()
    generated = transformer.transform_phase(options, stories_root=tmp_path)

    assert len(generated) == 1
    output = generated[0].read_text(encoding="utf-8")
    assert "Quoted text" in output


def test_bdsmlibrary_transformer_splits_indented_paragraphs() -> None:
    html = """
    <html><body>
    <h3 align="center">Indented Story</h3>
    <pre>
        "So, Miss Brooks, why are you applying for this job?"
        Jennifer looked down at her hands when she replied. "Mister Hane..."
      He stared at her, and Jennifer met his gaze for a moment before looking away again.

        Jennifer took the offered money, with a bit of disbelief in her eyes. "Really?" she said.
    </pre>
    </body></html>
    """

    transformer = Transformer()
    markdown = transformer._convert_html_to_markdown(html)  # type: ignore[attr-defined]

    paragraphs = markdown.strip().split("\n\n")
    assert paragraphs[0].startswith("# Indented Story")
    assert len(paragraphs) == 5
    assert paragraphs[1].startswith('"So, Miss Brooks')
    assert "He stared at her" in paragraphs[3]
    assert paragraphs[2].startswith("Jennifer looked down at her hands")
    assert paragraphs[4].startswith("Jennifer took the offered money")
