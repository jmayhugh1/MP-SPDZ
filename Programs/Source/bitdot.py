from Compiler.compilerLib import Compiler
from Compiler.library import print_ln, for_range
from Compiler.GC.types import sint, sbitintvec


"""
Compilation and run instructions.

Save this file as:
    /Users/joshuamayhugh/Projects/aima-python/MP-SPDZ/Programs/Source/bitdot.py

Set PYTHONPATH from the MP-SPDZ project root:
    export PYTHONPATH=/Users/joshuamayhugh/Projects/aima-python/MP-SPDZ

Compile directly from Python:
    python3 /Users/joshuamayhugh/Projects/aima-python/MP-SPDZ/Programs/Source/bitdot.py \
      --bit_length 8

Or, from the MP-SPDZ root, you can also use the standard compiler flow:
    ./compile.py -B bitdot

MP-SPDZ documents -B / --binary as compiling for binary computation, and
Compiler.GC.types as the binary-circuit type system. :contentReference[oaicite:1]{index=1}

Build the online phase executable if needed:
    make -j8 shamir-party.x
or another binary-capable backend you use.

Input format:
- Party 0 provides two integers.
- Each integer is interpreted as a bit-vector of length --bit_length.
- Bits are used in least-significant-bit-first order internally.

Example input file for party 0:
    13
    11

This means:
    a = 13 = 1101_2
    b = 11 = 1011_2

Bitwise AND:
    1101 AND 1011 = 1001 = 9

Boolean overlap:
    OR_i (a_i AND b_i) = 1

Run with 2 parties, for example:
   echo "13" | ./semi-bin-party.x -N 2 -I -p 0 -pn 5001 bitdot 
   echo "11" | ./semi-bin-party.x -N 2 -I -p 1 -pn 5001 bitdot
"""

compiler = Compiler()
compiler.parser.add_option("--bit_length", dest="bit_length", type=int, default=4)


@compiler.register_function("bitdot")
def bitdot():
    compiler.parse_args()
    bit_length = compiler.options.bit_length

    print_ln("Running binary-circuit bit overlap with bit_length=%s", bit_length)

    # Read two secret integers from party 0 directly as secret bit-vectors.
    # inputb/inputbvec are the underlying binary-input instructions in MP-SPDZ. :contentReference[oaicite:2]{index=2}

    a = sint.get_input_from(0)
    b = sint.get_input_from(1)
    bit_length = compiler.options.bit_length

    # Run 100 iterations
    @for_range(100)
    def _(iteration):
        # Native bitwise AND in the binary domain.
   

        # binary operation
        cbin = sbitintvec(a, bit_length) & sbitintvec(b, bit_length)
     
        # binary -> arithmetic
        c = sint(cbin)

        print_ln("Iteration %s: a & b = %s", iteration, c.reveal())


if __name__ == "__main__":
    compiler.compile_func()
