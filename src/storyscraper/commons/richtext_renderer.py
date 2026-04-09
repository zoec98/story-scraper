"""Shared rich-text document rendering helpers."""

from __future__ import annotations

import html
import json


def render_richtext_document(payload: str | dict[str, object]) -> str | None:
    """Render a ProseMirror/Tiptap-like document payload to HTML."""

    document: object = payload
    if isinstance(payload, str):
        try:
            document = json.loads(payload)
        except json.JSONDecodeError:
            return None

    if not isinstance(document, dict):
        return None
    return render_richtext_node(document)


def render_tiptap_markup(markup: str) -> str | None:
    """Render DeviantArt-style Tiptap markup payloads to HTML."""

    try:
        payload = json.loads(markup)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    document = payload.get("document")
    if not isinstance(document, dict):
        return None
    return render_richtext_node(document)


def render_richtext_node(node: dict[str, object]) -> str:
    node_type = node.get("type")
    if not isinstance(node_type, str):
        return ""

    attrs = node.get("attrs")
    attributes = attrs if isinstance(attrs, dict) else {}
    content = node.get("content")
    children = ""
    if isinstance(content, list):
        children = "".join(
            render_richtext_node(child) for child in content if isinstance(child, dict)
        )

    if node_type == "doc":
        return children
    if node_type == "paragraph":
        return f"<p>{children}</p>"
    if node_type == "heading":
        level = attributes.get("level", 1)
        if not isinstance(level, int):
            level = 1
        level = max(1, min(6, level))
        return f"<h{level}>{children}</h{level}>"
    if node_type == "blockquote":
        return f"<blockquote>{children}</blockquote>"
    if node_type == "bulletList":
        return f"<ul>{children}</ul>"
    if node_type == "orderedList":
        start = attributes.get("start", 1)
        if isinstance(start, int) and start != 1:
            return f'<ol start="{start}">{children}</ol>'
        return f"<ol>{children}</ol>"
    if node_type == "listItem":
        return f"<li>{children}</li>"
    if node_type == "hardBreak":
        return "<br/>"
    if node_type == "horizontalRule":
        return "<hr/>"
    if node_type == "text":
        text = node.get("text")
        if not isinstance(text, str):
            return ""
        return apply_marks(text, node.get("marks"))
    if node_type == "da-mention":
        user: dict[str, object] = {}
        raw_user = attributes.get("user")
        if isinstance(raw_user, dict):
            user = raw_user
        username = user.get("username")
        if isinstance(username, str) and username:
            return f"@{username}"
        return ""
    return children


def apply_marks(text: str, marks: object) -> str:
    rendered = html.escape(text, quote=True)
    if not isinstance(marks, list):
        return rendered

    for mark in marks:
        if not isinstance(mark, dict):
            continue
        mark_type = mark.get("type")
        attrs = mark.get("attrs")
        attributes = attrs if isinstance(attrs, dict) else {}
        if mark_type == "bold":
            rendered = f"<strong>{rendered}</strong>"
        elif mark_type == "italic":
            rendered = f"<em>{rendered}</em>"
        elif mark_type == "underline":
            rendered = f"<u>{rendered}</u>"
        elif mark_type == "strike":
            rendered = f"<del>{rendered}</del>"
        elif mark_type == "code":
            rendered = f"<code>{rendered}</code>"
        elif mark_type == "link":
            href = attributes.get("href")
            if isinstance(href, str) and href:
                rendered = f'<a href="{html.escape(href, quote=True)}">{rendered}</a>'

    return rendered
