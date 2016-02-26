import os
from os.path import join as pjoin

import pickle
import numpy as np
import theano
import theano.tensor as T
from collections import OrderedDict

from learn2track import factories

from smartlearner.interfaces import Model
from smartlearner import utils as smartutils
from smartlearner.utils import sharedX
import smartlearner.initializers as initer


class LayerDense(object):
    def __init__(self, input_size, output_size, activation="identity", name="Dense"):
        self.input_size = input_size
        self.output_size = output_size
        self.name = name
        self.activation = activation
        self.activation_fct = factories.make_activation_function(self.activation)

        # Regression output weights and biases
        self.W = sharedX(value=np.zeros((self.input_size, self.output_size)), name=self.name+'_W')
        self.b = sharedX(value=np.zeros(output_size), name=self.name+'_b')

    def initialize(self, weights_initializer=initer.UniformInitializer(1234)):
        weights_initializer(self.W)

    @property
    def parameters(self):
        return [self.W, self.b]

    def fprop(self, X):
        preactivation = T.dot(X, self.W) + self.b
        out = self.activation_fct(preactivation)
        return out


class LayerRegression(object):
    def __init__(self, input_size, output_size, normed=True, name="Regression"):

        self.input_size = input_size
        self.output_size = output_size
        self.normed = normed
        self.name = name

        # Regression output weights and biases
        self.W = sharedX(value=np.zeros((self.input_size, self.output_size)), name=self.name+'_W')
        self.b = sharedX(value=np.zeros(output_size), name=self.name+'_b')

    def initialize(self, weights_initializer=initer.UniformInitializer(1234)):
        weights_initializer(self.W)

    @property
    def parameters(self):
        return [self.W, self.b]

    def fprop(self, X):
        out = T.dot(X, self.W) + self.b
        # Normalize the output vector.
        if self.normed:
            out /= (T.sqrt(T.sum(out**2, axis=1, keepdims=True) + 1e-8))

        return out


class LayerSoftmax(object):
    def __init__(self, input_size, output_size, name="Softmax"):

        self.input_size = input_size
        self.output_size = output_size
        self.name = name

        # Regression output weights and biases
        self.W = sharedX(value=np.zeros((self.input_size, self.output_size)), name=self.name+'_W')
        self.b = sharedX(value=np.zeros(output_size), name=self.name+'_b')

    def initialize(self, weights_initializer=initer.UniformInitializer(1234)):
        weights_initializer(self.W)

    @property
    def parameters(self):
        return [self.W, self.b]

    def fprop(self, X):
        preactivation = T.dot(X, self.W) + self.b
        # The softmax function, applied to a matrix, computes the softmax values row-wise.
        out = T.nnet.softmax(preactivation)
        return out


class LayerLSTMSlow(object):
    def __init__(self, input_size, hidden_size, activation="tanh", name="LSTM"):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.name = name
        self.activation = activation
        self.activation_fct = factories.make_activation_function(self.activation)

        # Input weights (i:input, o:output, f:forget, m:memory)
        self.Wi = sharedX(value=np.zeros((input_size, hidden_size)), name=self.name+'_Wi')
        self.Wo = sharedX(value=np.zeros((input_size, hidden_size)), name=self.name+'_Wo')
        self.Wf = sharedX(value=np.zeros((input_size, hidden_size)), name=self.name+'_Wf')
        self.Wm = sharedX(value=np.zeros((input_size, hidden_size)), name=self.name+'_Wm')

        # Biases (i:input, o:output, f:forget, m:memory)
        self.bi = sharedX(value=np.zeros(hidden_size), name=self.name+'_bi')
        self.bo = sharedX(value=np.zeros(hidden_size), name=self.name+'_bo')
        self.bf = sharedX(value=np.zeros(hidden_size), name=self.name+'_bf')
        self.bm = sharedX(value=np.zeros(hidden_size), name=self.name+'_bm')

        # Recurrence weights (i:input, o:output, f:forget, m:memory)
        self.Ui = sharedX(value=np.zeros((hidden_size, hidden_size)), name=self.name+'_Ui')
        self.Uo = sharedX(value=np.zeros((hidden_size, hidden_size)), name=self.name+'_Uo')
        self.Uf = sharedX(value=np.zeros((hidden_size, hidden_size)), name=self.name+'_Uf')
        self.Um = sharedX(value=np.zeros((hidden_size, hidden_size)), name=self.name+'_Um')

        # Memory weights (i:input, o:output, f:forget, m:memory)
        self.Vi = sharedX(value=np.ones(hidden_size), name=self.name+'_Vi')
        self.Vo = sharedX(value=np.ones(hidden_size), name=self.name+'_Vo')
        self.Vf = sharedX(value=np.ones(hidden_size), name=self.name+'_Vf')

    def initialize(self, weights_initializer=initer.UniformInitializer(1234)):
        for param in [self.Wi, self.Wo, self.Wf, self.Wm]:
            weights_initializer(param)

        for param in [self.Ui, self.Uo, self.Uf, self.Um]:
            weights_initializer(param)

    @property
    def parameters(self):
        return [self.Wi, self.Wo, self.Wf, self.Wm,
                self.Ui, self.Uo, self.Uf, self.Um,
                self.bi, self.bo, self.bf, self.bm,
                self.Vi, self.Vo, self.Vf]

    def fprop(self, Xi, last_h, last_m):
        # TODO: replace sigmoid by ReLU?
        gate_i = T.nnet.sigmoid(T.dot(Xi, self.Wi) + T.dot(last_h, self.Ui) + last_m*self.Vi + self.bi)
        mi = T.tanh(T.dot(Xi, self.Wm) + T.dot(last_h, self.Um) + self.bm)

        gate_f = T.nnet.sigmoid(T.dot(Xi, self.Wf) + T.dot(last_h, self.Uf) + last_m*self.Vf + self.bf)
        m = gate_i*mi + gate_f*last_m

        gate_o = T.nnet.sigmoid(T.dot(Xi, self.Wo) + T.dot(last_h, self.Uo) + m*self.Vo + self.bo)
        h = gate_o * self.activation_fct(m)

        return h, m


class LayerLSTM(object):
    def __init__(self, input_size, hidden_size, activation="tanh", name="LSTM"):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.name = name
        self.activation = activation
        self.activation_fct = factories.make_activation_function(self.activation)

        # Input weights (i:input, o:output, f:forget, m:memory)
        # Concatenation of the weights in that order: Wi, Wo, Wf, Wm
        self.W = sharedX(value=np.zeros((input_size, 4*hidden_size)), name=self.name+'_W')

        # Biases (i:input, o:output, f:forget, m:memory)
        # Concatenation of the biases in that order: bi, bo, bf, bm
        self.b = sharedX(value=np.zeros(4*hidden_size), name=self.name+'_b')

        # Recurrence weights (i:input, o:output, f:forget, m:memory)
        # Concatenation of the recurrence weights in that order: Ui, Uo, Uf, Um
        self.U = sharedX(value=np.zeros((hidden_size, 4*hidden_size)), name=self.name+'_U')

        # Memory weights (i:input, o:output, f:forget, m:memory)
        self.Vi = sharedX(value=np.ones(hidden_size), name=self.name+'_Vi')
        self.Vo = sharedX(value=np.ones(hidden_size), name=self.name+'_Vo')
        self.Vf = sharedX(value=np.ones(hidden_size), name=self.name+'_Vf')

    def initialize(self, weights_initializer=initer.UniformInitializer(1234)):
        weights_initializer(self.W)
        weights_initializer(self.U)

    @property
    def parameters(self):
        return [self.W, self.U, self.b,
                self.Vi, self.Vo, self.Vf]

    def fprop(self, Xi, last_h, last_m):
        def slice_(x, no):
            if type(no) is str:
                no = ['i', 'o', 'f', 'm'].index(no)
            return x[:, no*self.hidden_size: (no+1)*self.hidden_size]

        # SPEEDUP: compute the first linear transformation outside the scan i.e. for all timestep at once.
        # EDIT: I try and didn't see much speedup!
        Xi = (T.dot(Xi, self.W) + self.b)
        preactivation = Xi + T.dot(last_h, self.U)

        gate_i = T.nnet.sigmoid(slice_(preactivation, 'i') + last_m*self.Vi)
        mi = self.activation_fct(slice_(preactivation, 'm'))

        gate_f = T.nnet.sigmoid(slice_(preactivation, 'f') + last_m*self.Vf)
        m = gate_i*mi + gate_f*last_m

        gate_o = T.nnet.sigmoid(slice_(preactivation, 'o') + m*self.Vo)
        h = gate_o * self.activation_fct(m)

        return h, m


class LayerGRU(object):
    """ Gated Recurrent Unit

    References
    ----------
    .. [Chung14] Junyoung Chung, Caglar Gulcehre, KyungHyun Cho, Yoshua Bengio
                 "Empirical Evaluation of Gated Recurrent Neural Networks on Sequence Modeling",
                 http://arxiv.org/pdf/1412.3555v1.pdf, 2014
    """
    def __init__(self, input_size, hidden_size, activation="tanh", name="GRU"):
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.name = name
        self.activation = activation
        self.activation_fct = factories.make_activation_function(self.activation)

        # Input weights (z:update, r:reset)
        # Concatenation of the weights in that order: Wz, Wr, Wh
        self.W = sharedX(value=np.zeros((input_size, 3*hidden_size)), name=self.name+'_W')
        # self.Wh = sharedX(value=np.zeros((input_size, 2*hidden_size)), name=self.name+'_Wh')

        # Biases (z:update, r:reset)
        # Concatenation of the biases in that order: bz, br, bh
        self.b = sharedX(value=np.zeros(3*hidden_size), name=self.name+'_b')
        # self.bh = sharedX(value=np.zeros(hidden_size), name=self.name+'_bh')

        # Recurrence weights (z:update, r:reset)
        # Concatenation of the recurrence weights in that order: Uz, Ur
        self.U = sharedX(value=np.zeros((hidden_size, 2*hidden_size)), name=self.name+'_U')
        self.Uh = sharedX(value=np.zeros((hidden_size, hidden_size)), name=self.name+'_Uh')

    def initialize(self, weights_initializer=initer.UniformInitializer(1234)):
        weights_initializer(self.W)
        # weights_initializer(self.Wh)
        weights_initializer(self.U)
        weights_initializer(self.Uh)

    @property
    def parameters(self):
        return [self.W, self.b, self.U, self.Uh]

    def fprop(self, Xi, last_h):
        def slice_(x, no):
            if type(no) is str:
                if no == 'zr':
                    return x[:, :2*self.hidden_size]

                no = ['z', 'r', 'h'].index(no)

            return x[:, no*self.hidden_size: (no+1)*self.hidden_size]

        Xi = (T.dot(Xi, self.W) + self.b)
        preactivation = slice_(Xi, 'zr') + T.dot(last_h, self.U)

        gate_z = T.nnet.sigmoid(slice_(preactivation, 'z'))  # Update gate
        gate_r = T.nnet.sigmoid(slice_(preactivation, 'r'))  # Reset gate

        # Candidate activation
        c = self.activation_fct(slice_(Xi, 'h') + T.dot(last_h*gate_r, self.Uh))
        h = (1-gate_z)*last_h + gate_z*c

        return h