#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys

# Hack so you don't have to put the library containing this script in the PYTHONPATH.
sys.path = [os.path.abspath(os.path.join(__file__, '..', '..'))] + sys.path

import numpy as np
import argparse

from learn2track.utils import load_bundle, save_bundle


def buildArgsParser():
    DESCRIPTION = "Script to split bundles to form training data."
    p = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    p.add_argument('bundles', metavar='bundle', type=str, nargs="+", help='list of training data files (.npz).')
    p.add_argument('--split', type=float, nargs=3, help='respectively the sizes of the split for trainset, validset and testset.', default=[0.8, 0.1, 0.1])
    p.add_argument('--split_type', type=str, choices=["percentage", "count"], help='type of the split, either use percents or fixed counts.', default="percentage")
    p.add_argument('--seed', type=int, help='seed to use to shuffle data.', default=1234)
    p.add_argument('--delete', action="store_true", help='delete bundle file after being splitted.')

    return p


def main():
    parser = buildArgsParser()
    args = parser.parse_args()
    print(args)

    rng = np.random.RandomState(args.seed)

    for bundle in args.bundles:
        print("Splitting {} as follow {} using {}".format(bundle, args.split, args.split_type))
        inputs, targets = load_bundle(bundle)

        nb_examples = len(inputs)
        indices = np.arange(nb_examples)
        rng.shuffle(indices)

        if args.split_type == "percentage":
            trainset_size = int(np.round(args.split[0] * nb_examples))
            validset_size = int(np.round(args.split[1] * nb_examples))
            testset_size = int(np.round(args.split[2] * nb_examples))
            # Make sure the splits sum to nb_examples
            testset_size += nb_examples - (trainset_size + validset_size + testset_size)
        elif args.split_type == "count":
            raise NotImplementedError("Split type `count` not implemented yet!")

        assert trainset_size + validset_size + testset_size == nb_examples
        assert len(inputs[:trainset_size]) == trainset_size
        assert len(inputs[trainset_size:-testset_size]) == validset_size
        assert len(inputs[-testset_size:]) == testset_size
        assert len(targets[:trainset_size]) == trainset_size
        assert len(targets[trainset_size:-testset_size]) == validset_size
        assert len(targets[-testset_size:]) == testset_size

        trainset_indices = indices[:trainset_size]
        validset_indices = indices[trainset_size:-testset_size]
        testset_indices = indices[-testset_size:]

        save_bundle(bundle[:-4] + "_trainset.npz",
                    inputs=inputs[trainset_indices].copy(),
                    targets=targets[trainset_indices].copy(),
                    indices=trainset_indices)
        save_bundle(bundle[:-4] + "_validset.npz",
                    inputs=inputs[validset_indices].copy(),
                    targets=targets[validset_indices].copy(),
                    indices=validset_indices)
        save_bundle(bundle[:-4] + "_testset.npz",
                    inputs=inputs[testset_indices].copy(),
                    targets=targets[testset_indices].copy(),
                    indices=testset_indices)

        if args.delete:
            os.remove(bundle)


if __name__ == '__main__':
    main()