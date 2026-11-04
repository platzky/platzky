import logging

import pytest
from werkzeug.test import TestResponse

from platzky.config import Config
from platzky.platzky import create_app_from_config

CONTENT_URLS = ["/blog/slug", "/blog/page/slug"]
CONTENT_ERROR = "Please contact the site administrator."


def _get(url: str, markdown: str, flags: dict[str, bool] | None = None) -> TestResponse:
    content = {
        "author": "author",
        "slug": "slug",
        "title": "title",
        "language": "en",
        "contentInMarkdown": markdown,
        "excerpt": "excerpt",
    }
    config = Config.model_validate(
        {
            "APP_NAME": "testApp",
            "SECRET_KEY": "secret",
            "USE_WWW": False,
            "BLOG_PREFIX": "/blog",
            "TRANSLATION_DIRECTORIES": [],
            "FEATURE_FLAGS": flags or {},
            "DB": {
                "TYPE": "json",
                "DATA": {
                    "site_content": {"posts": [content], "pages": [content]},
                    "plugins": {},
                },
            },
        }
    )
    app = create_app_from_config(config)
    return app.test_client().get(url)


def _html(url: str, markdown: str, flags: dict[str, bool] | None = None) -> str:
    response = _get(url, markdown, flags)
    assert response.status_code == 200
    return response.get_data(as_text=True)


def _refused(url: str, markdown: str) -> str:
    response = _get(url, markdown)
    assert response.status_code == 500
    assert CONTENT_ERROR in response.get_data(as_text=True)
    return response.get_data(as_text=True)


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_markdown_is_rendered_as_html(url: str):
    html = _html(url, "First line.\n\n## Heading\n\nSome **bold** text.\n\n> A quote")
    assert "<p>First line.</p>" in html
    assert "<h2>Heading</h2>" in html
    assert "<strong>bold</strong>" in html
    assert "<blockquote><p>A quote</p></blockquote>" in html
    assert "## Heading" not in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_markdown_links_lists_and_task_lists_are_rendered(url: str):
    html = _html(url, "[Passkey](https://example.com/a_b_c)\n\n- one\n- [ ] todo\n- [x] done")
    assert '<a href="https://example.com/a_b_c">Passkey</a>' in html
    assert "<li>one</li>" in html
    assert 'type="checkbox"> todo</li>' in html
    assert 'checked="checked" disabled="disabled" type="checkbox"> done</li>' in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_shortcodes_inside_markdown_still_render(url: str):
    html = _html(url, 'Some *emphasis* and [link url="/x_y"]a **link**[/link].')
    assert '<a href="/x_y"' in html
    assert "<strong>link</strong>" in html
    assert "<em>emphasis</em>" in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_authored_html_passes_through_markdown(url: str):
    html = _html(url, "Before <b>bold</b> after.")
    assert "<p>Before <b>bold</b> after.</p>" in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_strip_content_html_keeps_markdown_formatting(url: str):
    html = _html(url, "**kept** and <b>stripped</b>", flags={"STRIP_CONTENT_HTML": True})
    assert "<strong>kept</strong>" in html
    assert "<b>stripped</b>" not in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_html_block_is_not_formatted_as_markdown(url: str):
    html = _html(url, 'Intro\n\n[html]<div class="box">\n\n    <img src="/a.png">\n</div>[/html]')
    assert '<div class="box">' in html
    assert '<img src="/a.png">' in html
    assert "<pre>" not in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_shortcode_alone_on_a_line_is_not_wrapped_in_a_paragraph(url: str):
    html = _html(url, 'Intro\n\n[image url="/a.png" alt="a"]\n\nOutro')
    assert '<img src="/a.png" alt="a">' in html
    assert "<p><img" not in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_line_right_after_a_shortcode_alone_is_still_markdown(url: str):
    html = _html(url, 'Intro\n\n[image url="/a.png" alt="a"]\nA caption with **bold** text')
    assert '<img src="/a.png" alt="a">' in html
    assert "<p>A caption with <strong>bold</strong> text</p>" in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_shortcode_on_its_own_line_inside_a_paragraph_keeps_the_paragraph(url: str):
    html = _html(url, 'Click\n[link url="/x"]here[/link]\nto **go**.')
    assert '<p>Click <a href="/x">here</a> to <strong>go</strong>.</p>' in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_blank_line_of_spaces_makes_paragraphs_inside_a_shortcode(url: str):
    html = _html(url, '[link url="/x"]first\n   \nsecond[/link]')
    assert "<p>first</p>" in html
    assert "<p>second</p>" in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_indented_shortcode_children_are_not_code_blocks(url: str):
    html = _html(
        url,
        '[slideshow]\n    [figure image="/a.jpg"][/figure]\n    [figure image="/b.jpg"][/figure]\n'
        "[/slideshow]",
    )
    assert 'src="/a.jpg"' in html
    assert 'src="/b.jpg"' in html
    assert "<pre>" not in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_markdown_never_links_to_script(url: str):
    html = _html(url, "[x](javascript:alert(2))")
    assert 'href="javascript:' not in html


@pytest.mark.parametrize(
    ("markdown", "shown"),
    [
        (
            'Write `[link url="/x"]go[/link]` for a link.',
            "<code>[link url=&#34;/x&#34;]go[/link]</code>",
        ),
        (
            '```\n[image url="/a.png"]\n```',
            "<pre><code>[image url=&#34;/a.png&#34;]\n</code></pre>",
        ),
        (
            'Intro\n\n    [image url="/a.png"]',
            "<pre><code>[image url=&#34;/a.png&#34;]\n</code></pre>",
        ),
    ],
)
def test_shortcode_in_code_is_shown_as_written(markdown: str, shown: str):
    html = _html("/blog/slug", markdown)
    assert shown in html
    assert "platzky-shortcode" not in html


def test_shortcode_outside_code_still_renders_beside_one_in_code():
    html = _html("/blog/slug", '`[image url="/a.png"]` renders as [image url="/a.png"]')
    assert "<code>[image url=&#34;/a.png&#34;]</code> renders as <img" in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_html_block_cannot_run_script(url: str):
    html = _refused(url, "[html]<b>kept</b><script>alert(1)</script>[/html]")
    assert "alert(1)" not in html


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_markdown_cannot_run_script(url: str, caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.ERROR):
        html = _refused(url, "**bold** <script>alert(1)</script>")
    assert "alert(1)" not in html
    assert "<script> is not allowed" in caplog.text


@pytest.mark.parametrize("url", CONTENT_URLS)
def test_markdown_cannot_carry_event_handlers(url: str):
    html = _refused(url, '<p onclick="alert(1)">go</p>')
    assert "alert(1)" not in html
