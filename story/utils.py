# coding: utf-8
import re
from difflib import SequenceMatcher

import yaml
from profanityfilter import ProfanityFilter
from func_timeout import func_timeout, FunctionTimedOut

YAML_FILE = "story/story_data.yaml"


with open("story/censored_words.txt", "r") as f:
    censored_words = [l.replace("\n", "") for l in f.readlines()]

pf = ProfanityFilter(custom_censor_list=censored_words)


def console_print(text, width=75):
    last_newline = 0
    i = 0
    while i < len(text):
        if text[i] == "\n":
            last_newline = 0
        elif last_newline > width and text[i] == " ":
            text = text[:i] + "\n" + text[i:]
            last_newline = 0
        else:
            last_newline += 1
        i += 1
    print(text)


def get_similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()


def get_num_options(num):

    while True:
        choice = input("Enter the number of your choice: ")
        try:
            result = int(choice)
            if result >= 0 and result < num:
                return result
            else:
                print("Error invalid choice. ")
        except ValueError:
            print("Error invalid choice. ")


def player_died(text):
    """
    TODO: Add in more sophisticated NLP, maybe a custom classifier
    trained on hand-labelled data that classifies second-person
    statements as resulting in death or not.
    """
    lower_text = text.lower()
    you_dead_regexps = [
        r"you('re| are) (dead|killed|slain|no more|nonexistent)",
        r"you (die|pass away|perish|suffocate|drown|bleed out)",
        r"you('ve| have) (died|perished|suffocated|drowned|been (killed|slain))",
        r"you (\w* )?(yourself )?to death",
        r"you (\w* )*(collapse|bleed out|chok(e|ed|ing)|drown|dissolve) (\w* )*and (die(|d)|pass away|cease to exist|(\w* )+killed)",
    ]
    return any(re.search(regexp, lower_text) for regexp in you_dead_regexps)


def player_won(text):
    lower_text = text.lower()
    won_phrases = [
        r"you ((\w* )*and |)live happily ever after",
        r"you ((\w* )*and |)live (forever|eternally|for eternity)",
        r"you ((\w* )*and |)(are|become|turn into) ((a|now) )?(deity|god|immortal)",
        r"you ((\w* )*and |)((go|get) (in)?to|arrive (at|in)) (heaven|paradise)",
        r"you ((\w* )*and |)celebrate your (victory|triumph)",
        r"you ((\w* )*and |)retire",
    ]
    return any(re.search(regexp, lower_text) for regexp in won_phrases)


def remove_profanity(text):
    return pf.censor(text)


def cut_trailing_quotes(text):
    num_quotes = text.count('"')
    if num_quotes % 2 == 0:
        return text
    else:
        final_ind = text.rfind('"')
        return text[:final_ind]

def fix_trailing_quotes(text):
    num_quotes = text.count('"')
    if num_quotes % 2 == 0:
        return text
    else:
        return text + '"'


def cut_trailing_action(text):
    lines = text.rstrip().split("\n")
    last_para = re.findall(r".+?(?:\.{1,3}|[!\?]|$)(?!\")", lines[-1])
    if len(last_para) < 1:
        return ""
    last_line = last_para[-1].rstrip()
    if (
        "you ask" in last_line.lower()
        or "you say" in last_line.lower()
    ) and len(lines) > 1:
        if len(last_para) > 1:
            last_para = last_para[:-1]
            lines[-1] = " ".join(last_para)
        else:
            lines = lines[:-1]
    text = "\n".join(lines)
    return text


def cut_trailing_sentence(text, raw=False):
    text = standardize_punctuation(text)
    last_punc = max(text.rfind("."), text.rfind("!"), text.rfind("?"))
    if last_punc <= 0:
        last_punc = len(text) - 1

    et_token = text.find("<")
    if et_token > 0:
        last_punc = min(last_punc, et_token - 1)
    elif et_token == 0:
        last_punc = min(last_punc, et_token)

    if not raw:
        act_token = text.find(">")
        if act_token > 0:
            last_punc = min(last_punc, act_token - 1)
        elif act_token == 0:
            last_punc = min(last_punc, act_token)

    text = text[:last_punc+1]

    text = fix_trailing_quotes(text)
    if not raw:
        text = cut_trailing_action(text)
    return text


def replace_outside_quotes(text, current_word, repl_word):
    text = standardize_punctuation(text)

    reg_expr = re.compile(current_word + '(?=([^"]*"[^"]*")*[^"]*$)')

    output = reg_expr.sub(repl_word, text)
    return output


def is_first_person(text):

    count = 0
    for pair in first_to_second_mappings:
        variations = mapping_variation_pairs(pair)
        for variation in variations:
            reg_expr = re.compile(variation[0] + '(?=([^"]*"[^"]*")*[^"]*$)')
            matches = re.findall(reg_expr, text)
            count += len(matches)

    if count > 3:
        return True
    else:
        return False


def is_second_person(text):
    count = 0
    for pair in second_to_first_mappings:
        variations = mapping_variation_pairs(pair)
        for variation in variations:
            reg_expr = re.compile(variation[0] + '(?=([^"]*"[^"]*")*[^"]*$)')
            matches = re.findall(reg_expr, text)
            count += len(matches)

    if count > 3:
        return True
    else:
        return False


def capitalize(word):
    return word[0].upper() + word[1:]


def mapping_variation_pairs(mapping):
    mapping_list = []
    mapping_list.append((" " + mapping[0] + " ", " " + mapping[1] + " "))
    mapping_list.append(
        (" " + capitalize(mapping[0]) + " ", " " + capitalize(mapping[1]) + " ")
    )

    # Change you it's before a punctuation
    if mapping[0] is "you":
        mapping = ("you", "me")
    mapping_list.append((" " + mapping[0] + ",", " " + mapping[1] + ","))
    mapping_list.append((" " + mapping[0] + "\\?", " " + mapping[1] + "\\?"))
    mapping_list.append((" " + mapping[0] + "\\!", " " + mapping[1] + "\\!"))
    mapping_list.append((" " + mapping[0] + "\\.", " " + mapping[1] + "."))

    return mapping_list


first_to_second_mappings = [
    ("I'm", "you're"),
    ("Im", "you're"),
    ("Ive", "you've"),
    ("I am", "you are"),
    ("was I", "were you"),
    ("am I", "are you"),
    ("wasn't I", "weren't you"),
    ("I", "you"),
    ("I'd", "you'd"),
    ("i", "you"),
    ("I've", "you've"),
    ("was I", "were you"),
    ("am I", "are you"),
    ("wasn't I", "weren't you"),
    ("I", "you"),
    ("I'd", "you'd"),
    ("i", "you"),
    ("I've", "you've"),
    ("I was", "you were"),
    ("my", "your"),
    ("we", "you"),
    ("we're", "you're"),
    ("mine", "yours"),
    ("me", "you"),
    ("us", "you"),
    ("our", "your"),
    ("I'll", "you'll"),
    ("myself", "yourself"),
]

second_to_first_mappings = [
    ("you're", "I'm"),
    ("your", "my"),
    ("you are", "I am"),
    ("you were", "I was"),
    ("are you", "am I"),
    ("you", "I"),
    ("you", "me"),
    ("you'll", "I'll"),
    ("yourself", "myself"),
    ("you've", "I've"),
]


def capitalize_helper(string):
    string_list = list(string)
    string_list[0] = string_list[0].upper()
    return "".join(string_list)


def capitalize_first_letters(text):
    first_letters_regex = re.compile(r"((?<=[\.\?!]\s)(\w+)|(^\w+))")

    def cap(match):
        return capitalize_helper(match.group())

    result = first_letters_regex.sub(cap, text)
    return result


def standardize_punctuation(text):
    text = text.replace("’", "'")
    text = text.replace("`", "'")
    text = text.replace("“", '"')
    text = text.replace("”", '"')
    return text


def first_to_second_person(text):
    text = " " + text
    text = standardize_punctuation(text)
    for pair in first_to_second_mappings:
        variations = mapping_variation_pairs(pair)
        for variation in variations:
            text = replace_outside_quotes(text, variation[0], variation[1])

    return capitalize_first_letters(text[1:])


def second_to_first_person(text):
    text = " " + text
    text = standardize_punctuation(text)
    for pair in second_to_first_mappings:
        variations = mapping_variation_pairs(pair)
        for variation in variations:
            text = replace_outside_quotes(text, variation[0], variation[1])

    return capitalize_first_letters(text[1:])


def string_to_sentence_list(text):
    text = "    " + text + "     "
    text = text.replace("\n", "<stop><break><stop>")
    text = re.sub(r"(Mr|St|Mrs|Ms|Dr|Prof|Capt|Cpt|Lt|Mt)(\.)", r"\1<prd>", text)
    text = re.sub(r"(Inc|Ltd|Jr|Sr|Co)(\.)([\s\"\',])*(?=[a-z])", r"\1<prd>\2", text)
    text = re.sub(r"(\s)([A-Za-z])(\.)", r"\1\2<prd>", text)
    text = re.sub(r"([A-Za-z0-9])(\.)(?![\s\"\'\.])", r"\1<prd>", text)
    text = re.sub(r"<prd>([A-Za-z])(\.)([\s\"\',])*(?=[a-z])", r"<prd>\1<prd>\3", text)
    text = re.sub(r"([\.!\?])([\"\'])([\.,])?", r"\1\2\3<stop>", text)
    text = re.sub(r"([\.!\?])([^\"\'\.!\?])", r"\1<stop>\2", text)
    text = text.replace("<prd>",".")
    text = re.sub(r"(<stop>)(\s)*(<stop>)*(\s)*(<stop>)*","<stop>",text)
    sentences = text.split("<stop>")
    if sentences[-1] == "":
        del sentences[-1]
    sentences = [s.strip() for s in sentences]
    return sentences


def string_edit(text):
    text = text.strip()
    sentences = string_to_sentence_list(text)
    new_sentences = []
    for i in range(len(sentences) - 1):
        if len(sentences[i]) + len(sentences[i+1]) < 40 and sentences[i] != "<break>" and sentences[i+1] != "<break>":
            merged_sentence = sentences[i] + " " + sentences[i+1]
            print(merged_sentence)
            new_sentences.append(merged_sentence)
            sentences[i+1] = ""
        else:
            if sentences[i] != "":
                new_sentences.append(sentences[i])
    if sentences[-1] != "":
        new_sentences.append(sentences[-1])
    sentences = new_sentences
    sentence_choices = []
    for i in sentences:
        if i != "<break>":
            sentence_choices.append(i)

    console_print(text)
    if len(sentence_choices) == 0:
        console_print("No text to edit. Would you like to write something?\n0) Write new text\n1) Cancel\n")
        choice = get_num_options(2)
        if choice == 0:
            choice = 3
        else:
            choice = 4
    else:
        console_print("\n0) Edit a sentence\n1) Remove a sentence\n2) Add a new sentence\n3) Rewrite all\n4) Cancel\n")
        choice = get_num_options(5)

    if choice == 0:
        console_print("Pick a sentence to edit:\n")
        for i in range(len(sentence_choices)):
            console_print(str(i) + ") " + sentence_choices[i])
        console_print(str(len(sentence_choices)) + ") Cancel")
        choice = get_num_options(len(sentence_choices) + 1)
        while choice != len(sentence_choices):
            console_print("\n" + sentence_choices[choice])
            new_sentence = input("\nWrite the new sentence:\n")
            new_sentence = new_sentence.strip()
            new_sentence = new_sentence.replace("  ", " ")
            if new_sentence != "":
                if new_sentence[-1] not in [".", "!", "?", ",", "\"", "\'"]:
                    new_sentence += "."
                sentence_choices[choice] = new_sentence
            for i in range(len(sentence_choices)):
                console_print(str(i) + ") " + sentence_choices[i])
            console_print(str(len(sentence_choices)) + ") Cancel")
            choice = get_num_options(len(sentence_choices) + 1)
    elif choice == 1:
        console_print("Pick a sentence to remove:\n")
        for i in range(len(sentence_choices)):
            console_print(str(i) + ") " + sentence_choices[i])
        console_print(str(len(sentence_choices)) + ") Cancel")
        choice = get_num_options(len(sentence_choices) + 1)
        while choice != len(sentence_choices):
            sentence_choices[choice] = ""
            console_print("\n")
            for i in range(len(sentence_choices)):
                if sentence_choices[i] != "":
                    console_print(str(i) + ") " + sentence_choices[i])
            console_print(str(len(sentence_choices)) + ") Cancel")
            choice = get_num_options(len(sentence_choices) + 1)
    elif choice == 2:
        new_sentence = input("Write a new sentence:\n")
        new_sentence = new_sentence.strip()
        new_sentence = new_sentence.replace("  ", " ")
        if new_sentence != "":
            if new_sentence[-1] not in [".", "!", "?", ",", "\"", "\'"]:
                new_sentence += "."
            sentences.append("")
            sentence_choices.append(new_sentence)
    elif choice == 3:
        new_text = (input("Enter the new text (use \\n for new line):\n"))
        new_text = new_text.replace("  ", " ")
        new_text = new_text.replace("\\n", "\n")
        return new_text
    else:
        console_print("Cancelled.\n")
        return
    new_text = ""
    for i in range(len(sentences)):
        if sentences[i] == "<break>":
            new_text = new_text + "\n"
        else:
            new_text = new_text + sentence_choices[i - (sentences[0:i].count("<break>"))] + " "
    new_text = new_text.strip()
    return new_text
