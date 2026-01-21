# **************************************************************************** #
#                                                                              #
#                                                         :::      ::::::::    #
#    hoist.py                                           :+:      :+:    :+:    #
#                                                     +:+ +:+         +:+      #
#    By: tschumac <tschumac@student.42luxembourg    +#+  +:+       +#+         #
#                                                 +#+#+#+#+#+   +#+            #
#    Created: 2020/10/04 11:16:28 by cacharle          #+#    #+#              #
#    Updated: 2026/01/21 22:46:51 by tschumac         ###   ########.fr        #
#                                                                              #
# **************************************************************************** #

import re

import c_formatter_42.formatters.helper as helper

DECLARATION_REGEX = re.compile(
    r"^\s*{t}\s+{d};$".format(t=helper.REGEX_TYPE, d=helper.REGEX_DECL_NAME)
)


@helper.locally_scoped
def hoist(content: str) -> str:
    r"""Hoist local variable and split assigned declaration

    Assignment splitting:
    {                   {
        int a = 1;  =>      int a;
                            a = 1;
    }                   }

    Variable hoisting:
    {                         {
        puts("bonjour");          int a;
        int a;            =>      char b;
        char b;                   puts("bonjour");
    }                         }

    Only one empty line after declarations
    {                         {
                                  int a;
        int a;                    char b;
        puts("bonjour");  ->
                                  puts("bonjour");
        char b;               }
    }
    """
    input_lines = content.split("\n")
    lines = []
    # Split assignment
    for line in input_lines:
        m = re.match(
            r"^(?P<indent>\s+)"
            r"(?P<type>{t})\s+"
            r"(?P<name>{d})\s+=\s+"
            r"(?P<value>.+);$".format(t=helper.REGEX_TYPE, d=helper.REGEX_DECL_NAME),
            line,
        )
        # If line is a declaration + assignment on the same line,
        # create 2 new lines, one for the declaration and one for the assignment
        # NOTE: edge case for array declarations which can't be hoisted (See #56)
        if (
            m is not None
            and re.match(r".*\[.*\].*", m.group("name")) is None
            and re.match(r"\s*(const|static)\s.*", line) is None
        ):
            lines.append(f"\t{m.group('type')}\t{m.group('name')};")
            lines.append(
                "{}{} = {};".format(
                    m.group("indent"),
                    m.group("name").replace("*", ""),  # replace '*' for pointers
                    m.group("value"),
                )
            )
        else:
            lines.append(line)

    # Split declarations from body and remove empty lines
    declarations = []
    body = []
    in_static_const_array = False
    static_const_buffer = []
    static_const_arrays = []

    for line in lines:
        # Check if line is a complete static/const array declaration on one line
        # Matches: static arr[], const arr[], static const arr[], const static arr[]
        # And function pointer arrays: static type (*const arr[])(args) = {...};
        if re.match(r"^\s*(?:(?:static|const)\s+)+.*\[\s*\].*=\s*\{.*\}\s*;", line):
            # Check if it's a function pointer array (has parentheses with *)
            is_function_pointer = re.search(r"\(\s*\*", line) is not None

            if is_function_pointer:
                # Function pointer arrays - split the array content, not parameters
                line_length = len(line.expandtabs(4))
                if line_length > 80:
                    # Pattern: static type (*const name[])(params) = {content};
                    m = re.match(r"^(\s*(?:(?:static|const)\s+)+\S+\s+\(\*(?:const\s+)?\w+\[\]\)\s*\([^)]+\))(\s*=\s*\{)([^}]+)(\}\s*;)$", line)
                    if m:
                        declaration = m.group(1).strip()  # Everything before = {
                        equals_brace = m.group(2)  # The = { part
                        content = m.group(3).strip()  # Array content
                        suffix = m.group(4)  # Closing };

                        # Split content by comma
                        items = [item.strip() for item in content.split(',') if item.strip()]

                        # Build opening line (align will add proper tabs between declaration and =)
                        opening = "\t" + declaration + " = {"

                        # Build lines keeping multiple items per line until we exceed 80 columns
                        arr = [opening]
                        current_line = "\t"
                        first_item = True

                        for i, item in enumerate(items):
                            is_last = (i == len(items) - 1)
                            if is_last:
                                test_line = current_line + item + suffix
                            else:
                                test_line = current_line + item + ", "
                            test_length = len(test_line.expandtabs(4))

                            if not first_item and test_length > 80:
                                # Save current line and start new one
                                arr.append(current_line.rstrip())
                                if is_last:
                                    current_line = "\t" + item + suffix
                                else:
                                    current_line = "\t" + item + ", "
                            else:
                                current_line = test_line
                                first_item = False

                        if current_line.strip():
                            arr.append(current_line)

                        static_const_arrays.append(arr)
                    else:
                        # Fallback: keep as single line
                        static_const_arrays.append([line])
                else:
                    # Keep as single line if under 80 columns
                    static_const_arrays.append([line])
            else:
                # Simple array - only split if it exceeds 80 columns
                line_length = len(line.expandtabs(4))
                if line_length > 80:
                    # Extract the opening part and content
                    m = re.match(r"^(\s*(?:(?:static|const)\s+)+\S+)\s+(\w+\[\])\s*=\s*\{(.*)(\}\s*;)$", line)
                    if m:
                        type_part = m.group(1).strip()
                        var_name = m.group(2)
                        content = m.group(3).strip()
                        closing = m.group(4)

                        # Split content by comma and ensure space after each comma
                        items = [item.strip() for item in content.split(',') if item.strip()]

                        # Build opening with just one space (align function will add tabs later)
                        opening = "\t" + type_part + " " + var_name + " = {"

                        # Build lines keeping multiple items per line until we exceed 80 columns
                        arr = []
                        current_line = opening
                        first_item = True

                        for i, item in enumerate(items):
                            is_last = (i == len(items) - 1)
                            # Add space after comma only if more items follow on same line
                            if is_last:
                                test_line = current_line + item + closing
                            else:
                                test_line = current_line + item + ", "
                            test_length = len(test_line.expandtabs(4))

                            if not first_item and test_length > 80:
                                # Current line would exceed 80, save it without trailing space
                                arr.append(current_line.rstrip())
                                if is_last:
                                    current_line = "\t" + item + closing
                                else:
                                    current_line = "\t" + item + ", "
                            else:
                                # Add to current line
                                current_line = test_line
                                first_item = False

                        # Add the last line
                        if current_line:
                            arr.append(current_line)

                        static_const_arrays.append(arr)
                    else:
                        # Fallback: keep as single line
                        static_const_arrays.append([line])
                else:
                    # Keep as single line if under 80 columns
                    static_const_arrays.append([line])
        # Check if line starts a multi-line static/const array declaration
        # The opening { might be on the same line as content, so just check for { not followed by }; on same line
        # Matches both simple arrays and function pointer arrays
        elif re.match(r"^\s*(?:(?:static|const)\s+)+.*\[\s*\].*=\s*\{", line) and not re.search(r"\}\s*;", line):
            in_static_const_array = True
            # Check if it's a function pointer array
            is_function_pointer = re.search(r"\(\s*\*", line) is not None
            static_const_buffer = [line]
        # Check if we're continuing a static const array
        elif in_static_const_array:
            # Check if the line ends the array declaration (contains closing };)
            if re.search(r"\}\s*;", line):
                # For function pointers, keep original indentation
                # For simple arrays, normalize to single tab
                if is_function_pointer:
                    static_const_buffer.append(line)
                else:
                    static_const_buffer.append("\t" + line.lstrip())
                in_static_const_array = False
                static_const_arrays.append(static_const_buffer)
                static_const_buffer = []
            else:
                # Content line
                if is_function_pointer:
                    static_const_buffer.append(line)
                else:
                    static_const_buffer.append("\t" + line.lstrip())
        # Regular declaration check
        elif DECLARATION_REGEX.match(line) is not None:
            declarations.append(line)
        # Non-empty body lines
        elif line != "":
            body.append(line)

    # Combine declarations and static const arrays
    # Static const arrays should come first, then regular declarations
    lines = []
    for arr in static_const_arrays:
        lines.extend(arr)
    lines.extend(declarations)

    if len(lines) != 0:
        lines.append("")
    lines.extend(body)
    return "\n".join(lines)
