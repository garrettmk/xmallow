import re
import types
import itertools
from lxml import etree


########################################################################################################################


def remove_namespaces(xml):
    """Remove all traces of namespaces from the given XML string."""
    re_ns_decl = re.compile(r' xmlns(:\w*)?="[^"]*"', re.IGNORECASE)
    re_ns_open = re.compile(r'<\w+:')
    re_ns_close = re.compile(r'/\w+:')

    response = re_ns_decl.sub('', xml)  # Remove namespace declarations
    response = re_ns_open.sub('<', response)  # Remove namespaces in opening tags
    response = re_ns_close.sub('/', response)  # Remove namespaces in closing tags
    return response


########################################################################################################################


class ValidationError(Exception):
    pass


class Field:
    """Basic field type."""

    def __init__(self, path, cast=str, default=None, many=False, required=False):
        self.path = path
        self.cast = cast
        self.default = default
        self.many = many
        self.required = required

    def get_tags(self, root):
        """Return a list of tags selected by this field."""
        tags = root.xpath(self.path)
        return tags if self.many else tags[:1]

    def extract(self, tag):
        """Extract data from a tag."""
        if isinstance(self.cast, (Field, Schema)):
            return self.cast.load(tag)
        elif isinstance(self.cast, types.FunctionType):
            return self.cast(tag)
        else:
            return self.cast(tag.text)

    def load(self, tag):
        tags = self.get_tags(tag)
        if not tags and self.required:
            raise ValidationError(f'Required field is missing: {self.path}')

        tags = tags if self.many else tags[:1]
        results = [self.extract(tag) for tag in tags]

        if not results:
            return self.default() if callable(self.default) else self.default
        elif not self.many:
            return results[0]

        return results


class First(Field):
    """Takes an iterable of paths, and uses data from the first result."""

    def get_tags(self, root):
        tags = []
        for path in self.path:
            tags = root.xpath(path)
            if tags:
                break

        return tags


class Boolean(Field):
    """A field that casts to a Boolean value."""

    truthy = ('1', 'true', 'yes')
    falsy = ('0', 'false', 'no')

    def extract(self, tag):
        text = tag.text
        if text in self.truthy:
            return True
        elif text in self.falsy:
            return False

        return bool(text)


class String(Field):
    """A string field."""
    cast = str


class Int(Field):
    """An integer field."""
    cast = int


class Float(Field):
    """A float field."""
    cast = float


class DateTime(Field):
    """A datetime field."""
    format = NotImplemented

    def extract(self, tag):
        raise NotImplementedError


########################################################################################################################


class XMLSchemaMeta(type):

    def __init__(cls, name, bases, dict_):
        super().__init__(name, bases, dict_)

        fields = {name: field for name, field in cls.__dict__.items() if isinstance(field, Field)}
        base_fields = getattr(cls, '_fields', {})
        cls._fields = {k: v for k, v in itertools.chain(base_fields.items(), fields.items())}


class Schema(metaclass=XMLSchemaMeta):
    """Utility class for working with XML responses."""

    _fields = {}

    def __init__(self, xml=None):
        self._tree = None
        self.load(xml)

    def load(self, xml):
        if xml is None:
            self._tree = None
            return {}
        elif isinstance(xml, etree._Element):
            self._tree = xml
        else:
            xml = remove_namespaces(xml)
            self._tree = etree.fromstring(xml)

        data = {}
        for name, field in self._fields.items():
            data[name] = field.load(self._tree)

        return self.post_load(data)

    def post_load(self, data):
        return data



