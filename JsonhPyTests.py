import math
import unittest
from src.JsonhPy.JsonhPy import JsonhReader, JsonhReaderOptions, JsonhVersion, JsonhResult, JsonhToken, JsonTokenType, JsonhNumberParser

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

    def test_CommentTest(self):
        jsonh: str = """
1
2
"""
        element: int = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(element, 1)

        self.assertTrue(JsonhReader.parse_element_from_string(jsonh, JsonhReaderOptions(
            parse_single_element = True,
        )).is_error)

        jsonh2: str = """
1


"""

        self.assertFalse(JsonhReader.parse_element_from_string(jsonh2, JsonhReaderOptions(
            parse_single_element = True,
        )).is_error)

    # 
    # Edge Case Tests
    # 

    def test_QuotelessStringStartingWithKeywordTest(self):
        jsonh: str = """
[nulla, null b, null, @null]
"""
        element: list[str | None] = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(len(element), 4)
        self.assertEqual(element[0], "nulla")
        self.assertEqual(element[1], "null b")
        self.assertEqual(element[2], None)
        self.assertEqual(element[3], "null")

    def test_BracelessObjectWithInvalidValueTest(self):
        jsonh: str = """
a: {
"""
        self.assertTrue(JsonhReader.parse_element_from_string(jsonh).is_error)

    def test_NestedBracelessObjectTest(self):
        jsonh: str = """
[
    a: b
    c: d
]
"""
        self.assertTrue(JsonhReader.parse_element_from_string(jsonh).is_error)

    def test_QuotelessStringsLeadingTrailingWhitespaceTest(self):
        jsonh: str = """
[
    a b  , 
]
"""
        element: list[str] = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(len(element), 1)
        self.assertEqual(element[0], "a b")

    def test_SpaceInQuotelessPropertyNameTest(self):
        jsonh: str = """
{
    a b: c d
}
"""
        element: dict[str, str] = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(len(element), 1)
        self.assertEqual(element["a b"], "c d")

    def test_QuotelessStringsEscapeTest(self):
        jsonh: str = """
a: \\"5
b: \\\\z
c: 5 \\\\
"""
        element: dict[str, str] = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(len(element), 3)
        self.assertEqual(element["a"], "\"5")
        self.assertEqual(element["b"], "\\z")
        self.assertEqual(element["c"], "5 \\")

    def test_MultiQuotedStringsNoLastNewlineWhitespaceTest(self):
        jsonh: str = '''
"""
  hello world  """
'''
        element: str = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(element, "\n  hello world  ")

    def test_MultiQuotedStringsNoFirstWhitespaceNewlineTest(self):
        jsonh: str = '''
"""  hello world
  """
'''
        element: str = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(element, "  hello world\n  ")

    def test_QuotelessStringsEscapedLeadingTrailingWhitespaceTest(self):
        jsonh: str = """
\\nZ\\ \\r
"""
        element: str = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(element, "Z")

    def test_HexNumberWithETest(self):
        jsonh: str = """
0x5e3
"""

        self.assertEqual(JsonhReader.parse_element_from_string(jsonh).value(), 0x5e3)

        jsonh2: str = """
0x5e+3
"""

        self.assertEqual(JsonhReader.parse_element_from_string(jsonh2).value(), 5000)

    def test_NumberWithRepeatedUnderscoresTest(self):
        jsonh: str = """
100__000
"""
        element: int = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(element, 100_000)

    def test_NumberWithUnderscoreAfterBaseSpecifierTest(self):
        jsonh: str = """
0b_100
"""
        element: int = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(element, 0b_100)

    def test_NegativeNumberWithBaseSpecifierTest(self):
        jsonh: str = """
-0x5
"""
        element: int = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertEqual(element, -0x5)

    def test_NumberDotTest(self):
        jsonh: str = """
.
"""
        self.assertIsInstance(JsonhReader.parse_element_from_string(jsonh).value(), str)
        self.assertEqual(JsonhReader.parse_element_from_string(jsonh).value(), ".")

        jsonh2: str = """
-.
"""
        self.assertIsInstance(JsonhReader.parse_element_from_string(jsonh2).value(), str)
        self.assertEqual(JsonhReader.parse_element_from_string(jsonh2).value(), "-.")

    def test_DuplicatePropertyNameTest(self):
        jsonh: str = """
{
  a: 1,
  c: 2,
  a: 3,
}
"""
        element: dict[str, int] = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertDictEqual(element, {
            "a": 1,
            "c": 2,
            "a": 3,
        })

    def test_EmptyNumberTest(self):
        jsonh: str = """
0e
"""
        element: str = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertIsInstance(element, str)
        self.assertEqual(element, "0e")

    def test_LeadingZeroWithExponentTest(self):
        jsonh: str = """
[0e4, 0xe, 0xEe+2]
"""
        element: list[int] = JsonhReader.parse_element_from_string(jsonh).value()

        self.assertListEqual(element, [0e4, 0xe, 1400])

        jsonh2: str = """
[e+2, 0xe+2, 0oe+2, 0be+2]
"""
        element2: list[str] = JsonhReader.parse_element_from_string(jsonh2).value()

        self.assertListEqual(element2, ["e+2", "0xe+2", "0oe+2", "0be+2"])

        jsonh3: str = """
[0x0e+, 0b0e+_1]
"""
        element3: list[str] = JsonhReader.parse_element_from_string(jsonh3).value()

        self.assertListEqual(element3, ["0x0e+", "0b0e+_1"])

    def test_ErrorInBracelessPropertyNameTest(self):
        jsonh: str = """
a /
"""

        self.assertTrue(JsonhReader.parse_element_from_string(jsonh).is_error)

    def test_FirstPropertyNameInBracelessObjectTest(self):
        jsonh: str = """
a: b
"""

        self.assertDictEqual(JsonhReader.parse_element_from_string(jsonh).value(), { "a": "b" })

        jsonh2: str = """
0: b
"""

        self.assertDictEqual(JsonhReader.parse_element_from_string(jsonh2).value(), { "0": "b" })

        jsonh3: str = """
true: b
"""

        self.assertDictEqual(JsonhReader.parse_element_from_string(jsonh3).value(), { "true": "b" })

if __name__ == '__main__':
    unittest.main()
