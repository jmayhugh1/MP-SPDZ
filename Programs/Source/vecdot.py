from Compiler.compilerLib import Compiler
from Compiler.types import sint, Matrix
from Compiler.library import print_ln, for_range
import sys

"""
Compilation and run instructions.

Save this file as:
    /Users/joshuamayhugh/Projects/aima-python/MP-SPDZ/Programs/Source/vecdot.py

Set PYTHONPATH from the MP-SPDZ project root:
    export PYTHONPATH=/Users/joshuamayhugh/Projects/aima-python/MP-SPDZ

Compile:
    python3 /Users/joshuamayhugh/Projects/aima-python/MP-SPDZ/Programs/Source/vecdot.py -B

Build if needed:
    make -j8 shamir-party.x

Input format:
- Party 0 provides the first binary vector entries, then the second.
- Total inputs = 2 * --length integers.
- Each entry should be 0 or 1.

Example party0.input for length 4:
    1
    0
    1
    1
    1
    1
    0
    1

This means:
    x = [1,0,1,1]
    y = [1,1,0,1]

Dot product:
    x · y = 2

Run with 2 parties:
    echo "1 0 1 1 " | ./shamir-party.x -N 3 -I -p 0 -pn 5001 vecdot
    echo "1 1 0 1 " | ./shamir-party.x -N 3 -I -p 1 -pn 5001 vecdot
    ./shamir-party.x -N 3 -I -p 2 -pn 5001 vecdot
"""

compiler = Compiler()
compiler.parser.add_option("--length", dest="length", type=int, default=4)


@compiler.register_function("vecdot")
def vecdot():
    compiler.parse_args()

    n = compiler.options.length
    if n <= 0:
        print("Error: --length must be positive")
        sys.exit(1)

    x = Matrix(n, 1, sint)
    y = Matrix(n, 1, sint)

    # Read x from party 0
    for i in range(n):
        x[i][0] = sint.get_input_from(0)

    # Read y from party 1
    for i in range(n):
        y[i][0] = sint.get_input_from(1)

    # Run 100 iterations
    @for_range(100)
    def _(iteration):
        # Use built-in dot: x^T * y
        dot_result = x.transpose().dot(y)
        print_ln(
            "Iteration %s: Vector dot product = %s",
            iteration,
            dot_result[0][0].reveal(),
        )


if __name__ == "__main__":
    compiler.compile_func()
