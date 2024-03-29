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

from __future__ import print_function

import argparse
import collections
import math
import time
import os
import numpy as np
import pandas as pd
import psutil
import tensorflow.compat.v1 as tf
from cnvrg import Experiment
from matplotlib import pyplot as plt

tic = time.time()
cnvrg_workdir = os.environ.get("CNVRG_WORKDIR", "/cnvrg")
tf.disable_v2_behavior()
parser = argparse.ArgumentParser(description="""Preprocessor""")
parser.add_argument('-f', '--train_file', action='store', dest='train_file',
                    default='/data/movies_rec_sys/train_whole.csv', required=True, help="""training_file""")
parser.add_argument('--test_file', action='store', dest='test_file', default='/data/movies_rec_sys/test_whole.csv',
                    required=True, help="""test_file""")
parser.add_argument('--std_dev_1', action='store', dest='std_dev_1', default=0.5, required=True,
                    help="""std dev for training the model (hyperparameter)""")
parser.add_argument('--embed_dim_1', action='store', dest='embed_dim_1', default=30, required=True,
                    help="""number of dimensions of matrix (hyperparameter)""")
parser.add_argument('--num_of_steps_1', action='store', dest='num_of_steps_1', default=1000, required=True,
                    help="""number of steps that the model will run for (hyperparameter)""")
parser.add_argument('--learning_rate', action='store', dest='learning_rate', default=10., required=True,
                    help="""learning rate for gradient descent (hyperparameter)""")
parser.add_argument('--threshold', action='store', dest='threshold', default=0.8, required=True,
                    help="""threshold for choosing recommendations""")
parser.add_argument('--rec_method', action='store', dest='rec_method', default='DOT', required=True,
                    help="""DOT Product or COSINE Product""")
parser.add_argument('--precision_at_value', action='store', dest='precision_at_value', default=10, required=True,
                    help="""precision and recall at k""")

parser.add_argument('--project_dir', action='store', dest='project_dir',
                    help="""--- For inner use of cnvrg.io ---""")
parser.add_argument('--output_dir', action='store', dest='output_dir',
                    help="""--- For inner use of cnvrg.io ---""")

args = parser.parse_args()
train_file = args.train_file
test_file = args.test_file
std_dev_1 = float(args.std_dev_1)
embed_dim_1 = int(args.embed_dim_1)
num_of_steps_1 = int(args.num_of_steps_1)
learn_rate_1 = float(args.learning_rate)
threshold = float(args.threshold)
rec_method = args.rec_method
K = int(args.precision_at_value)

hyp = pd.DataFrame(columns=['dimension', 'alpha'])
hyp.at[0, 'dimension'] = embed_dim_1
# hyp.at[0,'reg_coef'] = reg_coef_1
hyp.at[0, 'alpha'] = learn_rate_1
hyp.to_csv('hyp.csv')
hyp_file = 'hyp1.csv'
hyp.to_csv(cnvrg_workdir + "/{}".format(hyp_file), index=False)

train_whole = pd.read_csv(train_file)
test_whole = pd.read_csv(test_file)
train_whole['user_id'] = train_whole['user_id'].astype(int)
train_whole['item_id'] = train_whole['item_id'].astype(int)
test_whole['user_id'] = test_whole['user_id'].astype(int)
test_whole['item_id'] = test_whole['item_id'].astype(int)

ratings = pd.concat([train_whole, test_whole])
users = ratings['user_id'].to_frame().drop_duplicates().sort_values('user_id').reset_index().drop('index', 1)

ratings['user_id'] = ratings['user_id'].astype(int)
ratings['item_id'] = ratings['item_id'].astype(int)
users['user_id'] = users['user_id'].astype(int)

movies = pd.DataFrame({'item_id': ratings['item_id'].unique()})


# @title Build a Sparse Matrix
def build_rating_sparse_tensor(ratings_df):
    """
    Args:
      ratings_df: a pd.DataFrame with `user_id`, `item_id` and `rating` columns.
    Returns:
      a tf.SparseTensor representing the ratings matrix.
    """
    indices = ratings_df[['user_id', 'item_id']].values
    values = ratings_df['rating'].values
    return tf.SparseTensor(
        indices=indices,
        values=values,
        dense_shape=[users.shape[0], movies.shape[0]])


# @title Mean Square Error
def sparse_mean_square_error(sparse_ratings, user_embeddings, movie_embeddings):
    predictions = tf.gather_nd(
        tf.matmul(user_embeddings, movie_embeddings, transpose_b=True),
        sparse_ratings.indices)
    loss = tf.losses.mean_squared_error(sparse_ratings.values, predictions)
    return loss


# @title CFModel helper class
class CFModel(object):
    """Simple class that represents a collaborative filtering model"""

    def __init__(self, embedding_vars, loss, metrics=None):
        """Initializes a CFModel.
        Args:
          embedding_vars: A dictionary of tf.Variables.
          loss: A float Tensor. The loss to optimize.
          metrics: optional list of dictionaries of Tensors. The metrics in each
            dictionary will be plotted in a separate figure during training.
        """
        self._embedding_vars = embedding_vars
        self._loss = loss
        self._metrics = metrics
        self._embeddings = {k: None for k in embedding_vars}
        self._session = None

    @property
    def embeddings(self):
        """The embeddings dictionary."""
        return self._embeddings

    def train(self, num_iterations=100, learning_rate=1.0, plot_results=True,
              optimizer=tf.train.GradientDescentOptimizer):
        """Trains the model.
        Args:
          iterations: number of iterations to run.
          learning_rate: optimizer learning rate.
          plot_results: whether to plot the results at the end of training.
          optimizer: the optimizer to use. Default to GradientDescentOptimizer.
        Returns:
          The metrics dictionary evaluated at the last iteration.
        """
        with self._loss.graph.as_default():
            opt = optimizer(learning_rate)
            train_op = opt.minimize(self._loss)
            local_init_op = tf.group(
                tf.variables_initializer(opt.variables()),
                tf.local_variables_initializer())
            if self._session is None:
                self._session = tf.Session()
                with self._session.as_default():
                    self._session.run(tf.global_variables_initializer())
                    self._session.run(tf.tables_initializer())
                    tf.train.start_queue_runners()

        with self._session.as_default():
            local_init_op.run()
            iterations = []
            metrics = self._metrics or ({},)
            metrics_vals = [collections.defaultdict(list) for _ in self._metrics]

            # Train and append results.
            for i in range(num_iterations + 1):
                _, results = self._session.run((train_op, metrics))

                if (i % 10 == 0) or i == num_iterations:
                    print("\r iteration %d: " % i + ", ".join(
                        ["%s=%f" % (k, v) for r in results for k, v in r.items()]),
                          end='')
                    iterations.append(i)
                    for metric_val, result in zip(metrics_vals, results):
                        for k, v in result.items():
                            metric_val[k].append(v)

            for k, v in self._embedding_vars.items():
                self._embeddings[k] = v.eval()

            if plot_results:
                # Plot the metrics.
                num_subplots = len(metrics) + 1
                fig = plt.figure()
                fig.set_size_inches(num_subplots * 10, 8)
                for i, metric_vals in enumerate(metrics_vals):
                    ax = fig.add_subplot(1, num_subplots, i + 1)
                    for k, v in metric_vals.items():
                        print(k)
                        print(v)
                        ax.plot(iterations, v, label=k)
                    ax.set_xlim([1, num_iterations])
                    ax.legend()
            return results


# @title Build Model
def build_model(train_ratings, test_ratings, embedding_dim=3, init_stddev=1.):
    # Split the ratings DataFrame into train and test.
    # train_ratings, test_ratings = split_dataframe(ratings)
    # SparseTensor representation of the train and test datasets.
    A_train = build_rating_sparse_tensor(train_ratings)
    A_test = build_rating_sparse_tensor(test_ratings)
    # Initialize the embeddings using a normal distribution.

    U = tf.Variable(tf.random_normal(
        [A_train.dense_shape[0], embedding_dim], stddev=init_stddev, seed=10))
    V = tf.Variable(tf.random_normal(
        [A_train.dense_shape[1], embedding_dim], stddev=init_stddev, seed=10))
    train_loss = sparse_mean_square_error(A_train, U, V)
    test_loss = sparse_mean_square_error(A_test, U, V)
    metrics = {
        'train_error': train_loss,
        'test_error': test_loss
    }
    embeddings = {
        "user_id": U,
        "item_id": V
    }
    return CFModel(embeddings, train_loss, [metrics])


# Build the CF model and train it.
model = build_model(train_whole, test_whole, embedding_dim=embed_dim_1, init_stddev=std_dev_1)
model.train(num_iterations=num_of_steps_1, learning_rate=learn_rate_1)

# @title Computing Scores
DOT = 'dot'
COSINE = 'cosine'


def compute_scores(query_embedding, item_embeddings, measure=DOT):
    u = query_embedding
    V = item_embeddings
    if measure == COSINE:
        V = V / np.linalg.norm(V, axis=1, keepdims=True)
        u = u / np.linalg.norm(u)
    scores = u.dot(V.T)
    return scores


max_v = ratings['rating'].max()
################## Computing Eval Metrics for Basic Matrix Factorization ########################
user1_movie_pred_whole = pd.DataFrame(columns=['user_id', 'item_id', 'rating', 'score', 'error'])
eval_metrics_whole = pd.DataFrame(columns=['user_id', 'rmse', 'precision', 'recall'])
recommend_whole = pd.DataFrame(columns=['user_id', 'item_id', 'score'])

for il in range(len(users)):
    scores = compute_scores(model.embeddings["user_id"][il], model.embeddings["item_id"], measure=rec_method)
    score_key = 'score'
    scores_1 = pd.DataFrame({
        score_key: list(scores),
        'item_id': movies['item_id']
    })
    user1 = test_whole.loc[test_whole['user_id'] == il]
    user1_movie = user1.merge(movies[['item_id']], on='item_id')
    user1_movie_pred = user1_movie.merge(scores_1[['item_id', 'score']])
    recommend = pd.DataFrame({
        'score': list(scores),
        'item_id': movies['item_id'],
        'user_id': il
    })
    recommend = recommend[~recommend['item_id'].isin(
        train_whole.loc[(train_whole['user_id'] == il)]['item_id'].to_list() +
        test_whole.loc[(test_whole['user_id'] == il)]['item_id'].to_list()
        )]
    user1_movie_pred = user1_movie_pred.sort_values(by=['score'], ascending=False)
    recommend_whole = pd.concat([recommend_whole, recommend])
    user_max = user1_movie_pred['score'].max()
    relevant_cnt = user1_movie_pred.rating.loc[user1_movie_pred.rating >= threshold * max_v].count()
    recommended_cnt = user1_movie_pred.score.loc[user1_movie_pred.score >= threshold * user_max].count()
    recommended_cnt_k = user1_movie_pred[:K].score.loc[user1_movie_pred.score >= threshold * user_max].count()
    rec_rel_cnt = user1_movie_pred.rating.loc[
        (user1_movie_pred.rating >= threshold * max_v) & (user1_movie_pred.score >= threshold * user_max)].count()
    rec_rel_cnt_k = user1_movie_pred[:K].rating.loc[
        (user1_movie_pred.rating >= threshold * max_v) & (user1_movie_pred.score >= threshold * user_max)].count()
    precision = rec_rel_cnt / recommended_cnt
    precision_k = rec_rel_cnt_k / recommended_cnt_k
    recall_k = rec_rel_cnt_k / relevant_cnt
    recall = rec_rel_cnt / relevant_cnt
    user1_movie_pred['error'] = user1_movie_pred['score'] - user1_movie_pred['rating']
    user1_movie_pred['error'] = user1_movie_pred['error'] ** 2

    eval_metrics = pd.DataFrame(
        {'user_id': il,  # users['user_id'][il],
         'rmse': math.sqrt(user1_movie_pred['error'].mean()),
         'precision': precision,
         'recall': recall,
         'recall@k': recall_k,
         'precision@k': precision_k,
         'rel_count': relevant_cnt,
         'rec_count': recommended_cnt,
         'rel_rec_count': rec_rel_cnt,
         'rec_count_k': recommended_cnt_k,
         'rel_rec_count_k': rec_rel_cnt_k
         }, index=[il])
    eval_metrics_whole = pd.concat([eval_metrics_whole, eval_metrics])
    user1_movie_pred_whole = pd.concat([user1_movie_pred_whole, user1_movie_pred])

metrics_file_name = 'eval_metrics_file.csv'
dataset_pred_name = 'user1_movie_pred_whole.csv'
eval_metrics_file = 'eval_metrics_file.csv'
recommends_file = 'recommend.csv'

eval_metrics_whole.to_csv(cnvrg_workdir + "/{}".format(metrics_file_name), index=False)
user1_movie_pred_whole.to_csv(cnvrg_workdir + "/{}".format(dataset_pred_name), index=False)
recommend_whole.to_csv(cnvrg_workdir + "/{}".format(recommends_file), index=False)

abc = eval_metrics_whole['precision'].mean()
abc1 = eval_metrics_whole['recall'].mean()
abc2 = eval_metrics_whole['rmse'].mean()
abc3 = eval_metrics_whole['precision@k'].mean()
abc4 = eval_metrics_whole['recall@k'].mean()
abc6 = eval_metrics_whole['rec_count_k'].mean()
abc7 = eval_metrics_whole['rel_rec_count_k'].mean()
abc8 = eval_metrics_whole['rel_count'].mean()
abc9 = eval_metrics_whole['rec_count'].mean()
abc10 = eval_metrics_whole['rel_rec_count'].mean()

e = Experiment()
e.log_param("precision", abc)
e.log_param("recall", abc1)
e.log_param("rmse", abc2)
e.log_param("learn_rate", learn_rate_1)
e.log_param("precision_at_k", abc3)
e.log_param("recall_at_k", abc4)
e.log_param("relevant_cnt", abc8)
e.log_param("recommended_cnt", abc9)
e.log_param("rel_rec_cnt", abc10)
e.log_param("recommended_cnt_k", abc6)
e.log_param("rel_rec_count_k", abc7)
composite_metric = (abc10 * (1 / 100) * 0.1) + (1 / abc2) * (0.4) + (abc4 * 0.25) + (abc3 * 0.25)
e.log_param("compositemetric", composite_metric)
print('RAM GB used:', psutil.virtual_memory()[3] / (1024 * 1024 * 1024))
toc = time.time()
print("time taken:", toc - tic)
e.log_param("MF_ram", psutil.virtual_memory()[3] / (1024 * 1024 * 1024))
e.log_param("MF_time", toc - tic)
