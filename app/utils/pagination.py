def paginate_query(query, page: int, per_page: int, max_per_page: int = 100):
    """Paginate a SQLAlchemy query.

    Returns:
        (items, total, pages) tuple
    """
    per_page = min(max(1, per_page), max_per_page)
    page = max(1, page)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    return pagination.items, pagination.total, pagination.pages
