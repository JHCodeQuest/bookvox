"""Build small synthetic epubs for tests, so no copyrighted book is needed."""
from ebooklib import epub


def build_epub(path, documents):
    """Write an epub where `documents` is a list of (file_name, paragraph_text)."""
    book = epub.EpubBook()
    book.set_identifier('test-book')
    book.set_title('Test Book')
    book.set_language('en')
    items = []
    for name, text in documents:
        item = epub.EpubHtml(title=name, file_name=name, lang='en')
        item.content = f'<html><body><p>{text}</p></body></html>'
        book.add_item(item)
        items.append(item)
    nav = epub.EpubNav()
    book.add_item(nav)
    book.add_item(epub.EpubNcx())  # without it read_epub fails to resolve the spine's toc id
    book.spine = items
    epub.write_epub(str(path), book)
