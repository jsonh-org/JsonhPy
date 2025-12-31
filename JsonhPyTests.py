import math
import unittest
from JsonhPy import JsonhReader, JsonhReaderOptions, JsonhVersion, JsonhResult, JsonhToken, JsonTokenType, JsonhNumberParser

class JsonhPyTests(unittest.TestCase):
    # 
    # Read Tests
    # 

    def test_BasicObjectTest(self):
        jsonh: str = """
{
    "a": "b"
}
"""
        reader: JsonhReader = JsonhReader(jsonh)
        tokens: list[JsonhResult[JsonhToken, str]] = list(reader.read_element())

        for token in tokens:
            self.assertFalse(token.is_error)
        self.assertEqual(tokens[0].value().json_type, JsonTokenType.START_OBJECT)
        self.assertEqual(tokens[1].value().json_type, JsonTokenType.PROPERTY_NAME)
        self.assertEqual(tokens[1].value().value, "a")
        self.assertEqual(tokens[2].value().json_type, JsonTokenType.STRING)
        self.assertEqual(tokens[2].value().value, "b")
        self.assertEqual(tokens[3].value().json_type, JsonTokenType.END_OBJECT)

    def test_NestableBlockCommentTest(self):
        jsonh: str = """
/* */
/=* *=/
/==*/=**=/*==/
/=*/==**==/*=/
0
"""
        reader: JsonhReader = JsonhReader(jsonh)
        tokens: list[JsonhResult[JsonhToken, str]] = list(reader.read_element())

        for token in tokens:
            self.assertFalse(token.is_error)
        self.assertEqual(tokens[0].value().json_type, JsonTokenType.COMMENT)
        self.assertEqual(tokens[0].value().value, " ")
        self.assertEqual(tokens[1].value().json_type, JsonTokenType.COMMENT)
        self.assertEqual(tokens[1].value().value, " ")
        self.assertEqual(tokens[2].value().json_type, JsonTokenType.COMMENT)
        self.assertEqual(tokens[2].value().value, "/=**=/")
        self.assertEqual(tokens[3].value().json_type, JsonTokenType.COMMENT)
        self.assertEqual(tokens[3].value().value, "/==**==/")
        self.assertEqual(tokens[4].value().json_type, JsonTokenType.NUMBER)
        self.assertEqual(tokens[4].value().value, "0")

    # 
    # Parse Tests
    # 

    def test_EscapeSequenceTest(self):
        jsonh: str = """
"\\U0001F47D and \\uD83D\\uDC7D"
"""
        element: str = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(element, "👽 and 👽")

    def test_QuotelessEscapeSequenceTest(self):
        jsonh: str = """
\\U0001F47D and \\uD83D\\uDC7D
"""
        element: str = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(element, "👽 and 👽")

    def test_MultiQuotedStringTest(self):
        jsonh: str = '''
""""
  Hello! Here's a quote: ". Now a double quote: "". And a triple quote! """. Escape: \\\\\\U0001F47D.
 """"
'''
        element: str = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(element, " Hello! Here's a quote: \". Now a double quote: \"\". And a triple quote! \"\"\". Escape: \\👽.")

    def test_ArrayTest(self):
        jsonh: str = '''
[
    1, 2,
    3
    4 5, 6
]
'''
        element: list[object] = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(len(element), 5)
        self.assertEqual(element[0], 1)
        self.assertEqual(element[1], 2)
        self.assertEqual(element[2], 3)
        self.assertEqual(element[3], "4 5")
        self.assertEqual(element[4], 6)

    def test_NumberParserTest(self):
        self.assertEqual(math.trunc(JsonhNumberParser.parse("1.2e3.4").value()), 3014)

    def test_BracelessObjectTest(self):
        jsonh: str = """
a: b
c : d
"""
        element: dict[str, str] = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(len(element), 2)
        self.assertEqual(element["a"], "b")
        self.assertEqual(element["c"], "d")

    def test_CommentTest(self):
        jsonh: str = """
[
    1 # hash comment
        2 // line comment
        3 /* block comment */, 4
]
"""
        element: list[int] = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(len(element), 4)
        self.assertEqual(element[0], 1)
        self.assertEqual(element[1], 2)
        self.assertEqual(element[2], 3)
        self.assertEqual(element[3], 4)

    def test_VerbatimStringTest(self):
        jsonh: str = """
{
    a\\\\: b\\\\
    @c\\\\: @d\\\\
    @e\\\\: f\\\\
}
"""
        element: dict[str, str] = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(len(element), 3)
        self.assertEqual(element["a\\"], "b\\")
        self.assertEqual(element["c\\\\"], "d\\\\")
        self.assertEqual(element["e\\\\"], "f\\")

        element2: dict[str, str] = JsonhReader.parse_element_from_string(jsonh, JsonhReaderOptions(
            version = JsonhVersion.V1,
        )).value()
        self.assertEqual(len(element2), 3)
        self.assertEqual(element2["a\\"], "b\\")
        self.assertEqual(element2["@c\\"], "@d\\")
        self.assertEqual(element2["@e\\"], "f\\")

        jsonh2: str = """
@"a\\\\": @'''b\\\\'''
"""
        element3: dict[str, str] = JsonhReader.parse_element_from_string(jsonh2).value()

        self.assertEqual(len(element3), 1)
        self.assertEqual(element3["a\\\\"], "b\\\\")

if __name__ == '__main__':
    unittest.main()
