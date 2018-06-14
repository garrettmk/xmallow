import pytest
import xmallow as xm


########################################################################################################################


@pytest.fixture()
def xml_example():
    with open('example.xml') as f:
        xml = f.read()

    return xml


########################################################################################################################



def test_basic_schema(xml_example):

    class CDSchema(xm.Schema):
        title = xm.Field('TITLE')
        artist = xm.Field('ARTIST')
        country = xm.Field('COUNTRY')
        company = xm.Field('COMPANY')
        price = xm.Field('PRICE', float)
        year = xm.Field('YEAR', int)
        missing = xm.Field('missingfield', str, 'missing')

    class CatalogSchema(xm.Schema):
        catalog = xm.Field('CATALOG', CDSchema, many=True)

    schema = CatalogSchema()
    print(schema.load(xml_example))