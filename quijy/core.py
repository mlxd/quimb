"""
Core functions for manipulating quantum objects.
"""

import numpy as np
import scipy.sparse as sp
from numexpr import evaluate as evl
from numba import jit


def isket(p):
    """ Checks if matrix is in ket form, i.e. a column """
    return p.shape[0] > 1 and p.shape[1] == 1  # Column vector check


def isbra(p):
    """ Checks if matrix is in bra form, i.e. a row """
    return p.shape[0] == 1 and p.shape[1] > 1  # Row vector check


def isop(p):
    """ Checks if matrix is an operator, i.e. square """
    m, n = np.shape(p)
    return m == n and m > 1  # Square matrix check


def isherm(a):
    """ Checks if matrix is hermitian, for sparse or dense"""
    if sp.issparse(a):
        # Since sparse, test that no .H elements are not unequal..
        return (a != a.H).nnz == 0
    return np.allclose(a, a.H)


def qonvert(data, qtype=None, sparse=False):
    """ Converts lists to 'quantum' i.e. complex matrices, kets being columns.
    Input:
        data:  list describing entries
        qtype: output type, either 'ket', 'bra' or 'dop' if given
        sparse: convert output to sparse 'csr' format.
    Returns:
        x: numpy or sparse matrix
    * Will unravel an array if 'ket' or 'bra' given.
    * Will conjugate if 'bra' given.
    * Will leave operators as is if 'dop' given, but make them if vector given
    """
    x = np.asmatrix(data, dtype=complex)
    sz = np.prod(x.shape)
    if qtype == 'ket':
        x.shape = (sz, 1)
    elif qtype == 'bra':
        x.shape = (1, sz)
        x = np.conj(x)
    elif qtype == 'dop' and not isop(x):
        x = qonvert(x, 'ket') * qonvert(x, 'ket').H
    return sp.csr_matrix(x, dtype=complex) if sparse else x


@jit
def tr(a):
    """ Trace of hermitian matrix (jit version faster than numpy!) """
    x = 0.0
    for i in range(a.shape[0]):
        x += a[i, i].real
    return x
# def tr(a):
#     """ Fallback version for debugging """
#     return np.real(np.trace(a))


def nrmlz(p):
    """ Returns the state p in normalized form """
    return (p / np.sqrt(p.H * p) if isket(p) else
            p / np.sqrt(p * p.H) if isbra(p) else
            p / tr(p))


@jit
def krnd2(a, b):
    """
    Fast tensor product of two dense arrays (Fast than numpy using jit)
    """
    m, n = a.shape
    p, q = b.shape
    x = np.empty((m * p, n * q), dtype=complex)
    for i in range(m):
        for j in range(n):
            x[i * p:(i + 1)*p, j * q:(j + 1) * q] = a[i, j] * b
    return np.asmatrix(x)
# def krnd2(a, b):  # Fallback for debugging
#     return np.kron(a, b)


def kron(*args):
    """ Tensor product of variable number of arguments.
    Input:
        args: objects to be tensored together
    Returns:
        operator
    The product is performed as (a * (b * (c * ...)))
    """
    a = args[0]
    b = args[1] if len(args) == 2 else  \
        kron(*args[1:])  # Recursively perform kron to 'right'
    return (sp.kron(a, b, 'csr') if (sp.issparse(a) or sp.issparse(b)) else
            krnd2(a, b))


def kronpow(a, pow):
    """ Returns 'a' tensored with itself pow times """
    return (1 if pow == 0 else
            a if pow == 1 else
            kron(*[a] * pow))


def eye(n, sparse=False):
    """ Return identity of size n in complex format, optionally sparse"""
    return (sp.eye(n, dtype=complex, format='csr') if sparse else
            np.eye(n, dtype=complex))


def eyepad(a, dims, inds, sparse=None):
    """ Pad an operator with identities to act on particular subsystem.
    Input:
        a: operator to act
        dims: list of dimensions of subsystems.
        inds: indices of dims to act a on.
        sparse: whether output should be sparse
    Returns:
        b: operator with a acting on each subsystem specified by inds
    Note that the actual numbers in dims[inds] are ignored and the size of
    a is assumed to match. Sparsity of the output can be inferred from
    input.
    """
    sparse = sp.issparse(a) if sparse is None else sparse
    inds = np.array(inds, ndmin=1)
    b = eye(np.prod(dims[0:inds[0]]), sparse=sparse)
    for i in range(len(inds) - 1):
        b = kron(b, a)
        pad_size = np.prod(dims[inds[i] + 1:inds[i + 1]])
        b = kron(b, eye(pad_size, sparse=sparse))
    b = kron(b, a)
    pad_size = np.prod(dims[inds[-1] + 1:])
    b = kron(b, eye(pad_size, sparse=sparse))
    return b


def chop(x, eps=1.0e-12):
    """
    Sets any values of x smaller than eps (relative to range(x)) to zero
    """
    xr = x.max() - x.min()
    xm = xr * eps
    x[abs(x) < xm] = 0
    return x


def ldmul(v, m):
    '''
    Fast left diagonal multiplication of v: vector of diagonal matrix, and m
    '''
    v = v.reshape(np.size(v), 1)
    return evl('v*m')


def rdmul(m, v):
    '''
    Fast right diagonal multiplication of v: vector of diagonal matrix, and m
    '''
    v = v.reshape(1, np.size(v))
    return evl('m*v')