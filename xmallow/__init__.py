import types
from lxml import etree


########################################################################################################################


class XMallowError(Exception):
    pass


class ValidationError(XMallowError):
    pass


class MissingFieldError(XMallowError):
    pass


########################################################################################################################


class Field:
    """Basic field type."""

    def __init__(self, path, cast=str, default=MissingFieldError, many=False):
        self.path = path
        self.cast = getattr(self, 'cast', None) or cast
        self.default = default
        self.many = many

    def get_tags(self, root):
        """Return a list of tags selected by this field."""
        tags = root.xpath(self.path)
        return tags if self.many else tags[:1]

    def extract(self, tag):
        """Extract data from a tag."""
        cast = self.cast

        # If our "type" is a Field or Schema, delegate to it's load() method. This allows nesting of Fields
        # and Schemas
        if isinstance(cast, (Field, Schema)):
            return cast.load(tag)

        # If our "type" is a function (not a callable), call that function with the tag as it's argument.
        # This allows fields to access properties of the tag other than just its text.
        elif isinstance(cast, types.FunctionType):
            return cast(tag)

        # Assume that self.cast is a primitive or a class, and pass it the tag's text as a value.
        else:
            return cast(tag.text)

    def load(self, tag):
        """Load data from an Element."""

        # Get the tags for this field's xpath and extract data from them
        tags = self.get_tags(tag)
        results = [self.extract(tag) for tag in tags]
        default = self.default

        # Handle the "no data" situation
        if not results:
            if isinstance(default, Exception):
                raise default(f'No results: {self.path}')
            elif callable(default):
                return default()
            else:
                return default

        # If many=False, return only the first results
        elif not self.many:
            return results[0]

        # Otherwise, the entire list
        return results


class First(Field):
    """Takes an iterable of paths, and uses data from the first result."""

    def get_tags(self, root):
        tags = []
        xpath = root.xpath

        for path in self.path:
            tags = xpath(path)
            if tags:
                break

        return tags


class Boolean(Field):
    """A field that casts to a Boolean value."""

    truthy = ('1', 'true', 'yes', 'Success', 'success', 'SUCCESS', 'ok')
    falsy = ('0', 'false', 'no', 'Failure', 'failure', 'FAILURE', 'error')

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


class SchemaMeta(type):

    def __init__(cls, name, bases, dict_):
        super().__init__(name, bases, dict_)

        # Collect all the fields for this schema and its bases.
        cls._fields = getattr(cls, '_fields', {})
        cls._fields.update({name: field for name, field in cls.__dict__.items() if isinstance(field, Field)})


class Schema(metaclass=SchemaMeta):
    """Utility class for working with XML responses."""

    _fields = {}
    dict_type = dict
    ignore_missing = False


    def load(self, xml):
        """Load data from an XML string or a Element."""

        # If the argument is a etree Element, use it as the tree root. This allows nesting of schemas
        if isinstance(xml, etree._Element):
            tree = xml

        # If the argument is a string, parse it using lxml.etree.fromstring()
        else:
            xml = remove_namespaces(xml)
            tree = etree.fromstring(xml)

        # Extract data using the schema's fields
        data = {}
        ignore_missing = self.ignore_missing

        for name, field in self._fields.items():
            try:
                data[name] = field.load(tree)
            except MissingFieldError as e:
                if not ignore_missing:
                    raise e

        # Post-processing
        data = self.post_load(data)
        data = self.dict_type(data) if self.dict_type is not dict else data

        return data

    def post_load(self, data):
        """Process the data before converting to dict_type. Default implementation does nothing."""
        return data



