#
# Copyright (c) 2011-2015 The developers of Aqualid project
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom
# the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE
#  OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


import operator
import itertools

try:
    zip_longest = itertools.zip_longest
except AttributeError:
    zip_longest = itertools.izip_longest

from aql.util_types import String, u_str, is_string, to_string, IgnoreCaseString,\
    Version, FilePath, AbsFilePath, to_sequence, is_sequence,\
    UniqueList, List, split_list_type, value_list_type,\
    Dict, split_dict_type, value_dict_type,\
    is_simple_value

__all__ = (
    'OptionType', 'StrOptionType', 'VersionOptionType', 'PathOptionType',
    'AbsPathOptionType', 'BoolOptionType',
    'EnumOptionType', 'RangeOptionType', 'ListOptionType', 'DictOptionType',
    'auto_option_type', 'OptionHelpGroup', 'OptionHelp',
    'ErrorOptionTypeEnumAliasIsAlreadySet',
    'ErrorOptionTypeEnumValueIsAlreadySet',
    'ErrorOptionTypeUnableConvertValue', 'ErrorOptionTypeNoEnumValues',
    'ErrorOptionTypeCantDeduce',
)

# ==============================================================================


class ErrorOptionTypeEnumAliasIsAlreadySet(Exception):

    def __init__(self, option, value, current_value, new_value):
        msg = "Alias '%s' of Enum Option '%s' can't be changed to " \
              "'%s' from '%s'" %\
              (value, option, new_value, current_value)
        super(ErrorOptionTypeEnumAliasIsAlreadySet, self).__init__(msg)

# ==============================================================================


class ErrorOptionTypeEnumValueIsAlreadySet(Exception):

    def __init__(self, option, value, new_value):
        msg = "Value '%s' of Enum Option '%s' can't be changed to alias " \
              "to '%s'" % (value, option, new_value)
        super(ErrorOptionTypeEnumValueIsAlreadySet, self).__init__(msg)

# ==============================================================================


class ErrorOptionTypeUnableConvertValue(TypeError):

    def __init__(self, option_help, invalid_value):
        if isinstance(option_help, OptionType):
            option_help = option_help.help()

        self.option_help = option_help
        self.invalid_value = invalid_value

        msg = "Unable to convert value '%s (%s)' to option %s" % (
            invalid_value, type(invalid_value), option_help.error_text())
        super(ErrorOptionTypeUnableConvertValue, self).__init__(msg)

# ==============================================================================


class ErrorOptionTypeNoEnumValues(TypeError):

    def __init__(self, option_type):
        msg = "Enum option type '%s' doesn't have any values." % (option_type,)
        super(ErrorOptionTypeNoEnumValues, self).__init__(msg)


class ErrorOptionTypeCantDeduce(Exception):

    def __init__(self, value):
        msg = "Unable to deduce option type from value type: '%s." % (
            type(value),)
        super(ErrorOptionTypeCantDeduce, self).__init__(msg)

# ==============================================================================


def auto_option_type(value):

    if is_sequence(value):
        unique = isinstance(value, (UniqueList, set, frozenset))

        value_type = type(next(iter(value), ''))

        opt_type = ListOptionType(value_type=value_type, unique=unique)

    elif isinstance(value, dict):
        opt_type = DictOptionType()

    elif isinstance(value, bool):
        opt_type = BoolOptionType()

    elif isinstance(value, IgnoreCaseString):
        opt_type = StrOptionType(ignore_case=True)

    elif is_string(value):
        opt_type = StrOptionType()

    elif isinstance(value, Version):
        opt_type = VersionOptionType()

    elif isinstance(value, FilePath):
        opt_type = PathOptionType()

    elif is_simple_value(value):
        opt_type = OptionType(value_type=type(value))

    else:
        raise ErrorOptionTypeCantDeduce(value)

    opt_type.is_auto = True

    return opt_type

# ==============================================================================


def _get_type_name(value_type):
    if issubclass(value_type, bool):
        name = "boolean"

    elif issubclass(value_type, int):
        name = "integer"

    elif issubclass(value_type, IgnoreCaseString):
        name = "case insensitive string"

    elif issubclass(value_type, (str, u_str)):
        name = "string"

    else:
        name = value_type.__name__

    return name.title()

# ==============================================================================


def _join_to_length(values, max_length=0, separator="", prefix="", suffix=""):

    result = []
    current_value = ""

    for value in values:
        value = prefix + value + suffix

        if len(current_value) + len(value) > max_length:
            if current_value:
                current_value += separator
                result.append(current_value)
                current_value = ""

        if current_value:
            current_value += separator

        current_value += value

    if current_value:
        result.append(current_value)

    return result

# ==============================================================================


def _indent_items(indent_value, values):

    result = []

    indent_spaces = ' ' * len(indent_value)

    for value in values:
        if value:
            if result:
                value = indent_spaces + value
            else:
                value = indent_value + value

        result.append(value)

    return result

# ==============================================================================


def _merge_lists(values1, values2, indent_size):
    result = []

    max_name = max(values1, key=len)
    indent_size = max(indent_size, len(max_name)) + 1

    for left, right in zip_longest(values1, values2, fillvalue=""):
        if not right:
            right_indent = ""
        else:
            right_indent = ' ' * (indent_size - len(left))

        value = left + right_indent + right

        result.append(value)

    return result


# ==============================================================================

class OptionHelp(object):
    __slots__ = (
        'option_type',
        '_names',
        'type_name',
        'allowed_values',
        'current_value',
    )

    def __init__(self, option_type):
        self.option_type = option_type

        help_type = option_type.help_type()
        self.type_name = help_type if help_type else None

        help_range = option_type.help_range()
        self.allowed_values = help_range if help_range else None

        self._names = []
        self.current_value = None

    # -----------------------------------------------------------

    @property
    def is_key(self):
        return self.option_type.is_tool_key

    @property
    def group(self):
        return self.option_type.group

    @property
    def description(self):
        return self.option_type.description

    @property
    def names(self):
        return self._names

    @names.setter
    def names(self, names):
        self._names = sorted(names, key=str.lower)

    # -----------------------------------------------------------

    def is_hidden(self):
        return not bool(self.description) or self.option_type.is_hidden

    # -----------------------------------------------------------

    def _current_value(self, details):
        if self.current_value is not None:
            if isinstance(self.current_value, (list, tuple, UniqueList)):
                current_value = [to_string(v) for v in self.current_value]
                if current_value:
                    current_value = _join_to_length(
                        current_value,
                        64,
                        separator=",",
                        prefix="'",
                        suffix="'")

                    current_value = _indent_items("[ ", current_value)
                    current_value[-1] += " ]"
                    details.extend(current_value)
                else:
                    details.append("[]")
            else:
                current_value = self.option_type.to_str(self.current_value)
                if not current_value:
                    current_value = "''"

                details.append(current_value)
        else:
            details.append("N/A")

    # -----------------------------------------------------------

    def text(self, brief=False, names_indent=0):

        details = []

        self._current_value(details)

        if not brief:
            if self.description:
                details.append(self.description)

            if self.type_name:
                details.append("Type: " + self.type_name)

            if self.allowed_values:
                details += _indent_items("Allowed values: ",
                                         self.allowed_values)

        details = _indent_items(": ", details)

        result = []

        if self.names:
            names = self.names
            key_marker = '* ' if self.is_key else '  '
            names = [key_marker + name for name in names]

            details = _merge_lists(names, details, names_indent + 2)

        result += details

        return result

    # -----------------------------------------------------------

    def error_text(self):

        result = []

        if self.names:
            result.append(', '.join(self.names))

        if self.type_name:
            result.append("Type: " + self.type_name)

        if self.allowed_values:
            result.append("Allowed values: %s" %
                          ', '.join(self.allowed_values))

        return '. '.join(result)

# ==============================================================================


class OptionHelpGroup(object):
    __slots__ = (
        'name',
        'max_option_name_length',
        'help_list',
    )

    def __init__(self, group_name):
        self.name = group_name
        self.max_option_name_length = 0
        self.help_list = []

    def append(self, option_help):
        self.max_option_name_length = max(
            self.max_option_name_length, len(max(option_help.names, key=len)))
        self.help_list.append(option_help)

    def __iter__(self):
        return iter(self.help_list)

    def text(self, brief=False, indent=0):

        result = []

        group_name = self.name
        if group_name:
            group_name = "%s:" % (group_name,)
            group_border_bottom = "-" * len(group_name)
            result.extend([group_name, group_border_bottom])

        names_indent = self.max_option_name_length

        self.help_list.sort(key=operator.attrgetter('names'))

        for option_help in self.help_list:
            opt_text = option_help.text(brief, names_indent)

            if (len(opt_text) > 1) and result and result[-1]:
                result.append("")

            result.extend(opt_text)

            if len(opt_text) > 1:
                result.append("")

        if indent:
            result = _indent_items(' ' * indent, result)

        return result

# ==============================================================================


class OptionType (object):

    __slots__ = (
        'value_type',
        'default',
        'description',
        'group',
        'range_help',
        'is_auto',
        'is_tool_key',
        'is_hidden',
    )

    # -----------------------------------------------------------

    def __init__(self,
                 value_type=str,
                 description=None,
                 group=None,
                 range_help=None,
                 default=NotImplemented,
                 is_tool_key=False,
                 is_hidden=False
                 ):

        if type(value_type) is type and issubclass(value_type, OptionType):
            value_type = value_type()

        self.value_type = value_type
        self.is_auto = False
        self.is_tool_key = is_tool_key
        self.is_hidden = is_hidden
        self.description = description
        self.group = group
        self.range_help = range_help
        if default is NotImplemented:
            self.default = NotImplemented
        else:
            self.default = value_type(default)

    # -----------------------------------------------------------

    def __call__(self, value=NotImplemented):
        """
        Converts a value to options' value
        """

        try:
            if value is NotImplemented:
                if self.default is NotImplemented:
                    return self.value_type()
                return self.default

            return self.value_type(value)
        except (TypeError, ValueError):
            raise ErrorOptionTypeUnableConvertValue(self, value)

    # -----------------------------------------------------------

    def to_str(self, value):
        """
        Converts a value to options' value string
        """
        return to_string(value)

    # -----------------------------------------------------------

    def help(self):
        return OptionHelp(self)

    # -----------------------------------------------------------

    def help_type(self):
        return _get_type_name(self.value_type)

    # -----------------------------------------------------------

    def help_range(self):
        """
        Returns a description (list of strings) about range of allowed values
        """
        if self.range_help:
            return list(to_sequence(self.range_help))

        return []

# ==============================================================================
# ==============================================================================


class StrOptionType (OptionType):

    def __init__(self,
                 ignore_case=False,
                 description=None,
                 group=None,
                 range_help=None,
                 is_tool_key=False,
                 is_hidden=False
                 ):

        value_type = IgnoreCaseString if ignore_case else String
        super(StrOptionType, self).__init__(value_type,
                                            description,
                                            group,
                                            range_help,
                                            is_tool_key=is_tool_key,
                                            is_hidden=is_hidden)

# ==============================================================================
# ==============================================================================


class VersionOptionType (OptionType):

    def __init__(self,
                 description=None,
                 group=None,
                 range_help=None,
                 is_tool_key=False,
                 is_hidden=False):

        super(VersionOptionType, self).__init__(Version,
                                                description,
                                                group,
                                                range_help,
                                                is_tool_key=is_tool_key,
                                                is_hidden=is_hidden)

    def help_type(self):
        return "Version String"

# ==============================================================================
# ==============================================================================


class PathOptionType (OptionType):

    def __init__(self,
                 description=None,
                 group=None,
                 range_help=None,
                 is_tool_key=False,
                 is_hidden=False,
                 default=NotImplemented
                 ):

        super(PathOptionType, self).__init__(FilePath,
                                             description,
                                             group,
                                             range_help,
                                             is_tool_key=is_tool_key,
                                             is_hidden=is_hidden,
                                             default=default)

    def help_type(self):
        return "File System Path"

# ==============================================================================
# ==============================================================================


class AbsPathOptionType (OptionType):

    def __init__(self,
                 description=None,
                 group=None,
                 range_help=None,
                 is_tool_key=False,
                 is_hidden=False,
                 default=NotImplemented
                 ):

        super(AbsPathOptionType, self).__init__(AbsFilePath,
                                                description,
                                                group,
                                                range_help,
                                                is_tool_key=is_tool_key,
                                                is_hidden=is_hidden,
                                                default=default)

    def help_type(self):
        return "File System Path"

# ==============================================================================
# ==============================================================================


class BoolOptionType (OptionType):

    __slots__ = (
        'true_value',
        'false_value',
        'true_values',
        'false_values',
        'aliases',
    )

    # -----------------------------------------------------------

    __true_values = ('yes', 'true', 'on', 'enabled', 'y', '1', 't')
    __false_values = ('no', 'false', 'off', 'disabled', 'n', '0', 'f')

    # -----------------------------------------------------------

    def __init__(self,
                 description=None,
                 group=None,
                 style=None,
                 true_values=None,
                 false_values=None,
                 default=False,
                 is_tool_key=False,
                 is_hidden=False
                 ):

        # noinspection PyTypeChecker
        super(BoolOptionType, self).__init__(bool, description, group,
                                             default=default,
                                             is_tool_key=is_tool_key,
                                             is_hidden=is_hidden)

        if style is None:
            style = ('true', 'false')
        else:
            style = map(IgnoreCaseString, style)

        if true_values is None:
            true_values = self.__true_values
        else:
            true_values = to_sequence(true_values)

        if false_values is None:
            false_values = self.__false_values
        else:
            false_values = to_sequence(false_values)

        self.true_value, self.false_value = style
        self.true_values = set()
        self.false_values = set()

        self.add_values(true_values, false_values)
        self.add_values(self.true_value, self.false_value)

    # -----------------------------------------------------------

    def __call__(self, value=NotImplemented):

        if type(value) is bool:
            return value

        if value is NotImplemented:
            value = self.default

        value_str = IgnoreCaseString(value)
        if value_str in self.true_values:
            return True

        if value_str in self.false_values:
            return False

        return True if value else False

    # -----------------------------------------------------------

    def to_str(self, value):
        return self.true_value if value else self.false_value

    # -----------------------------------------------------------

    def add_values(self, true_values, false_values):
        true_values = to_sequence(true_values)
        false_values = to_sequence(false_values)

        self.true_values.update(map(IgnoreCaseString, true_values))
        self.false_values.update(map(IgnoreCaseString, false_values))

    # -----------------------------------------------------------

    def help_range(self):

        def _make_help(value, values):
            values = list(values)
            values.remove(value)

            if values:
                values = ', '.join(sorted(values))
                return "%s (or %s)" % (value, values)

            return "%s" % (value,)

        return [_make_help(self.true_value, self.true_values),
                _make_help(self.false_value, self.false_values), ]

# ==============================================================================
# ==============================================================================


class EnumOptionType (OptionType):

    __slots__ = (
        '__values',
        'strict',

    )

    def __init__(self,
                 values,
                 description=None,
                 group=None,
                 value_type=IgnoreCaseString,
                 default=NotImplemented,
                 strict=True,
                 is_tool_key=False,
                 is_hidden=False
                 ):

        super(EnumOptionType, self).__init__(value_type, description, group,
                                             default=default,
                                             is_tool_key=is_tool_key,
                                             is_hidden=is_hidden)

        self.__values = {}

        if default is not NotImplemented:
            self.add_values(default)

        self.add_values(values)

        self.strict = strict

    # -----------------------------------------------------------

    def add_values(self, values):
        try:
            values = tuple(values.items())  # convert dictionary to a sequence
        except AttributeError:
            pass

        set_default_value = self.__values.setdefault
        value_type = self.value_type

        for value in to_sequence(values):

            it = iter(to_sequence(value))

            value = value_type(next(it))

            value = set_default_value(value, value)

            for alias in it:
                alias = value_type(alias)

                v = set_default_value(alias, value)
                if v != value:
                    if alias == v:
                        raise ErrorOptionTypeEnumValueIsAlreadySet(
                            self, alias, value)
                    else:
                        raise ErrorOptionTypeEnumAliasIsAlreadySet(
                            self, alias, v, value)

    # -----------------------------------------------------------

    def _get_default(self):
        value = self.default
        if value is not NotImplemented:
            return value

        try:
            return next(iter(self.__values.values()))
        except StopIteration:
            if self.strict:
                raise ErrorOptionTypeNoEnumValues(self)

        return self.value_type()

    # -----------------------------------------------------------

    def _convert_value(self, value):

        try:
            value = self.value_type(value)
        except (TypeError, ValueError):
            raise ErrorOptionTypeUnableConvertValue(self, value)

        try:
            return self.__values[value]
        except KeyError:
            if self.strict:
                raise ErrorOptionTypeUnableConvertValue(self, value)

        return value

    # -----------------------------------------------------------

    def __call__(self, value=NotImplemented):

        if value is NotImplemented:
            return self._get_default()

        return self._convert_value(value)

    # -----------------------------------------------------------

    def help_range(self):

        values = {}

        for alias, value in self.__values.items():
            if alias is value:
                values.setdefault(alias, [])
            else:
                values.setdefault(value, []).append(alias)

        help_str = []

        for value, aliases in values.items():
            s = to_string(value)
            if aliases:
                s += ' (or ' + ', '.join(map(to_string, aliases)) + ')'

            help_str.append(s)

        return help_str

    # -----------------------------------------------------------

    def range(self):
        values = []

        for alias, value in self.__values.items():
            if alias is value:
                values.append(alias)

        return values

# ==============================================================================
# ==============================================================================

# noinspection PyAttributeOutsideInit


class RangeOptionType (OptionType):

    __slots__ = (
        'min_value',
        'max_value',
        'restrain',
    )

    def __init__(self,
                 min_value,
                 max_value,
                 description=None,
                 group=None,
                 value_type=int,
                 restrain=True,
                 default=NotImplemented,
                 is_tool_key=False,
                 is_hidden=False
                 ):

        # noinspection PyTypeChecker
        super(RangeOptionType, self).__init__(value_type, description, group,
                                              default=default,
                                              is_tool_key=is_tool_key,
                                              is_hidden=is_hidden)

        self.set_range(min_value, max_value, restrain)
        if default is not NotImplemented:
            self.default = self(default)

    # -----------------------------------------------------------

    def set_range(self, min_value, max_value, restrain=True):

        if min_value is not None:
            try:
                min_value = self.value_type(min_value)
            except (TypeError, ValueError):
                raise ErrorOptionTypeUnableConvertValue(self, min_value)
        else:
            min_value = self.value_type()

        if max_value is not None:
            try:
                max_value = self.value_type(max_value)
            except (TypeError, ValueError):
                raise ErrorOptionTypeUnableConvertValue(self, max_value)
        else:
            max_value = self.value_type()

        self.min_value = min_value
        self.max_value = max_value

        if restrain is not None:
            self.restrain = restrain

    # -----------------------------------------------------------

    def __call__(self, value=NotImplemented):
        try:
            min_value = self.min_value

            if value is NotImplemented:
                if self.default is NotImplemented:
                    return min_value
                value = self.default

            value = self.value_type(value)

            if value < min_value:
                if self.restrain:
                    value = min_value
                else:
                    raise TypeError()

            max_value = self.max_value

            if value > max_value:
                if self.restrain:
                    value = max_value
                else:
                    raise TypeError()

            return value

        except TypeError:
            raise ErrorOptionTypeUnableConvertValue(self, value)

    # -----------------------------------------------------------

    def help_range(self):
        return ["%s ... %s" % (self.min_value, self.max_value)]

    # -----------------------------------------------------------

    def range(self):
        return [self.min_value, self.max_value]

# ==============================================================================
# ==============================================================================


class ListOptionType (OptionType):

    __slots__ = ('item_type',)

    # ==========================================================

    def __init__(self,
                 value_type=str,
                 unique=False,
                 separators=', ',
                 description=None,
                 group=None,
                 range_help=None,
                 is_tool_key=False,
                 is_hidden=False
                 ):

        if type(value_type) is type and issubclass(value_type, OptionType):
            value_type = value_type()

        if isinstance(value_type, OptionType):
            if description is None:
                description = value_type.description
                if description:
                    description = "List of: " + description

            if group is None:
                group = value_type.group

            if range_help is None:
                range_help = value_type.range_help

        if unique:
            list_type = UniqueList
        else:
            list_type = List

        list_type = value_list_type(list_type, value_type)

        if separators:
            list_type = split_list_type(list_type, separators)

        super(ListOptionType, self).__init__(list_type, description,
                                             group, range_help,
                                             is_tool_key=is_tool_key,
                                             is_hidden=is_hidden)
        self.item_type = value_type

    # -----------------------------------------------------------

    def __call__(self, values=None):
        try:
            if values is NotImplemented:
                values = []

            return self.value_type(values)

        except (TypeError, ValueError):
            raise ErrorOptionTypeUnableConvertValue(self, values)

    # -----------------------------------------------------------

    def help_type(self):

        if isinstance(self.item_type, OptionType):
            item_type = self.item_type.help_type()
        else:
            item_type = _get_type_name(self.item_type)

        return "List of %s" % item_type

    # -----------------------------------------------------------

    def help_range(self):

        if self.range_help:
            return list(to_sequence(self.range_help))

        if isinstance(self.item_type, OptionType):
            return self.item_type.help_range()

        return []

# ==============================================================================


class DictOptionType (OptionType):

    # ==========================================================

    def __init__(self,
                 key_type=str,
                 value_type=None,
                 separators=', ',
                 description=None,
                 group=None,
                 range_help=None,
                 is_tool_key=False,
                 is_hidden=False
                 ):

        if type(value_type) is type and issubclass(value_type, OptionType):
            value_type = value_type()

        if isinstance(value_type, OptionType):
            if description is None:
                description = value_type.description
                if description:
                    description = "List of: " + description

            if group is None:
                group = value_type.group

            if range_help is None:
                range_help = value_type.range_help

        dict_type = value_dict_type(Dict, key_type, value_type)

        if separators:
            dict_type = split_dict_type(dict_type, separators)

        super(DictOptionType, self).__init__(dict_type, description, group,
                                             range_help,
                                             is_tool_key=is_tool_key,
                                             is_hidden=is_hidden)

    # -----------------------------------------------------------

    def set_value_type(self, key, value_type):
        if isinstance(value_type, OptionType):
            value_type = value_type.value_type
        self.value_type.set_value_type(key, value_type)

    # -----------------------------------------------------------

    def __call__(self, values=None):
        try:
            if values is NotImplemented:
                values = None

            return self.value_type(values)

        except (TypeError, ValueError):
            raise ErrorOptionTypeUnableConvertValue(self, values)

    # -----------------------------------------------------------

    def help_type(self):

        value_type = self.value_type.get_value_type()
        if value_type is not None:
            if isinstance(value_type, OptionType):
                value_type = value_type.help_type()
            else:
                value_type = _get_type_name(value_type)

            return "Dictionary of %s" % (value_type,)

        return "Dictionary"

    # -----------------------------------------------------------

    def help_range(self):

        if self.range_help:
            return list(to_sequence(self.range_help))

        value_type = self.value_type.get_value_type()
        if isinstance(value_type, OptionType):
            return value_type.help_range()

        return []
