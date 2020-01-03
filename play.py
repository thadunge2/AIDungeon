#!/usr/bin/env python3
import os
import random
import sys
import time

from generator.gpt2.gpt2_generator import *
from story import grammars
from story.story_manager import *
from story.utils import *
from playsound import playsound
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import base64
import getpass

from banners.bannerRan import *

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"


def splash():
    print("0) New Game\n1) Load Game\n")
    choice = get_num_options(2)

    if choice == 1:
        return "load"
    else:
        return "new"


def salt_password(password, old_salt = None):
    password = password.encode()
    salt = old_salt if old_salt is not None else os.urandom(32)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(password)), salt


def random_story(story_data):
    # random setting
    # settings = list(story_data["settings"])
    # n_settings = len(settings)
    # rand_n = random.randint(0, n_settings - 1)
    # setting_key = settings[rand_n]

    # temporarily only available in fantasy
    setting_key = "fantasy"

    # random character
    characters = list(story_data["settings"][setting_key]["characters"])
    n_characters = len(characters)
    rand_n = random.randint(0, n_characters - 1)
    character_key = characters[rand_n]

    # random name
    name = grammars.direct(setting_key, "fantasy_name")

    return setting_key, character_key, name


def select_game():
    with open(YAML_FILE, "r") as stream:
        data = yaml.safe_load(stream)

    # Random story?
    print("Random story?")
    console_print("0) yes")
    console_print("1) no")
    choice = get_num_options(2)

    if choice == 0:
        setting_key, character_key, name = random_story(data)
    else:
        # User-selected story...
        print("\n\nPick a setting.")
        settings = data["settings"].keys()
        for i, setting in enumerate(settings):
            print_str = str(i) + ") " + setting
            if setting == "fantasy":
                print_str += " (recommended)"

            console_print(print_str)
        console_print(str(len(settings)) + ") custom")
        choice = get_num_options(len(settings) + 1)

        if choice == len(settings):
            context, prompt = get_custom_prompt()
            return True, None, None, None, context, prompt

        setting_key = list(settings)[choice]

        print("\nPick a character")
        characters = data["settings"][setting_key]["characters"]
        for i, character in enumerate(characters):
            console_print(str(i) + ") " + character)
        character_key = list(characters)[get_num_options(len(characters))]

        name = input("\nWhat is your name? ")

    setting_description = data["settings"][setting_key]["description"]
    character = data["settings"][setting_key]["characters"][character_key]

    return False, setting_key, character_key, name, character, setting_description


def get_custom_prompt():
    console_print(
        "\n(optional, can be left blank) Enter a prompt that describes who you are and what are your goals. The AI will "
        "always remember this prompt and will use it for context, ex:\n 'Your name is John Doe. You are a knight in "
        "the kingdom of Larion. You were sent by the king to track down and slay an evil dragon.'\n"
    )
    context = input("Story Context: ")
    if len(context) > 0 and not context.endswith(" "):
        context = context + " "
    console_print(
        "\nNow enter a prompt that describes the start of your story. This comes after the Story Context and will give the AI "
        "a starting point for the story. Unlike the context, the AI will eventually forget this prompt, ex:\n 'You enter the forest searching for the dragon and see' "
    )
    prompt = input("Starting Prompt: ")
    return context, prompt


def get_curated_exposition(
    setting_key, character_key, name, character, setting_description
):
    name_token = "<NAME>"
    if (
        character_key == "noble"
        or character_key == "knight"
        or character_key == "wizard"
        or character_key == "peasant"
        or character_key == "rogue"
    ):
        context = grammars.generate(setting_key, character_key, "context") + "\n\n"
        context = context.replace(name_token, name)
        prompt = grammars.generate(setting_key, character_key, "prompt")
        prompt = prompt.replace(name_token, name)
    else:
        context = (
            "You are "
            + name
            + ", a "
            + character_key
            + " "
            + setting_description
            + "You have a "
            + character["item1"]
            + " and a "
            + character["item2"]
            + ". "
        )
        prompt_num = np.random.randint(0, len(character["prompts"]))
        prompt = character["prompts"][prompt_num]

    return context, prompt


def instructions():
    text = "\nAI Dungeon 2 Instructions:"
    text += '\n Enter actions starting with a verb ex. "go to the tavern" or "attack the orc"'
    text += '\n'
    text += '\n To speak enter \'say "(thing you want to say)"\''
    text += '\n or just "(thing you want to say)"'
    text += '\n'
    text += '\n If you want something to happen or be done by someone else, enter '
    text += '\n \'!(thing you want to happen.\\n other thing on a new line.)'
    text += '\n ex. "!A dragon swoops down and eats Sir Theo."'
    text += '\n'
    text += "\nThe following commands can be entered for any action: "
    text += '\n  "/revert"         Reverts the last action allowing you to pick a different'
    text += '\n                    action.'
    text += '\n  "/retry"          Reverts the last action and tries again with the same action.'
    text += '\n  "/alter"          Edit the most recent AI response'
    text += '\n  "/quit"           Quits the game and saves'
    text += '\n  "/reset"          Starts a new game and saves your current one'
    text += '\n  "/restart"        Starts the game from beginning with same settings'
    text += '\n  "/cloud off/on"   Turns off and on cloud saving when you use the "save" command'
    text += '\n  "/saving off/on"  Turns off and on saving'
    text += '\n  "/encrypt"        Turns on encryption when saving and loading'
    text += '\n  "/autosave"       Toggle autosave on and off. Default is off.'
    text += '\n  "/save [name]"    Save your current game or create a new save if name was supplied'
    text += '\n  "/load"           Asks for a save ID and loads the game if the ID is valid'
    text += '\n  "/print"          Prints a transcript of your adventure'
    text += '\n  "/help"           Prints these instructions again'
    text += '\n  "/showstats"      Prints the current game settings'
    text += '\n  "/censor off/on"  Turn censoring off or on.'
    text += '\n  "/ping off/on"    Turn playing a ping sound when the AI responds off or on.'
    text += '\n                    (not compatible with Colab)'
    text += '\n  "/infto ##"       Set a timeout for the AI to respond.'
    text += '\n  "/temp #.#"       Changes the AI\'s temperature'
    text += '\n                    (higher temperature = less focused). Default is 0.4.'
    text += '\n  "/top ##"         Changes the AI\'s top_p. Default is 0.9.'
    text += '\n  "/raw off/on"     Changes whether to feed the AI raw text instead of CYOA, interprets \\n as newline. (default off).'
    text += '\n  "/remember XXX"   Commit something important to the AI\'s memory for that session.'
    text += '\n  "/context"        Edit what your AI has currently committed to memory.'
    return text


def play_aidungeon_2():
    console_print(
        "AI Dungeon 2 will save and use your actions and game to continually improve AI Dungeon."
        + " If you would like to disable this enter '/saving off' as an action. This will also turn off the "
        + "ability to save games."
    )

    upload_story = True
    ping = False
    generator = None
    autosave = False
    story_manager = UnconstrainedStoryManager(generator, upload_story=upload_story, cloud=False)
    print("\n")

    ranBanner =  bannerRan()
    openingPass = (ranBanner.banner_number)

    with open(openingPass, "r", encoding="utf-8") as file:
        starter = file.read()
    print(starter)

    while True:
        if story_manager.story is not None:
            story_manager.story = None

        while story_manager.story is None:
            print("\n\n")
            splash_choice = splash()

            if splash_choice == "new":
                print("\n\n")
                is_custom, setting_key, character_key, name, character, setting_description = select_game()
                if is_custom:
                    context, prompt = character, setting_description
                else:
                    context, prompt = get_curated_exposition(setting_key, character_key, name, character, setting_description)
                if generator is None:
                    generator_config = input("Would you like to select a different generator? (default: model_v5) (y/N) ")
                    if generator_config.lower() == "y":
                        try:
                            model_name = input("Model name: ")
                            console_print("Use raw narrative text as input for this model instead of CYOA prompts?")
                            console_print("Example user input in raw mode: He took the beast by the horns and ripped out its eyes.\\n In the distance, a horn sounded.")
                            console_print("Example user input in regular mode: > Take beast by horns and rip out its eyes.")
                            use_raw = input("y/N ")
                            print("\nInitializing AI Dungeon! (This might take a few minutes)\n")
                            generator = GPT2Generator(model_name=model_name, raw=use_raw.lower()=="y")
                        except:
                            console_print("Failed to set model. Make sure it is installed in generator/gpt2/models/")
                            continue
                    else:
                        print("\nInitializing AI Dungeon! (This might take a few minutes)\n")
                        generator = GPT2Generator()
                    story_manager.generator = generator
                change_config = input("Would you like to enter a new temp and top_p now? (default: 0.4, 0.9) (y/N) ")
                if change_config.lower() == "y":
                    story_manager.generator.change_temp(float(input("Enter a new temp (default 0.4): ") or 0.4))
                    story_manager.generator.change_top_p(float(input("Enter a new top_p (default 0.9): ") or 0.9))
                    console_print("Please wait while the AI model is regenerated...")
                    story_manager.generator.gen_output()
                console_print(instructions())
                print("\nGenerating story...")
                story_manager.generator.generate_num = 120
                story_manager.start_new_story(
                    prompt, context=context, upload_story=upload_story
                )
                print("\n")
                console_print(str(story_manager.story))
                story_manager.generator.generate_num = story_manager.generator.default_gen_num

            else:
                load_ID = input("What is the ID of the saved game? (prefix with gs:// if it is a cloud save) ")
                print("\nLoading Game...\n")
                if load_ID.startswith("gs://"):
                    story_manager.cloud = True
                    load_ID = load_ID[5:]
                story_manager.set_encryption(None)
                result = story_manager.load_from_storage(load_ID)
                if result is None:
                    password = getpass.getpass("Enter password (if this is an encrypted save): ")
                    if len(password) > 0:
                        salt = story_manager.load_salt(load_ID)
                        if salt is not None:
                            story_manager.set_encryption(salt_password(password, salt)[0], salt)
                            result = story_manager.load_from_storage(load_ID)
                            if result is not None:
                                print('encryption set (disable with /encrypt)')
                                console_print(result)
                else:
                    console_print(result)

                if story_manager.story is None:
                    console_print("File not found, or invalid password")
                    story_manager.set_encryption(None)

        while True:
            if autosave and upload_story:
                story_manager.save_story()
            sys.stdin.flush()
            action = input("\n> ").strip()
            if len(action) > 0 and action[0] == "/":
                split = action[1:].split(" ")  # removes preceding slash
                command = split[0].lower()
                args = split[1:]
                if command == "reset":
                    story_manager.story.get_rating()
                    story_manager.print_save()
                    break

                elif command == "restart":
                    story_manager.story.actions = []
                    story_manager.story.results = []
                    console_print("Game restarted.")
                    console_print(story_manager.story.story_start)
                    continue

                elif command == "quit":
                    story_manager.story.get_rating()
                    exit()

                elif command == "saving":
                    if len(args) == 0:
                        console_print("Saving is " + ("enabled." if upload_story else "disabled.") + " Use /saving " +
                                      ("off" if upload_story else "on") + " to change.")
                    elif args[0] == "off":
                        upload_story = False
                        story_manager.upload_story = False
                        console_print("Saving turned off.")
                    elif args[0] == "on":
                        upload_story = True
                        story_manager.upload_story = True
                        console_print("Saving turned on.")
                    else:
                        console_print(f"Invalid argument: {args[0]}")

                elif command == "cloud":
                    if len(args) == 0:
                        console_print("Cloud saving is " + ("enabled." if story_manager.cloud else "disabled.") + " Use /cloud " +
                                      ("off" if story_manager.cloud else "on") + " to change.")
                    elif args[0] == "off":
                        story_manager.cloud = False
                        console_print("Cloud saving turned off.")
                    elif args[0] == "on":
                        story_manager.cloud = True
                        console_print("Cloud saving turned on.")
                    else:
                        console_print(f"Invalid argument: {args[0]}")

                elif command == "encrypt":
                    password = getpass.getpass("Enter password (blank to disable encryption): ")
                    if len(password) == 0:
                        story_manager.set_encryption(None)
                        console_print("Encryption disabled.")
                    else:
                        password, salt = salt_password(password)
                        story_manager.set_encryption(password, salt)
                        console_print("Updated password for encryption/decryption.")

                elif command == "autosave":
                    if len(args) == 0:
                        console_print("Autosaving is " + ("enabled." if autosave else "disabled."))
                    elif args[0] == "off":
                        if not autosave:
                            console_print("Autosaving is already disabled.")
                        else:
                            autosave = False
                            console_print("Autosaving is now disabled.")
                    elif args[0] == "on":
                        if autosave:
                            console_print("Autosaving is already enabled.")
                        else:
                            autosave = True
                            console_print("Autosaving is now enabled.")
                    else:
                        console_print(f"Invalid argument: {args[0]}")

                elif command == "help":
                    console_print(instructions())

                elif command == "showstats":
                    text = "saving is set to:      " + str(upload_story)
                    text += "\ncloud saving is set to:" + str(story_manager.cloud)
                    text += "\nencryption is set to:  " + str(story_manager.has_encryption())
                    text += "\nautosaving is set to:  " + str(autosave)
                    text += "\nping is set to:        " + str(ping)
                    text += "\ncensor is set to:      " + str(story_manager.generator.censor)
                    text += "\ntemperature is set to: " + str(story_manager.generator.temp)
                    text += "\ntop_p is set to:       " + str(story_manager.generator.top_p)
                    text += "\ncurrent model is:      " + story_manager.generator.model_name
                    text += "\nraw is set to:         " + str(story_manager.generator.raw)
                    print(text)

                elif command == "censor":
                    if len(args) == 0:
                        if generator.censor:
                            console_print("Censor is enabled.")
                        else:
                            console_print("Censor is disabled.")
                    elif args[0] == "off":
                        if not generator.censor:
                            console_print("Censor is already disabled.")
                        else:
                            generator.censor = False
                            console_print("Censor is now disabled.")

                    elif args[0] == "on":
                        if generator.censor:
                            console_print("Censor is already enabled.")
                        else:
                            generator.censor = True
                            console_print("Censor is now enabled.")
                    else:
                        console_print(f"Invalid argument: {args[0]}")

                elif command == "ping":
                    if len(args) == 0:
                        console_print("Ping is " + ("enabled." if ping else "disabled."))
                    elif args[0] == "off":
                        if not ping:
                            console_print("Ping is already disabled.")
                        else:
                            ping = False
                            console_print("Ping is now disabled.")
                    elif args[0] == "on":
                        if ping:
                            console_print("Ping is already enabled.")
                        else:
                            ping = True
                            console_print("Ping is now enabled.")
                    else:
                        console_print(f"Invalid argument: {args[0]}")

                elif command == "load":
                    if len(args) == 0:
                        load_ID = input("What is the ID of the saved game? (prefix with gs:// if it is a cloud save) ")
                    else:
                        load_ID = args[0]
                    console_print("\nLoading Game...\n")
                    if load_ID.startswith("gs://"):
                        story_manager.cloud = True
                        load_ID = load_ID[5:]
                    result = story_manager.load_from_storage(load_ID)
                    if result is None:
                        salt = story_manager.load_salt(load_ID)
                        if salt is not None:
                            password = getpass.getpass("Enter the password you saved this file with: ")
                            story_manager.set_encryption(salt_password(password, salt)[0], salt)
                            result = story_manager.load_from_storage(load_ID)
                        else:
                            result = story_manager.load_from_storage(load_ID, decrypt=False)

                    if result is None:
                        console_print("File not found, or invalid encryption password set")
                    else:
                        console_print(result)

                elif command == "save":
                    if upload_story:
                        if len(args) == 0:
                            print("Create a new save, or overwrite the current save?")
                            print("0) New save\n1) Overwrite current save\n")
                            choice = get_num_options(2)
                            name = None
                            overwrite = (choice == 1)
                        else:
                            name = args[0]
                            overwrite = False
                        save_id = story_manager.save_story(name, overwrite)
                        console_print("Game saved.")
                        console_print(f"To load the game, type 'load' and enter the following ID: {save_id}")
                    else:
                        console_print("Saving has been turned off. Cannot save.")

                elif command == "print":
                    line_break = input("Format output with extra newline? (y/n)\n> ")
                    print("\nPRINTING\n")
                    if line_break == "y":
                        console_print(str(story_manager.story))
                    else:
                        print(str(story_manager.story))

                elif command == "revert":
                    if len(story_manager.story.actions) == 0:
                        console_print("You can't go back any farther. ")
                        continue

                    story_manager.story.actions = story_manager.story.actions[:-1]
                    story_manager.story.results = story_manager.story.results[:-1]
                    console_print("Last action reverted. ")
                    if len(story_manager.story.results) > 0:
                        console_print(story_manager.story.results[-1])
                    else:
                        console_print(story_manager.story.story_start)
                    continue

                elif command == "infto":

                    if len(args) != 1:
                        console_print("Failed to set timeout. Example usage: /infto 30")
                    else:
                        try:
                            story_manager.inference_timeout = int(args[0])
                            console_print("Set timeout to {}".format(story_manager.inference_timeout))
                        except ValueError:
                            console_print("Failed to set timeout. Example usage: /infto 30")
                            continue

                elif command == "temp":

                    if len(args) != 1:
                        console_print("Failed to set temperature. Example usage: /temp 0.4")
                    else:
                        try:
                            console_print("Regenerating model, please wait...")
                            story_manager.generator.change_temp(float(args[0]))
                            story_manager.generator.gen_output()
                            console_print("Set temp to {}".format(story_manager.generator.temp))
                        except ValueError:
                            console_print("Failed to set temperature. Example usage: /temp 0.4")
                            continue

                elif command == "top":

                    if len(args) != 1:
                        console_print("Failed to set top_p. Example usage: /top 0.9")
                    else:
                        try:
                            console_print("Regenerating model, please wait...")
                            story_manager.generator.change_top_p(float(args[0]))
                            story_manager.generator.gen_output()
                            console_print("Set top_p to {}".format(story_manager.generator.top_p))
                        except ValueError:
                            console_print("Failed to set top_p. Example usage: /top 0.9")
                            continue

                elif command == "raw":
                    if len(args) == 0:
                        console_print("Raw input is " + ("enabled." if story_manager.generator.raw else "disabled."))
                    elif args[0] == "off":
                        if not story_manager.generator.raw:
                            console_print("Raw input is already disabled.")
                        else:
                            story_manager.generator.change_raw(False)
                            console_print("Raw input is now disabled.")
                    elif args[0] == "on":
                        if story_manager.generator.raw:
                            console_print("Raw input is already enabled.")
                        else:
                            story_manager.generator.change_raw(True)
                            console_print("Raw input is now enabled.")
                    else:
                        console_print(f"Invalid argument: {args[0]}")

                elif command == 'remember':
                    if len(args) == 0:
                        console_print("Failed to add to memory. Example usage: /remember that Sir Theo is a knight")
                    else:
                        story_manager.story.context += "You know " + " ".join(args[0:]) + ". "
                        console_print("You make sure to remember {}.".format(" ".join(action.split(" ")[1:])))

                elif command == 'retry':

                    if len(story_manager.story.actions) is 0:
                        console_print("There is nothing to retry.")
                        continue

                    last_action = story_manager.story.actions.pop()
                    last_result = story_manager.story.results.pop()

                    try:
                        try:
                            story_manager.act_with_timeout(last_action)
                            console_print(last_action)
                            console_print(story_manager.story.results[-1])
                        except FunctionTimedOut:
                            console_print("That input caused the model to hang (timeout is {}, use infto ## command to change)".format(story_manager.inference_timeout))
                            if ping:
                                playsound('ping.mp3')
                    except NameError:
                        pass
                    if ping:
                        playsound('ping.mp3')

                    continue

                elif command == 'context':
                    try:
                        current_context = story_manager.get_context()
                        console_print("Current story context: \n")
                        new_context = string_edit(current_context)
                        if new_context is None:
                            pass
                        else:
                            story_manager.set_context(new_context)
                            console_print("Story context updated.\n")
                    except:
                        console_print("Something went wrong, cancelling.")
                        pass

                elif command == 'alter':
                    try:
                        console_print("\nThe AI thinks this was what happened:\n")
                        try:
                            current_result = story_manager.story.results[-1]
                        except IndexError:
                            current_result = story_manager.story.story_start
                        new_result = string_edit(current_result)
                        if new_result is None:
                            pass
                        else:
                            try:
                                story_manager.story.results[-1] = new_result
                            except IndexError:
                                story_manager.story.story_start = new_result
                            console_print("Result updated.\n")
                    except:
                        console_print("Something went wrong, cancelling.")
                        pass

                else:
                    console_print(f"Unknown command: {command}")

            else:
                if not story_manager.generator.raw:
                    if action == "":
                        action = "> "

                    elif action[0] == '!':
                        action = "> \n" + action[1:].replace("\\n", "\n")

                    elif action[0] != '"':
                        action = action.strip()
                        if not action.lower().startswith("you ") and not action.lower().startswith("i "):
                            action = "You " + action

                        action = action[0].lower() + action[1:]

                        if action[-1] not in [".", "?", "!"]:
                            action = action + "."

                        action = "> " + first_to_second_person(action)

                    action = "\n" + action + "\n"

                    if "say" in action or "ask" in action or "\"" in action:
                        story_manager.generator.generate_num = 120
                else:
                    action = action.replace("\\n", "\n")

                try:
                    result = "\n" + story_manager.act_with_timeout(action)
                except FunctionTimedOut:
                    console_print("That input caused the model to hang (timeout is {}, use infto ## command to change)".format(story_manager.inference_timeout))
                    if ping:
                        playsound('ping.mp3')
                    continue
                if len(story_manager.story.results) >= 2:
                    similarity = get_similarity(
                        story_manager.story.results[-1], story_manager.story.results[-2]
                    )
                    if similarity > 0.9:
                        story_manager.story.actions = story_manager.story.actions[:-1]
                        story_manager.story.results = story_manager.story.results[:-1]
                        console_print(
                            "Woops that action caused the model to start looping. Try a different action to prevent that."
                        )
                        if ping:
                            playsound('ping.mp3')
                        continue

                if player_won(result):
                    console_print(result + "\n CONGRATS YOU WIN")
                    console_print("\nOptions:")
                    console_print("0) Start a new game")
                    console_print(
                        "1) \"I'm not done yet!\" (If you didn't actually win) "
                    )
                    console_print("Which do you choose? ")
                    choice = get_num_options(2)
                    if choice == 0:
                        story_manager.story.get_rating()
                        break
                    else:
                        console_print("Sorry about that...where were we?")
                        console_print(result)

                elif player_died(result):
                    console_print(result + "\n YOU DIED. GAME OVER")
                    console_print("\nOptions:")
                    console_print("0) Start a new game")
                    console_print(
                        "1) \"I'm not dead yet!\" (If you didn't actually die) "
                    )
                    console_print("Which do you choose? ")
                    choice = get_num_options(2)
                    if choice == 0:
                        story_manager.story.get_rating()
                        break
                    else:
                        console_print("Sorry about that...where were we?")
                        console_print(result)

                else:
                    console_print(result)
                if ping:
                    playsound('ping.mp3')
                story_manager.generator.generate_num = story_manager.generator.default_gen_num


if __name__ == "__main__":
    play_aidungeon_2()
