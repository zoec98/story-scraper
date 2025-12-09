from storyscraper.transformers.wattpad_transformer import Transformer


def test_wattpad_transformer_extracts_panel_content() -> None:
    html = """
    <div id="sp1" class="page">
        <div class="part-header">
            <h1 class="h2">Ch 3 The Town</h1>
        </div>
        <div class="panel panel-reading">
            <pre>
                <div class="trinityAudioPlaceholder"></div>
                <p>Intro text.</p>
                <p>I warily eased through the undergrowth.</p>
            </pre>
        </div>
        <div class="panel panel-reading">
            <pre>
                <p>Calum and Merryl disappeared before we reached the spires.</p>
                <p>They'd kill as many as they could get their claws on.</p>
            </pre>
        </div>
        <div class="right-rail">ads</div>
    </div>
    """

    transformer = Transformer()
    markdown = transformer._convert_html_to_markdown(html)  # type: ignore[attr-defined]

    assert markdown.lstrip().startswith("# Ch 3 The Town")
    assert "Intro text." in markdown
    assert "I warily eased through the undergrowth." in markdown
    assert "Calum and Merryl disappeared before we reached the spires." in markdown
    assert "kill as many as they could get their claws on." in markdown
    assert "trinityAudioPlaceholder" not in markdown
    assert "ads" not in markdown
