#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

# Hack so you don't have to put the library containing this script in the PYTHONPATH.
sys.path = [os.path.abspath(os.path.join(__file__, '..', '..'))] + sys.path

import numpy as np
import argparse
from os.path import join as pjoin

import theano
import theano.tensor as T

from smartlearner import Trainer
from smartlearner import tasks, views, stopping_criteria
from smartlearner.direction_modifiers import DirectionClipping


from learn2track import utils
from learn2track.utils import Timer
from learn2track.factories import WEIGHTS_INITIALIZERS, weigths_initializer_factory, batch_scheduler_factory, ACTIVATION_FUNCTIONS
from learn2track.factories import optimizer_factory
from learn2track.factories import model_factory
from learn2track.factories import loss_factory

from learn2track import datasets
from learn2track.batch_schedulers import TractographyBatchScheduler
from learn2track.neurotools import VolumeManager


def build_train_gru_argparser(subparser):
    DESCRIPTION = "Train a GRU."

    p = subparser.add_parser("gru_regression", description=DESCRIPTION, help=DESCRIPTION)

    # p.add_argument('dataset', type=str, help='folder containing training data (.npz files).')

    # Model options (GRU)
    model = p.add_argument_group("GRU arguments")

    model.add_argument('--hidden-sizes', type=int, nargs='+', default=500,
                       help="Size of the hidden layers. Default: 500")

    model.add_argument('--weights-initialization', type=str, default='orthogonal', choices=WEIGHTS_INITIALIZERS,
                       help='which type of initialization to use when creating weights [{0}].'.format(", ".join(WEIGHTS_INITIALIZERS)))
    model.add_argument('--initialization-seed', type=int, default=1234,
                       help='seed used to generate random numbers. Default=1234')

    model.add_argument('--learn-to-stop', action="store_true",
                       help='if specified, the model will be trained to learn when to stop tracking')

    model.add_argument('--normalize', action="store_true",
                       help='if specified, output direction the model produces will have unit length.')

    model.add_argument('--feed-previous-direction', action="store_true",
                       help='if specified, the model will be given the previous direction as an additional input')

    # General parameters (optional)
    general = p.add_argument_group("General arguments")
    general.add_argument('-f', '--force', action='store_true', help='restart training from scratch instead of resuming.')
    general.add_argument('--view', action='store_true', help='display learning curves.')


def build_train_gru_mixture_argparser(subparser):
    DESCRIPTION = "Train a gaussian mixture GRU."

    p = subparser.add_parser("gru_mixture", description=DESCRIPTION, help=DESCRIPTION)

    # p.add_argument('dataset', type=str, help='folder containing training data (.npz files).')

    # Model options (GRU)
    model = p.add_argument_group("GRU arguments")

    model.add_argument('--hidden-sizes', type=int, nargs='+', default=500,
                       help="Size of the hidden layers. Default: 500")

    model.add_argument('-n', '--n-gaussians', type=int, default=2, help='Number of gaussians in the mixture. Default: 2')

    model.add_argument('--weights-initialization', type=str, default='orthogonal', choices=WEIGHTS_INITIALIZERS,
                       help='which type of initialization to use when creating weights [{0}].'.format(", ".join(WEIGHTS_INITIALIZERS)))
    model.add_argument('--initialization-seed', type=int, default=1234,
                       help='seed used to generate random numbers. Default=1234')

    model.add_argument('--normalize', action="store_true",
                       help='if specified, output direction the model produces will have unit length.')

    model.add_argument('--feed-previous-direction', action="store_true",
                       help='if specified, the model will be given the previous direction as an additional input')

    # General parameters (optional)
    general = p.add_argument_group("General arguments")
    general.add_argument('-f', '--force', action='store_true', help='restart training from scratch instead of resuming.')
    general.add_argument('--view', action='store_true', help='display learning curves.')


def build_train_gru_multistep_argparser(subparser):
    DESCRIPTION = "Train a multistep GRU."

    p = subparser.add_parser("gru_multistep", description=DESCRIPTION, help=DESCRIPTION)

    # Model options (GRU)
    model = p.add_argument_group("GRU arguments")

    model.add_argument('--hidden-sizes', type=int, nargs='+', default=500,
                       help="Size of the hidden layers. Default: 500")

    model.add_argument('-k', type=int, required=True, help="Prediction horizon for multistep training")
    model.add_argument('-m', type=int, required=True, help="Number of samples used in the Monte-Carlo estimate")

    model.add_argument('--feed-previous-direction', action="store_true",
                       help='if specified, the model will be given the previous direction as an additional input')

    model.add_argument('--weights-initialization', type=str, default='orthogonal', choices=WEIGHTS_INITIALIZERS,
                       help='which type of initialization to use when creating weights [{0}].'.format(", ".join(WEIGHTS_INITIALIZERS)))
    model.add_argument('--initialization-seed', type=int, default=1234,
                       help='seed used to generate random numbers. Default=1234')

    # General parameters (optional)
    general = p.add_argument_group("General arguments")
    general.add_argument('-f', '--force', action='store_true', help='restart training from scratch instead of resuming.')
    general.add_argument('--view', action='store_true', help='display learning curves.')


def build_train_ffnn_regression_argparser(subparser):
    DESCRIPTION = "Train a FFNN on a regression task."

    p = subparser.add_parser("ffnn_regression", description=DESCRIPTION, help=DESCRIPTION)

    # Model options (GRU)
    model = p.add_argument_group("FFNN regression arguments")

    model.add_argument('--hidden-sizes', type=int, nargs='+', default=500,
                       help="Size of the hidden layers. Default: 500")

    model.add_argument('--activation', type=str, default='tanh', choices=ACTIVATION_FUNCTIONS,
                       help='which type of activation function to use for hidden layers.'.format(", ".join(ACTIVATION_FUNCTIONS)))

    model.add_argument('--weights-initialization', type=str, default='orthogonal', choices=WEIGHTS_INITIALIZERS,
                       help='which type of initialization to use when creating weights [{0}].'.format(", ".join(WEIGHTS_INITIALIZERS)))
    model.add_argument('--initialization-seed', type=int, default=1234,
                       help='seed used to generate random numbers. Default=1234')

    model.add_argument('--learn-to-stop', action="store_true",
                       help='if specified, the model will be trained to learn when to stop tracking')

    model.add_argument('--normalize', action="store_true",
                       help='if specified, output direction the model produces will have unit length.')

    model.add_argument('--feed-previous-direction', action="store_true",
                       help='if specified, the model will be given the previous direction as an additional input')

    # General parameters (optional)
    general = p.add_argument_group("General arguments")
    general.add_argument('-f', '--force', action='store_true', help='restart training from scratch instead of resuming.')
    general.add_argument('--view', action='store_true', help='display learning curves.')


def build_argparser():
    DESCRIPTION = ("Script to train a GRU model from a dataset of streamlines"
                   " coordinates expressed in voxel space and a DWI on a regression task.")
    p = argparse.ArgumentParser(description=DESCRIPTION)

    # Dataset options
    dataset = p.add_argument_group("Data options")
    dataset.add_argument('--train-subjects', nargs='+', required=True,
                         help='file containing training data (as generated by `process_streamlines.py`).')
    dataset.add_argument('--valid-subjects', nargs='+', required=True,
                         help='file containing validation data (as generated by `process_streamlines.py`).')
    dataset.add_argument('--use-sh-coeffs', action='store_true',
                         help='if specified, use Spherical Harmonic coefficients as inputs to the model. Default: dwi coefficients.')

    duration = p.add_argument_group("Training duration options")
    duration.add_argument('--max-epoch', type=int, metavar='N', default=100,
                          help='if specified, train for a maximum of N epochs. Default: %(default)s')
    duration.add_argument('--lookahead', type=int, metavar='K', default=10,
                          help='use early stopping with a lookahead of K. Default: %(default)s')
    duration.add_argument('--lookahead-eps', type=float, default=1e-3,
                          help='in early stopping, an improvement is whenever the objective improve of at least `eps`. Default: %(default)s',)

    # Training options
    training = p.add_argument_group("Training options")
    training.add_argument('--batch-size', type=int,
                          help='size of the batch to use when training the model. Default: 100.', default=100)
    # training.add_argument('--neighborhood-patch', type=int, metavar='N',
    #                       help='if specified, patch (as a cube, i.e. NxNxN) around each streamlines coordinates will be concatenated to the input.')
    training.add_argument('--noisy-streamlines-sigma', type=float,
                          help='if specified, it is the standard deviation of the gaussian noise added independently to every point of every streamlines at each batch.')
    training.add_argument('--clip-gradient', type=float,
                          help='if provided, gradient norms will be clipped to this value (if it exceeds it).')
    training.add_argument('--seed', type=int, default=1234,
                          help='seed used to generate random numbers in the batch scheduler. Default=1234')

    # Optimizer options
    optimizer = p.add_argument_group("Optimizer (required)")
    optimizer = optimizer.add_mutually_exclusive_group(required=True)
    optimizer.add_argument('--SGD', metavar="LR", type=str, help='use SGD with constant learning rate for training.')
    optimizer.add_argument('--AdaGrad', metavar="LR [EPS=1e-6]", type=str, help='use AdaGrad for training.')
    optimizer.add_argument('--Adam', metavar="[LR=0.0001]", type=str, help='use Adam for training.')
    optimizer.add_argument('--RMSProp', metavar="LR", type=str, help='use RMSProp for training.')
    optimizer.add_argument('--Adadelta', action="store_true", help='use Adadelta for training.')

    # General options (optional)
    general = p.add_argument_group("General arguments")
    general.add_argument('--name', type=str,
                         help='name of the experiment. Default: name is generated from arguments.')

    general.add_argument('-f', '--force', action='store_true', help='restart training from scratch instead of resuming.')
    general.add_argument('--view', action='store_true', help='display learning curves.')

    subparser = p.add_subparsers(title="Models", dest="model")
    subparser.required = True   # force 'required' testing
    build_train_gru_argparser(subparser)
    build_train_gru_mixture_argparser(subparser)
    build_train_gru_multistep_argparser(subparser)
    build_train_ffnn_regression_argparser(subparser)

    return p


def tsne_view(trainset, volume_manager):

    batch_scheduler = TractographyBatchScheduler(trainset,
                                                 batch_size=20000,
                                                 noisy_streamlines_sigma=False,
                                                 seed=1234,
                                                 normalize_target=True)
    rng = np.random.RandomState(42)
    rng.shuffle(batch_scheduler.indices)

    bundle_name_pattern = "CST_Left"
    # batch_inputs, batch_targets, batch_mask = batch_scheduler._prepare_batch(trainset.get_bundle(bundle_name_pattern, return_idx=True))
    inputs, targets, mask = batch_scheduler._next_batch(3)
    mask = mask.astype(bool)
    idx = np.arange(mask.sum())
    rng.shuffle(idx)

    coords = T.matrix('coords')
    eval_at_coords = theano.function([coords], volume_manager.eval_at_coords(coords))

    M = 2000 * len(trainset.subjects)
    coords = inputs[mask][idx[:M]]
    X = eval_at_coords(coords)

    from sklearn.manifold.t_sne import TSNE
    tsne = TSNE(n_components=2, verbose=2, random_state=42)
    Y = tsne.fit_transform(X)

    import matplotlib.pyplot as plt
    plt.figure()
    ids = range(len(trainset.subjects))
    markers = ['s', 'o', '^', 'v', '<', '>', 'h']
    colors = ['cyan', 'darkorange', 'darkgreen', 'magenta', 'pink', 'k']
    for i, marker, color in zip(ids, markers, colors):
        idx = coords[:, -1] == i
        print("Subject #{}: ".format(i), idx.sum())
        plt.scatter(Y[idx, 0], Y[idx, 1], 20, color=color, marker=marker, label="Subject #{}".format(i))

    plt.legend()
    plt.show()


def main():
    parser = build_argparser()
    args = parser.parse_args()
    print(args)
    print("Using Theano v.{}".format(theano.version.short_version))

    hyperparams_to_exclude = ['max_epoch', 'force', 'name', 'view', 'shuffle_streamlines']
    experiment_path, hyperparams, resuming = utils.maybe_create_experiment_folder(args, exclude=hyperparams_to_exclude)

    # Log the command currently running.
    with open(pjoin(experiment_path, 'cmd.txt'), 'a') as f:
        f.write(" ".join(sys.argv) + "\n")

    print("Resuming:" if resuming else "Creating:", experiment_path)

    with Timer("Loading dataset", newline=True):
        trainset_volume_manager = VolumeManager()
        validset_volume_manager = VolumeManager()
        trainset = datasets.load_tractography_dataset(args.train_subjects, trainset_volume_manager, name="trainset", use_sh_coeffs=args.use_sh_coeffs)
        validset = datasets.load_tractography_dataset(args.valid_subjects, validset_volume_manager, name="validset", use_sh_coeffs=args.use_sh_coeffs)
        print("Dataset sizes:", len(trainset), " |", len(validset))

        if args.view:
            tsne_view(trainset, trainset_volume_manager)
            sys.exit(0)

        batch_scheduler = batch_scheduler_factory(hyperparams, dataset=trainset, train_mode=True)
        print("An epoch will be composed of {} updates.".format(batch_scheduler.nb_updates_per_epoch))
        print(trainset_volume_manager.data_dimension, args.hidden_sizes, batch_scheduler.target_size)

    with Timer("Creating model"):
        input_size = trainset_volume_manager.data_dimension
        if hyperparams['feed_previous_direction']:
            input_size += 3

        model = model_factory(hyperparams,
                              input_size=input_size,
                              output_size=batch_scheduler.target_size,
                              volume_manager=trainset_volume_manager)
        model.initialize(weigths_initializer_factory(args.weights_initialization,
                                                     seed=args.initialization_seed))

    with Timer("Building optimizer"):
        loss = loss_factory(hyperparams, model, trainset)

        if args.clip_gradient is not None:
            loss.append_gradient_modifier(DirectionClipping(threshold=args.clip_gradient))

        optimizer = optimizer_factory(hyperparams, loss)

    with Timer("Building trainer"):
        trainer = Trainer(optimizer, batch_scheduler)

        # Log training error
        loss_monitor = views.MonitorVariable(loss.loss)
        avg_loss = tasks.AveragePerEpoch(loss_monitor)
        trainer.append_task(avg_loss)

        # Print average training loss.
        trainer.append_task(tasks.Print("Avg. training loss:         : {}", avg_loss))

        # if args.learn_to_stop:
        #     l2err_monitor = views.MonitorVariable(T.mean(loss.mean_sqr_error))
        #     avg_l2err = tasks.AveragePerEpoch(l2err_monitor)
        #     trainer.append_task(avg_l2err)
        #
        #     crossentropy_monitor = views.MonitorVariable(T.mean(loss.cross_entropy))
        #     avg_crossentropy = tasks.AveragePerEpoch(crossentropy_monitor)
        #     trainer.append_task(avg_crossentropy)
        #
        #     trainer.append_task(tasks.Print("Avg. training L2 err:       : {}", avg_l2err))
        #     trainer.append_task(tasks.Print("Avg. training stopping:     : {}", avg_crossentropy))
        #     trainer.append_task(tasks.Print("L2 err : {0:.4f}", l2err_monitor, each_k_update=100))
        #     trainer.append_task(tasks.Print("stopping : {0:.4f}", crossentropy_monitor, each_k_update=100))

        # Print NLL mean/stderror.
        # train_loss = L2DistanceForSequences(model, trainset)
        # train_batch_scheduler = StreamlinesBatchScheduler(trainset, batch_size=1000,
        #                                                   noisy_streamlines_sigma=None,
        #                                                   nb_updates_per_epoch=None,
        #                                                   seed=1234)

        # train_error = views.LossView(loss=train_loss, batch_scheduler=train_batch_scheduler)
        # trainer.append_task(tasks.Print("Trainset - Error        : {0:.2f} | {1:.2f}", train_error.sum, train_error.mean))

        # HACK: To make sure all subjects in the volume_manager are used in a batch, we have to split the trainset/validset in 2 volume managers
        model.volume_manager = validset_volume_manager
        valid_loss = loss_factory(hyperparams, model, validset)
        valid_batch_scheduler = batch_scheduler_factory(hyperparams,
                                                        dataset=validset,
                                                        train_mode=False)

        valid_error = views.LossView(loss=valid_loss, batch_scheduler=valid_batch_scheduler)
        trainer.append_task(tasks.Print("Validset - Error        : {0:.2f} | {1:.2f}", valid_error.sum, valid_error.mean))

        # HACK: Restore trainset volume manager
        model.volume_manager = trainset_volume_manager

        lookahead_loss = valid_error.sum

        direction_norm = views.MonitorVariable(T.sqrt(sum(map(lambda d: T.sqr(d).sum(), loss.gradients.values()))))
        # trainer.append_task(tasks.Print("||d|| : {0:.4f}", direction_norm))

        # logger = tasks.Logger(train_error.mean, valid_error.mean, valid_error.sum, direction_norm)
        logger = tasks.Logger(valid_error.mean, valid_error.sum, direction_norm)
        trainer.append_task(logger)

        if args.view:
            import pylab as plt

            def _plot(*args, **kwargs):
                plt.figure(1)
                plt.clf()
                plt.show(False)
                plt.subplot(121)
                plt.plot(np.array(logger.get_variable_history(0)).flatten(), label="Train")
                plt.plot(np.array(logger.get_variable_history(1)).flatten(), label="Valid")
                plt.legend()

                plt.subplot(122)
                plt.plot(np.array(logger.get_variable_history(3)).flatten(), label="||d'||")
                plt.draw()

            trainer.append_task(tasks.Callback(_plot))

        # Callback function to stop training if NaN is detected.
        def detect_nan(obj, status):
            if np.isnan(model.parameters[0].get_value().sum()):
                print("NaN detected! Stopping training now.")
                sys.exit()

        trainer.append_task(tasks.Callback(detect_nan, each_k_update=1))

        # Callback function to save training progression.
        def save_training(obj, status):
            trainer.save(experiment_path)

        trainer.append_task(tasks.Callback(save_training))

        # Early stopping with a callback for saving every time model improves.
        def save_improvement(obj, status):
            """ Save best model and training progression. """
            if np.isnan(model.parameters[0].get_value().sum()):
                print("NaN detected! Not saving the model. Crashing now.")
                sys.exit()

            print("*** Best epoch: {0} ***\n".format(obj.best_epoch))
            model.save(experiment_path)

        # Print time for one epoch
        trainer.append_task(tasks.PrintEpochDuration())
        trainer.append_task(tasks.PrintTrainingDuration())
        trainer.append_task(tasks.PrintTime(each_k_update=100))  # Profiling

        # Add stopping criteria
        trainer.append_task(stopping_criteria.MaxEpochStopping(args.max_epoch))
        early_stopping = stopping_criteria.EarlyStopping(lookahead_loss, lookahead=args.lookahead, eps=args.lookahead_eps, callback=save_improvement)
        trainer.append_task(early_stopping)

    with Timer("Compiling Theano graph"):
        trainer.build_theano_graph()

    if resuming:
        if not os.path.isdir(pjoin(experiment_path, 'training')):
            print("No 'training/' folder. Assuming it failed before"
                  " the end of the first epoch. Starting a new training.")
        else:
            with Timer("Loading"):
                trainer.load(experiment_path)

    with Timer("Training"):
        trainer.train()


if __name__ == "__main__":
    main()
