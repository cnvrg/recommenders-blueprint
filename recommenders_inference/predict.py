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

import pandas as pd
import time


tic = time.time()


fullpred1 = '/input/compare/recommend.csv'
mapping_file_user = '/input/data_validation/userdict.csv'
mapping_file_item = '/input/data_validation/itemdict.csv'
top_count = 5
fullpred = pd.read_csv(fullpred1)
mapping_item = pd.read_csv(mapping_file_item)
mapping_user = pd.read_csv(mapping_file_user)



def predict(data):
    # TODO: convert y to dataframe
    y = pd.DataFrame({'user_id': [data["user_id"]]})
    #y = pd.DataFrame([y],columns=['user_id'])
    mapping_user['originaluser_id'] = mapping_user['originaluser_id'].astype(
        str)
    mapping_item['originalitem_id'] = mapping_item['originalitem_id'].astype(
        str)
    # convert input user ids to strings and rename the userid column to originaluser_id
    user_id_input = pd.DataFrame(
        list(y['user_id'].astype('str')), columns=['originaluser_id'])
    # convert user ids to internal ids
    converted_user_id = mapping_user.merge(
        user_id_input, on='originaluser_id', how='inner')
    # fullpred.dtypes
    # get all the predictions for all items for the users requested
    results = fullpred.merge(converted_user_id, on='user_id', how='inner')
    print(results.columns)
    groups = results.groupby('user_id', sort=True)
    finaloutput = pd.DataFrame(columns=['originaluser_id', 'originalitem_id'])
    for group in groups.groups.keys():
        # get top k recommendations for a user in the results
        group_length = round(len(groups.get_group(group))*0.25)
        recommendations = groups.get_group(group).sort_values(
            'score', ascending=False).head(group_length)
        # convert top k recommendations from internal to external
        recommendations = recommendations.merge(mapping_item, on='item_id', how='inner')[
            ['originaluser_id', 'originalitem_id']]
        finaloutput = pd.concat(
            [finaloutput, recommendations], ignore_index=True)
    finaloutput = finaloutput.rename(
        {'originaluser_id': 'user_id', 'originalitem_id': 'item_id'}, axis=1)
    finaloutput_2 = pd.DataFrame(columns=['user_id', 'item_id'])
    for i in range(len(finaloutput['user_id'].unique())):
        cur_user = finaloutput['user_id'].unique()[i]
        test = finaloutput.loc[finaloutput['user_id']
                               == str(cur_user)].sample(n=10, replace=True)
        finaloutput_2 = pd.concat([finaloutput_2, test])
    top_cnt = 0
    top_count = 10

    response = finaloutput_2['item_id'][top_cnt:(top_count + top_cnt)].astype(str).to_list()
    return {'recommendations': response}
