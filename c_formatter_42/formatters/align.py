# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    align.py                                           :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: tschumac <tschumac@student.42luxembourg    +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2020/10/04 09:56:31 by cacharle          #+#    #+#              #
#    Updated: 2026/01/21 22:46:51 by tschumac         ###   ########.fr        #
#                                                                              #
# **************************************************************************** #

from __future__ import annotations

import re
import typing

if typing.TYPE_CHECKING:
    from typing import Literal

from c_formatter_42.formatters import helper

TYPEDECL_OPEN_REGEX = re.compile(
    r"""^(?P<prefix>\s*(typedef\s+)?   # Maybe a typedef
        (struct|enum|union))           # Followed by a struct, enum or union
        \s*(?P<suffix>[a-zA-Z_]\w+)?$  # Name of the type declaration
    """,
    re.X,
)
TYPEDECL_CLOSE_REGEX = re.compile(
    r"""^(?P<prefix>\})\s*             # Closing } followed by any amount of spaces
        (?P<suffix>([a-zA-Z_]\w+)?;)$  # Name of the type (if typedef used)
    """,
    re.X,
)


def align_scope(content: str, scope: Literal["local", "global"]) -> str:
    """Align content
    scope can be either local or global
      local:  for variable declarations in function
      global: for function prototypes
    """

    lines = content.split("\n")
    # select regex according to scope
    if scope == "local":
        align_regex = "^\t" r"(?P<prefix>{type})\s+" r"(?P<suffix>\**{decl};)$"
    elif scope == "global":
        align_regex = (
            r"^(?P<prefix>{type})\s+"
            r"(?P<suffix>({name}\(.*\)?;?)|({decl}(;|(\s+=\s+.*))))$"
        )
    align_regex = align_regex.format(
        type=helper.REGEX_TYPE, name=helper.REGEX_NAME, decl=helper.REGEX_DECL_NAME
    )
    lines_to_be_aligned = [re.match(align_regex, line) for line in lines]
    aligned = [
        (i, match.group("prefix"), match.group("suffix"))
        for i, match in enumerate(lines_to_be_aligned)
        if match is not None
        and match.group("prefix") not in ["struct", "union", "enum"]
    ]

    # For local scope, also check for static/const array declarations
    # Including function pointer arrays for alignment
    if scope == "local":
        # Simple arrays
        static_const_array_regex = re.compile(
            r"^\t(?P<prefix>(?:(?:static|const)\s+)+\S+)\s+(?P<suffix>\w+\[\]\s*=\s*\{.*)"
        )
        # Function pointer arrays: static type (*const name[])(params) = {
        # Match up to (*const, then suffix starts with name
        func_ptr_array_regex = re.compile(
            r"^\t(?P<prefix>(?:(?:static|const)\s+)+\S+\s+\(\*(?:const)?)\s+(?P<suffix>\w+\[\]\)\s*\([^)]+\)\s*=\s*\{.*)"
        )
        for i, line in enumerate(lines):
            # Try function pointer array first
            m = func_ptr_array_regex.match(line)
            if m is not None:
                aligned.append((i, m.group("prefix"), m.group("suffix")))
                continue
            # Then try simple array
            m = static_const_array_regex.match(line)
            if m is not None:
                aligned.append((i, m.group("prefix"), m.group("suffix")))

    # Global type declaration (struct/union/enum)
    if scope == "global":
        in_type_scope = False
        for i, line in enumerate(lines):
            m = TYPEDECL_OPEN_REGEX.match(line)
            if m is not None:
                in_type_scope = True
                if m.group("suffix") is not None and "typedef" not in m.group("prefix"):
                    aligned.append((i, m.group("prefix"), m.group("suffix")))
                continue
            m = TYPEDECL_CLOSE_REGEX.match(line)
            if m is not None:
                in_type_scope = False
                if line != "};":
                    aligned.append((i, m.group("prefix"), m.group("suffix")))
                continue
            if in_type_scope:
                m = re.match(
                    r"^(?P<prefix>\s+{type})\s+"
                    r"(?P<suffix>\**{decl};)$".format(
                        type=helper.REGEX_TYPE, decl=helper.REGEX_DECL_NAME
                    ),
                    line,
                )
                if m is not None:
                    aligned.append((i, m.group("prefix"), m.group("suffix")))

    # Minimum alignment required for each line
    min_alignment = max(
        (len(prefix.expandtabs(4)) // 4 + 1 for _, prefix, _ in aligned), default=1
    )
    for i, prefix, suffix in aligned:
        alignment = len(prefix.expandtabs(4)) // 4
        lines[i] = prefix + "\t" * (min_alignment - alignment) + suffix
        if scope == "local":
            lines[i] = (
                "\t" + lines[i]
            )  # Adding one more indent for inside the type declaration
    return "\n".join(lines)


@helper.locally_scoped
def align_local(content: str) -> str:
    """Wrapper for align_scope to use local_scope decorator"""
    return align_scope(content, scope="local")


def align(content: str) -> str:
    """Align the content in global and local scopes"""
    content = align_scope(content, scope="global")
    content = align_local(content)
    return content
