import re
from importlib import import_module
import unicodedata
SENTENCE_SEPARATORS = [".", ","]
SUPPORTED_LANGUAGES = ['en', 'es', 'hi', 'ru']
RE_BUG_LANGUAGES = ['hi']


class LanguageData:
    """Main language class to populate the requisite language-specific variables."""
    unit_numbers = {}
    direct_numbers = {}
    tens = {}
    hundreds = {}
    big_powers_of_ten = {}
    skip_tokens = []
    all_numbers = {}
    unit_and_direct_numbers = {}

    def __init__(self, language):
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f'"{language}" is not a supported language')
        language_info = getattr(import_module('number_parser.data.' + language), 'info')
        self.unit_numbers = _normalize_dict(language_info["UNIT_NUMBERS"])
        self.direct_numbers = _normalize_dict(language_info["DIRECT_NUMBERS"])
        self.tens = _normalize_dict(language_info["TENS"])
        self.hundreds = _normalize_dict(language_info["HUNDREDS"])
        self.big_powers_of_ten = _normalize_dict(language_info["BIG_POWERS_OF_TEN"])
        self.skip_tokens = language_info["SKIP_TOKENS"]

        self.all_numbers = {**self.unit_numbers, **self.direct_numbers, **self.tens,
                            **self.hundreds, **self.big_powers_of_ten}
        self.unit_and_direct_numbers = {**self.unit_numbers, **self.direct_numbers}
        self.maximum_group_value = 10000 if language_info["USE_LONG_SCALE"] else 100


def _check_validity(current_token, previous_token, previous_power_of_10, total_value, current_grp_value, lang_data):
    """Identifies whether the new token can continue building the previous number."""
    if current_token in lang_data.unit_and_direct_numbers and previous_token in lang_data.unit_and_direct_numbers:
        return False

    if current_token in lang_data.direct_numbers and previous_token in lang_data.tens:
        return False

    elif current_token in lang_data.tens:
        if previous_token in lang_data.tens or previous_token in lang_data.unit_and_direct_numbers:
            return False

    elif current_token in lang_data.hundreds:
        if previous_token not in lang_data.big_powers_of_ten and previous_token is not None:
            return False

    elif current_token in lang_data.big_powers_of_ten:
        power_of_ten = lang_data.big_powers_of_ten[current_token]
        if power_of_ten < current_grp_value:
            return False
        if total_value != 0 and previous_power_of_10 is not None and power_of_ten >= previous_power_of_10:
            return False
    return True


def _check_large_multiplier(current_token, total_value, current_grp_value, lang_data):
    """Checks if the current token (power of ten) is larger than the total value formed till now."""
    combined_value = total_value + current_grp_value
    if combined_value == 0:
        return False
    if current_token in lang_data.big_powers_of_ten:
        large_value = lang_data.big_powers_of_ten[current_token]
        if large_value > combined_value and large_value != 100:
            return True
    return False


def _build_number(token_list, lang_data):
    """Incrementally builds a number from the list of tokens."""
    total_value = 0
    current_grp_value = 0
    previous_token = None
    previous_power_of_10 = None
    value_list = []
    used_skip_tokens = []

    for token in token_list:
        if token.isspace() or token == "":
            continue
        if token in lang_data.skip_tokens:
            used_skip_tokens.append(token)
            continue

        is_large_multiplier = _check_large_multiplier(token, total_value, current_grp_value, lang_data)
        if is_large_multiplier:
            combined_value = total_value + current_grp_value
            total_value = combined_value * lang_data.big_powers_of_ten[token]
            previous_token = token
            current_grp_value = 0
            used_skip_tokens = []
            previous_power_of_10 = lang_data.big_powers_of_ten[token]
            continue

        valid = _check_validity(token, previous_token, previous_power_of_10, total_value, current_grp_value, lang_data)
        if not valid:
            total_value += current_grp_value
            value_list.append(str(total_value))
            total_value = 0
            current_grp_value = 0
            for skip_token in used_skip_tokens:
                value_list.append(skip_token)
            previous_power_of_10 = None

        if token in lang_data.unit_and_direct_numbers:
            current_grp_value += lang_data.unit_and_direct_numbers[token]

        elif token in lang_data.tens:
            current_grp_value += lang_data.tens[token]

        elif token in lang_data.hundreds:
            current_grp_value += lang_data.hundreds[token]

        elif token in lang_data.big_powers_of_ten:
            power_of_ten = lang_data.big_powers_of_ten[token]
            if current_grp_value == 0:
                current_grp_value = 1

            current_grp_value *= power_of_ten
            if power_of_ten > lang_data.maximum_group_value:
                total_value += current_grp_value
                current_grp_value = 0
                previous_power_of_10 = power_of_ten

        previous_token = token
        used_skip_tokens = []
    total_value += current_grp_value
    value_list.append(str(total_value))
    return value_list


def _tokenize(input_string, language):
    """Breaks string on any non-word character."""
    input_string = input_string.replace('\xad', '')
    if language in RE_BUG_LANGUAGES:
        return input_string.split()
    tokens = re.split(r'(\W)', input_string)
    return tokens


def _strip_accents(word):
    """Removes accent from the input word."""
    return ''.join(char for char in unicodedata.normalize('NFD', word) if unicodedata.category(char) != 'Mn')


def _normalize_tokens(token_list):
    """Converts all tokens to lowercase then removes accents."""
    return [_strip_accents(token.lower()) for token in token_list]


def _normalize_dict(lang_dict):
    """Removes the accent from each key of input dictionary"""
    return {_strip_accents(word): number for word, number in lang_dict.items()}


def _is_cardinal_token(token, language):
    lang_dict = LanguageData(language)
    return bool(token in lang_dict.all_numbers)


def _is_ordinal_token(token, language):
    token = _apply_cardinal_conversion(token, language)
    return _is_cardinal_token(token, language)


def _is_skip_token(token, language):
    lang_dict = LanguageData(language)
    return bool(token in lang_dict.skip_tokens)


def is_number_token(token, language):
    return _is_cardinal_token(token, language) or _is_ordinal_token(token, language) # or _is_skip_token(token, language)


def _apply_cardinal_conversion(input_string, language):
    # this will be coming from the LanguageData
    CARDINAL_DIRECT_NUMBERS = {'first': 'one', 'second': 'two', 'third': 'three', 'fifth': 'five', 'eighth': 'eight',
                               'ninth': 'nine', 'twelfth': 'twelve'}
    input_string = input_string.lower()
    for word, number in CARDINAL_DIRECT_NUMBERS.items():
        input_string = input_string.replace(word, number)
    input_string = re.sub(r'ieth$', 'y', input_string)
    input_string = re.sub(r'th$', '', input_string)
    return input_string


def parse_ordinal(input_string, language='en'):
    input_string = _apply_cardinal_conversion(input_string, language)
    return parse_number(input_string, language)


def parse_number(input_string, language='en'):
    """Converts a single number written in natural language to a numeric type"""
    lang_data = LanguageData(language)
    if input_string.isnumeric():
        return int(input_string)

    tokens = _tokenize(input_string, language)
    normalized_tokens = _normalize_tokens(tokens)
    for index, token in enumerate(normalized_tokens):
        if token in lang_data.all_numbers or token.isspace() or len(token) == 0:
            continue
        if token in lang_data.skip_tokens and index != 0:
            continue
        return None
    number_built = _build_number(normalized_tokens, lang_data)
    if len(number_built) == 1:
        return int(number_built[0])
    return None


def parse(input_string, language='en'):
    """
    Converts all the numbers in a sentence written in natural language to their numeric type while keeping
    the other words unchanged. Returns the transformed string.
    """

    tokens = _tokenize(input_string, language)
    if tokens is None:
        return None

    sentence = []
    current_number = []
    building_number = False

    for token in tokens:
        normalized_token = _strip_accents(token.lower())
        is_number = is_number_token(normalized_token, language)

        if not building_number:  # case 1: it's not building a number
            if is_number:
                # start number building process
                building_number = True
                current_number.append(token)
            else:
                # continue with next token
                sentence.append(token)
        else:  # case 2: it's building a number
            if is_number or token.isspace() or token == '' or _is_skip_token(token, language):
                # add token to the current number
                current_number.append(token)
            else:  # build number
                # 1. parse number
                number = _parse_number_tokens(current_number, language)

                # 2. Add number and current token to tokens
                sentence.append(number)
                if current_number[-1].isspace():
                    sentence.append(current_number[-1])
                sentence.append(token)

                # 3. Reset process
                building_number = False
                current_number = []

    # When finishing the loop, if the last element is a number we need to add it
    if building_number:
        number = _parse_number_tokens(current_number, language)
        sentence.append(number)

    return ''.join(sentence)


def _parse_number_tokens(current_number, language):
    # TODO: Add logic to handle multpliple following numbers
    # Basic idea:
    # current_number = ['twenty', 'three', 'three']
    # number = parse_number(current_number[0]) --> 20
    # number = parse_number(f'{current_number[0]} {current_number[1]}') --> 23
    # number = parse_number(f'{current_number[0]} {current_number[1]} {current_number[3]}') --> None
    # '23 3'

    current_number_str = ''.join(
        map(_strip_accents, map(str.lower, current_number))
    )
    number = parse_number(current_number_str, language)
    if not number:
        # try with ordinal
        number = parse_ordinal(current_number_str)
    return str(number) if number else current_number_str