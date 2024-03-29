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
import argparse
import os
import psutil
import time
from cnvrg import Experiment

cnvrg_workdir = os.environ.get("CNVRG_WORKDIR", "/cnvrg")
tic=time.time()
parser = argparse.ArgumentParser(description="""Preprocessor""")
#parser.add_argument('-f','--output_rec', action='store', dest='output_rec', default='/input/compare/recommend.csv', required=True, help="""training_file""")
parser.add_argument('--last_item', action='store', dest='last_item', default='cat', required=False, help="""test_file""")

#parser.add_argument('--project_dir', action='store', dest='project_dir',
#                        help="""--- For inner use of cnvrg.io ---""")
#parser.add_argument('--output_dir', action='store', dest='output_dir',
#                        help="""--- For inner use of cnvrg.io ---""")
#args = parser.parse_args()
for k in os.environ.keys():
    if 'PASSED_CONDITION' in k and os.environ[k] == 'true':
        print("Yes123")
        task_name = k.replace('CNVRG_', '').replace('_PASSED_CONDITION', '').lower()
#train_1 = args.output_rec
#train file = f'/input/{task_name}/{args.output_rec}'
train_file = '/input/'+task_name+'/'+'recommend.csv'
train = pd.read_csv(train_file)
file_name_variable = 'recommend.csv'
train.to_csv(cnvrg_workdir + "/{}".format(file_name_variable), index=False)
print('RAM GB used:', psutil.virtual_memory()[3]/(1024 * 1024 * 1024))
toc=time.time()
print("time taken:",toc-tic)
e = Experiment()
e.log_param("compare_ram", psutil.virtual_memory()[3]/(1024 * 1024 * 1024))
e.log_param("compare_time", toc-tic)
#for i in os.environ:
#    print(i,'-',os.environ[i])
#    print("iteration")
