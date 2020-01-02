import json
import os
import subprocess
import uuid
import copy
from subprocess import Popen

from story.utils import *
import atexit

from cryptography.fernet import Fernet, InvalidToken
from generator.gpt2.gpt2_generator import GPT2Generator
import base64

save_path = "./saves/"


class Story:
    def __init__(
        self, story_start, context="", seed=None, game_state=None
    ):
        self.story_start = story_start
        self.context = context
        self.rating = -1

        # list of actions. First action is the prompt length should always equal that of story blocks
        self.actions = []

        # list of story blocks first story block follows prompt and is intro story
        self.results = []

        # Only needed in constrained/cached version
        self.seed = seed
        self.choices = []
        self.possible_action_results = None
        self.uuid = None

        if game_state is None:
            game_state = dict()
        self.game_state = game_state
        self.memory = 20

    def init_from_dict(self, story_dict):
        self.story_start = story_dict["story_start"]
        self.seed = story_dict["seed"]
        self.actions = story_dict["actions"]
        self.results = story_dict["results"]
        self.choices = story_dict["choices"]
        self.possible_action_results = story_dict["possible_action_results"]
        self.game_state = story_dict["game_state"]
        self.context = story_dict["context"]
        self.uuid = story_dict["uuid"]

        if "rating" in story_dict.keys():
            self.rating = story_dict["rating"]
        else:
            self.rating = -1

    def initialize_from_json(self, json_string):
        story_dict = json.loads(json_string)
        self.init_from_dict(story_dict)

    def add_to_story(self, action, story_block):
        self.actions.append(action)
        self.results.append(story_block)

    def latest_result(self):
        mem_ind = self.memory
        if len(self.results) < 5:
            latest_result = self.story_start
        else:
            latest_result = self.context
        while mem_ind > 0:

            if len(self.results) >= mem_ind:
                latest_result += self.actions[-mem_ind] + self.results[-mem_ind]

            mem_ind -= 1
        return latest_result

    def __str__(self):
        story_list = [self.story_start]
        for i in range(len(self.results)):
            story_list.append("\n" + self.actions[i])
            story_list.append("\n" + self.results[i])

        return "".join(story_list)

    def to_dict(self):
        story_dict = {}
        story_dict["story_start"] = self.story_start
        story_dict["seed"] = self.seed
        story_dict["actions"] = self.actions
        story_dict["results"] = self.results
        story_dict["choices"] = self.choices
        story_dict["possible_action_results"] = self.possible_action_results
        story_dict["game_state"] = self.game_state
        story_dict["context"] = self.context
        story_dict["uuid"] = self.uuid
        story_dict["rating"] = self.rating
        return story_dict

    def to_json(self):
        return json.dumps(self.to_dict())

    def get_rating(self):
        while True:
            try:
                rating = input("Please rate the story quality from 1-10: ")
                rating_float = max(min(float(rating), 10), 1)
            except ValueError:
                print("Please return a valid number.")
            else:
                self.rating = rating_float
                return


class StoryManager:
    def __init__(self, generator, upload_story=True, cloud=False):
        self.generator = generator
        self.story = None
        self.inference_timeout = 120
        self.cloud = cloud
        self.upload_story = upload_story
        self.encryptor = None
        self.salt = None
        atexit.register(self.print_save)

    def start_new_story(
        self, story_prompt, context="", game_state=None, upload_story=False
    ):
        self.upload_story = upload_story
        block = self.generator.generate(context + story_prompt)
        block = cut_trailing_sentence(block)
        self.story = Story(
            context + story_prompt + block,
            context=context,
            game_state=game_state
        )
        return str(self.story)

    def load_story(self, story, from_json=False):
        if from_json:
            self.story = Story("")
            self.story.initialize_from_json(story)
        else:
            self.story = story
        return str(story)

    def load_salt(self, story_id):
        file_name = "story" + story_id + ".bin"
        exists = os.path.isfile(os.path.join(save_path, file_name))
        if exists:
            with open(os.path.join(save_path, file_name), "rb") as fp:
                story_encrypted = fp.read()
                return base64.urlsafe_b64decode(story_encrypted[:44])
        return None

    def load_from_storage(self, story_id, decrypt=True):
        if not os.path.exists(save_path):
            return None

        decrypt = decrypt and self.encryptor is not None

        file_name = "story" + story_id + (".bin" if decrypt else ".json")
        if self.cloud:
            cmd = "gsutil cp gs://aidungeonstories/" + file_name + " " + save_path
            os.system(cmd)

        exists = os.path.isfile(os.path.join(save_path, file_name))
        if exists:
            if decrypt:
                with open(os.path.join(save_path, file_name), "rb") as fp:
                    story_encrypted = fp.read()
                    try:
                        story_decrypted = self.encryptor.decrypt(story_encrypted[44:])
                    except InvalidToken:
                        return None
                    game = json.loads(story_decrypted.decode())
            else:
                with open(os.path.join(save_path, file_name), "r") as fp:
                    game = json.load(fp)
            self.story = Story("")
            self.story.init_from_dict(game)
            changed = False
            if "model" in game.keys():
                if self.generator is not None:
                    if self.generator.model_name != game["model"]:
                        console_print("Warning: Save was generated using the model " + game["model"] + "; load this save in a new session to use this model.")
                else:
                    console_print("Generating model (This might take a few minutes)")
                    try:
                        self.generator = GPT2Generator(model_name=game["model"])
                    except:
                        console_print("Warning: The model used by the save (" + game["model"] + ") is not installed. Using the default.")
                        self.generator = GPT2Generator()
            else:
                if self.generator is None:
                    self.generator = GPT2Generator()
            if "top_p" in game.keys():
                changed = changed or self.generator.change_top_p(game["top_p"])
            if "temp" in game.keys():
                changed = changed or self.generator.change_temp(game["temp"])
            if "raw" in game.keys():
                self.generator.change_raw(game["raw"])
            if changed:
                console_print("Please wait while the AI model is regenerated...")
                self.generator.gen_output()
            return str(self.story)
        else:
            return None

    def save_story(self, name=None, overwrite=True):
        if self.story.uuid is None:
            self.story.uuid = str(uuid.uuid1())

        if name:
            story_id = name
            overwrite = False
        else:
            story_id = self.story.uuid if overwrite else str(uuid.uuid1())

        saved_story = self.story if overwrite else copy.copy(self.story)
        saved_story.uuid = story_id
        story_dict = saved_story.to_dict()
        story_dict["top_p"] = self.generator.top_p
        story_dict["temp"] = self.generator.temp
        story_dict["raw"] = self.generator.raw
        story_dict["model"] = self.generator.model_name

        if not os.path.exists(save_path):
            os.makedirs(save_path)

        story_json = json.dumps(story_dict)
        if self.encryptor is not None:
            story_encoded = story_json.encode()
            story_encrypted = self.encryptor.encrypt(story_encoded)
            file_name = "story" + str(story_id) + ".bin"
            with open(os.path.join(save_path, file_name), "wb") as sf:
                sf.write(base64.urlsafe_b64encode(self.salt) + story_encrypted)
        else:
            file_name = "story" + str(story_id) + ".json"
            with open(os.path.join(save_path, file_name), "w") as sf:
                sf.write(story_json)

        FNULL = open(os.devnull, "w")
        if self.cloud:
            p = Popen(
                ["gsutil", "cp", os.path.join(save_path, file_name), "gs://aidungeonstories"],
                stdout=FNULL,
                stderr=subprocess.STDOUT,
            )
        return story_id

    def set_encryption(self, key, salt=""):
        if key is None:
            self.encryptor = None
            self.salt = None
        else:
            self.encryptor = Fernet(key)
            self.salt = salt

    def has_encryption(self):
        return self.encryptor is not None

    def print_save(self):
        if self.upload_story:
            story_id = self.save_story()
            console_print("Game saved.")
            console_print(
                "To load the game, type 'load' and enter the following ID: " + story_id
            )

    def json_story(self):
        return self.story.to_json()

    def story_context(self):
        return self.story.latest_result()


class UnconstrainedStoryManager(StoryManager):
    def act(self, action_choice):
        if self.generator.raw:
            if len(action_choice) > 0:
                if not action_choice[-1].isspace():
                    action_choice = action_choice + " "
                if not action_choice[0].isspace():
                    action_choice = " " + action_choice
            else:
                action_choice = " "
        result = self.generate_result(action_choice)
        self.story.add_to_story(action_choice, result)
        return result

    def act_with_timeout(self, action_choice):
        return func_timeout(self.inference_timeout, self.act, (action_choice,))

    def generate_result(self, action):
        block = self.generator.generate(self.story_context() + action)
        return block

    def set_context(self, context):
        self.story.context = context
    def get_context(self):
        return self.story.context
