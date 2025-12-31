import re
import json
from decimal import Decimal, localcontext

class JSONHSyntaxError(ValueError):
    pass

class JSONHReader:
    RESERVED = set([",", ":", "[", "]", "{", "}", "/", "#", '"', "'", "@"])

    def __init__(self, source: str):
        self.source = source
        self.i = 0
        self.n = len(source)
        self.comments: list[str] = []

    @staticmethod
    def to_json_from_string(str: str) -> str:
        return JSONHReader(str).to_json()

    def to_json(self) -> str:
        self._skip()
        out = self._read_root_json()
        self._skip()
        if not self._eof():
            raise self._err("Trailing characters")
        return out

    def _eof(self) -> bool:
        return self.i >= self.n

    def _peek(self, k: int = 0) -> str:
        j = self.i + k
        return self.source[j] if j < self.n else ""

    def _take(self) -> str:
        c = self._peek()
        self.i += 1
        return c

    def _err(self, msg: str) -> JSONHSyntaxError:
        return JSONHSyntaxError(f"{msg} at {self.i}")

    def _prev_char(self) -> str:
        return self.source[self.i - 1] if self.i > 0 else ""

    def _can_start_line_comment(self) -> bool:
        # Guard to avoid treating http:// or foo//bar as a comment
        return self.i == 0 or self._prev_char().isspace()

    def _can_start_block_comment(self) -> bool:
        if self.i == 0:
            return True
        prev = self._prev_char()
        return prev.isspace() or prev in "{[,:"

    def _consume_newline(self) -> bool:
        if self._peek() == "\n":
            self.i += 1
            return True
        if self._peek() == "\r":
            self.i += 1
            if self._peek() == "\n":
                self.i += 1
            return True
        return False

    def _skip(self) -> bool:
        had_nl = False
        while not self._eof():
            c = self._peek()
            if c in " \t":
                self.i += 1
                continue
            if c in "\n\r":
                had_nl = True
                self._consume_newline()
                continue
            if c == "#" and self._can_start_line_comment():
                start = self.i
                while not self._eof() and self._peek() not in "\n\r":
                    self.i += 1
                self.comments.append(self.source[start:self.i])
                continue
            if self._peek() == "/" and self._peek(1) == "/" and self._can_start_line_comment():
                start = self.i
                self.i += 2
                while not self._eof() and self._peek() not in "\n\r":
                    self.i += 1
                self.comments.append(self.source[start:self.i])
                continue
            if self._peek() == "/" and self._peek(1) == "*" and self._can_start_block_comment():
                start = self.i
                self.i += 2
                while True:
                    if self._eof():
                        raise self._err("Unterminated block comment")
                    if self._peek() in "\n\r":
                        had_nl = True
                        self._consume_newline()
                        continue
                    if self._peek() == "*" and self._peek(1) == "/":
                        self.i += 2
                        break
                    self.i += 1
                self.comments.append(self.source[start:self.i])
                continue
            if self._peek() == "/" and self._peek(1) == "=" and self._can_start_block_comment():
                start = self.i
                self.i += 1
                eq = 0
                while self._peek() == "=":
                    eq += 1
                    self.i += 1
                if self._peek() != "*":
                    self.i = start
                    break
                self.i += 1
                stack = [eq]
                while stack:
                    if self._eof():
                        raise self._err("Unterminated nestable block comment")
                    if self._peek() in "\n\r":
                        had_nl = True
                        self._consume_newline()
                        continue
                    if self._peek() == "/" and self._peek(1) == "=":
                        j = self.i + 1
                        eq2 = 0
                        while j < self.n and self.source[j] == "=":
                            eq2 += 1
                            j += 1
                        if j < self.n and self.source[j] == "*":
                            stack.append(eq2)
                            self.i = j + 1
                            continue
                    if self._peek() == "*":
                        k = stack[-1]
                        if self.i + 1 + k < self.n and \
                           self.source[self.i+1:self.i+1+k] == ("=" * k) and \
                           self.source[self.i+1+k] == "/":
                            stack.pop()
                            self.i = self.i + 2 + k
                            continue
                    self.i += 1
                self.comments.append(self.source[start:self.i])
                continue
            break
        return had_nl

    def _read_bare_token(self) -> str:
        buf: list[str] = []
        while not self._eof():
            c = self._peek()
            if c in "\n\r":
                break
            if c in self.RESERVED:
                break
            if c == "\\":
                self.i += 1
                if self._eof():
                    break
                nxt = self._peek()
                if nxt in "\n\r":
                    self._consume_newline()
                    continue
                buf.append("\\")
                buf.append(self._take())
                continue
            buf.append(self._take())
        return "".join(buf).strip()
 
    def _read_value(self) -> str:
        self._skip()
        c = self._peek()
        if c == "{":
            return self._read_object()
        if c == "[":
            return self._read_array()
        if c in "\"'":
            q = c
            run = 0
            while self._peek(run) == q:
                run += 1
            if run >= 3:
                return self._read_multiquote()
            return self._read_string()
        if c == "@":
            return self._read_verbatim()
        tok = self._read_bare_token()
        if tok in ("true", "false", "null"):
            return tok
        num = JSONHNumberParser.to_decimal_literal(tok, decimals=15)
        if num is not None:
            return num
        try:
            return JSONHQuotelessDecoder.decode_to_json(tok)
        except Exception as e:
            raise self._err(str(e))

    def _read_key_json(self) -> str:
        self._skip()
        c = self._peek()
        if c in "\"'":
            return self._read_string()
        if c == "@":
            v = self._read_verbatim()
            if isinstance(v, str) and v.startswith('"'):
                return v
            return json.dumps(v, ensure_ascii=False)
        tok = self._read_bare_token()
        if not tok:
            raise self._err("Expected key in object")
        try:
            key = JSONHQuotelessDecoder.decode(tok, strip=True)
        except Exception as e:
            raise self._err(str(e))
        return json.dumps(key, ensure_ascii=False)

    def _read_braceless_object(self) -> str:
        pairs: list[str] = []
        while True:
            self._skip()
            if self._eof():
                break
            key = self._read_key_json()
            self._skip()
            if self._peek() != ":":
                raise self._err("Expected ':' in braceless object")
            self.i += 1
            val = self._read_value()
            pairs.append(f"{key}:{val}")
            had_nl = self._skip()
            if self._eof():
                break
            if self._peek() == ",":
                self.i += 1
                continue
            if had_nl:
                continue
            raise self._err("Expected ',' or newline after braceless pair")
        return "{" + ",".join(pairs) + "}"

    def _read_object(self) -> str:
        if self._take() != "{":
            raise self._err("Expected '{'")
        parts = ["{"]
        first = True
        while True:
            sep_nl = self._skip()
            c = self._peek()
            if c == "}":
                self._take()
                parts.append("}")
                return "".join(parts)
            if not first:
                if c == ",":
                    self._take()
                    self._skip()
                    c = self._peek()
                    if c == "}":
                        self._take()
                        parts.append("}")
                        return "".join(parts)
                elif not sep_nl:
                    raise self._err("Expected ',', newline, or '}' after object pair")
                parts.append(",")
            key_json = self._read_key_json()
            self._skip()
            if self._peek() != ":":
                raise self._err("Expected ':' in object")
            self._take()
            val_json = self._read_value()
            parts.extend([key_json, ":", val_json])
            first = False

    def _read_array(self) -> str:
        if self._take() != "[":
            raise self._err("Expected '['")
        items: list[str] = []
        self._skip()
        if self._peek() == "]":
            self.i += 1
            return "[]"
        while True:
            val = self._read_value()
            items.append(val)
            sep_nl = self._skip()
            if self._peek() == ",":
                self.i += 1
                self._skip()
                if self._peek() == "]":
                    self.i += 1
                    break
                continue
            if self._peek() == "]":
                self.i += 1
                break
            if sep_nl:
                continue
            raise self._err("Expected ',', newline, or ']' after array item")
        return "[" + ",".join(items) + "]"

    def _read_string(self) -> str:
        quote = self._take()
        if quote not in "\"'":
            raise self._err("Expected string quote")
        buf = []
        while not self._eof():
            c = self._take()
            if c == quote:
                decoded = JSONHQuotelessDecoder.decode("".join(buf), strip=False)
                return json.dumps(decoded, ensure_ascii=False)
            if c == "\\":
                if self._eof():
                    raise self._err("Unterminated string escape")
                nxt = self._take()
                buf.append("\\")
                buf.append(nxt)
                if nxt == "\r" and self._peek() == "\n":
                    buf.append("\n")
                    self.i += 1
                continue
            buf.append(c)
        raise self._err("Unterminated string")

    def _read_verbatim(self) -> str:
        if self._take() != "@":
            raise self._err("Expected '@'")
        if self._eof():
            raise self._err("Expected string immediately after '@'")
        if self._peek().isspace() or self._peek() in "#/":
            raise self._err("Expected string immediately after '@'")
        raw = self._read_quoteless_raw(is_verbatim=True)
        return json.dumps(raw, ensure_ascii=False)

    def _read_multiquote(self) -> str:
        q = self._peek()
        quote_count = 0
        while self._peek(quote_count) == q:
            quote_count += 1
        if quote_count < 3:
            raise self._err("Expected multi-quote")
        _start_quotes = self.i
        self.i += quote_count
        delimiter = q * quote_count
        end = self.source.find(delimiter, self.i)
        if end == -1:
            raise self._err("Unterminated multi-quote")
        content = self.source[self.i:end]
        has_first = False
        has_last = False
        if content.startswith("\n") or content.startswith("\r"):
            has_first = True
        elif content and content[0] in " \t":
            nl = content.find("\n")
            cr = content.find("\r")
            first_nl = min([x for x in [nl, cr] if x != -1], default=-1)
            if first_nl > 0 and content[:first_nl].strip() == "":
                has_first = True
        if content.endswith("\n") or content.endswith("\r"):
            has_last = True
        elif content and content[-1] in " \t":
            last_nl = max(content.rfind("\n"), content.rfind("\r"))
            if last_nl >= 0 and content[last_nl+1:].strip() == "":
                has_last = True
        if has_first and has_last:
            if content.startswith("\r\n"):
                content = content[2:]
            elif content.startswith("\n") or content.startswith("\r"):
                content = content[1:]
            else:
                first_nl = min([x for x in [content.find("\n"), content.find("\r")] if x != -1], default=-1)
                if first_nl >= 0:
                    if content[first_nl:first_nl+2] == "\r\n":
                        content = content[first_nl+2:]
                    else:
                        content = content[first_nl+1:]
            if content.endswith("\r\n"):
                content = content[:-2]
            elif content.endswith("\n") or content.endswith("\r"):
                content = content[:-1]
            else:
                last_nl = max(content.rfind("\n"), content.rfind("\r"))
                if last_nl >= 0:
                    content = content[:last_nl]
            line_start = self.source.rfind("\n", 0, end)
            if line_start == -1:
                line_start = self.source.rfind("\r", 0, end)
            if line_start != -1:
                closing_indent = self.source[line_start+1:end]
                if closing_indent.strip() == "":
                    indent_len = len(closing_indent)
                    lines = content.splitlines(True)
                    new_lines = []
                    for ln in lines:
                        if ln.startswith(closing_indent):
                            new_lines.append(ln[indent_len:])
                        else:
                            new_lines.append(ln)
                    content = "".join(new_lines)
        decoded = []
        j = 0
        while j < len(content):
            if content[j] == "\\" and j + 1 < len(content):
                nx = content[j+1]
                if nx == "n": decoded.append("\n"); j += 2; continue
                if nx == "r": decoded.append("\r"); j += 2; continue
                if nx == "t": decoded.append("\t"); j += 2; continue
                if nx == "\\": decoded.append("\\"); j += 2; continue
                if nx == '"': decoded.append('"'); j += 2; continue
                if nx == "'": decoded.append("'"); j += 2; continue
                if nx == "u" and j + 5 < len(content):
                    try:
                        decoded.append(chr(int(content[j+2:j+6], 16)))
                        j += 6; continue
                    except:
                        pass
                if nx == "U" and j + 9 < len(content):
                    try:
                        decoded.append(chr(int(content[j+2:j+10], 16)))
                        j += 10; continue
                    except:
                        pass
                decoded.append(nx); j += 2; continue
            decoded.append(content[j])
            j += 1
        self.i = end + quote_count
        return json.dumps("".join(decoded), ensure_ascii=False)

    def _read_root_json(self) -> str:
        self._skip()
        c = self._peek()
        if c in "{[":
            return self._read_value()
        save = self.i
        try:
            _ = self._read_key_json()
            self._skip()
            is_obj = (self._peek() == ":")
        except Exception:
            is_obj = False
        self.i = save
        if is_obj:
            return self._read_braceless_object()
        return self._read_value()

    def _read_quoteless_raw(self, *, is_verbatim: bool) -> str:
        buf: list[str] = []
        while not self._eof():
            c = self._peek()
            if c in "\r\n":
                break
            if c in self.RESERVED:
                break
            if c == "\\" and not is_verbatim:
                self.i += 1
                if self._eof():
                    break
                nxt = self._take()
                if nxt == "\n":
                    continue
                if nxt == "\r":
                    if self._peek() == "\n":
                        self.i += 1
                    continue
                buf.append("\\")
                buf.append(nxt)
                continue
            buf.append(self._take())
        return "".join(buf).strip()

class JSONHQuotelessDecoder:
    _HEX = "0123456789abcdefABCDEF"
    _ESCAPABLE_PUNCT = set([",", ":", "[", "]", "{", "}", "#", "@"])

    @staticmethod
    def decode(tok: str, *, strip: bool = True) -> str:
        out = []
        i = 0
        n = len(tok)
        def need(k: int):
            if i + k > n:
                raise ValueError("Incomplete escape sequence")
        def read_hex(k: int) -> int:
            nonlocal i
            need(k)
            s = tok[i:i+k]
            if any(c not in JSONHQuotelessDecoder._HEX for c in s):
                raise ValueError("Invalid hex escape")
            i += k
            return int(s, 16)
        while i < n:
            c = tok[i]
            if c != "\\":
                out.append(c)
                i += 1
                continue
            i += 1
            if i >= n:
                raise ValueError("Dangling backslash")
            esc = tok[i]
            i += 1
            if esc == "\n":
                continue
            if esc == "\r":
                if i < n and tok[i] == "\n":
                    i += 1
                continue
            if esc == " ":
                out.append(" ")
                continue
            if esc in JSONHQuotelessDecoder._ESCAPABLE_PUNCT:
                out.append(esc)
                continue
            if esc == "n": out.append("\n"); continue
            if esc == "r": out.append("\r"); continue
            if esc == "t": out.append("\t"); continue
            if esc == "\\": out.append("\\"); continue
            if esc == '"': out.append('"'); continue
            if esc == "'": out.append("'"); continue
            if esc == "/": out.append("/"); continue
            if esc == "b": out.append("\b"); continue
            if esc == "f": out.append("\f"); continue
            if esc == "v": out.append("\v"); continue
            if esc == "0": out.append("\0"); continue
            if esc == "a": out.append("\a"); continue
            if esc == "e": out.append("\x1b"); continue
            if esc == "x":
                cp = read_hex(2)
                out.append(chr(cp))
                continue
            if esc == "u":
                hi = read_hex(4)
                if 0xD800 <= hi <= 0xDBFF and i + 6 <= n and tok[i:i+2] == "\\u":
                    i += 2
                    lo = read_hex(4)
                    if 0xDC00 <= lo <= 0xDFFF:
                        cp = 0x10000 + ((hi - 0xD800) << 10) + (lo - 0xDC00)
                        out.append(chr(cp))
                        continue
                    raise ValueError("Invalid low surrogate")
                out.append(chr(hi))
                continue
            if esc == "U":
                cp = read_hex(8)
                out.append(chr(cp))
                continue
            raise ValueError(f"Invalid escape \\{esc}")
        s = "".join(out)
        return s.strip() if strip else s

    @staticmethod
    def decode_to_json(tok: str) -> str:
        # One conservative policy choice: unescaped / is rejected in quoteless tokens (easy to remove if undesired).
        for idx, ch in enumerate(tok):
            if ch == "/" and (idx == 0 or tok[idx - 1] != "\\"):
                raise ValueError("Slash rejected by policy")
        s = JSONHQuotelessDecoder.decode(tok, strip=True)
        return json.dumps(s, ensure_ascii=False)
    
class JSONHNumberParser:
    @staticmethod
    def to_decimal_literal(token: str, decimals: int = 15) -> str | None:
        try:
            value, _ = JSONHNumberParser._parse(token, decimals=decimals)
        except Exception:
            return None
        if value == value.to_integral_value():
            return str(value.to_integral_value())
        s = format(value, "f")
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        if s.startswith("."):
            s = "0" + s
        if s.startswith("-."):
            s = s.replace("-.", "-0.", 1)
        return s

    @staticmethod
    def _parse(token: str, decimals: int) -> tuple[Decimal, bool]:
        s = token.strip()
        if not s:
            raise ValueError("empty")
        if s in {".", "-.", "+."}:
            raise ValueError("bare dot")
        s = s.replace("_", "")
        sign = 1
        if s[0] == "-":
            sign = -1
            s = s[1:]
        elif s[0] == "+":
            s = s[1:]
        if not s:
            raise ValueError("no digits")
        base = 10
        base_digits = "0123456789"
        if s.startswith(("0x", "0X")):
            base = 16
            base_digits = "0123456789abcdef"
            s = s[2:]
        elif s.startswith(("0b", "0B")):
            base = 2
            base_digits = "01"
            s = s[2:]
        elif s.startswith(("0o", "0O")):
            base = 8
            base_digits = "01234567"
            s = s[2:]
        if not s:
            raise ValueError("no digits after base prefix")
        mantissa_part, exponent_part = JSONHNumberParser._split_exponent(s, base_digits)
        if exponent_part is not None:
            if not JSONHNumberParser._contains_any_digit(mantissa_part, base_digits):
                raise ValueError("missing mantissa digits")
            if not exponent_part or not JSONHNumberParser._contains_any_digit(exponent_part, base_digits):
                raise ValueError("missing exponent digits")
        mantissa = JSONHNumberParser._parse_fractional_number(mantissa_part, base, base_digits)
        used_fractional_exponent = False
        if exponent_part is None:
            out = mantissa
        else:
            exponent = JSONHNumberParser._parse_fractional_number(exponent_part, base, base_digits, allow_sign=True)
            pow10, fractional = JSONHNumberParser._pow10(exponent, decimals)
            used_fractional_exponent = fractional
            out = mantissa * pow10
        if sign == -1:
            out = -out
        if used_fractional_exponent:
            out = JSONHNumberParser._round_decimal_places(out, decimals)
        return out, used_fractional_exponent

    @staticmethod
    def _split_exponent(digits: str, base_digits: str) -> tuple[str, str | None]:
        if "e" in base_digits:
            for i, ch in enumerate(digits):
                if ch not in ("e", "E"):
                    continue
                if i + 1 < len(digits) and digits[i + 1] in ("+", "-"):
                    return digits[:i], digits[i + 1 :]
            return digits, None
        m = re.search(r"[eE]", digits)
        if not m:
            return digits, None
        i = m.start()
        return digits[:i], digits[i + 1 :]

    @staticmethod
    def _contains_any_digit(text: str, base_digits: str) -> bool:
        allowed = set(base_digits)
        for ch in text:
            if ch.lower() in allowed:
                return True
        return False

    @staticmethod
    def _parse_fractional_number(digits: str, base: int, base_digits: str, allow_sign: bool = False) -> Decimal:
        s = digits.strip()
        if not s:
            raise ValueError("empty fractional")
        local_sign = 1
        if allow_sign and s[0] in "+-":
            if s[0] == "-":
                local_sign = -1
            s = s[1:]
            if not s:
                raise ValueError("sign only")
        if "." not in s:
            n = JSONHNumberParser._parse_whole_number(s, base, base_digits)
            return Decimal(n * local_sign)
        whole_s, frac_s = s.split(".", 1)
        whole = JSONHNumberParser._parse_whole_number(whole_s, base, base_digits, allow_empty=True)
        frac = JSONHNumberParser._parse_whole_number(frac_s, base, base_digits, allow_empty=True)
        combined = Decimal(f"{whole}.{frac}")
        return combined * local_sign

    @staticmethod
    def _parse_whole_number(digits: str, base: int, base_digits: str, allow_empty: bool = False) -> int:
        s = digits.strip()
        if not s:
            if allow_empty:
                return 0
            raise ValueError("empty whole")
        allowed = set(base_digits)
        for ch in s:
            c = ch.lower()
            if c not in allowed:
                raise ValueError(f"invalid digit {ch!r} for base {base}")
        return int(s, base)

    @staticmethod
    def _pow10(exponent: Decimal, decimals: int) -> tuple[Decimal, bool]:
        if exponent == exponent.to_integral_value():
            n = int(exponent)
            return (Decimal(1).scaleb(n), False)
        with localcontext() as ctx:
            ctx.prec = max(50, decimals + 25)
            ln10 = Decimal(10).ln()
            val = (exponent * ln10).exp()
            val = JSONHNumberParser._round_decimal_places(val, decimals)
            return (val, True)

    @staticmethod
    def _round_decimal_places(x: Decimal, decimals: int) -> Decimal:
        q = Decimal(1).scaleb(-decimals)
        return x.quantize(q)