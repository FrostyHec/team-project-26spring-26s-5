"""Campus news source adapters.

Keep this package init lightweight.  Individual source modules may import
heavier dependencies such as email services, so callers should import concrete
adapters from their module paths when needed.
"""

__all__: list[str] = []
