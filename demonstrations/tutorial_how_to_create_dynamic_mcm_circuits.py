r"""How to create dynamic circuits with mid-circuit measurements
================================================================

Measuring qubits in the middle of a quantum circuit execution can be useful in many ways.
From understanding the inner workings of a circuit, over hardware characterization,
modeling and error mitigation, to error correction, algorithmic improvements and even up to full
computations encoded as measurements in measurement-based quantum computation (MBQC).

Before turning to any of these advanced topics, it is worthwhile to familiarize ourselves with
the syntax and features around mid-circuit measurements (MCMs). In this how-to, we will focus on
dynamic quantum circuits that use control flow based on mid-circuit measurements.
Most of the advanced concepts mentioned above incorporate MCMs in this way, making it a
key ingredient to scalable quantum computing.

.. figure:: ../_static/demonstration_assets/how_to_collect_mcm_stats/socialsthumbnail_how_to_create_dynamic_mcm_circuits.png
    :align: center
    :width: 50%

If you are interested in how to collect statistics about performed mid-circuit measurements
in PennyLane, also check out our
how-to on collecting MCM stats.
"""

######################################################################
# Minimal working example
# -----------------------
#
# We start with a minimal dynamic circuit on two qubits. It rotates one qubit
# about the ``X``-axis and prepares the other qubit in a fixed state.
# After an entangling :class:`~.pennylane.CNOT` gate, the second qubit is measured,
# and if it measured a ``1``, an :class:`~.pennylane.S` gate is applied.
# Finally, the expectation value of the Pauli ``Y`` operator is returned.
#

import pennylane as qml
import numpy as np

dev = qml.device("default.qubit")

magic_state = np.array([1.0, np.exp(1j * np.pi / 4)]) / np.sqrt(2)


@qml.qnode(dev, interface="numpy")
def circuit(x):
    qml.RX(x, 0)

    qml.QubitStateVector(magic_state, 1)
    qml.CNOT(wires=[0, 1])
    mcm = qml.measure(1)
    qml.cond(mcm, qml.S)(wires=0)

    return qml.expval(qml.Y(0))


x = 1.361
print(circuit(x))

######################################################################
# In case you wondered, this circuit implements a so-called T-gadget,
# but this does not concern us here.
#
# After this minimal example, we construct a more complex circuit showcasing
# more features of dynamic circuits in PennyLane.
#
# Defining quantum subprograms
# ----------------------------
#
# We start by defining two quantum subprograms: blocks of single-qubit
# and two-qubit gates, applied in one layer each.
# We also fix the number of qubits we will work with to four.
#

num_wires = 4
wires = list(range(num_wires))


def first_block(x):
    [qml.RX(x, w) for w in wires]
    [qml.CNOT([w, (w + 1) % num_wires]) for w in wires]


def block(param):
    [qml.CRY(param, wires=[w, (w + 1) % num_wires]) for w in wires]
    [qml.Hadamard(w) for w in wires]


######################################################################
# Processing MCMs into boolean conditions
# ---------------------------------------
#
# Next, we define two functions that will process MCMs into a boolean condition
# within the feedforward control flow of the dynamic quantum circuit.
# They are chosen arbitrarily, but showcase that standard arithmetic and
# comparators are supported with MCM values (for more details, consider the
# `introduction to MCMs <https://docs.pennylane.ai/en/stable/introduction/measurements.html#mid-circuit-measurements-and-conditional-operations>`_
# and the documentation of :func:`~.pennylane.measure`.
#


def condition1(mcms):
    return np.dot(2 ** np.arange(len(mcms)), mcms) >= 5


def condition2(mcms):
    return np.dot(3 ** np.arange(len(mcms)), mcms) < 4


######################################################################
# Miscellaneous preparations
# --------------------------
#
# To conclude our preparations, we also define a shot-based device (with fixed seed)
# and a Hamiltonian to be measured.
#

dev = qml.device("default.qubit", shots=100, seed=5214)

ops = [qml.X(0) @ qml.Y(1), qml.Z(1) @ qml.X(2), qml.Y(2) @ qml.Z(3), qml.X(3) @ qml.Y(0)]
H = qml.dot([0.3, 1.2, 0.7, -0.5], ops)

######################################################################
# Defining the dynamic quantum circuit
# ------------------------------------
#
# Now we are ready to create a :class:`.pennylane.QNode`. It will execute blocks
# of quantum gates interleaved with layers of mid-circuit measurements.
# The MCMs are either processed into a condition for whether the next block is
# applied, using the functions ``condition1`` and ``condition2`` from above,
# or they are used for postselection.
#


@qml.qnode(dev)
def circ(x, y, z):
    # Apply the first block of gates
    first_block(x)
    # Measure all qubits w/o resetting them; store the mid-circuit measurement values
    first_mcms = [qml.measure(w) for w in wires]
    # Compute a boolean condition based on the MCMs
    mid_block_condition = condition1(first_mcms)
    # Apply another block of quantum gates if the computed condition is True
    qml.cond(mid_block_condition, block)(y)
    # Measure the first qubit and postselect on having measured "1"
    postselected_mcm = qml.measure(0, postselect=1)
    # Measure the other qubits and reset them
    second_mcms = [qml.measure(w, reset=True) for w in wires[1:]]
    # Compute a boolean condition based on the second set of MCMs
    last_block_condition = condition2(second_mcms)
    # If the second computed condition is True, apply another block.
    # If it is False, instead apply the first block once more
    qml.cond(last_block_condition, block, first_block)(z)
    # Return the (standard) expectation value of the precomputed Hamiltonian,
    # the counters for the two boolean conditions and a common counter
    # for all performed MCMs
    return (
        qml.expval(H),
        qml.counts(mid_block_condition),
        qml.counts(last_block_condition),
        qml.counts([*first_mcms, postselected_mcm, *second_mcms]),
    )


np.random.seed(23)
x, y, z = np.random.random(3)

print(circ(x, y, z))

######################################################################
# Great, the circuit runs! And it does not only estimate the expectation value of ``H``,
# but it also returns the samples of the dynamic circuit conditions ``mid_block_condition``
# and ``last_block_condition`` as well as all performed measurements individually.
#
# Visualizing the dynamic circuit
# -------------------------------
#
# Finally, let's look at the circuit we constructed:
#

print(qml.draw(circ, max_length=300)(x, y, z))
fig, ax = qml.draw_mpl(circ)(x, y, z)

######################################################################
# Can you detect all blocks we included and how they are conditioned on
# the MCM values? Note how independent measurement values cross with a
# gap between the double-drawn wires (``═║═``) just like quantum and classical
# wires do (``─║─``), whereas measurement values that are processed
# together are shown without such a gap (``═╬═``).
#
# This concludes our brief how-to on dynamic circuits with mid-circuit measurements
# in PennyLane. For details on MCMs, consider the
# `documentation on MCMs <https://docs.pennylane.ai/en/stable/introduction/measurements.html#mid-circuit-measurements-and-conditional-operations>`_,
# the documentation of :func:`~.pennylane.measure` and other related demos and how-tos
# shown at the top right.
