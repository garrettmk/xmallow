import types
import itertools
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

    cast = str
    default = MissingFieldError
    many = False
    required = None
    meta = {}

    def __init__(self, path, cast=None, **kwargs):
        super().__init__()
        self.path = path
        self.cast = self.cast if cast is None else cast

        for key, value in kwargs.items():
            if key in ('default', 'many', 'required'):
                setattr(self, key, value)
            else:
                self.meta.update(key=value)

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

            # Use raise if default is an instance or subclass of Exception
            if isinstance(default, Exception):
                raise default

            elif isinstance(default, type) and issubclass(default, Exception):
                raise default(f'No results: {self.path}')

            # If default is a function, return it's return value
            if callable(default):
                return default()

            # Otherwise, return it as-is
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


class Attribute(Field):
    """Retrieves an attribute of an element."""

    def __init__(self, *args, attr=None, **kwargs):
        super().__init__(*args, **kwargs)
        if attr is None:
            raise ValueError(f'An attribute name is required.')
        else:
            self.attr = attr

    def extract(self, tag):
        attr = self.attr

        if attr in tag.attrib:
            return self.cast(tag.attrib.get(attr))
        else:
            raise MissingFieldError


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


class List(Field):
    """A list of values."""
    many = True


class Nested(Field):
    """A nested schema."""

    def __init__(self, path, schema, **kwargs):
        super().__init__(path, **kwargs)
        self.cast = schema


########################################################################################################################


class SchemaMeta(type):

    def __init__(cls, name, bases, dict_):
        super().__init__(name, bases, dict_)

        fields = {name: field for name, field in cls.__dict__.items() if isinstance(field, Field)}
        base_fields = getattr(cls, '_fields', {})
        cls._fields = {k: v for k, v in itertools.chain(base_fields.items(), fields.items())}


class Schema(metaclass=SchemaMeta):
    """Utility class for working with XML responses."""

    _fields = {}
    context = {}
    dict_type = dict
    ignore_missing = False

    def __init__(self, **kwargs):
        super().__init__()

        for key, value in kwargs.items():
            if key in ('dict_type', 'ignore_missing', 'context'):
                setattr(self, key, value)
            else:
                self.context.update(key=value)

    def load(self, xml):
        """Load data from an XML string or a Element."""

        # If the argument is a etree Element, use it as the tree root. This allows nesting of schemas
        if isinstance(xml, etree._Element):
            tree = xml

        # If the argument is a string, parse it using lxml.etree.fromstring()
        else:
            tree = etree.fromstring(xml)

        # Extract data using the schema's fields
        data = self.dict_type()
        ignore_missing = self.ignore_missing

        for name, field in self._fields.items():
            try:
                data[name] = field.load(tree)
            except MissingFieldError as e:
                # Note the use of "is True" below, this on purpose
                if field.required is True or not ignore_missing:
                    raise e

        # Post-processing
        data = self.post_load(data)
        if not isinstance(data, (self.dict_type, dict)):
            raise TypeError(f'post_load() must return a dict or dict-like object, not {type(data)}')

        return data

    def post_load(self, data):
        """Process the data before converting to dict_type. Default implementation does nothing."""
        return data



