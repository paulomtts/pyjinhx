import re
from html.parser import HTMLParser
from pydantic import BaseModel, Field


RE_PASCAL_CASE_TAG_NAME = re.compile(r'^[A-Z](?:[a-z]+(?:[A-Z][a-z]+)*)?$')

class Tag(BaseModel):
    name: str
    attrs: dict[str, str]
    content: list[str] = Field(default_factory=list)
    self_closing: bool = False
    raw_opening_tag: str = ""

    # def build_component(self) -> "BaseComponent":

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []          # stack of Tag instances
        self.output = []         # final output buffer
        self.tags = []

    def _is_custom_component(self, tag: str) -> bool:
        return bool(RE_PASCAL_CASE_TAG_NAME.match(tag))
    
    def _extract_tag_name_from_raw(self, raw_tag: str) -> str:
        match = re.search(r'<\s*([A-Za-z][A-Za-z0-9]*)', raw_tag)
        if match:
            return match.group(1)
        return ""

    def _attrs_to_dict(self, attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        result = {}
        for attr_name, attr_value in attrs:
            result[attr_name] = attr_value if attr_value is not None else ""
        return result

    def _escape_content(self, content: str) -> str:
        return content.replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')

    def handle_starttag(self, tag, attrs):
        raw_tag_text = self.get_starttag_text()
        original_tag_name = self._extract_tag_name_from_raw(raw_tag_text)
        
        if original_tag_name and self._is_custom_component(original_tag_name):
            attrs_dict = self._attrs_to_dict(attrs)
            tag_instance = Tag(name=original_tag_name, attrs=attrs_dict, self_closing=False, raw_opening_tag=raw_tag_text)
            self.stack.append(tag_instance)
        else:
            attrs_str = ""
            if attrs:
                attrs_list = []
                for attr_name, attr_value in attrs:
                    if attr_value is None:
                        attrs_list.append(attr_name)
                    else:
                        attrs_list.append(f'{attr_name}="{attr_value}"')
                attrs_str = " " + " ".join(attrs_list)
            
            tag_html = f"<{tag}{attrs_str}>"
            if self.stack:
                self.stack[-1].content.append(tag_html)
            else:
                self.output.append(tag_html)

    def handle_startendtag(self, tag, attrs):
        raw_tag_text = self.get_starttag_text()
        original_tag_name = self._extract_tag_name_from_raw(raw_tag_text)
        
        if original_tag_name and self._is_custom_component(original_tag_name):
            if self.stack:
                self.stack[-1].content.append(raw_tag_text)
            else:
                content = ""
                escaped_content = self._escape_content(content)
                rendered = f'Registry.render("{original_tag_name}", content="{escaped_content}")'
                self.output.append(rendered)
        else:
            attrs_str = ""
            if attrs:
                attrs_list = []
                for attr_name, attr_value in attrs:
                    if attr_value is None:
                        attrs_list.append(attr_name)
                    else:
                        attrs_list.append(f'{attr_name}="{attr_value}"')
                attrs_str = " " + " ".join(attrs_list)
            
            tag_html = f"<{tag}{attrs_str} />"
            if self.stack:
                self.stack[-1].content.append(tag_html)
            else:
                self.output.append(tag_html)

    def handle_endtag(self, tag):
        if self.stack and self._is_custom_component(self.stack[-1].name) and tag.lower() == self.stack[-1].name.lower():
            tag_instance = self.stack.pop()
            self.tags.append(tag_instance)
            inner = "".join(tag_instance.content).strip()
            
            if self.stack:
                closing_tag = f"</{tag_instance.name}>"
                raw_html = tag_instance.raw_opening_tag + inner + closing_tag
                self.stack[-1].content.append(raw_html)
            else:
                escaped_content = self._escape_content(inner)
                rendered = f'Registry.render(name="{tag_instance.name}", data={tag_instance.attrs}, content="{escaped_content}")'
                self.output.append(rendered)
        else:
            closing_tag = f"</{tag}>"
            if self.stack:
                self.stack[-1].content.append(closing_tag)
            else:
                self.output.append(closing_tag)

    def handle_data(self, data):
        if self.stack:
            self.stack[-1].content.append(data)
        else:
            self.output.append(data)

    def render(self, source: str):
        """
        Renders the source string and returns HTML markup.
        """
        pass


# ----------------------------------------------------

source = """
<div>
<MyComp id="1">
   Hello
   <MyComp id="2">Nested!</MyComp>
   {% for item in items %}
   <div>{{ item }}</div>
   {% endfor %}
</MyComp>
</div>
"""

parser = Parser()
parser.feed(source)
print(''.join(parser.output))
for item in parser.tags:
    print(item)