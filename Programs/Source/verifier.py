from Compiler.compilerLib import Compiler
import sys
from Compiler.types import Matrix, Array, sint, MemValue
from Compiler.library import for_range, print_ln
from typing import Tuple
from private_path_query_utils import PrivatePathQueryUtils
from matsat_utils import MatSatUtils

""" compilation instructions
export PYTHONPATH=/Users/joshuamayhugh/Projects/aima-python/MP-SPDZ
python3 /Users/joshuamayhugh/Projects/aima-python/MP-SPDZ/Programs/Source/verifier.py --num_parties 3 --grid_size 4 --query_size 3
make -j8 shamir-party.x

# run parties (typically in 3 terminals)
./shamir-party.x -N 3 -p 0 -I -pn 5001 verifier
./shamir-party.x -N 3 -p 1 -I -pn 5001 verifier
./shamir-party.x -N 3 -p 2 -I -pn 5001 verifier

Input order (IMPORTANT):
- For each Bob party b in {1..num_parties-1}:
  for t in 0..T-1:
    for r in 0..grid_size-1:
      for c in 0..grid_size-1:
        input d_{t,r,c} (0 or 1)

- For Alice party 0:
  input start_x, start_y
  for i in 1..T-1:
    input dx_i, dy_i   (so time i location = time i-1 + (dx,dy))

"""

usage = "usage: %prog [options] [args]"
compiler = Compiler(usage=usage)
compiler.parser.add_option("--num_parties", dest="num_parties", type=int)
compiler.parser.add_option("--grid_size", dest="grid_size", type=int)
compiler.parser.add_option("--query_size", dest="query_size", type=int)
compiler.parser.add_option("--iteration_no", dest="iteration_no", type=int, default=0)
compiler.parser.add_option(
    "--is_graph", dest="is_graph", action="store_true", default=False
)
compiler.parser.add_option(
    "--print_beliefs", dest="print_beliefs", action="store_true", default=False
)


@compiler.register_function("verifier")
def verifier():
    def get_arg_info() -> Tuple[int, int, int, int, bool, bool]:
        compiler.parse_args()
        if not compiler.options.num_parties:
            print("Error: num_parties argument is required")
            sys.exit(1)
        if not compiler.options.grid_size:
            print("Error: grid_size argument is required")
            sys.exit(1)
        if not compiler.options.query_size:
            print("Error: query_size argument is required")
            sys.exit(1)
        return (
            compiler.options.num_parties,
            compiler.options.grid_size,
            compiler.options.query_size,
            compiler.options.iteration_no or 0,
            compiler.options.is_graph,
            compiler.options.print_beliefs,
        )

    num_parties, grid_size, query_size, iteration_no, is_graph, print_beliefs = (
        get_arg_info()
    )

    def get_path_from_bob(hazard_matrix: Matrix, bob_id: int) -> None:
        """
        Get all hazard locations from Bob and OR them into the hazard matrix.

        In grid mode, hazard_matrix[i][j] represents whether cell (i,j) is hazardous.
        In graph mode, Bob supplies edge-state values:
          2 = traversable edge, 1 = blocked edge, 0 = no edge.
        Non-traversable (0/1) is treated as hazardous for the queried path.
        """
        assert (
            bob_id >= 1 and bob_id < num_parties
        ), "Bob ID must be between 1 and num_parties-1"
        for i in range(grid_size):
            for j in range(grid_size):
                d = sint.get_input_from(bob_id)
                if is_graph:
                    hazard_bit = sint(1) - (d == sint(2))
                else:
                    hazard_bit = d
                hazard_matrix[i][j] = (hazard_matrix[i][j] + hazard_bit) > 0

    # Path length differs between grid and graph modes.
    # - Grid mode: query_size is number of moves; path length is query_size + 1 (including start).
    # - Graph mode: query_size is number of edges; path length is query_size.
    if is_graph:
        path_length = query_size
    else:
        path_length = query_size + 1

    qx, qy, _ = PrivatePathQueryUtils.create_path(query_size, is_graph)

    hazard_matrix = Matrix(grid_size, grid_size, sint)
    hazard_matrix.assign_all(0)
    result_array = Array(path_length, sint)
    result_array.assign_all(0)

    for bob in range(1, num_parties):
        get_path_from_bob(hazard_matrix, bob)

    # We are going to loop through every element in qx, qy and every element in the grid and if
    for i in range(path_length):
        for j in range(grid_size):
            for k in range(grid_size):
                # we will create a confition
                condition = (qx[i] == j) * (qy[i] == k) * hazard_matrix[j][k]
                result_array[i] = result_array[i] + condition

    # return the sum of result array is greater than 0
    total = MemValue(sint(0))

    @for_range(path_length)
    def _(i):
        total.write(total.read() + result_array[i])

    hits_secret = total.read()
    is_safe = hits_secret == 0  # 1 means safe/solved, 0 means unsafe
    prior, _ = MatSatUtils.load_prior(grid_size, iteration_no)
    posterior, info_gain = MatSatUtils.update_prior(
        prior, qx, qy, grid_size, path_length, is_safe
    )
    MatSatUtils.save_posterior(posterior, grid_size)

    # Print prior and posterior beliefs if flag is set
    if print_beliefs:
        print_ln("=== PRIOR BELIEFS (before query) ===")
        for i in range(grid_size):
            for j in range(grid_size):
                print_ln("prior[%s][%s] = %s", i, j, prior[i][j].reveal())

        print_ln("=== POSTERIOR BELIEFS (after query) ===")
        for i in range(grid_size):
            for j in range(grid_size):
                print_ln("posterior[%s][%s] = %s", i, j, posterior[i][j].reveal())
        print_ln("=== END BELIEFS ===")

    print_ln("information_gain= %s", info_gain.reveal())
    print_ln("Path is safe: %s", is_safe.reveal())
    print_ln("Hazards on path (count of matches): %s", hits_secret.reveal())
    # Structured result payload for robust parsing by Python-side helpers.
    print_ln("RESULT_TYPE=VerifierResult")
    print_ln("RESULT_IS_SOLVED=%s", is_safe.reveal())
    print_ln("RESULT_INFORMATION_GAIN=%s", info_gain.reveal())
    print_ln("RESULT_HAZARDS_ON_PATH=%s", hits_secret.reveal())


if __name__ == "__main__":
    compiler.compile_func()
