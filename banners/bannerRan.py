import random
import sys
import time

import json
import os
import warnings

import numpy as np


import glob, os

stat_mini     = 1
stat_max = 0
listBanners = []


#HOW TO USE IT:
#1 copy the opening.txt
#2 remove the graphic (but do keep top logo for consistency)
#3 add ASCII art that is 78 or less characters in width
#4 save  txt file under a complete new name

class bannerRan:
    def __init__(self):
        banner_number = load_banner()      #insert function to get random
        self.banner_number = banner_number

def load_banner():
    global stat_max
    global stat_mini
    global listBanners
    hey = scanBanners() #load text and get proper numbers	

    choose_between = r(stat_mini, stat_max)
	
    x = random.choice(listBanners)
    return x
	
def r(x,y):  #randmom, picks between X and Y
    return int(str(random.randint(x,y)))
	
	
def scanBanners():
    global stat_max
    global listBanners
    dir_path = os.path.dirname(os.path.realpath(__file__)) # directory of banners path
    #os.chdir("")
    
    i = 0
    for file in glob.glob("banners/*.txt"):
        i+=1
        listBanners.append(file)
        #print(str(i), file)
        
    stat_max = i


    x = dir_path
    return x
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
