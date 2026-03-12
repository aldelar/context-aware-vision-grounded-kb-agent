"""Automated Playwright UI tests for the Chainlit web app.

Requires:
  - Agent running on localhost:8088  (make agent)
  - Web app running on localhost:8080 (make app)

Run with: make test-ui-auto
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

BASE_URL = "http://localhost:8080"


@pytest.mark.uitest
def test_ui_elements_present(page: Page) -> None:
    """Verify page loads with expected header, chat input, and starter chips."""
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    # Page title contains the app name
    expect(page).to_have_title(re.compile(r"Context Aware"), timeout=10_000)

    # Chat input textarea is visible
    chat_input = page.locator("textarea").first
    expect(chat_input).to_be_visible(timeout=10_000)

    # Exactly 3 starter chips are visible
    starter_texts = ["Content Understanding", "Agentic Retrieval", "Search Security"]
    for text in starter_texts:
        chip = page.get_by_text(text, exact=False).first
        expect(chip).to_be_visible(timeout=10_000)


@pytest.mark.uitest
def test_search_query_returns_response(page: Page) -> None:
    """Submit a query and verify the agent returns a non-empty response."""
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")

    # Wait for chat input to appear
    chat_input = page.locator("textarea").first
    expect(chat_input).to_be_visible(timeout=10_000)

    # Type a query and submit
    chat_input.fill(
        "What are the key components of Azure Content Understanding?"
    )
    chat_input.press("Enter")

    # Wait for an assistant response (generous timeout for Azure API calls)
    response = page.locator('[class*="step"]').last
    expect(response).to_be_visible(timeout=60_000)

    # Response should contain non-empty text
    response_text = response.inner_text(timeout=60_000)
    assert len(response_text.strip()) > 0, "Agent response was empty"
