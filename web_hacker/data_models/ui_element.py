"""
web_hacker/data_models/ui_element.py

UI Element data models for comprehensive element description and replay.
"""

from enum import StrEnum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class SelectorType(StrEnum):
    CSS = "css"
    XPATH = "xpath"
    TEXT = "text"          # e.g. "button with label X"
    ROLE = "role"          # e.g. role+name/aria-label
    NAME = "name"          # input[name="..."]
    ID = "id"              # #id


# Default priority mapping for selector types (lower = higher priority)
DEFAULT_SELECTOR_PRIORITIES: Dict[SelectorType, int] = {
    SelectorType.ID: 10,           # Highest priority - IDs are unique
    SelectorType.NAME: 20,         # Form controls by name are very stable
    SelectorType.CSS: 30,          # CSS selectors (with stable attributes)
    SelectorType.ROLE: 40,         # ARIA roles + labels
    SelectorType.TEXT: 50,         # Text-based matching
    SelectorType.XPATH: 80,        # XPath (often brittle, last resort)
}


class Selector(BaseModel):
    """
    A single way to locate an element.
    `value` is the raw string (CSS, XPath, etc.)
    `type` tells the executor how to interpret it.
    `priority` controls which selector to try first (lower = higher priority).
    If not specified, uses the default priority for the selector type.
    """
    type: SelectorType
    value: str
    priority: Optional[int] = Field(
        default=None,
        description="Priority for this selector (lower = higher priority). If None, uses default for selector type.",
    )

    description: Optional[str] = Field(
        default=None,
        description="Human readable note (e.g. 'primary stable selector').",
    )
    
    def get_priority(self) -> int:
        """Get the effective priority, using default if not set."""
        if self.priority is not None:
            return self.priority
        return DEFAULT_SELECTOR_PRIORITIES.get(self.type, 100)


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class UiElement(BaseModel):
    """
    Unified description of a UI element sufficient for robust replay.

    - Raw DOM data (tag, attributes, text)
    - Multiple selectors (CSS, XPath, text-based, etc.)
    - Context (URL, frame)
    """
    # Context
    url: Optional[str] = Field(
        default=None,
        description="Page URL where this element was observed.",
    )
    frame_xpath: Optional[str] = Field(
        default=None,
        description="XPath to the frame/iframe containing this element (if any).",
    )

    # Core DOM identity
    tag_name: str
    id: Optional[str] = None
    name: Optional[str] = None
    class_names: Optional[List[str]] = Field(default=None, description="List of CSS class names.")

    # Common attributes
    type_attr: Optional[str] = Field(default=None, description="Input type, button type, etc.")
    role: Optional[str] = None
    aria_label: Optional[str] = None
    placeholder: Optional[str] = None
    title: Optional[str] = None
    href: Optional[str] = None
    src: Optional[str] = None
    value: Optional[str] = None

    # Full attribute map for anything else (data-*, etc.)
    attributes: Optional[Dict[str, str]] = Field(
        default=None,
        description="All raw attributes from the DOM element.",
    )

    # Content
    text: Optional[str] = Field(
        default=None,
        description="Trimmed inner text (useful for text-based selectors).",
    )

    # Geometry
    bounding_box: Optional[BoundingBox] = None

    # Locators (multiple ways to find it again)
    selectors: Optional[List[Selector]] = Field(
        default=None,
        description="Ordered list of selectors to try when locating this element.",
    )

    # Convenience accessors for most common selectors
    css_path: Optional[str] = None    # from getElementPath
    xpath: Optional[str] = None       # full xpath

    def build_default_selectors(self) -> None:
        """
        Populate `selectors` from known fields if empty.
        Call this once after constructing from raw DOM.
        """
        if self.selectors is None:
            self.selectors = []
        elif self.selectors:
            return
        
        # Ensure attributes is a dict for easier access
        if self.attributes is None:
            self.attributes = {}
        
        # Ensure class_names is a list
        if self.class_names is None:
            self.class_names = []

        # Highest priority: ID (uses default priority from DEFAULT_SELECTOR_PRIORITIES)
        if self.id:
            self.selectors.append(
                Selector(
                    type=SelectorType.ID,
                    value=self.id,
                    description="Locate by DOM id",
                )
            )

        # Name / placeholder for inputs
        if self.name and self.tag_name.lower() in {"input", "textarea", "select"}:
            self.selectors.append(
                Selector(
                    type=SelectorType.NAME,
                    value=self.name,
                    description="Locate form control by name",
                )
            )
        if self.placeholder and self.tag_name.lower() in {"input", "textarea"}:
            self.selectors.append(
                Selector(
                    type=SelectorType.CSS,
                    value=f'{self.tag_name.lower()}[placeholder="{self.placeholder}"]',
                    description="Locate by placeholder",
                )
            )

        # Role + text
        if self.role and self.text:
            snippet = self.text.strip()
            if snippet:
                self.selectors.append(
                    Selector(
                        type=SelectorType.TEXT,
                        value=snippet[:80],
                        description=f"Locate by role={self.role} and text snippet",
                    )
                )

        # Direct CSS and XPath if we have them
        if self.css_path:
            self.selectors.append(
                Selector(
                    type=SelectorType.CSS,
                    value=self.css_path,
                    description="Recorded CSS path",
                )
            )
        if self.xpath:
            self.selectors.append(
                Selector(
                    type=SelectorType.XPATH,
                    value=self.xpath,
                    description="Full XPath (last resort)",
                )
            )

        # Fallback: first stable-looking class
        if not self.selectors and self.class_names:
            stable_classes = [
                c for c in self.class_names
                if not c.startswith("sc-")
                and not c.startswith("css-")
                and (not c.isalnum() or len(c) < 10)
            ]
            if stable_classes:
                cls = stable_classes[0]
                self.selectors.append(
                    Selector(
                        type=SelectorType.CSS,
                        value=f".{cls}",
                        description="Fallback by single stable-looking class",
                    )
                )

