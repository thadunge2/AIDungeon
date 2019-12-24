import json
import os
import warnings
import time

import torch
import torch.nn.functional as F
import numpy as np
from transformers import GPT2LMHeadModel, GPT2Tokenizer
import logging
from story.utils import *

warnings.filterwarnings("ignore")
logging.getLogger("transformers.tokenization_utils").setLevel(logging.WARN)
logging.getLogger("transformers.modeling_utils").setLevel(logging.WARN)
logging.getLogger("transformers.configuration_utils").setLevel(logging.WARN)

# This will be in the next transformers release, delete then
def top_k_top_p_filtering(logits, top_k=0, top_p=1.0, filter_value=-float("Inf"), min_tokens_to_keep=1):
    """ Filter a distribution of logits using top-k and/or nucleus (top-p) filtering
        Args:
            logits: logits distribution shape (batch size, vocabulary size)
            if top_k > 0: keep only top k tokens with highest probability (top-k filtering).
            if top_p < 1.0: keep the top tokens with cumulative probability >= top_p (nucleus filtering).
                Nucleus filtering is described in Holtzman et al. (http://arxiv.org/abs/1904.09751)
            Make sure we keep at least min_tokens_to_keep per batch example in the output
        From: https://gist.github.com/thomwolf/1a5a29f6962089e871b94cbd09daf317
    """
    if top_k > 0:
        top_k = min(max(top_k, min_tokens_to_keep), logits.size(-1))  # Safety check
        # Remove all tokens with a probability less than the last token of the top-k
        indices_to_remove = logits < torch.topk(logits, top_k)[0][..., -1, None]
        logits[indices_to_remove] = filter_value

    if top_p < 1.0:
        sorted_logits, sorted_indices = torch.sort(logits, descending=True)
        cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)

        # Remove tokens with cumulative probability above the threshold (token with 0 are kept)
        sorted_indices_to_remove = cumulative_probs > top_p
        if min_tokens_to_keep > 1:
            # Keep at least min_tokens_to_keep (set to min_tokens_to_keep-1 because we add the first one below)
            sorted_indices_to_remove[..., :min_tokens_to_keep] = 0
        # Shift the indices to the right to keep also the first token above the threshold
        sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
        sorted_indices_to_remove[..., 0] = 0

        # scatter sorted tensors to original indexing
        indices_to_remove = sorted_indices_to_remove.scatter(
            dim=1, index=sorted_indices, source=sorted_indices_to_remove
        )
        logits[indices_to_remove] = filter_value
    return logits

class GPT2LMHeadWPastModel(GPT2LMHeadModel):
    def prepare_inputs_for_generation(self, input_ids, past=None, **kwargs):
        return {"input_ids": input_ids, 'past': past}
    
    def _generate_no_beam_search(
        self,
        input_ids,
        cur_len,
        max_length,
        do_sample,
        temperature,
        top_k,
        top_p,
        repetition_penalty,
        pad_token_id,
        eos_token_ids,
        batch_size,
    ):
        """ Generate sequences for each example without beam search (num_beams == 1).
            All returned sequence are generated independantly.
        """
        # current position / max lengths / length of generated sentences / unfinished sentences
        unfinished_sents = input_ids.new(batch_size).fill_(1)

        past = None

        while cur_len < max_length:
            if past is not None:
                model_inputs = self.prepare_inputs_for_generation(tokens_to_add.unsqueeze(-1), past=past)
            else:
                model_inputs = self.prepare_inputs_for_generation(input_ids, past=past)
            outputs = self(**model_inputs)
            next_token_logits = outputs[0][:, -1, :]
            past = outputs[1]

            # repetition penalty from CTRL paper (https://arxiv.org/abs/1909.05858)
            if repetition_penalty != 1.0:
                for i in range(batch_size):
                    for previous_tokens in set(input_ids[i].tolist()):
                        next_token_logits[i, previous_tokens] /= repetition_penalty

            if do_sample:
                # Temperature (higher temperature => more likely to sample low probability tokens)
                if temperature > 0 and temperature != 1.0:
                    next_token_logits = next_token_logits / temperature
                # Top-p/top-k filtering
                next_token_logits = top_k_top_p_filtering(next_token_logits, top_k=top_k, top_p=top_p)
                # Sample
                next_token = torch.multinomial(F.softmax(next_token_logits, dim=-1), num_samples=1).squeeze(1)
            else:
                # Greedy decoding
                next_token = torch.argmax(next_token_logits, dim=-1)

            # update generations and finished sentences
            tokens_to_add = next_token * unfinished_sents + pad_token_id * (1 - unfinished_sents)
            input_ids = torch.cat([input_ids, tokens_to_add.unsqueeze(-1)], dim=-1)
            for eos_token_id in eos_token_ids:
                unfinished_sents.mul_(tokens_to_add.ne(eos_token_id).long())
            cur_len = cur_len + 1

            # stop when there is a </s> in each sentence, or if we exceed the maximul length
            if unfinished_sents.max() == 0:
                break

        # add eos_token_ids to unfinished sentences
        if cur_len == max_length:
            input_ids[:, -1].masked_fill_(unfinished_sents.to(dtype=torch.bool), eos_token_ids[0])

        return input_ids
    
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
        self.device = torch.device("cuda" if torch.cuda.is_available() and not self.no_cuda else "cpu")
        self.tokenizer = GPT2Tokenizer.from_pretrained("gpt2-xl")
        self.model = GPT2LMHeadWPastModel.from_pretrained(self.checkpoint_path)
        self.model = self.model.to(self.device)

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
        context_tokens = self.tokenizer.encode(prompt, add_special_tokens=False, return_tensors='pt').to(self.device)
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
