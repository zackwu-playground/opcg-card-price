import types
import sys

# Provide minimal stub modules for requests and bs4
sys.modules.setdefault('requests', types.ModuleType('requests'))

class FakeTag:
    def __init__(self, text):
        self._text = text
    def get_text(self, strip=False):
        return self._text.strip() if strip else self._text

from html.parser import HTMLParser

class H2Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_target = False
        self.data = []
        self.headers = []
    def handle_starttag(self, tag, attrs):
        if tag == 'h2':
            for name, val in attrs:
                if name == 'class' and val == 'accordion-header':
                    self.in_target = True
                    self.data = []
    def handle_endtag(self, tag):
        if tag == 'h2' and self.in_target:
            self.headers.append(''.join(self.data))
            self.in_target = False
    def handle_data(self, data):
        if self.in_target:
            self.data.append(data)

class FakeBeautifulSoup:
    def __init__(self, html, parser):
        self.html = html
    def select(self, selector):
        if selector != 'h2.accordion-header':
            return []
        parser = H2Parser()
        parser.feed(self.html)
        return [FakeTag(text) for text in parser.headers]

bs4_module = types.ModuleType('bs4')
bs4_module.BeautifulSoup = FakeBeautifulSoup
sys.modules.setdefault('bs4', bs4_module)

from test import parse_headers


def test_parse_headers():
    html = """
    <html>
        <body>
            <h2 class="accordion-header">First header</h2>
            <div><h2 class="accordion-header">Second header</h2></div>
            <h2>Ignored header</h2>
            <h2 class="accordion-header">Third header</h2>
        </body>
    </html>
    """
    expected = ["First header", "Second header", "Third header"]
    assert parse_headers(html) == expected
