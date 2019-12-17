#!/usr/bin/env python3
import os
import sys
import random
import time

from generator.gpt2.gpt2_generator import *
from story import grammars
from story.story_manager import *
from story.utils import *
from playsound import playsound

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"


def splash():
    print("0) New Game\n1) Load Game\n")
    choice = get_num_options(2)

    if choice == 1:
        return "load"
    else:
        return "new"


def random_story(story_data):
    # random setting
    settings = story_data["settings"].keys()
    n_settings = len(settings)
    rand_n = random.randint(0, n_settings - 1)
    for i, setting in enumerate(settings):
        if i == rand_n:
            setting_key = setting

    # temporarily only available in fantasy
    setting_key = "fantasy"

    # random character
    characters = story_data["settings"][setting_key]["characters"]
    n_characters = len(characters)
    rand_n = random.randint(0, n_characters - 1)
    for i, character in enumerate(characters):
        if i == rand_n:
            character_key = character

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

            context = ""
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


def get_curated_exposition(setting_key, character_key, name, character, setting_description):
    name_token = "<NAME>"
    if (
        character_key == "noble"
        or character_key == "knight"
        or character_key == "wizard"
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
    text += '\n \'!(thing you want to happen)'
    text += '\n ex. "!A dragon swoops down and eats Sir Theo."'
    text += '\n'
    text += "\nThe following commands can be entered for any action: "
    text += '\n  "/revert"         Reverts the last action allowing you to pick a different'
    text += '\n                    action.'
    text += '\n  "/retry"          Reverts the last action and tries again with the same action.'
    text += '\n  "/alter"          Edit the most recent AI response'
    text += '\n  "/quit"           Quits the game and saves'
    text += '\n  "/restart"        Starts a new game and saves your current one'
    text += '\n  "/cloud"          Turns on cloud saving when you use the "save" command'
    text += '\n  "/save"           Makes a new save of your game and gives you the save ID'
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
    text += '\n  "/remember XXX"   Commit something important to the AI\'s memory for that session.'
    text += '\n  "/context"        Rewrites everything your AI has currently committed to memory.'
    text += '\n  "/editcontext     Lets you rewrite specific parts of the context.'
    return text


def play_aidungeon_2():

    console_print(
        "AI Dungeon 2 will save and use your actions and game to continually improve AI Dungeon."
        + " If you would like to disable this enter '/nosaving' as an action. This will also turn off the "
        + "ability to save games."
    )

    upload_story = True
    ping = False

    print("\nInitializing AI Dungeon! (This might take a few minutes)\n")
    generator = GPT2Generator()
    story_manager = UnconstrainedStoryManager(generator)
    print("\n")

    with open("opening.txt", "r", encoding="utf-8") as file:
        starter = file.read()
    print(starter)

    while True:
        if story_manager.story != None:
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
                if load_ID.startswith("gs://"):
                    result = story_manager.load_new_story(load_ID[5:], upload_story=upload_story, cloud=True)
                    story_manager.story.cloud = True
                else:
                    result = story_manager.load_new_story(load_ID, upload_story=upload_story)
                print("\nLoading Game...\n")
                print(result)

        while True:
            sys.stdin.flush()
            action = input("> ").strip()
            if len(action) > 0 and action[0] == "/":
                split = action[1:].split(" ")  # removes preceding slash
                command = split[0].lower()
                args = split[1:]
                if command == "restart":
                    while True:
                        try:
                            rating = input("Please rate the story quality from 1-10: ")
                            rating_float = max(min(float(rating), 10), 1)
                        except ValueError:
                            print("Please return a valid number.")
                        else:
                            story_manager.story.rating = rating_float
                            break
                    break

                elif command == "quit":
                    while True:
                        try:
                            rating = input("Please rate the story quality from 1-10: ")
                            rating_float = max(min(float(rating), 10), 1)
                        except ValueError:
                            print("Please return a valid number.")
                        else:
                            story_manager.story.rating = rating_float
                            break
                    exit()

                elif command == "nosaving":
                    upload_story = False
                    story_manager.story.upload_story = False
                    console_print("Saving turned off.")

                elif command == "cloud":
                    story_manager.story.cloud = True
                    console_print("Cloud saving turned on.")

                elif command == "help":
                    console_print(instructions())

                elif command == "showstats":
                    text =    "nosaving is set to:    " + str(not upload_story) 
                    text += "\nping is set to:        " + str(ping) 
                    text += "\ncensor is set to:      " + str(generator.censor) 
                    text += "\ntemperature is set to: " + str(story_manager.generator.temp) 
                    text += "\ntop_p is set to:       " + str(story_manager.generator.top_p) 
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
                    if args[0] == "off":
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
                    if load_ID.startswith("gs://"):
                        story_manager.story.cloud = True
                        result = story_manager.story.load_from_storage(load_ID[5:])
                    else:
                        result = story_manager.story.load_from_storage(load_ID)
                    console_print("\nLoading Game...\n")
                    console_print(result)

                elif command == "save":
                    if upload_story:
                        id = story_manager.story.save_to_storage()
                        console_print("Game saved.")
                        console_print(f"To load the game, type 'load' and enter the following ID: {id}")
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

                elif command == "alter": 
                    if len(story_manager.story.results) is 0: 
                        console_print("There's no results to alter.\n") 
                        continue 
     
                    console_print("\nThe AI thinks this was what happened:\n") 
                    print(story_manager.story.results[-1]) 
                    result = input("\nWhat actually happened was (use \\n for new line):\n\n") 
                    result = result.replace("\\n", "\n") 
                    story_manager.story.results[-1] = result 

                elif command == "infto":

                    if len(args) != 1:
                        console_print("Failed to set timeout. Example usage: infto 30")
                    else:
                        try:
                            story_manager.inference_timeout = int(args[0])
                            console_print("Set timeout to {}".format(story_manager.inference_timeout))
                        except:
                            console_print("Failed to set timeout. Example usage: infto 30")
                            continue
                    
                elif command == "temp":
                
                    if len(args) != 1:
                        console_print("Failed to set temperature. Example usage: temp 0.4")
                    else:
                        try:
                            console_print("Regenerating model, please wait...")
                            story_manager.generator.change_temp(float(args[0]))
                            story_manager.generator.gen_output()
                            console_print("Set temp to {}".format(story_manager.generator.temp))
                        except:
                            console_print("Failed to set temperature. Example usage: temp 0.4")
                            continue
                
                elif command == "top":
                
                    if len(args) != 1:
                        console_print("Failed to set top_p. Example usage: top 0.9")
                    else:
                        try:
                            console_print("Regenerating model, please wait...")
                            story_manager.generator.change_top_p(float(args[0]))
                            story_manager.generator.gen_output()
                            console_print("Set top_p to {}".format(story_manager.generator.top_p))
                        except:
                            console_print("Failed to set top_p. Example usage: top 0.9")
                            continue
                
                elif command == 'remember':

                    try:
                        story_manager.story.context += "You know " + " ".join(args[0:]) + ". "
                        console_print("You make sure to remember {}.".format(" ".join(action.split(" ")[1:])))
                    except:
                        console_print("Failed to add to memory. Example usage: remember that Sir Theo is a knight")
                    
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

                elif command == "context":
                    console_print("Current story context: \n" + story_manager.get_context() + "\n")
                    new_context = input("Enter a new context describing the general status of your character and story: ")
                    story_manager.set_context(new_context)
                    console_print("Story context updated.\n")

                elif command == 'editcontext':
                    try:
                        current_context = story_manager.get_context()
                        current_context = current_context.strip()
                        context_list = current_context.split(".")

                        if context_list[-1] == "":
                            del context_list[-1]

                        for i in range(len(context_list)):
                            context_list[i] = context_list[i].strip()

                        console_print("Current story context:\n" + current_context + "\n")
                        console_print("0) Remove a sentence\n1) Edit a sentence\n2) Add a new sentence\n3) Cancel\n")
                        choice = get_num_options(4)

                        if choice == 0:
                            console_print("Pick a sentence to remove:\n")
                            for i in range(len(context_list)):
                                console_print(str(i) + ") " + context_list[i])
                            choice = get_num_options(len(context_list))
                            del context_list[choice]
                        elif choice == 1:
                            console_print("Pick a sentence to edit:\n")
                            for i in range(len(context_list)):
                                console_print(str(i) + ") " + context_list[i])
                            choice = get_num_options(len(context_list))
                            console_print(context_list[choice])
                            context_list[choice] = input("\nWrite the new sentence:\n")
                        elif choice == 2:
                            context_list.append(input("Write a new sentence:\n"))
                        else:
                            console_print("Cancelled.\n")
                            continue

                        current_context = ""
                        for i in range(len(context_list)):
                            if context_list[i] == "":
                                continue
                            if context_list[i][-1] == ".":
                                context_list[i] = context_list[i] + " "
                            elif context_list[i][-1] != " ":
                                context_list[i] = context_list[i] + ". "
                            current_context = current_context + context_list[i]
                        current_context = current_context.strip()
                        story_manager.set_context(current_context)
                        console_print("Story context updated.\n")

                    except:
                        console_print("Something went wrong, cancelling.")
                        pass

                else:
                    console_print(f"Unknown command: {command}")

            else:
                if action == "":
                    action = "\n> \n"
                    
                elif action[0] == '!':
                    action = "\n> \n" + action[1:].replace("\\n", "\n") + "\n"

                elif action[0] != '"':
                    action = action.strip()
                    if not action.lower().startswith("you ") and not action.lower().startswith("i "):
                        action = "You " + action
                        
                    action = action[0].lower() + action[1:]

                    if action[-1] not in [".", "?", "!"]:
                        action = action + "."

                    action = first_to_second_person(action)

                    action = "\n> " + action + "\n"

                if "say" in action or "ask" in action or "\"" in action:
                    story_manager.generator.generate_num = 120
                    
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
                    break
                elif player_died(result):
                    console_print(result)
                    console_print("YOU DIED. GAME OVER")
                    console_print("\nOptions:")
                    console_print("0) Start a new game")
                    console_print(
                        "1) \"I'm not dead yet!\" (If you didn't actually die) "
                    )
                    console_print("Which do you choose? ")
                    choice = get_num_options(2)
                    if choice == 0:
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
