import json
import os
import warnings
import time

import torch
import numpy as np
from transformers import GPT2LMHeadModel, GPT2Tokenizer
from story.utils import *

warnings.filterwarnings("ignore")

class GPT2Generator:
    def __init__(self, generate_num=80, temperature=0.4, top_p=0.9, censor=False, no_cuda=False):
        self.generate_num = generate_num
        self.default_gen_num = generate_num
        self.temp = temperature
        self.top_p = top_p
        self.censor = censor
        self.no_cuda = no_cuda

        self.model_name = os.path.join("model_v5","pytorch-convert")
        self.model_dir = os.path.join("generator","gpt2","models")
        self.checkpoint_path = os.path.join(self.model_dir, self.model_name)
        
        self.seed = int(round(time.time()))
        self.initialize_seed()
        self.tokenizer = GPT2Tokenizer.from_pretrained("gpt2-xl")
        self.model = GPT2LMHeadModel.from_pretrained(self.checkpoint_path)
        self.model.to(torch.device("cuda" if torch.cuda.is_available() and not self.no_cuda else "cpu"))

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
        print("Prompt: {}".format(prompt))
        cursor = len(prompt)
        context_tokens = self.tokenizer.encode(prompt, add_special_tokens=False, return_tensors='pt')
        new_prompt = self.model.generate(input_ids = context_tokens,
                                        max_length = cursor + self.generate_num,
                                        temperature = self.temp,
                                        top_p = self.top_p,
                                        do_sample = True,
                                        repetition_penalty = 1.15)[0].tolist()
        return self.tokenizer.decode(new_prompt).rstrip()[cursor:]

    def generate(self, prompt, options=None, seed=1, depth=1):

        debug_print = True
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
        if len(split_prompt) < 3:
            return prompt
        expendable_text = ">".join(split_prompt[2:])
        return split_prompt[0] + (">" + expendable_text if len(expendable_text) > 0 else "")
        
    def change_temp(self, t):
        changed = t != self.temp
        self.temp = t
        return changed
        
    def change_top_p(self, t):
        changed = t != self.top_p
        self.top_p = t
        return changed
        
    def initialize_seed(self):
        np.random.seed(self.seed)
        torch.random.manual_seed(self.seed)
        torch.cuda.manual_seed(self.seed)
