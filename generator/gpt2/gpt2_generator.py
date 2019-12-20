import json
import os
import warnings

import numpy as np
import tensorflow as tf
from generator.gpt2.src import encoder, model, sample
from story.utils import *

warnings.filterwarnings("ignore")

tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)


class GPT2Generator:
    def __init__(self, generate_num=80, temperature=0.4, top_p=0.9, censor=False):
        self.generate_num = generate_num
        self.default_gen_num = generate_num
        self.temp = temperature
        #self.top_k = top_k
        self.top_p = top_p
        self.censor = censor

        self.model_name = "model_v5"
        self.model_dir = "generator/gpt2/models"
        self.checkpoint_path = os.path.join(self.model_dir, self.model_name)

        self.batch_size = 1
        self.samples = 1

        models_dir = os.path.expanduser(os.path.expandvars(self.model_dir))
        self.enc = encoder.get_encoder(self.model_name, models_dir)

        config = tf.compat.v1.ConfigProto()
        config.gpu_options.allow_growth = True
        self.sess = tf.compat.v1.Session(config=config)

        self.context = tf.placeholder(tf.int32, [self.batch_size, None])
        # np.random.seed(seed)
        # tf.set_random_seed(seed)
        self.gen_output()

        saver = tf.train.Saver()
        ckpt = tf.train.latest_checkpoint(os.path.join(models_dir, self.model_name))
        saver.restore(self.sess, ckpt)

    def prompt_replace(self, prompt):
        # print("\n\nBEFORE PROMPT_REPLACE:")
        # print(repr(prompt))
        prompt = prompt.replace("#", "")
        prompt = prompt.replace("*", "")
        prompt = prompt.replace("\n\n", "\n")
        prompt = re.sub("(?<=\w)\.\.(?:\s|$)", ".", prompt)
        prompt = prompt.rstrip(" ")
        # prompt = second_to_first_person(prompt)

        # print("\n\nAFTER PROMPT_REPLACE")
        # print(repr(prompt))
        return prompt

    def result_replace(self, result, actions):
        # print("\n\nBEFORE RESULT_REPLACE:")
        # print(repr(result))
        
        result = result.replace('."', '".')
        result = result.replace("#", "")
        result = result.replace("*", "")
        result = result.replace("\n\n", "\n")
        result = re.sub("(?<=\w)\.\.(?:\s|$)", ".", result)
        # result = first_to_second_person(result)
        result = cut_trailing_sentence(result)
        for sentence in actions:
            result = result.replace(sentence.strip()+" ", "")
        if len(result) == 0:
            return ""
        first_letter_capitalized = result[0].isupper()
        if self.censor:
            result = remove_profanity(result)

        if not first_letter_capitalized:
            result = result[0].lower() + result[1:]

        #
        # print("\n\nAFTER RESULT_REPLACE:")
        # print(repr(result))

        return result

    def generate_raw(self, prompt):
        while len(prompt) > 3500:
            prompt = self.cut_down_prompt(prompt)
        context_tokens = self.enc.encode(prompt)
        generated = 0
        for _ in range(self.samples // self.batch_size):
            out = self.sess.run(
                self.output,
                feed_dict={
                    self.context: [context_tokens for _ in range(self.batch_size)]
                },
            )[:, len(context_tokens) :]
            for i in range(self.batch_size):
                generated += 1
                text = self.enc.decode(out[i])
        return text

    def generate(self, prompt, options=None, seed=1, depth=1):

        debug_print = False
        prompt = self.prompt_replace(prompt)
        last_prompt = prompt[prompt.rfind(">")+2:] if prompt.rfind(">") > -1 else prompt

        if debug_print:
            print("******DEBUG******")
            print("Prompt is: ", repr(prompt))

        text = self.generate_raw(prompt)

        if debug_print:
            print("Generated result is: ", repr(text))
            print("******END DEBUG******")

        result = text
        result = self.result_replace(result, re.findall(r".+?(?:\.{1,3}|[!\?]|$)(?!\")", last_prompt))
        if len(result) == 0 and depth < 20:
            return self.generate(self.cut_down_prompt(prompt), depth=depth+1)
        elif result.count(".") < 2 and depth < 20:
            return self.generate(prompt, depth=depth+1)

        return result
        
    def cut_down_prompt(self, prompt):
        split_prompt = prompt.split(">")
        expendable_text = ">".join(split_prompt[2:])
        return split_prompt[0] + (">" + expendable_text if len(expendable_text) > 0 else "")
        
    def gen_output(self):
        models_dir = os.path.expanduser(os.path.expandvars(self.model_dir))
        hparams = model.default_hparams()
        with open(os.path.join(models_dir, self.model_name, "hparams.json")) as f:
            hparams.override_from_dict(json.load(f))
        seed = np.random.randint(0, 100000)
        self.output = sample.sample_sequence(
            hparams=hparams,
            length=self.generate_num,
            context=self.context,
            batch_size=self.batch_size,
            temperature=self.temp,
            #top_k=self.top_k,
            top_p=self.top_p,
        )
        
    def change_temp(self, t):
        changed = t != self.temp
        self.temp = t
        return changed
        
    def change_top_p(self, t):
        changed = t != self.top_p
        self.top_p = t
        return changed
