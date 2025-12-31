<img src="https://github.com/jsonh-org/Jsonh/blob/main/IconUpscaled.png?raw=true" width=180>

[![PyPI](https://img.shields.io/pypi/v/JsonhPy.svg)](https://pypi.python.org/pypi/JsonhPy)

**JSON for Humans.**

JSON is great. Until you miss that trailing comma... or want to use comments. What about multiline strings?
JSONH provides a much more elegant way to write JSON that's designed for humans rather than machines.

Since JSONH is compatible with JSON, any JSONH syntax can be represented with equivalent JSON.

## JsonhPy

JsonhPy is a parser implementation of [JSONH V1 & V2](https://github.com/jsonh-org/Jsonh) for Python 3.

## Example

```jsonh
{
    // use #, // or /**/ comments
    
    // quotes are optional
    keys: without quotes,

    // commas are optional
    isn\'t: {
        that: cool? # yes
    }

    // use multiline strings
    haiku: '''
        Let me die in spring
          beneath the cherry blossoms
            while the moon is full.
        '''
    
    // compatible with JSON5
    key: 0xDEADCAFE

    // or use JSON
    "old school": 1337
}
```

## Usage

Everything you need is contained within `JsonhReader`:

```py
from JsonhPy.JsonhPy import *

jsonh: str = """
{
    this is: awesome
}
"""
json: str = JsonhReader.parse_element_from_string(jsonh).value()
```