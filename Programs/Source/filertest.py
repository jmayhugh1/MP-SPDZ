from Compiler.compilerLib import Compiler
from Compiler.types import sint
from Compiler.library import print_ln, if_e, else_

""" compilation instructions
export PYTHONPATH=/Users/joshuamayhugh/Projects/aima-python/MP-SPDZ
python3 /Users/joshuamayhugh/Projects/aima-python/MP-SPDZ/Programs/Source/filertest.py
make -j8 shamir-party.x
./shamir-party.x -N 3 -p 0 -pn 5001 fileoutput
./shamir-party.x -N 3 -p 1 -pn 5001 fileoutput
./shamir-party.x -N 3 -p 2 -pn 5001 fileoutput
"""

compiler = Compiler()


@compiler.register_function("fileoutput")
def fileoutput():
    stop, shares = sint.read_from_file(0, 1)
    print_ln("stop=%s value=%s", stop, shares[0].reveal())


if __name__ == "__main__":
    compiler.compile_func()
