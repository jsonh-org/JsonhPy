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
    #end

    @staticmethod
    def from_value[T, E](value: T) -> "JsonhResult[T, E]":
        return JsonhResult(True, value_or_none=value)
    #end

    @staticmethod
    def from_error[T, E](error: E) -> "JsonhResult[T, E]":
        return JsonhResult(False, error_or_none=error)
    #end

    def value(self) -> T:
        if self.is_error:
            raise RuntimeError(f"Result was error: {self.error_or_none}")
        #end
        return self.value_or_none
    #end

    def error(self) -> E:
        if not self.is_error:
            raise RuntimeError(f"Result was value: {self.value_or_none}")
        #end
        return self.error_or_none
    #end

    def __repr__(self) -> str:
        if self.is_error:
            return f"error ({self.error_or_none!r})"
        #end
        return f"value ({self.value_or_none!r})"
    #end
#end

class JsonhRef[T]:
    ref: T

    def __init__(self, ref: T):
        self.ref = ref
    #end
#end

class JsonhReaderOptions:
    pass
#end

class JsonTokenType(Enum):
    NONE = 0
    START_OBJECT = 1
    END_OBJECT = 2
    START_ARRAY = 3
    END_ARRAY = 4
    PROPERTY_NAME = 5
    COMMENT = 6
    STRING = 7
    NUMBER = 8
    TRUE = 9
    FALSE = 10
    NULL = 11
#end

class JsonhToken:
    json_type: JsonTokenType
    value: str

    def __init__(self, json_type: JsonTokenType, value: str):
        self.json_type = json_type
        self.value = value
    #end
#end

class JsonhReader:
    # The string to read characters from.
    string: str
    # The index in the string.
    index: int
    # The options to use when reading JSONH.
    options: JsonhReaderOptions
    # The number of characters read from the string.
    char_counter: int

    # Characters that cannot be used unescaped in quoteless strings.
    _RESERVED_CHARS = set(['\\', ',', ':', '[', ']', '{', '}', '/', '#', '"', '\'', '@'])
    # Characters that are considered newlines.
    _NEWLINE_CHARS = set(['\n', '\r', '\u2028', '\u2029'])
    # Characters that are considered whitespace.
    _WHITESPACE_CHARS = set([
        '\u0020', '\u00A0', '\u1680', '\u2000', '\u2001', '\u2002', '\u2003', '\u2004', '\u2005',
        '\u2006', '\u2007', '\u2008', '\u2009', '\u200A', '\u202F', '\u205F', '\u3000', '\u2028',
        '\u2029', '\u0009', '\u000A', '\u000B', '\u000C', '\u000D', '\u0085',
    ])

    def __init__(self, string: str, options: JsonhReaderOptions = JsonhReaderOptions()) -> None:
        """
        Constructs a reader that reads JSONH from a string.
        """
        self.string = string
        self.options = options
        self.char_counter = 0
    #end

    @staticmethod
    def parse_element_from_string(string: str, options: JsonhReaderOptions = JsonhReaderOptions()) -> object:
        """
        Parses a single element from a string.
        """
        return JsonhReader(string, options).parse_element()
    #end

    def parse_element(self) -> object:
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
            #end
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
            #end
        #end

        def start_element(element: object | None) -> None:
            nonlocal current_elements
            nonlocal submit_element

            submit_element(element)
            current_elements.append(element)
        #end

        def parse_next_element() -> None:
            nonlocal self
            nonlocal current_property_name
            
            for token_result in self.read_element():
                # Check error
                if token_result.is_error:
                    return JsonhResult.from_error(token_result.error)
                #end
                
                match token_result.value.json_type:
                    # Null
                    case JsonTokenType.NULL:
                        element: None = None
                        if submit_element(element):
                            return JsonhResult.from_value(element)
                        #end
                    #end
                    # True
                    case JsonTokenType.TRUE:
                        element: bool = True
                        if submit_element(element):
                            return JsonhResult.from_value(element)
                        #end
                    #end
                    # False
                    case JsonTokenType.FALSE:
                        element: bool = False
                        if submit_element(element):
                            return JsonhResult.from_value(element)
                        #end
                    #end
                    # String
                    case JsonTokenType.STRING:
                        element: bool = token_result.value().value
                        if submit_element(element):
                            return JsonhResult.from_value(element)
                        #end
                    #end
                    # Number
                    case JsonTokenType.NUMBER:
                        result: JsonhResult[float] = JsonhNumberParser.parse(token_result.value().value)
                        if result.is_error:
                            return JsonhResult.from_error(result.error())
                        #end
                        element: float = token_result.value().value
                        if submit_element(element):
                            return JsonhResult.from_value(element)
                        #end
                    # Start Object
                    case JsonTokenType.START_OBJECT:
                        element: dict[str, object] = {}
                        start_element(element)
                    #end
                    # Start Array
                    case JsonTokenType.START_ARRAY:
                        element: list[object] = []
                        start_element(element)
                    #end
                    # End Object/Array
                    case JsonTokenType.END_OBJECT, JsonTokenType.END_ARRAY:
                        # Nested element
                        if len(current_elements) > 1:
                            current_elements.pop()
                        # Root element
                        else:
                            return JsonhResult.from_value(current_elements[-1])
                        #end
                    #end
                    # Property Name
                    case JsonTokenType.PROPERTY_NAME:
                        current_property_name = token_result.value().value
                    #end
                    # Comment
                    case JsonTokenType.COMMENT:
                        pass
                    #end
                    # Not Implemented
                    case _:
                        return JsonhResult.from_error("Token type not implemented")
                    #end
                #end
            #end
        #end

        next_element = parse_next_element()

        # Ensure exactly one element
        if self.options.parse_single_element:
            for token in self._read_end_of_elements():
                if token.is_error:
                    return JsonhResult.from_error(token.error())
                #end
            #end
        #end

        return next_element

    def find_property_value(self, property_name: str) -> bool:
        pass
    #end

    def has_token(self) -> bool:
        pass
    #end

    def read_end_of_elements(self) -> Iterator[JsonhResult]:
        # Comments & whitespace
        for token in self._read_comments_and_whitespace():
            if token.is_error:
                yield JsonhResult.from_error(token.error())
                return
            #end
        #end
        
        # Peek char
        if self._peek() != None:
            yield JsonhResult.from_error("Expected end of elements")
        #end
    #end

    def read_element(self) -> Iterator[JsonhResult[JsonhToken, str]]:
        # Comments & whitespace
        for token in self._read_comments_and_whitespace():
            if token.is_error:
                yield JsonhResult.from_error(token.error())
                return
            #end
        #end

        # Peek char
        next: str | None = self._peek()
        if next == None:
            yield JsonhResult.from_error("Expected token, got end of input")
            return
        #end

        # Object
        if next == '{':
            for token in self._read_object():
                if token.is_error:
                    yield JsonhResult.from_error(token.error())
                    return
                #end
                yield token
            #end
        # Array
        elif next == '[':
            for token in self._read_array():
                if token.is_error:
                    yield JsonhResult.from_error(token.error())
                    return
                #end
                yield token
            #end
        # Primitive value (null, true, false, string, number)
        else:
            token: JsonhResult[JsonhToken, str] = self._read_primitive_element()
            if token.is_error:
                yield JsonhResult.from_error(token.error())
                return
            #end

            # Detect braceless object from property name
            if token.value().json_type == JsonTokenType.STRING:
                for token2 in self._read_braceless_object_or_end_of_string(token.value()):
                    if token2.is_error:
                        yield token2
                        return
                    #end
                    yield token2
                #end
            # Primitive value
            else:
                yield token
            #end
        #end
    #end

    def _read_object(self) -> Iterator[JsonhResult[JsonhToken, str]]:
        pass
    #end

    def _read_braceless_object(self, property_name_tokens: Iterable[JsonhToken] | None = None) -> Iterator[JsonhResult[JsonhToken, str]]:
        pass
    #end

    def _read_braceless_object_or_end_of_string(self, string_token: JsonhToken) -> Iterator[JsonhResult[JsonhToken, str]]:
        pass
    #end

    def _read_property(self, property_name_tokens: Iterable[JsonhToken] | None = None) -> Iterator[JsonhResult[JsonhToken, str]]:
        pass
    #end

    def _read_property_name(self, string: str | None = None) -> Iterator[JsonhResult[JsonhToken, str]]:
        pass
    #end

    def _read_array(self) -> Iterator[JsonhResult[JsonhToken, str]]:
        pass
    #end

    def _read_item(self) -> Iterator[JsonhResult[JsonhToken, str]]:
        pass
    #end

    def _read_string(self) -> JsonhResult[JsonhToken, str]:
        pass
    #end

    def _read_quoteless_string(self, initial_chars: str = "", is_verbatim: bool = False) -> JsonhResult[JsonhToken, str]:
        pass
    #end

    def _detect_quoteless_string(self) -> tuple[bool, str]:
        pass
    #end

    def _read_number(self) -> tuple[JsonhResult[JsonhToken, str], str]:
        pass
    #end

    def _read_number_no_exponent(self, number_builder: JsonhRef, base_digits: str, has_base_specifier: bool = False, has_leading_zero: bool = False) -> JsonhResult[None, None]:
        pass
    #end

    def _read_number_or_quoteless_string(self) -> JsonhResult[JsonhToken, str]:
        pass
    #end

    def _read_primitive_element(self) -> JsonhResult[JsonhToken, str]:
        pass
    #end

    def _read_comments_and_whitespace(self) -> Iterator[JsonhResult[JsonhToken, str]]:
        pass
    #end

    def _read_comment(self) -> JsonhResult[JsonhToken, str]:
        pass
    #end

    def _read_whitespace(self) -> None:
        pass
    #end

    def _read_hex_sequence(self, length: int) -> JsonhResult[int, str]:
        pass
    #end

    def _read_escape_sequence(self) -> JsonhResult[str, str]:
        pass
    #end

    def _peek(self) -> str | None:
        if self.index >= len(self.string):
            return None
        #end
        next: str = self.string[self.index]
        return next
    #end

    def _read(self) -> str | None:
        if self.index >= len(self.string):
            return None
        #end
        next: str = self.string[self.index]
        self.index += 1
        self.char_counter += 1
        return next
    #end

    def _read_one(self, option: str) -> bool:
        if self._peek() == option:
            self._read()
            return True
        #end
        return False
    #end

    def _read_any(self, *options: str) -> str | None:
        # Peek char
        next: str | None = self._peek()
        if next == None:
            return None
        #end
        # Match option
        if not (next in options):
            return None
        #end
        # Option matched
        self._read()
        return next
    #end
#end