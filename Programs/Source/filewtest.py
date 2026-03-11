from Compiler.compilerLib import Compiler
from Compiler.types import sint
from Compiler.library import print_ln

""" compilation instructions
export PYTHONPATH=/Users/joshuamayhugh/Projects/aima-python/MP-SPDZ
python3 /Users/joshuamayhugh/Projects/aima-python/MP-SPDZ/Programs/Source/filewtest.py
make -j8 shamir-party.x
./shamir-party.x -N 3 -p 0 -pn 5001 fileinput
./shamir-party.x -N 3 -p 1 -pn 5001 fileinput
./shamir-party.x -N 3 -p 2 -pn 5001 fileinput
"""

compiler = Compiler()


@compiler.register_function("fileinput")
def fileinput():
    x = sint(63434)
    sint.write_to_file([x])  # or sint.write_to_file(x)


if __name__ == "__main__":
    compiler.compile_func()
