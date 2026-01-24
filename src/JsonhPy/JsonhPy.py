from enum import Enum
from typing import Iterator, Iterable

class JsonhResult[T, E]:
    is_error: bool
    value_or_none: T | None
    error_or_none: E | None

    def __init__(self, is_error: bool, value_or_none: T | None = None, error_or_none: E | None = None):
        self.is_error = is_error
        self.value_or_none = value_or_none
        self.error_or_none = error_or_none

    @staticmethod
    def from_value[T, E](value: T = None) -> "JsonhResult[T, E]":
        return JsonhResult(False, value, None)

    @staticmethod
    def from_error[T, E](error: E = None) -> "JsonhResult[T, E]":
        return JsonhResult(True, None, error)

    def value(self) -> T:
        if self.is_error:
            raise RuntimeError(f"Result was error: {self.error_or_none}")
        return self.value_or_none

    def error(self) -> E:
        if not self.is_error:
            raise RuntimeError(f"Result was value: {self.value_or_none}")
        return self.error_or_none

    def __repr__(self) -> str:
        if self.is_error:
            return f"error ({self.error_or_none!r})"
        return f"value ({self.value_or_none!r})"

class JsonhRef[T]:
    ref: T

    def __init__(self, ref: T):
        self.ref = ref

class JsonhVersion(Enum):
    """
    The major versions of the JSONH specification.
    """
    LATEST = 0
    """
    Indicates that the latest version should be used (currently V2).
    """
    V1 = 1
    """
    Version 1 of the specification, released 2025/03/19.
    """
    V2 = 2
    """
    Version 2 of the specification, released 2025/11/19.
    """

class JsonTokenType(Enum):
    """
    The types of tokens that make up a JSON document.
    """
    NONE = 0
    """
    Indicates that there is no value (not to be confused with NULL).
    """
    START_OBJECT = 1
    """
    The start of an object.
    
    Example: `{`
    """
    END_OBJECT = 2
    """
    The end of an object.

    Example: `}`
    """
    START_ARRAY = 3
    """
    The start of an array.

    Example: `[`
    """
    END_ARRAY = 4
    """
    The end of an array.

    Example: `]`
    """
    PROPERTY_NAME = 5
    """
    A property name in an object.

    Example: `"key":`
    """
    COMMENT = 6
    """
    A comment.

    Example: `// comment`
    """
    STRING = 7
    """
    A string.

    Example: `"value"`
    """
    NUMBER = 8
    """
    A number.

    Example: `10`
    """
    TRUE = 9
    """
    A true boolean.

    Example: `true`
    """
    FALSE = 10
    """
    A false boolean.

    Example: `false`
    """
    NULL = 11
    """
    A null value.
    
    Example: `null`
    """

class JsonhToken:
    json_type: JsonTokenType
    value: str

    def __init__(self, json_type: JsonTokenType, value: str = ""):
        self.json_type = json_type
        self.value = value

class JsonhNumberParser:
    """
    Methods for parsing JSONH numbers.

    Unlike `JsonhReader.read_element()`, minimal validation is done here. Ensure the input is valid.
    """
    @staticmethod
    def parse(jsonh_number: str) -> JsonhResult[float, str]:
        # Remove underscores
        jsonh_number = jsonh_number.replace("_", "")
        digits: str = jsonh_number

        # Get sign
        sign: int = 1
        if digits.startswith('-'):
            sign = -1
            digits = digits[1:]
        elif digits.startswith('+'):
            sign = 1
            digits = digits[1:]

        # Decimal
        base_digits: str = "0123456789"
        # Hexadecimal
        if digits.startswith("0x") or digits.startswith("0X"):
            base_digits = "0123456789abcdef"
            digits = digits[2:]
        # Binary
        elif digits.startswith("0b") or digits.startswith("0B"):
            base_digits = "01"
            digits = digits[2:]
        # Octal
        elif digits.startswith("0o") or digits.startswith("0O"):
            base_digits = "01234567"
            digits = digits[2:]

        # Parse number with base digits
        number: JsonhResult[float, str] = JsonhNumberParser._parse_fractional_number_with_exponent(digits, base_digits)
        if number.is_error:
            return number

        # Apply sign
        if sign != 1:
            number.value_or_none *= sign
        return number

    @staticmethod
    def _parse_fractional_number_with_exponent(digits: str, base_digits: str) -> JsonhResult[float, str]:
        """
        Converts a fractional number with an exponent (e.g. `12.3e4.5`) from the given base (e.g. `01234567`) to a base-10 real.
        """
        # Find exponent
        exponent_index: int = -1
        # Hexadecimal exponent
        if 'e' in base_digits:
            for index in range(0, len(digits)):
                if digits[index] not in ['e', 'E']:
                    continue
                if index + 1 >= len(digits) or (digits[index + 1] not in ['-', '+']):
                    continue
                exponent_index = index
                break
        # Exponent
        else:
            exponent_index = JsonhNumberParser._index_of_any(digits, ['e', 'E'])

        # If no exponent then parse real
        if exponent_index < 0:
            return JsonhNumberParser._parse_fractional_number(digits, base_digits)

        # Get mantissa and exponent
        mantissa_part: str = digits[:exponent_index]
        exponent_part: str = digits[(exponent_index + 1):]

        # Parse mantissa and exponent
        mantissa: JsonhResult[float, str] = JsonhNumberParser._parse_fractional_number(mantissa_part, base_digits)
        if mantissa.is_error:
            return mantissa
        exponent: JsonhResult[float, str] = JsonhNumberParser._parse_fractional_number(exponent_part, base_digits)
        if exponent.is_error:
            return exponent

        # Multiply mantissa by 10 ^ exponent
        return JsonhResult.from_value(mantissa.value() * (10 ** exponent.value()))

    @staticmethod
    def _parse_fractional_number(digits: str, base_digits: str) -> JsonhResult[float, str]:
        """
        Converts a fractional number (e.g. `123.45`) from the given base (e.g. `01234567`) to a base-10 real.
        """
        # Find dot index
        dot_index: int = digits.find('.')
        # If no dot then normalize integer
        if dot_index < 0:
            return JsonhNumberParser._parse_whole_number(digits, base_digits)

        # Get parts of number
        whole_part: str = digits[:dot_index]
        fractional_part: str = digits[(dot_index + 1):]

        # Parse parts of number
        whole: JsonhResult[int, str] = JsonhNumberParser._parse_whole_number(whole_part, base_digits)
        if whole.is_error:
            return whole
        fraction: JsonhResult[int, str] = JsonhNumberParser._parse_whole_number(fractional_part, base_digits)
        if fraction.is_error:
            return fraction

        # Get fraction leading zeroes
        fraction_leading_zeroes: str = ""
        for index in range(0, len(fractional_part)):
            if fractional_part[index] == '0':
                fraction_leading_zeroes += '0'
            else:
                break

        # Combine whole and fraction
        return JsonhResult.from_value(float(str(whole.value()) + "." + fraction_leading_zeroes + str(fraction.value())))

    @staticmethod
    def _parse_whole_number(digits: str, base_digits: str) -> JsonhResult[int, str]:
        """
        Converts a whole number (e.g. `12345`) from the given base (e.g. `01234567`) to a base-10 integer.
        """
        # Get sign
        sign: int = 1
        if digits.startswith('-'):
            sign = -1
            digits = digits[1:]
        elif digits.startswith('+'):
            sign = 1
            digits = digits[1:]

        # Add each column of digits
        integer: int = 0
        for index in range(0, len(digits)):
            # Get current digit
            digit_char: str = digits[index]
            digit_int: int = base_digits.find(digit_char.lower())

            # Ensure digit is valid
            if digit_int < 0:
                return JsonhResult.from_error(f"Invalid digit: '{digit_char}'")

            # Get magnitude of current digit column
            column_number: int = len(digits) - 1 - index
            column_magnitude: int = len(base_digits) ** column_number

            # Add value of column
            integer += digit_int * column_magnitude

        # Apply sign
        if sign != 1:
            integer *= sign
        return JsonhResult.from_value(integer)

    @staticmethod
    def _index_of_any(input: str, chars: Iterable[str]) -> float:
        for i in range(0, len(input)):
            char: str = input[i]
            if char in chars:
                return i
        return -1

class JsonhReaderOptions:
    """
    Options for a JsonhReader.
    """
    version: JsonhVersion.LATEST
    """
    Specifies the major version of the JSONH specification to use.
    """
    incomplete_inputs: bool = False
    """
    Enables/disables parsing unclosed inputs.
    
    ```
    {
      "key": "val
    ```
    
    This is potentially useful for large language models that stream responses.
    
    Only some tokens can be incomplete in this mode, so it should not be relied upon.
    """
    parse_single_element: bool = False
    """
    Enables/disables checks for exactly one element when parsing.
    
    ```
    "cat"
    "dog" // Error: Expected single element
    ```
    
    This option does not apply when reading elements, only when parsing elements.
    """

    def __init__(self, version: JsonhVersion = JsonhVersion.LATEST, incomplete_inputs: bool = False, parse_single_element: bool = False):
        """
        Constructs options for a JsonhReader.
        """
        self.version = version
        self.incomplete_inputs = incomplete_inputs
        self.parse_single_element = parse_single_element

    def supports_version(self, minimum_version: JsonhVersion) -> bool:
        """
        Returns whether version is greater than or equal to minimum_version.
        """

        latest_version: JsonhVersion = JsonhVersion.V2

        options_version: JsonhVersion = latest_version if self.version == JsonhVersion.LATEST else self.version
        given_version: JsonhVersion = latest_version if minimum_version == JsonhVersion.LATEST else minimum_version

        return options_version.value >= given_version.value

class JsonhReader:
    string: str
    """
    The string to read characters from.
    """
    index: int
    """
    The index in the string.
    """
    options: JsonhReaderOptions
    """
    The options to use when reading JSONH.
    """
    char_counter: int
    """
    The number of characters read from the string.
    """

    def _RESERVED_CHARS(self):
        """
        Characters that cannot be used unescaped in quoteless strings.
        """
        return self._RESERVED_CHARS_V2 if self.options.supports_version(JsonhVersion.V2) else self._RESERVED_CHARS_V1

    _RESERVED_CHARS_V1 = set(['\\', ',', ':', '[', ']', '{', '}', '/', '#', '"', '\''])
    """
    Characters that cannot be used unescaped in quoteless strings in JSONH V1.
    """
    _RESERVED_CHARS_V2 = set(['\\', ',', ':', '[', ']', '{', '}', '/', '#', '"', '\'', '@'])
    """
    Characters that cannot be used unescaped in quoteless strings in JSONH V2.
    """
    _NEWLINE_CHARS = set(['\n', '\r', '\u2028', '\u2029'])
    """
    Characters that are considered newlines.
    """
    _WHITESPACE_CHARS = set([
        '\u0020', '\u00A0', '\u1680', '\u2000', '\u2001', '\u2002', '\u2003', '\u2004', '\u2005',
        '\u2006', '\u2007', '\u2008', '\u2009', '\u200A', '\u202F', '\u205F', '\u3000', '\u2028',
        '\u2029', '\u0009', '\u000A', '\u000B', '\u000C', '\u000D', '\u0085',
    ])
    """
    Characters that are considered whitespace.
    """

    def __init__(self, string: str, options: JsonhReaderOptions = JsonhReaderOptions()) -> None:
        """
        Constructs a reader that reads JSONH from a string.
        """
        self.string = string
        self.index = 0
        self.options = options
        self.char_counter = 0

    @staticmethod
    def parse_element_from_string(string: str, options: JsonhReaderOptions = JsonhReaderOptions()) -> JsonhResult[object, str]:
        """
        Parses a single element from a string.
        """
        return JsonhReader(string, options).parse_element()

    def parse_element(self) -> JsonhResult[object, str]:
        """
        Parses a single element from the reader.
        """
        current_elements: list[object] = []
        current_property_name: str | None = None

        def submit_element(element: object) -> bool:
            nonlocal current_elements
            nonlocal current_property_name

            # Root value
            if len(current_elements) == 0:
                return True
            # Array item
            if current_property_name == None:
                current_array: list[object] = current_elements[-1]
                current_array.append(element)
                return False
            # Object property
            else:
                current_object: dict[str, object] = current_elements[-1]
                current_object[current_property_name] = element
                current_property_name = None
                return False

        def start_element(element: object | None) -> None:
            nonlocal current_elements
            nonlocal submit_element

            submit_element(element)
            current_elements.append(element)

        def parse_next_element() -> JsonhResult[object, str]:
            nonlocal self
            nonlocal current_property_name

            for token_result in self.read_element():
                # Check error
                if token_result.is_error:
                    return JsonhResult.from_error(token_result.error())

                match token_result.value().json_type:
                    # Null
                    case JsonTokenType.NULL:
                        element: None = None
                        if submit_element(element):
                            return JsonhResult.from_value(element)
                    # True
                    case JsonTokenType.TRUE:
                        element: bool = True
                        if submit_element(element):
                            return JsonhResult.from_value(element)
                    # False
                    case JsonTokenType.FALSE:
                        element: bool = False
                        if submit_element(element):
                            return JsonhResult.from_value(element)
                    # String
                    case JsonTokenType.STRING:
                        element: bool = token_result.value().value
                        if submit_element(element):
                            return JsonhResult.from_value(element)
                    # Number
                    case JsonTokenType.NUMBER:
                        result: JsonhResult[float] = JsonhNumberParser.parse(token_result.value().value)
                        if result.is_error:
                            return JsonhResult.from_error(result.error())
                        element: float = result.value()
                        if submit_element(element):
                            return JsonhResult.from_value(element)
                    # Start Object
                    case JsonTokenType.START_OBJECT:
                        element: dict[str, object] = {}
                        start_element(element)
                    # Start Array
                    case JsonTokenType.START_ARRAY:
                        element: list[object] = []
                        start_element(element)
                    # End Object/Array
                    case JsonTokenType.END_OBJECT | JsonTokenType.END_ARRAY:
                        # Nested element
                        if len(current_elements) > 1:
                            current_elements.pop()
                        # Root element
                        else:
                            return JsonhResult.from_value(current_elements[-1])
                    # Property Name
                    case JsonTokenType.PROPERTY_NAME:
                        current_property_name = token_result.value().value
                    # Comment
                    case JsonTokenType.COMMENT:
                        pass
                    # Not Implemented
                    case _:
                        return JsonhResult.from_error("Token type not implemented")

        next_element = parse_next_element()

        # Ensure exactly one element
        if self.options.parse_single_element:
            for token in self.read_end_of_elements():
                if token.is_error:
                    return JsonhResult.from_error(token.error())

        return next_element

    def find_property_value(self, property_name: str) -> bool:
        """
        Tries to find the given property name in the reader.
        For example, to find `c`:
        ```
        // Original position
        {
          "a": "1",
          "b": {
            "c": "2"
          },
          "c":/* Final position */ "3"
        }
        ```
        """
        current_depth: int = 0

        for token_result in self.read_element():
            # Check error
            if token_result.is_error:
                return False

            match token_result.value().json_type:
                # Start structure
                case JsonTokenType.START_OBJECT | JsonTokenType.START_ARRAY:
                    current_depth += 1
                # End structure
                case JsonTokenType.END_OBJECT | JsonTokenType.END_ARRAY:
                    current_depth -= 1
                # Property name
                case JsonTokenType.PROPERTY_NAME:
                    if current_depth == 1 and token_result.value().value == property_name:
                        # Path found
                        return True

        # Path not found
        return False

    def has_token(self) -> bool:
        """
        Reads whitespace and returns whether the reader contains another token.
        """
        # Whitespace
        self._read_whitespace()

        # Peek char
        return self._peek() != None

    def read_end_of_elements(self) -> Iterator[JsonhResult]:
        """
        Reads comments and whitespace and errors if the reader contains another element.
        """
        # Comments & whitespace
        for token in self._read_comments_and_whitespace():
            if token.is_error:
                yield JsonhResult.from_error(token.error())
                return
            yield token
        
        # Peek char
        if self._peek() != None:
            yield JsonhResult.from_error("Expected end of elements")

    def read_element(self) -> Iterator[JsonhResult[JsonhToken, str]]:
        """
        Reads a single element from the reader.
        """
        # Comments & whitespace
        for token in self._read_comments_and_whitespace():
            if token.is_error:
                yield JsonhResult.from_error(token.error())
                return
            yield token

        # Peek char
        next: str | None = self._peek()
        if next == None:
            yield JsonhResult.from_error("Expected token, got end of input")
            return

        # Object
        if next == '{':
            for token in self._read_object():
                if token.is_error:
                    yield JsonhResult.from_error(token.error())
                    return
                yield token
        # Array
        elif next == '[':
            for token in self._read_array():
                if token.is_error:
                    yield JsonhResult.from_error(token.error())
                    return
                yield token
        # Primitive value (null, true, false, string, number)
        else:
            token: JsonhResult[JsonhToken, str] = self._read_primitive_element()
            if token.is_error:
                yield JsonhResult.from_error(token.error())
                return

            # Detect braceless object from property name
            for token2 in self._read_braceless_object_or_end_of_primitive(token.value()):
                if token2.is_error:
                    yield token2
                    return
                yield token2

    def _read_object(self) -> Iterator[JsonhResult[JsonhToken, str]]:
        # Opening brace
        if not self._read_one('{'):
            # Braceless object
            for token in self._read_braceless_object():
                if token.is_error:
                    yield token
                    return
                yield token
        # Start object
        yield JsonhResult.from_value(JsonhToken(JsonTokenType.START_OBJECT))

        while True:
            # Comments & whitespace
            for token in self._read_comments_and_whitespace():
                if token.is_error:
                    yield token
                    return
                yield token

            next: str | None = self._peek()
            if next == None:
                # End of incomplete object
                if self.options.incomplete_inputs:
                    yield JsonhResult.from_value(JsonhToken(JsonTokenType.END_OBJECT))
                    return
                # Missing closing brace
                yield JsonhResult.from_error("Expected `}` to end object, got end of input")

            # Closing brace
            if next == '}':
                # End of object
                self._read()
                yield JsonhResult.from_value(JsonhToken(JsonTokenType.END_OBJECT))
                return
            # Property
            else:
                for token in self._read_property():
                    if token.is_error:
                        yield token
                        return
                    yield token

    def _read_braceless_object(self, property_name_tokens: Iterable[JsonhToken] | None = None) -> Iterator[JsonhResult[JsonhToken, str]]:
        # Start of object
        yield JsonhResult.from_value(JsonhToken(JsonTokenType.START_OBJECT))

        # Initial tokens
        if property_name_tokens != None:
            for initial_token in self._read_property(property_name_tokens):
                if initial_token.is_error:
                    yield initial_token
                    return
                yield initial_token
        
        while True:
            # Comments & whitespace
            for token in self._read_comments_and_whitespace():
                if token.is_error:
                    yield token
                    return
                yield token
            
            if self._peek() == None:
                # End of braceless object
                yield JsonhResult.from_value(JsonhToken(JsonTokenType.END_OBJECT))
                return
            
            # Property
            for token in self._read_property():
                if token.is_error:
                    yield token
                    return
                yield token

    def _read_braceless_object_or_end_of_primitive(self, primitive_token: JsonhToken) -> Iterator[JsonhResult[JsonhToken, str]]:
        # Comments & whitespace
        property_name_tokens: list[JsonhToken] | None = None
        for comment_or_whitespace_token in self._read_comments_and_whitespace():
            if comment_or_whitespace_token.is_error:
                yield comment_or_whitespace_token
                return
            if property_name_tokens == None:
                property_name_tokens = []
            property_name_tokens.append(comment_or_whitespace_token.value())
        
        # Primitive
        if not self._read_one(':'):
            # Primitive
            yield JsonhResult.from_value(primitive_token)
            # Comments & whitespace
            if property_name_tokens != None:
                for comment_or_whitespace_token in property_name_tokens:
                    yield JsonhResult.from_value(comment_or_whitespace_token)
            # End of primitive
            return

        # Property name
        if property_name_tokens == None:
            property_name_tokens = []
        property_name_tokens.append(JsonhToken(JsonTokenType.PROPERTY_NAME, primitive_token.value))

        # Braceless object
        for object_token in self._read_braceless_object(property_name_tokens):
            if object_token.is_error:
                yield object_token
                return
            yield object_token

    def _read_property(self, property_name_tokens: Iterable[JsonhToken] | None = None) -> Iterator[JsonhResult[JsonhToken, str]]:
        if property_name_tokens != None:
            for token in property_name_tokens:
                yield JsonhResult.from_value(token)
        else:
            for token in self._read_property_name():
                if token.is_error:
                    yield token
                    return
                yield token

        # Comments & whitespace
        for token in self._read_comments_and_whitespace():
            if token.is_error:
                yield token
                return
            yield token
        
        # Property value
        for token in self.read_element():
            if token.is_error:
                yield token
                return
            yield token

        # Comments & whitespace
        for token in self._read_comments_and_whitespace():
            if token.is_error:
                yield token
                return
            yield token

        # Optional comma
        self._read_one(',')

    def _read_property_name(self, string: str | None = None) -> Iterator[JsonhResult[JsonhToken, str]]:
        # String
        if string == None:
            string_token: JsonhResult[JsonhToken, str] = self._read_string()
            if string_token.is_error:
                yield string_token
                return
            string = string_token.value().value
        
        # Comments & whitespace
        for token in self._read_comments_and_whitespace():
            if token.is_error:
                yield token
                return
            yield token

        # Colon
        if not self._read_one(':'):
            yield JsonhResult.from_error("Expected `:` after property name in object")
            return

        # End of property name
        yield JsonhResult.from_value(JsonhToken(JsonTokenType.PROPERTY_NAME, string))

    def _read_array(self) -> Iterator[JsonhResult[JsonhToken, str]]:
        # Opening bracket
        if not self._read_one('['):
            yield JsonhResult.from_error("Expected `[` to start array")
            return
        # Start of array
        yield JsonhResult.from_value(JsonhToken(JsonTokenType.START_ARRAY))

        while True:
            # Comments & whitespace
            for token in self._read_comments_and_whitespace():
                if token.is_error:
                    yield token
                    return
                yield token

            next: str | None = self._peek()
            if next == None:
                # End of incomplete array
                if self.options.incomplete_inputs:
                    yield JsonhResult.from_value(JsonhToken(JsonTokenType.END_ARRAY))
                    return
                # Missing closing bracket
                yield JsonhResult.from_error("Expected `]` to end array, got end of input")
                return
            
            # Closing bracket
            if next == ']':
                # End of array
                self._read()
                yield JsonhResult.from_value(JsonhToken(JsonTokenType.END_ARRAY))
                return
            # Item
            else:
                for token in self._read_item():
                    if token.is_error:
                        yield token
                        return
                    yield token

    def _read_item(self) -> Iterator[JsonhResult[JsonhToken, str]]:
        # Element
        for token in self.read_element():
            if token.is_error:
                yield token
                return
            yield token

        # Comments & whitespace
        for token in self._read_comments_and_whitespace():
            if token.is_error:
                yield token
                return
            yield token

        # Optional comma
        self._read_one(',')

    def _read_string(self) -> JsonhResult[JsonhToken, str]:
        # Verbatim
        is_verbatim: bool = False
        if self.options.supports_version(JsonhVersion.V2) and self._read_one('@'):
            is_verbatim = True

            # Ensure string immediately follows verbatim symbol
            next: str | None = self._peek()
            if next == None or next == '#' or next == '/' or next in self._WHITESPACE_CHARS:
                return JsonhResult.from_error("Expected string to immediately follow verbatim symbol")

        # Start quote
        start_quote: str | None = self._read_any('"', '\'')
        if start_quote == None:
            return self._read_quoteless_string("", is_verbatim)

        # Count multiple quotes
        start_quote_counter = 1
        while self._read_one(start_quote):
            start_quote_counter += 1

        # Empty string
        if start_quote_counter == 2:
            return JsonhResult.from_value(JsonhToken(JsonTokenType.STRING, ""))

        # Count multiple end quotes
        end_quote_counter: int = 0

        # Read string
        string_builder: str = ""

        while True:
            next: str | None = self._read()
            if next == None:
                return JsonhResult.from_error("Expected end of string, got end of input")

            # Partial end quote was actually part of string
            if next != start_quote:
                string_builder += start_quote * end_quote_counter
                end_quote_counter = 0

            # End quote
            if next == start_quote:
                end_quote_counter += 1
                if end_quote_counter == start_quote_counter:
                    break
            # Escape sequence
            elif next == '\\':
                if is_verbatim:
                    string_builder += next
                else:
                    escape_sequence_result: JsonhResult[str, str] = self._read_escape_sequence()
                    if escape_sequence_result.is_error:
                        return JsonhResult.from_error(escape_sequence_result.error())
                    string_builder += escape_sequence_result.value()
            # Literal character
            else:
                string_builder += next

        # Condition: skip remaining steps unless started with multiple quotes
        if start_quote_counter > 1:
            # Pass 1: count leading whitespace -> newline
            has_leading_whitespace_newline: bool = False
            leading_whitespace_newline_counter: int = 0
            index: int = 0
            while index < len(string_builder):
                next: str = string_builder[index]

                # Newline
                if next in self._NEWLINE_CHARS:
                    # Join CR LF
                    if next == '\r' and index + 1 < len(string_builder) and string_builder[index + 1] == '\n':
                        index += 1
                    
                    has_leading_whitespace_newline = True
                    leading_whitespace_newline_counter = index + 1
                    break
                # Non-whitespace
                elif next not in self._WHITESPACE_CHARS:
                    break

                index += 1

            # Condition: skip remaining steps if pass 1 failed
            if has_leading_whitespace_newline:
                # Pass 2: count trailing newline -> whitespace
                has_trailing_newline_whitespace: bool = False
                last_newline_index: int = 0
                trailing_whitespace_counter: int = 0
                index: int = 0
                while index < len(string_builder):
                    next: str = string_builder[index]

                    # Newline
                    if next in self._NEWLINE_CHARS:
                        has_trailing_newline_whitespace = True
                        last_newline_index = index
                        trailing_whitespace_counter = 0

                        # Join CR LF
                        if next == '\r' and index + 1 < len(string_builder) and string_builder[index + 1] == '\n':
                            index += 1
                    # Whitespace
                    elif next in self._WHITESPACE_CHARS:
                        trailing_whitespace_counter += 1
                    # Non-whitespace
                    else:
                        has_trailing_newline_whitespace = False
                        trailing_whitespace_counter = 0

                    index += 1

                # Condition: skip remaining steps if pass 2 failed
                if has_trailing_newline_whitespace:
                    # Pass 3: strip trailing newline -> whitespace
                    string_builder = string_builder[:last_newline_index]

                    # Pass 4: strip leading whitespace -> newline
                    string_builder = string_builder[leading_whitespace_newline_counter:]

                    # Condition: skip remaining steps if no trailing whitespace
                    if trailing_whitespace_counter > 0:
                        # Pass 5: strip line-leading whitespace
                        is_line_leading_whitespace: bool = True
                        line_leading_whitespace_counter: int = 0
                        index: int = 0
                        while index < len(string_builder):
                            next: str = string_builder[index]

                            # Newline
                            if next in self._NEWLINE_CHARS:
                                is_line_leading_whitespace = True
                                line_leading_whitespace_counter = 0
                            # Whitespace
                            elif next in self._WHITESPACE_CHARS:
                                if is_line_leading_whitespace:
                                    # Increment line-leading whitespace
                                    line_leading_whitespace_counter += 1

                                    # Maximum line-leading whitespace reached
                                    if line_leading_whitespace_counter == trailing_whitespace_counter:
                                        # Remove line-leading whitespace
                                        string_builder = string_builder[:(index + 1 - line_leading_whitespace_counter)] + string_builder[(index + 1):]
                                        index -= line_leading_whitespace_counter
                                        # Exit line-leading whitespace
                                        is_line_leading_whitespace = False
                            # Non-whitespace
                            else:
                                if is_line_leading_whitespace:
                                    # Remove partial line-leading whitespace
                                    string_builder = string_builder[:(index - line_leading_whitespace_counter)] + string_builder[index:]
                                    index -= line_leading_whitespace_counter
                                    # Exit line-leading whitespace
                                    is_line_leading_whitespace = False

                            index += 1

        # End of string
        return JsonhResult.from_value(JsonhToken(JsonTokenType.STRING, string_builder))

    def _read_quoteless_string(self, initial_chars: str = "", is_verbatim: bool = False) -> JsonhResult[JsonhToken, str]:
        is_named_literal_possible: bool = not is_verbatim

        # Read quoteless string
        string_builder: str = initial_chars

        while True:
            # Peek char
            next: str | None = self._peek()
            if next == None:
                break

            # Escape sequence
            if next == '\\':
                self._read()
                if is_verbatim:
                    string_builder += next
                else:
                    escape_sequence_result: JsonhResult[str] = self._read_escape_sequence()
                    if escape_sequence_result.is_error:
                        return JsonhResult.from_error(escape_sequence_result.error())
                    string_builder += escape_sequence_result.value()
                is_named_literal_possible = False
            # End on reserved character
            elif next in self._RESERVED_CHARS():
                break
            # End on newline
            elif next in self._NEWLINE_CHARS:
                break
            # Literal character
            else:
                self._read()
                string_builder += next

        # Ensure not empty
        if len(string_builder) == 0:
            return JsonhResult.from_error("Empty quoteless string")

        # Trim whitespace
        string_builder = self._strip_any(string_builder, self._WHITESPACE_CHARS)

        # Match named literal
        if is_named_literal_possible:
            match string_builder:
                case "null":
                    return JsonhResult.from_value(JsonhToken(JsonTokenType.NULL, "null"))
                case "true":
                    return JsonhResult.from_value(JsonhToken(JsonTokenType.TRUE, "true"))
                case "false":
                    return JsonhResult.from_value(JsonhToken(JsonTokenType.FALSE, "false"))

        # End of quoteless string
        return JsonhResult.from_value(JsonhToken(JsonTokenType.STRING, string_builder))

    def _detect_quoteless_string(self) -> tuple[bool, str]:
        # Read whitespace
        whitespace_builder: str = ""

        while True:
            # Read char
            next: str | None = self._peek()
            if next == None:
                break

            # Newline
            if next in self._NEWLINE_CHARS:
                # Quoteless strings cannot contain unescaped newlines
                found_quoteless_string: bool = False
                whitespace_chars: str = whitespace_builder
                return found_quoteless_string, whitespace_chars

            # End of whitespace
            if next not in self._WHITESPACE_CHARS:
                break

            # Whitespace
            whitespace_builder += next
            self._read()

        # Found quoteless string if found backslash or non-reserved char
        next_char: str | None = self._peek()
        found_quoteless_string: bool = next_char != None and (next_char == '\\' or next_char not in self._RESERVED_CHARS())
        whitespace_chars: str = whitespace_builder
        return found_quoteless_string, whitespace_chars

    def _read_number(self) -> tuple[JsonhResult[JsonhToken, str], str]:
        # Read number
        number_builder: JsonhRef[str] = JsonhRef[str]("")

        # Read sign
        sign: str | None = self._read_any('-', '+')
        if sign != None:
            number_builder.ref += sign

        # Read base
        base_digits: str = "0123456789"
        has_base_specifier: bool = False
        has_leading_zero: bool = False
        if self._read_one('0'):
            number_builder.ref += '0'
            has_leading_zero = True

            hex_base_char: str | None = self._read_any('x', 'X')
            if hex_base_char != None:
                number_builder.ref += hex_base_char
                base_digits = "0123456789abcdef"
                has_base_specifier = True
                has_leading_zero = False
            else:
                binary_base_char: str | None = self._read_any('b', 'B')
                if binary_base_char != None:
                    number_builder.ref += binary_base_char
                    base_digits = "01"
                    has_base_specifier = True
                    has_leading_zero = False
                else:
                    octal_base_char: str | None = self._read_any('o', 'O')
                    if octal_base_char != None:
                        number_builder.ref += octal_base_char
                        base_digits = "01234567"
                        has_base_specifier = True
                        has_leading_zero = False

        # Read main number
        main_result: JsonhResult[None, None] = self._read_number_no_exponent(number_builder, base_digits, has_base_specifier, has_leading_zero)
        if main_result.is_error:
            number: JsonhResult[None, str] = JsonhResult.from_error(main_result.error())
            partial_chars_read: str = number_builder.ref
            return number, partial_chars_read

        # Possible hexadecimal exponent
        if number_builder.ref[-1] in ['e', 'E']:
            # Read sign (mandatory)
            exponent_sign: str | None = self._read_any('-', '+')
            if exponent_sign != None:
                number_builder.ref += exponent_sign

                # Missing digit between base specifier and exponent (e.g. `0xe+`)
                if has_base_specifier and len(number_builder.ref) == 4:
                    number: JsonhResult[None, str] = JsonhResult.from_error("Missing digit between base specifier and exponent")
                    partial_chars_read: str = number_builder.ref
                    return number, partial_chars_read

                # Read exponent number
                exponent_result: JsonhResult[None, None] = self._read_number_no_exponent(number_builder, base_digits)
                if exponent_result.is_error:
                    number: JsonhResult[None, str] = JsonhResult.from_error(exponent_result.error())
                    partial_chars_read: str = number_builder.ref
                    return number, partial_chars_read
        # Exponent
        else:
            exponent_char: str | None = self._read_any('e', 'E')
            if exponent_char != None:
                number_builder.ref += exponent_char

                # Read sign
                exponent_sign: str | None = self._read_any('-', '+')
                if exponent_sign != None:
                    number_builder.ref += exponent_sign

                # Read exponent number
                exponent_result: JsonhResult[None, None] = self._read_number_no_exponent(number_builder, base_digits)
                if exponent_result.is_error:
                    number: JsonhResult[None, str] = JsonhResult.from_error(exponent_result.error())
                    partial_chars_read: str = number_builder.ref
                    return number, partial_chars_read

        # End of number
        number: JsonhResult[JsonhToken, str] = JsonhResult.from_value(JsonhToken(JsonTokenType.NUMBER, number_builder.ref))
        partial_chars_read: str = ""
        return number, partial_chars_read

    def _read_number_no_exponent(self, number_builder: JsonhRef[str], base_digits: str, has_base_specifier: bool = False, has_leading_zero: bool = False) -> JsonhResult[None, None]:
        # Leading underscore
        if (not has_base_specifier) and self._peek() == '_':
            return JsonhResult.from_error("Leading `_` in number")

        is_fraction: bool = False
        is_empty: bool = True

        # Leading zero (not base specifier)
        if has_leading_zero:
            is_empty = False

        while True:
            # Peek char
            next: str | None = self._peek()
            if next == None:
                break

            # Digit
            if next.lower() in base_digits:
                self._read()
                number_builder.ref += next
                is_empty = False
            # Dot
            elif next == '.':
                self._read()
                number_builder.ref += next
                is_empty = False

                # Duplicate dot
                if is_fraction:
                    return JsonhResult.from_error("Duplicate `.` in number")
                is_fraction = True
            # Underscore
            elif next == '_':
                self._read()
                number_builder.ref += next
                is_empty = False
            # Other
            else:
                break

        # Ensure not empty
        if is_empty:
            return JsonhResult.from_error("Empty number")

        # Ensure at least one digit
        if not self._contains_any_except(number_builder.ref, ['.', '-', '+', '_']):
            return JsonhResult.from_error("Number must have at least one digit")

        # Trailing underscore
        if number_builder.ref.endswith('_'):
            return JsonhResult.from_error("Trailing `_` in number")

        # End of number
        return JsonhResult.from_value()

    def _read_number_or_quoteless_string(self) -> JsonhResult[JsonhToken, str]:
        # Read number
        number: JsonhResult[JsonhToken, str]; partial_chars_read: str
        number, partial_chars_read = self._read_number()
        if not number.is_error:
            # Try read quoteless string starting with number
            found_quoteless_string: bool; whitespace_chars: str
            found_quoteless_string, whitespace_chars = self._detect_quoteless_string()
            if found_quoteless_string:
                return self._read_quoteless_string(number.value().value + whitespace_chars)
            # Otherwise, accept number
            else:
                return number
        # Read quoteless string starting with malformed number
        else:
            return self._read_quoteless_string(partial_chars_read)

    def _read_primitive_element(self) -> JsonhResult[JsonhToken, str]:
        # Peek char
        next: str | None = self._peek()
        if next == None:
            return JsonhResult.from_error("Expected primitive element, got end of input")

        # Number
        if len(next) == 1 and ((ord('0') <= ord(next) <= ord('9')) or (next in ['-', '+', '.'])):
            return self._read_number_or_quoteless_string()
        # String
        elif (next in ['"', '\'']) or (self.options.supports_version(JsonhVersion.V2) and next == '@'):
            return self._read_string()
        # Quoteless string (or named literal)
        else:
            return self._read_quoteless_string()

    def _read_comments_and_whitespace(self) -> Iterator[JsonhResult[JsonhToken, str]]:
        while True:
            # Whitespace
            self._read_whitespace()

            # Peek char
            next: str | None = self._peek()
            if next == None:
                return

            # Comment
            if next in ['#', '/']:
                comment: JsonhResult[JsonhToken, str] = self._read_comment()
                if comment.is_error:
                    yield comment
                    return
                yield comment
            # End of comments
            else:
                return

    def _read_comment(self) -> JsonhResult[JsonhToken, str]:
        block_comment: bool = False
        start_nest_counter: int = 0

        # Hash-style comment
        if self._read_one('#'):
            pass
        elif self._read_one('/'):
            # Line-style comment
            if self._read_one('/'):
                pass
            # Block-style comment
            elif self._read_one('*'):
                block_comment = True
            # Nestable block-style comment
            elif self.options.supports_version(JsonhVersion.V2) and self._peek() == '=':
                block_comment = True
                while self._read_one('='):
                    start_nest_counter += 1
                if not self._read_one('*'):
                    return JsonhResult.from_error("Expected `*` after start of nesting block comment")
            else:
                return JsonhResult.from_error("Unexpected `/`")
        else:
            return JsonhResult.from_error("Unexpected character")

        # Read comment
        comment_builder: str = ""

        while True:
            # Read char
            next: str | None = self._read()

            if block_comment:
                # Error
                if next == None:
                    return JsonhResult.from_error("Expected end of block comment, got end of input")
                
                # End of block comment
                if next == '*':
                    # End of nestable block comment
                    if self.options.supports_version(JsonhVersion.V2):
                        # Count nests
                        end_nest_counter: int = 0
                        while end_nest_counter < start_nest_counter and self._read_one('='):
                            end_nest_counter += 1
                        # Partial end nestable block comment was actually part of comment
                        if end_nest_counter < start_nest_counter or self._peek() != '/':
                            comment_builder += '*'
                            while end_nest_counter > 0:
                                comment_builder += '='
                                end_nest_counter -= 1
                            continue

                    # End of block comment
                    if self._read_one('/'):
                        return JsonhResult.from_value(JsonhToken(JsonTokenType.COMMENT, comment_builder))
            else:
                # End of line comment
                if next == None or next in self._NEWLINE_CHARS:
                    return JsonhResult.from_value(JsonhToken(JsonTokenType.COMMENT, comment_builder))

            # Comment char
            comment_builder += next

    def _read_whitespace(self) -> None:
        while True:
            # Peek char
            next: str | None = self._peek()
            if next == None:
                return
            
            # Whitespace
            if next in self._WHITESPACE_CHARS:
                self._read()
            # End of whitespace
            else:
                return

    def _read_hex_sequence(self, length: int) -> JsonhResult[int, str]:
        hex_chars: str = ""

        for index in range(0, length):
            next: str | None = self._read()

            # Hex digit
            if next != None and ((ord('0') <= ord(next) <= ord('9')) or (ord('A') <= ord(next) <= ord('F')) or (ord('a') <= ord(next) <= ord('f'))):
                hex_chars += next
            # Unexpected char
            else:
                return JsonhResult.from_error("Incorrect number of hexadecimal digits in unicode escape sequence")

        # Parse unicode character from hex digits
        return JsonhResult.from_value(int(hex_chars, base=16))

    def _read_escape_sequence(self) -> JsonhResult[str, str]:
        escape_char: str | None = self._read()
        if escape_char == None:
            return JsonhResult.from_error("Expected escape sequence, got end of input")

        match escape_char:
            # Reverse solidus
            case '\\':
                return JsonhResult.from_value('\\')
            # Backspace
            case 'b':
                return JsonhResult.from_value('\b')
            # Form feed
            case 'f':
                return JsonhResult.from_value('\f')
            # Newline
            case 'n':
                return JsonhResult.from_value('\n')
            # Carriage return
            case 'r':
                return JsonhResult.from_value('\r')
            # Tab
            case 't':
                return JsonhResult.from_value('\t')
            # Vertical tab
            case 'v':
                return JsonhResult.from_value('\v')
            # Null
            case '0':
                return JsonhResult.from_value('\0')
            # Alert
            case 'a':
                return JsonhResult.from_value('\a')
            # Escape
            case 'e':
                return JsonhResult.from_value('\u001b')
            # Unicode hex sequence
            case 'u':
                return self._read_hex_escape_sequence(4)
            # Short unicode hex sequence
            case 'x':
                return self._read_hex_escape_sequence(2)
            # Long unicode hex sequence
            case 'U':
                return self._read_hex_escape_sequence(8)
            # Escaped newline
            case self._NEWLINE_CHARS:
                # Join CR LF
                if escape_char == 'r':
                    self._read_one('\n')
                return JsonhResult.from_value("")
            # Other
            case _:
                return JsonhResult.from_value(escape_char)

    def _read_hex_escape_sequence(self, length: int) -> JsonhResult[str, str]:
        # This method is used to combine escaped UTF-16 surrogate pairs (e.g. "\uD83D\uDC7D" -> "👽")

        # Read hex digits & convert to uint
        code_point: JsonhResult[int, str] = self._read_hex_sequence(length)
        if code_point.is_error:
            return JsonhResult.from_error(code_point.error())

        # High surrogate
        if (self._is_utf16_high_surrogate(code_point.value())):
            original_position: int = self.index
            # Escape sequence
            if self._read_one('\\'):
                next: str | None = self._read_any('u', 'x', 'U')
                # Low surrogate escape sequence
                if next:
                    # Read hex sequence
                    low_code_point: JsonhResult[int, str]
                    match next:
                        case 'u':
                            low_code_point = self._read_hex_sequence(4)
                        case 'x':
                            low_code_point = self._read_hex_sequence(2)
                        case 'U':
                            low_code_point = self._read_hex_sequence(8)
                    # Ensure hex sequence read successfully
                    if low_code_point.is_error:
                        return JsonhResult.from_error(low_code_point.error())
                    # Combine high and low surrogates
                    code_point.value_or_none = self._utf16_surrogates_to_code_point(code_point.value(), low_code_point.value())
                # Other escape sequence
                else:
                    self.index = original_position

        # Rune
        return JsonhResult.from_value(chr(code_point.value()))

    @staticmethod
    def _utf16_surrogates_to_code_point(high_surrogate: int, low_surrogate: int) -> int:
        return 0x10000 + (((high_surrogate - 0xD800) << 10) | (low_surrogate - 0xDC00))

    @staticmethod
    def _is_utf16_high_surrogate(code_point: int) -> bool:
        return code_point >= 0xD800 and code_point <= 0xDBFF

    def _peek(self) -> str | None:
        if self.index >= len(self.string):
            return None
        next: str = self.string[self.index]
        return next

    def _read(self) -> str | None:
        if self.index >= len(self.string):
            return None
        next: str = self.string[self.index]
        self.index += 1
        self.char_counter += 1
        return next

    def _read_one(self, option: str) -> bool:
        if self._peek() == option:
            self._read()
            return True
        return False

    def _read_any(self, *options: str) -> str | None:
        # Peek char
        next: str | None = self._peek()
        if next == None:
            return None
        # Match option
        if not (next in options):
            return None
        # Option matched
        self._read()
        return next

    @staticmethod
    def _strip_any(input: str, trim_chars: Iterable[str]) -> str:
        start: int = 0
        end: int = len(input)

        while start < end and input[start] in trim_chars:
            start += 1

        while end > start and input[end - 1] in trim_chars:
            end -= 1

        return input[start:end]

    @staticmethod
    def _contains_any_except(input: str, allowed: Iterable[str]) -> bool:
        for char in input:
            if char not in allowed:
                return True
        return False
