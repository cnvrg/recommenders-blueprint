# Copyright (c) 2022 Intel Corporation
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# SPDX-License-Identifier: MIT

import argparse
import pandas as pd
import psutil
import time
from cnvrg import Experiment
import os

cnvrg_workdir = os.environ.get("CNVRG_WORKDIR", "/cnvrg")
tic=time.time()
parser = argparse.ArgumentParser(description="""Preprocessor""")
parser.add_argument('-f','--filename', action='store', dest='filename', default='/data/movies_rec_sys/ratings_2.csv', required=True, help="""string. csv topics data file""")
# parser.add_argument('--project_dir', action='store', dest='project_dir',
#                         help="""--- For inner use of cnvrg.io ---""")
# parser.add_argument('--output_dir', action='store', dest='output_dir',
#                         help="""--- For inner use of cnvrg.io ---""")
args = parser.parse_args()
FILENAME = args.filename
df = pd.read_csv(FILENAME)
#if len(df['rating'].unique()) == 2:
#    df['rating'].replace(to_replace=1,value=2,inplace=True)
#    df['rating'].replace(to_replace=0,value=1,inplace=True)
#    print("Changed")
############## check column headings #############
headers=['user_id','item_id']
if not all([i in df.columns for i in headers]):
    raise Exception('Data must contain |user_id|item_id| columns!')

if 'rating' in df.columns:  # EXPLICIT
    print('Data is in Explicit format!')
    print(df.head())
else:  # IMPLICIT
    print('Data is in Implicit format!')
    print(df.head())
    df['rating'] = 1
    unique_users = df['user_id'].unique()
    unique_items = df['item_id'].unique()
    for user in unique_users:
        for item in unique_items:
            if not ((df['user_id'] == user) & (df['item_id'] == item)).any():  # add negative rows
                df2 = pd.DataFrame({'user_id': [user], 'item_id': [item], 'rating': [0]})
                df = pd.concat([df, df2], ignore_index=True)


# if(all(df.columns==headers)==False):
#
#         # raise("Column headings not correct!")
#################### CHECK NAN #############
df=df.dropna()
#################### CHECK ratings are either integers or floats #############
try:
    df['rating']=df['rating'].astype('float')
except:
    print("Ratings have to be either integers or floats")
    raise()
########## Convert user and item ids to strings ##########

df['user_id']=df['user_id'].astype('str')

df['item_id']=df['item_id'].astype('str')

#################### CHECK ratings are between -10 and 10 #############

if(min(df['rating'])<-10 or max(df['rating'])>10):
    print("ratings have to be positive")
    raise()

##########normalize the ratings globally#########    
print('RAM GB used:', psutil.virtual_memory()[3]/(1024 * 1024 * 1024))
    
#Create two dataframe mapping original user id and item id to internal representation and one dataframe of the original translated ratings frame
processed_dataframe=pd.DataFrame(columns=['user_id','item_id','rating'])

current_u_index = 0
current_i_index = 0

user = []
item = []
rating = []
raw2inner_id_users = {}
raw2inner_id_items = {}
# user raw id, item raw id, rating
for urid, irid, r in df.itertuples(index=False):
            try:
                uid = raw2inner_id_users[urid]
            except KeyError:
                uid = current_u_index
                raw2inner_id_users[urid] = current_u_index
                current_u_index += 1
            try:
                iid = raw2inner_id_items[irid]
            except KeyError:
                iid = current_i_index
                raw2inner_id_items[irid] = current_i_index
                current_i_index += 1
            
            user.append(uid)
            item.append(iid)
            rating.append(r)
data={'originaluser_id':raw2inner_id_users.keys(),'user_id':raw2inner_id_users.values()}
convertuser=pd.DataFrame(data)
###########Total input size###########
print('RAM GB used:', psutil.virtual_memory()[3]/(1024 * 1024 * 1024))

print("number of users:",len(data))

data={'originalitem_id':raw2inner_id_items.keys(),'item_id':raw2inner_id_items.values()}
convertitem=pd.DataFrame(data)

print("number of items:",len(data))

data={'user_id':user,'item_id':item,'rating':rating}
processed_dataframe=pd.DataFrame(data) ####create a ready to use dataframe with converted values######    


full = "ratingstranslated.csv"
itemdict = "itemdict.csv" 
userdict = "userdict.csv" 
processed_dataframe.to_csv(cnvrg_workdir + "/{}".format(full), index=False)
convertitem.to_csv(cnvrg_workdir + "/{}".format(itemdict), index=False)
convertuser.to_csv(cnvrg_workdir + "/{}".format(userdict), index=False)
convertitem.to_csv(cnvrg_workdir + '/itemdict_1.csv')
convertuser.to_csv(cnvrg_workdir + '/userdict_1.csv')

print('RAM GB used:', psutil.virtual_memory()[3]/(1024 * 1024 * 1024))
toc=time.time()
print("time taken:",toc-tic)
e = Experiment()
e.log_param("dataval_ram", psutil.virtual_memory()[3]/(1024 * 1024 * 1024))
e.log_param("dataval_time", toc-tic)